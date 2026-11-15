"""Router comparison: same window for all, sums trace back to the committed CSVs."""

import json

import pandas as pd
import pytest

from settlemark.__main__ import _stable
from settlemark.config import ROOT, load_config
from settlemark.peers import compare, window_rows
from settlemark.stats import StatsError


def test_compare_matches_csv_sums():
    cfg = load_config()
    R = json.loads((ROOT / "results" / "results.json").read_text())
    P = compare(cfg, R["window_end"], R["near_market_cap"])
    assert _stable(P) == R["peers"]  # results.json rounds to 12 significant digits
    assert P["routers"] == 5 and P["window_days"] == 91
    th = next(r for r in P["rows"] if r["slug"] == "thorchain")
    v = pd.read_csv(ROOT / "data" / "peers" / "thorchain_volume.csv")
    v = v[(v.date >= P["window_start"]) & (v.date <= P["window_end"])]
    assert th["volume_usd"] == pytest.approx(v.usd.sum())
    assert th["fee_bps"] == pytest.approx(th["fees_usd"] / th["volume_usd"] * 1e4)
    me = next(r for r in P["rows"] if r["slug"] == "near_intents")
    iv = pd.read_csv(ROOT / "data" / "intents_volume.csv")
    assert me["volume_usd"] == pytest.approx(iv[(iv.date >= P["window_start"]) & (iv.date <= P["window_end"])].usd.sum())
    assert me["mcap_to_annual_revenue"] == pytest.approx(R["near_market_cap"] / (me["revenue_usd"] * 365 / 91))
    assert P["intents_volume_rank"] == [r["slug"] for r in P["rows"]].index("near_intents") + 1


def test_window_with_missing_data_refuses():
    cfg = load_config()
    with pytest.raises(StatsError):
        window_rows(cfg, pd.Timestamp("2027-02-01"), pd.Timestamp("2027-03-01"), 1.0)
