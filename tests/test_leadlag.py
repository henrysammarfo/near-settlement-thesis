"""Lead and lag statistics, checked against SciPy and statsmodels reference values."""

import numpy as np
import pytest

from settlemark.analysis import analyse
from settlemark.config import load_config
from settlemark.deep import deep
from settlemark.leadlag import leadlag
from settlemark.stats import StatsError, betainc, cross_corr, f_pvalue, granger, granger_f


def test_betainc_hand_value():
    # I_0.4(2, 3) = sum_{j=2..4} C(4, j) 0.4^j 0.6^(4-j) = 0.5248
    assert betainc(2, 3, 0.4) == pytest.approx(0.5248, abs=1e-12)
    assert betainc(2, 3, 0.0) == 0.0 and betainc(2, 3, 1.0) == 1.0


@pytest.mark.parametrize(
    ("f", "d1", "d2", "scipy_sf"),
    [
        (4.9646, 1, 10, 0.050000052192913744),
        (2.6896, 3, 30, 0.06402690232245167),
        (7.5625, 4, 20, 0.0007002776280445505),
        (0.37, 2, 90, 0.6917800811020228),
    ],
)
def test_f_pvalue_matches_scipy(f, d1, d2, scipy_sf):
    assert f_pvalue(f, d1, d2) == pytest.approx(scipy_sf, rel=1e-9)


def test_granger_f_matches_statsmodels():
    rng = np.random.default_rng(1)
    x = rng.normal(size=80)
    y = np.r_[0, 0.6 * x[:-1]] + rng.normal(size=80)
    f, d1, d2 = granger_f(y, x, 2)
    # statsmodels.tsa.stattools.grangercausalitytests(..., [2])[2][0]["ssr_ftest"]
    assert (d1, d2) == (2, 73)
    assert f == pytest.approx(18.882278285302732, rel=1e-10)


def test_granger_finds_a_planted_lead_and_not_noise():
    rng = np.random.default_rng(3)
    x = rng.normal(size=100)
    led = np.r_[0, 0.8 * x[:-1]] + 0.5 * rng.normal(size=100)
    g = granger(led, x, 1)
    assert g["p_value"] < 1e-6 and g["p_shift"] < 0.05
    noise = rng.normal(size=100)
    assert granger(noise, x, 2)["p_value"] > 0.05


def test_cross_corr_sign_convention():
    rng = np.random.default_rng(5)
    a = rng.normal(size=60)
    b = np.r_[0.0, 0.0, a[:-2]]  # b is a, two steps later: a leads b by 2
    xc = dict(cross_corr(a, b, 3))
    assert max(xc, key=xc.get) == 2 and xc[2] > 0.9


def test_granger_rejects_bad_input():
    with pytest.raises(StatsError):
        granger_f([1.0] * 5, [2.0] * 5, 2)
    with pytest.raises(StatsError):
        granger_f(list(range(30)), list(range(30)), 0)


def test_leadlag_on_committed_data_is_null_and_reported():
    cfg = load_config()
    R, F = analyse(cfg)
    _D, S = deep(cfg, R, F)
    L = leadlag(cfg, F, S["chain"])
    series = {t["series"] for t in L["tests"]}
    assert {"aa", "tx", "storage"} <= series
    for t in L["tests"]:
        assert len(t["xcorr"]) == 2 * L["max_lag"] + 1
        assert [g["lags"] for g in t["intents_leads"]] == [1, 2, 3, 4]
        assert 0 <= t["headline_p"] <= 1 and 0 < t["headline_p_shift"] <= 1
    # The honest finding: no usage series is led by Intents volume at the 5% level.
    assert L["series_where_intents_leads"] == []
    assert L["tests_run"] == 24
