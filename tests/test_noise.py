import math
import random

import pytest

from sejr import noise


def _months(count: int, start: int = 2015) -> list[str]:
    return [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(count)]


def _counts(values: list[int]) -> list[dict]:
    return [
        {"month": m, "value": float(v), "n": v}
        for m, v in zip(_months(len(values)), values, strict=True)
    ]


def _poisson_bar(then: int, now: int) -> float:
    return noise.Z * math.sqrt(1 / then + 1 / now)


def test_overdispersed_counts_get_a_wider_bar_than_poisson():
    rng = random.Random(166)
    # Multiplicative month-to-month swings of about 15% around 300 posts, far beyond Poisson.
    pts = _counts([round(300 * math.exp(rng.gauss(0, 0.15))) for _ in range(60)])
    bars = noise.series_bars("posts.hiring", "count", pts)
    d = noise.dispersions("posts.hiring", "count", pts, {})[-1]
    assert d > 3
    then, now = pts[-13]["value"], pts[-1]["value"]
    assert bars[-1]["1y"] == pytest.approx(
        math.sqrt(d) * _poisson_bar(then, now), abs=1e-3
    )
    assert bars[-1]["1y"] > 1.5 * _poisson_bar(then, now)


def test_smooth_series_never_gets_a_bar_narrower_than_sampling():
    pts = _counts([300 + i for i in range(40)])  # a straight line: zero residuals
    assert noise.dispersions("posts.hiring", "count", pts, {})[-1] == 1.0
    assert noise.series_bars("posts.hiring", "count", pts)[-1]["1y"] == pytest.approx(
        _poisson_bar(327, 339), abs=1e-3
    )


def test_short_history_falls_back_to_a_wide_bar():
    pts = _counts([300] * (noise.MIN_HISTORY + 1))
    d = noise.dispersions("posts.hiring", "count", pts, {})
    assert d[-1] == noise.FALLBACK_DISPERSION
    assert (
        noise.dispersions("posts.hiring", "count", _counts([300] * 40), {})[-1] == 1.0
    )


def test_share_bars_use_the_binomial_times_dispersion():
    rng = random.Random(7)
    pts = [
        {"month": m, "value": min(0.9, max(0.1, rng.gauss(0.3, 0.08))), "n": 300}
        for m in _months(50)
    ]
    d = noise.dispersions("x", "share", pts, {})[-1]
    a, b = pts[-4]["value"], pts[-1]["value"]
    p = (a + b) / 2
    binomial = noise.Z * math.sqrt(p * (1 - p) * 2 / 300)
    assert d > 1
    assert noise.series_bars("x", "share", pts)[-1]["3m"] == pytest.approx(
        math.sqrt(d) * binomial, abs=1e-3
    )


def test_bars_are_point_in_time():
    rng = random.Random(3)
    pts = _counts([round(rng.uniform(200, 500)) for _ in range(90)])
    del pts[40]  # a gap must not let later months leak in either
    full = noise.series_bars("posts.hiring", "count", pts)
    for i in range(len(pts)):
        assert (
            noise.series_bars("posts.hiring", "count", pts[: i + 1])[-1] == full[i]
        ), i


def test_bootstrap_variance_is_seeded_and_shrinks_with_n():
    rng = random.Random(1)
    small = [rng.uniform(100_000, 250_000) for _ in range(30)]
    large = small * 8
    assert noise.log_median_variance(small, "k:2026-10") == noise.log_median_variance(
        small, "k:2026-10"
    )
    assert noise.log_median_variance(large, "s") < noise.log_median_variance(small, "s")


def test_mood_bars_never_go_below_the_floor():
    pts = [
        {"month": m, "value": 2.0 + 0.001 * i, "n": 500}
        for i, m in enumerate(_months(30))
    ]
    extras = {p["month"]: 0.8 / 500 for p in pts}
    bars = noise.series_bars("seeker_mood.seeking", "score", pts, extras)
    assert bars[-1]["1y"] == noise.SCORE_FLOOR
