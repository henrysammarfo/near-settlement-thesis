"""The valuation model, checked against hand computed cases."""

import itertools

import pytest

from settlemark.stats import StatsError
from settlemark.valuation import breakeven_weekly_volume, dcf, growth_path, implied_growth


def test_growth_path_fades_to_terminal():
    p = growth_path(0.5, 0.03, 5, 5)
    assert p[:5] == [0.5] * 5 and p[-1] == pytest.approx(0.03) and len(p) == 10
    assert all(a >= b for a, b in itertools.pairwise(p))


def test_dcf_with_constant_growth_is_gordon():
    # Growth equal to terminal growth in every year collapses to a growing perpetuity: c(1+g)/(r-g).
    assert dcf(100.0, 0.03, 0.10, 0.03, 5, 5) == pytest.approx(100 * 1.03 / 0.07, rel=1e-12)


def test_dcf_zero_growth_is_perpetuity():
    assert dcf(10.0, 0.0, 0.2, 0.0, 3, 2) == pytest.approx(50.0)


def test_dcf_rejects_bad_rates():
    with pytest.raises(StatsError):
        dcf(1.0, 0.1, 0.03, 0.03)


def test_implied_growth_inverts_dcf():
    v = dcf(18.0, 0.42, 0.15, 0.03)
    assert implied_growth(v, 18.0, 0.15, 0.03) == pytest.approx(0.42, abs=1e-9)


def test_breakeven_volume():
    # 52 weeks * $1B * 4 bps * 100% = $20.8M a year
    assert breakeven_weekly_volume(20.8e6, 4e-4, 1.0) == pytest.approx(1e9)
    with pytest.raises(StatsError):
        breakeven_weekly_volume(1.0, 0.0, 1.0)
