"""Noise bars: how large a change must be before we call it a move.

A bar is the 95% half-width of the change into month t from 3, 12 or 60 months earlier,
on the log scale for counts, ratios, dollars and years and on the value itself for shares
and scores. Each month's value varies by its sampling variance v (Poisson for counts,
binomial for shares, a bootstrap for medians: salary, years asked for, post length) plus
an extra variance s² that is the same for every month of a series: the wobble sampling
can't explain. s² is estimated from how far each month strays from the average of its two
neighbors, using only months <= t, so a bar never changes once its month is published. The
bar is 1.96 * sqrt(2 s² + v_then + v_now).
"""

import math
import random
import statistics
from collections.abc import Iterable
from datetime import date

import duckdb

from sejr.aggregate import ANSWERS, SCALARS, SNAPSHOT, _params

Z = 1.96
WINDOWS = {"3m": 3, "1y": 12, "5y": 60}
# s² comes from the last HISTORY neighbor residuals. It is the value that makes the median
# of r² / Var(r) equal the median of a chi-square with one degree of freedom, so the odd
# structural break or holiday dip doesn't widen every later bar.
HISTORY = 36
MIN_HISTORY = 12
# Of those, at least this many must come from months that weren't all zero, so a stack
# term that just took off doesn't get its s² from two years of zeros.
MIN_MOVING = 6
MEDIAN_CHI2_1 = 0.4549
# With fewer residuals than that, assume the month-to-month noise is ten times the
# sampling variance (about what post counts show over the long run), so a young series
# gets a wide bar rather than a falsely narrow one.
FALLBACK_DISPERSION = 10.0
BOOTSTRAP_DRAWS = 400
# Mood bars come out near 0.02, but they leave out classifier error, so they never go
# below the 0.2 convention the style guide used before.
SCORE_FLOOR = 0.2
# Never compared across months, so it gets no bar.
SKIP = {"removed_share.hiring", "removed_share.seeking"}

ANSWER_METRICS = {f"{m.metric}.{m.kind}": m for m in SCALARS}
# Medians whose sampling variance comes from a bootstrap of the month's posts. Years asked for
# are whole numbers that tie across months like round salaries, so they get the bootstrap
# alone too; post length varies smoothly, so it keeps the neighbor-residual s².
BOOTSTRAP_UNITS = ("usd", "years")
BOOTSTRAP_KEYS = ("post_length_median.hiring",)


def _relative(unit: str) -> bool:
    """Counts, ratios, dollars and years compare by relative change; shares and scores by difference."""
    return unit in ("count", "ratio", "usd", "years")


def _bootstrapped(key: str, unit: str) -> bool:
    return unit in BOOTSTRAP_UNITS or key in BOOTSTRAP_KEYS


def _log_variance(key: str, unit: str, value: float, n: int, extra: float | None):
    """Sampling variance of ln(value) for one month."""
    if value <= 0 or not n:
        return None
    if _bootstrapped(key, unit):
        return extra  # bootstrap variance of the log median
    if unit == "count":
        return 1 / value
    if key.startswith("seekers_per_post"):
        return 1 / (value * n) + 1 / n  # 1/S + 1/H, with H = n and S = value * n
    if key.startswith("replies_per_post"):
        return 1 / (value * n)  # Poisson total replies
    return extra


def _abs_variance(unit: str, p: float, n: int, extra: float | None):
    """Sampling variance of the value itself; shares use the p they are given."""
    if unit == "share":
        return p * (1 - p) / n if n and 0 < p < 1 else None
    return extra  # score: sample variance over n


def _month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def residuals(
    key: str, unit: str, pts: list[dict], extras: dict
) -> list[tuple[float, float] | None]:
    """(r², V) for each point against its two neighbors, or None when it can't be measured.

    r is the point minus the average of its neighbors and V the sampling part of Var(r), so
    Var(r) = 1.5 s² + V. A share that is 0 in all three months (a stack term before it
    caught on) is (0, 0): it counts toward MIN_HISTORY but not toward the estimate.
    """
    out: list[tuple[float, float] | None] = [None] * len(pts)
    for i in range(1, len(pts) - 1):
        trio = pts[i - 1 : i + 2]
        idx = [_month_index(p["month"]) for p in trio]
        if idx[1] - idx[0] != 1 or idx[2] - idx[1] != 1:
            continue
        values = [p["value"] for p in trio]
        if _relative(unit):
            vs = [
                _log_variance(key, unit, p["value"], p["n"], extras.get(p["month"]))
                for p in trio
            ]
            if None in vs or min(values) <= 0:
                continue
            y = [math.log(v) for v in values]
        else:
            pooled = sum(values) / 3
            if unit == "share" and pooled in (0, 1):
                out[i] = (0.0, 0.0)
                continue
            vs = [
                _abs_variance(unit, pooled, p["n"], extras.get(p["month"]))
                for p in trio
            ]
            if None in vs:
                continue
            y = values
        out[i] = ((y[1] - (y[0] + y[2]) / 2) ** 2, vs[1] + (vs[0] + vs[2]) / 4)
    return out


def _median_z2(history: list[tuple[float, float]], s2: float) -> float:
    return statistics.median(
        0.0 if not r2 else r2 / d if (d := 1.5 * s2 + v) else math.inf
        for r2, v in history
    )


def excess_variance(history: list[tuple[float, float]]) -> float:
    """s² such that the median of r² / (1.5 s² + V) is MEDIAN_CHI2_1; 0 when sampling suffices."""
    if _median_z2(history, 0.0) <= MEDIAN_CHI2_1:
        return 0.0
    # The median falls as s² grows, so bisect. At hi every ratio is below MEDIAN_CHI2_1.
    lo, hi = 0.0, max(r2 for r2, _ in history) / (1.5 * MEDIAN_CHI2_1)
    for _ in range(40):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if _median_z2(history, mid) > MEDIAN_CHI2_1 else (lo, mid)
    return (lo + hi) / 2


def excess_variances(
    key: str, unit: str, pts: list[dict], extras: dict
) -> list[float | None]:
    """s² for each point, or None (use the fallback) when history is too short.

    Salary and years medians get 0: the median of a few dozen round numbers often ties
    across months, so neighbor residuals are mostly zero and say nothing. Their bar is the
    bootstrap alone.
    """
    if unit in BOOTSTRAP_UNITS:
        return [0.0] * len(pts)
    found = residuals(key, unit, pts, extras)
    out: list[float | None] = []
    for i in range(len(pts)):
        # The residual at j uses point j + 1, so only j <= i - 1 is known at point i.
        known = [r for r in found[:i] if r is not None][-HISTORY:]
        # All-zero share months (V = 0) count as history but say nothing about wobble.
        moving = [r for r in known if r[1] > 0]
        enough = len(known) >= MIN_HISTORY and len(moving) >= MIN_MOVING
        out.append(excess_variance(moving) if enough else None)
    return out


def bar(
    key: str, unit: str, then: dict, now: dict, s2: float | None, extras: dict
) -> float | None:
    """Half-width of the change from `then` to `now`: on ln(now/then) for relative units."""
    if _relative(unit):
        vs = [
            _log_variance(key, unit, p["value"], p["n"], extras.get(p["month"]))
            for p in (then, now)
        ]
    else:
        p = (then["value"] + now["value"]) / 2
        vs = [
            _abs_variance(unit, p, q["n"], extras.get(q["month"])) for q in (then, now)
        ]
    if None in vs:
        return None
    if s2 is None:
        s2 = (FALLBACK_DISPERSION - 1) * vs[1]
    half_width = Z * math.sqrt(2 * s2 + sum(vs))
    return max(half_width, SCORE_FLOOR) if unit == "score" else half_width


def series_bars(
    key: str, unit: str, pts: list[dict], extras: dict | None = None
) -> list[dict[str, float]]:
    """For each point, {window: bar} for the windows whose earlier month is in the series."""
    extras = extras or {}
    by_index = {_month_index(p["month"]): p for p in pts}
    out = []
    for p, s2 in zip(pts, excess_variances(key, unit, pts, extras), strict=True):
        now = _month_index(p["month"])
        bars = {}
        for window, k in WINDOWS.items():
            if (then := by_index.get(now - k)) and (
                b := bar(key, unit, then, p, s2, extras)
            ) is not None:
                bars[window] = round(b, 3)
        out.append(bars)
    return out


def log_median_variance(values: list[float], seed: str) -> float | None:
    """Bootstrap variance of ln(median), seeded so a month always gets the same answer."""
    if len(values) < 2 or min(values) <= 0:
        return None
    rng = random.Random(seed)
    draws = [
        math.log(statistics.median(rng.choices(values, k=len(values))))
        for _ in range(BOOTSTRAP_DRAWS)
    ]
    return statistics.variance(draws)


def _post_values(con: duckdb.DuckDBPyConnection, key: str, month: str) -> list[float]:
    m = ANSWER_METRICS[key]
    rows = con.execute(
        SNAPSHOT
        + f"SELECT a.value {ANSWERS} AND a.value IS NOT NULL ORDER BY a.post_id",
        _params(date.fromisoformat(f"{month}-01"), m),
    ).fetchall()
    return [v for (v,) in rows]


def _month_variance(
    key: str, unit: str, values: list[float], seed: str
) -> float | None:
    if _bootstrapped(key, unit):
        return log_median_variance(values, seed)
    return statistics.variance(values) / len(values) if len(values) > 1 else None


def month_extras(
    con: duckdb.DuckDBPyConnection, key: str, unit: str, months: Iterable[str]
) -> dict[str, float]:
    """Per-month sampling variances that need the posts: medians and mood scores."""
    if unit != "score" and not _bootstrapped(key, unit):
        return {}
    extras = {}
    for month in months:
        values = _post_values(con, key, month)
        if (v := _month_variance(key, unit, values, f"{key}:{month}")) is not None:
            extras[month] = v
    return extras


def attach(con: duckdb.DuckDBPyConnection, data: dict) -> None:
    """Add `bar` to every exported point (docs/architecture.md, export contract)."""
    for key, metric in data["metrics"].items():
        pts = metric["series"]
        if key in SKIP or not pts:
            continue
        extras = month_extras(con, key, metric["unit"], [p["month"] for p in pts])
        for p, bars in zip(
            pts, series_bars(key, metric["unit"], pts, extras), strict=True
        ):
            if bars:
                p["bar"] = bars
    for breakdown in data["breakdowns"].values():
        pts = breakdown["series"]
        by_month = {p["month"]: p for p in pts}
        for category in breakdown["categories"]:
            cat_pts = [
                {"month": p["month"], "value": p["values"][category], "n": p["n"]}
                for p in pts
                if category in p["values"]
            ]
            for cp, bars in zip(
                cat_pts, series_bars(category, "share", cat_pts), strict=True
            ):
                for window, b in bars.items():
                    by_month[cp["month"]].setdefault("bar", {}).setdefault(window, {})[
                        category
                    ] = b
