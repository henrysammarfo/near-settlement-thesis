"""Unit tests for settlemark.stats against hand checkable cases."""

import numpy as np
import pandas as pd
import pytest

from settlemark.stats import StatsError, bootstrap_corr_ci, lagged_corr, log_changes, pearson, weekly


def test_pearson_perfect_positive_and_negative():
    x = [1, 2, 3, 4, 5]
    assert pearson(x, [2, 4, 6, 8, 10]) == pytest.approx(1.0)
    assert pearson(x, [10, 8, 6, 4, 2]) == pytest.approx(-1.0)


def test_pearson_matches_hand_computation():
    x = np.array([1.0, 2.0, 3.0, 4.0])
    y = np.array([1.0, 3.0, 2.0, 5.0])
    dx, dy = x - x.mean(), y - y.mean()
    expected = (dx * dy).sum() / np.sqrt((dx**2).sum() * (dy**2).sum())
    assert pearson(x, y) == pytest.approx(expected)  # 0.8315...
    assert pearson(x, y) == pytest.approx(0.831522, abs=1e-6)


def test_pearson_rejects_constant_short_mismatched_and_nan():
    with pytest.raises(StatsError):
        pearson([1, 1, 1], [1, 2, 3])
    with pytest.raises(StatsError):
        pearson([1, 2], [1, 2])
    with pytest.raises(StatsError):
        pearson([1, 2, 3], [1, 2])
    with pytest.raises(StatsError):
        pearson([1, 2, np.nan], [1, 2, 3])


def test_bootstrap_is_deterministic_and_bounded():
    rng = np.random.default_rng(0)
    x = rng.normal(size=80)
    y = 0.6 * x + rng.normal(size=80)
    a = bootstrap_corr_ci(x, y, resamples=500, seed=7)
    b = bootstrap_corr_ci(x, y, resamples=500, seed=7)
    assert a == b
    lo, hi = a
    assert -1 <= lo < hi <= 1
    assert lo < pearson(x, y) < hi


def test_bootstrap_interval_narrows_with_more_data_and_covers_zero_for_noise():
    rng = np.random.default_rng(1)
    big_x, big_y = rng.normal(size=2000), rng.normal(size=2000)
    lo_s, hi_s = bootstrap_corr_ci(big_x[:40], big_y[:40], resamples=500, seed=3)
    lo_b, hi_b = bootstrap_corr_ci(big_x, big_y, resamples=500, seed=3)
    assert (hi_b - lo_b) < (hi_s - lo_s)
    assert lo_b < 0 < hi_b


def test_bootstrap_level_changes_width():
    rng = np.random.default_rng(2)
    x = rng.normal(size=100)
    y = x + rng.normal(size=100)
    w90 = np.diff(bootstrap_corr_ci(x, y, 800, 5, 0.90))[0]
    w50 = np.diff(bootstrap_corr_ci(x, y, 800, 5, 0.50))[0]
    assert w50 < w90
    with pytest.raises(StatsError):
        bootstrap_corr_ci(x, y, 800, 5, 1.5)


def test_lagged_corr_detects_a_one_step_lead():
    rng = np.random.default_rng(4)
    x = rng.normal(size=200)
    y = np.r_[0.0, x[:-1]]  # y copies x one step later, so x leads y
    assert lagged_corr(x, y, 1) == pytest.approx(1.0)
    assert abs(lagged_corr(y, x, 1)) < 0.25


def test_lagged_corr_rejects_bad_lag():
    with pytest.raises(StatsError):
        lagged_corr([1, 2, 3, 4, 5], [5, 3, 4, 1, 2], 0)


def test_log_changes_values_and_rejects_non_positive():
    df = pd.DataFrame({"a": [1.0, np.e, np.e**3]})
    out = log_changes(df)
    assert list(out["a"]) == pytest.approx([1.0, 2.0])
    with pytest.raises(StatsError):
        log_changes(pd.DataFrame({"a": [1.0, 0.0, 2.0]}))


def test_weekly_drops_partial_edge_weeks():
    idx = pd.date_range("2026-01-01", "2026-01-31", freq="D")  # Thursday to Saturday
    df = pd.DataFrame({"v": 1.0}, index=idx)
    w = weekly(df, {"v": "sum"}, "W-SUN")
    assert (w["v"] == 7).all()
    assert len(w) == 3
