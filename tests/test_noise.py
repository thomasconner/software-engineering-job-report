import math
import random
import statistics

import pytest

from sejr import noise


def _months(count: int, start: int = 2015) -> list[str]:
    return [f"{start + i // 12}-{i % 12 + 1:02d}" for i in range(count)]


def _counts(values: list[int]) -> list[dict]:
    return [
        {"month": m, "value": float(v), "n": v}
        for m, v in zip(_months(len(values)), values, strict=True)
    ]


def _poisson_bar(then: float, now: float) -> float:
    return noise.Z * math.sqrt(1 / then + 1 / now)


def _noisy_counts(rng: random.Random, months: int, sigma: float) -> list[dict]:
    """Counts around 300 with log-scale noise sigma, then Poisson-like sampling on top."""
    means = [300 * math.exp(rng.gauss(0, sigma)) for _ in range(months)]
    return _counts([round(rng.gauss(m, math.sqrt(m))) for m in means])


def _history(pts: list[dict]) -> list[tuple[float, float]]:
    return [r for r in noise.residuals("posts.hiring", "count", pts, {}) if r]


def _unfloored_dispersion(pts: list[dict]) -> float:
    return noise._median_z2(_history(pts), 0.0) / noise.MEDIAN_CHI2_1


def test_pure_sampling_noise_has_dispersion_near_one():
    ds = [
        _unfloored_dispersion(_noisy_counts(random.Random(s), 120, 0))
        for s in range(25)
    ]
    assert 0.8 <= statistics.median(ds) <= 1.25


def test_excess_variance_recovers_the_known_log_noise():
    sigma2 = 0.15**2
    estimates = [
        noise.excess_variance(_history(_noisy_counts(random.Random(s), 120, 0.15)))
        for s in range(25)
    ]
    assert statistics.median(estimates) == pytest.approx(sigma2, rel=0.2)
    # In D terms: the unfloored ratio is about 1 + 1.5 sigma² / v, with v = 1/300.
    d = statistics.median(
        _unfloored_dispersion(_noisy_counts(random.Random(s), 120, 0.15))
        for s in range(25)
    )
    assert d == pytest.approx(1 + 1.5 * sigma2 * 300 / 1.5, rel=0.25)


def _outlier_growth(seed: int) -> tuple[float, float]:
    """How much three tripled months grow the estimate, and how much a mean-based one grows."""
    pts = _noisy_counts(random.Random(seed), 120, 0.15)
    clean = noise.excess_variance(_history(pts))
    for i in (30, 70, 100):
        pts[i] = {**pts[i], "value": pts[i]["value"] * 3, "n": pts[i]["n"] * 3}
    history = _history(pts)
    mean_based = (
        statistics.mean(r2 for r2, _ in history)
        - statistics.mean(v for _, v in history)
    ) / 1.5
    return noise.excess_variance(history) / clean, mean_based / clean


def test_a_few_outlier_months_barely_move_the_estimate():
    robust, mean_based = zip(*(_outlier_growth(s) for s in range(8)), strict=True)
    assert statistics.median(robust) < 1.6
    assert statistics.median(mean_based) > 2


def test_overdispersed_counts_get_a_wider_bar_than_poisson():
    pts = _noisy_counts(random.Random(166), 60, 0.15)
    s2 = noise.excess_variances("posts.hiring", "count", pts, {})[-1]
    then, now = pts[-13]["value"], pts[-1]["value"]
    expected = noise.Z * math.sqrt(2 * s2 + 1 / then + 1 / now)
    bar = noise.series_bars("posts.hiring", "count", pts)[-1]["1y"]
    assert bar == pytest.approx(expected, abs=1e-3)
    assert bar > 1.5 * _poisson_bar(then, now)


def test_smooth_series_gets_the_sampling_bar():
    pts = _counts([300 + i for i in range(40)])  # a straight line: zero residuals
    assert noise.excess_variances("posts.hiring", "count", pts, {})[-1] == 0.0
    assert noise.series_bars("posts.hiring", "count", pts)[-1]["1y"] == pytest.approx(
        _poisson_bar(327, 339), abs=1e-3
    )


def test_short_history_falls_back_to_a_wide_bar():
    pts = _counts([300] * (noise.MIN_HISTORY + 1))
    assert noise.excess_variances("posts.hiring", "count", pts, {})[-1] is None
    wide = noise.Z * math.sqrt((2 * noise.FALLBACK_DISPERSION - 1) / 300 + 1 / 300)
    assert noise.series_bars("posts.hiring", "count", pts)[-1]["3m"] == pytest.approx(
        wide, abs=1e-3
    )


def _take_off(seed: int) -> list[dict]:
    """Three years at 0%, then about 10% with an extra 3-point s.d. plus binomial sampling."""
    rng = random.Random(seed)
    values = [0.0] * 36
    for _ in range(30):
        p = min(0.9, max(0.01, rng.gauss(0.10, 0.03)))
        values.append(min(0.9, max(0.01, rng.gauss(p, math.sqrt(p * (1 - p) / 300)))))
    return [{"month": m, "value": v, "n": 300} for m, v in zip(_months(66), values)]


def test_a_share_that_takes_off_gets_its_own_wobble_soon():
    # Point 35 + k has k moving residuals behind it (the first is centered on point 35).
    # Zeros already fill MIN_HISTORY, so only MIN_MOVING moving ones are needed.
    estimates = []
    for seed in range(10):
        s2 = noise.excess_variances("rag", "share", _take_off(seed), {})
        assert s2[35 + noise.MIN_MOVING - 1] is None
        assert s2[35 + noise.MIN_MOVING] is not None
        estimates.append(s2[35 + 12])
    assert sum(e > 0 for e in estimates) >= 8


def test_share_bars_add_the_excess_to_the_binomial():
    rng = random.Random(7)
    pts = [
        {"month": m, "value": min(0.9, max(0.1, rng.gauss(0.3, 0.08))), "n": 300}
        for m in _months(50)
    ]
    s2 = noise.excess_variances("x", "share", pts, {})[-1]
    a, b = pts[-4]["value"], pts[-1]["value"]
    p = (a + b) / 2
    assert s2 > 0
    assert noise.series_bars("x", "share", pts)[-1]["3m"] == pytest.approx(
        noise.Z * math.sqrt(2 * s2 + p * (1 - p) * 2 / 300), abs=1e-3
    )


def test_salary_bars_are_bootstrap_only():
    pts = [{"month": m, "value": 200_000.0, "n": 40} for m in _months(30)]
    extras = {p["month"]: 0.003 for p in pts}
    pts[-1]["value"] = 230_000.0
    bars = noise.series_bars("salary_max_median_usd.hiring", "usd", pts, extras)
    assert bars[-1]["1y"] == pytest.approx(noise.Z * math.sqrt(0.006), abs=1e-3)


def test_bars_are_point_in_time():
    rng = random.Random(3)
    pts = _counts([round(rng.uniform(200, 500)) for _ in range(90)])
    del pts[40]  # a gap must not let later months leak in either
    full = noise.series_bars("posts.hiring", "count", pts)
    for i in range(len(pts)):
        bars = noise.series_bars("posts.hiring", "count", pts[: i + 1])
        assert bars[-1] == full[i], i


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
