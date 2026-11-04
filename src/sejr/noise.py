"""Noise bars: how large a change must be before we call it a move.

A bar is the 95% half-width of the change into month t from 3, 12 or 60 months earlier.
It starts from the sampling variance of each month (Poisson for counts, binomial for
shares, a bootstrap for salary medians) and widens it by a dispersion factor D measured
on the series' own history: how much more each month strays from the average of its two
neighbors than sampling alone would allow. D for month t reads only months <= t, so a
bar never changes once its month is published.
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
# D is the median of the last HISTORY squared z-scores, scaled so it estimates their mean
# when the residuals are normal. The median ignores the odd structural break or holiday dip.
HISTORY = 36
MIN_HISTORY = 12
# With less history than that, assume about the dispersion post counts show over the long
# run, so a young series gets a wide bar rather than a falsely narrow one.
FALLBACK_DISPERSION = 10.0
MEDIAN_CHI2_1 = 0.4549
BOOTSTRAP_DRAWS = 400
# Never compared across months, so it gets no bar.
SKIP = {"removed_share.hiring", "removed_share.seeking"}

ANSWER_METRICS = {f"{m.metric}.{m.kind}": m for m in SCALARS}


def _relative(unit: str) -> bool:
    """Counts, ratios and dollars are compared by relative change; shares and scores by difference."""
    return unit in ("count", "ratio", "usd")


def _log_variance(key: str, unit: str, value: float, n: int, extra: float | None):
    """Sampling variance of ln(value) for one month."""
    if value <= 0 or not n:
        return None
    if unit == "count":
        return 1 / value
    if key.startswith("seekers_per_post"):
        return 1 / (value * n) + 1 / n  # 1/S + 1/H, with H = n and S = value * n
    if key.startswith("replies_per_post"):
        return 1 / (value * n)  # Poisson total replies
    return extra  # usd: bootstrap variance of the log median


def _abs_variance(unit: str, p: float, n: int, extra: float | None):
    """Sampling variance of the value itself; shares use the p they are given."""
    if unit == "share":
        return p * (1 - p) / n if n and 0 < p < 1 else None
    return extra  # score: sample variance over n


def _month_index(month: str) -> int:
    return int(month[:4]) * 12 + int(month[5:7]) - 1


def _residual_z2(
    key: str, unit: str, pts: list[dict], extras: dict
) -> list[float | None]:
    """z² for each point against its two neighbors, or None when it can't be measured."""
    out: list[float | None] = [None] * len(pts)
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
            vs = [
                _abs_variance(unit, pooled, p["n"], extras.get(p["month"]))
                for p in trio
            ]
            if None in vs:
                continue
            y = values
        expected = vs[1] + (vs[0] + vs[2]) / 4
        if expected > 0:
            out[i] = (y[1] - (y[0] + y[2]) / 2) ** 2 / expected
    return out


def dispersions(key: str, unit: str, pts: list[dict], extras: dict) -> list[float]:
    """D for each point, from residuals whose right-hand neighbor is no later than it."""
    z2 = _residual_z2(key, unit, pts, extras)
    out = []
    for i in range(len(pts)):
        # The residual at j uses point j + 1, so only j <= i - 1 is known at point i.
        known = [z for z in z2[:i] if z is not None][-HISTORY:]
        if len(known) < MIN_HISTORY:
            out.append(FALLBACK_DISPERSION)
        else:
            out.append(max(1.0, statistics.median(known) / MEDIAN_CHI2_1))
    return out


def bar(
    key: str, unit: str, then: dict, now: dict, d: float, extras: dict
) -> float | None:
    """Half-width of the change from `then` to `now`: relative for log series, else absolute."""
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
    return Z * math.sqrt(d * sum(vs))


def series_bars(
    key: str, unit: str, pts: list[dict], extras: dict | None = None
) -> list[dict[str, float]]:
    """For each point, {window: bar} for the windows whose earlier month is in the series."""
    extras = extras or {}
    by_index = {_month_index(p["month"]): p for p in pts}
    out = []
    for p, d in zip(pts, dispersions(key, unit, pts, extras), strict=True):
        now = _month_index(p["month"])
        bars = {}
        for window, k in WINDOWS.items():
            if (then := by_index.get(now - k)) and (
                b := bar(key, unit, then, p, d, extras)
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


def _month_variance(unit: str, values: list[float], seed: str) -> float | None:
    if unit == "usd":
        return log_median_variance(values, seed)
    return statistics.variance(values) / len(values) if len(values) > 1 else None


def month_extras(
    con: duckdb.DuckDBPyConnection, key: str, unit: str, months: Iterable[str]
) -> dict[str, float]:
    """Per-month sampling variances that need the posts: salary medians and mood scores."""
    if unit not in ("usd", "score"):
        return {}
    extras = {}
    for month in months:
        values = _post_values(con, key, month)
        if (v := _month_variance(unit, values, f"{key}:{month}")) is not None:
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
