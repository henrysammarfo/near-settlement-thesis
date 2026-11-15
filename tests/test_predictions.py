"""Predictions are frozen: the committed file must match its published hash, and scoring waits for data."""

import datetime as dt
import json
import re
import shutil

import pandas as pd
import pytest

from settlemark import predictions as P
from settlemark.config import ROOT, load_config
from settlemark.stats import days


def committed():
    return json.loads((ROOT / "data" / "predictions.json").read_text())


def test_committed_predictions_match_published_hash():
    md = (ROOT / "PREDICTIONS.md").read_text()
    published = re.search(r"sha256 `([0-9a-f]{64})`", md).group(1)
    assert P.sha256_of(committed()) == published
    assert P.render_md(committed()) == md


def test_predictions_are_specific_and_dated():
    data = committed()
    assert data["created_at_utc"] < "2026-11-16"  # frozen before the first scored week began
    ids = [p["id"] for p in data["predictions"]]
    assert ids == [f"P{i}" for i in range(1, 9)]
    for p in data["predictions"]:
        assert p["op"] in P.OPS and 0 < p["probability"] < 1 and isinstance(p["threshold"], float | int)
        assert p["window_end"] in (P.END_4W, P.END_8W)


def test_freeze_refuses_to_overwrite():
    with pytest.raises(FileExistsError):
        P.freeze(load_config(), {})


def test_everything_pending_before_windows_close():
    s = P.score(load_config(), dt.date(2026, 12, 14))
    assert s["resolved"] == 0 and s["brier"] is None
    assert {r["status"] for r in s["results"]} == {"PENDING"}


def test_scoring_with_future_data(tmp_path):
    """Append synthetic future rows to copies of the CSVs and check HIT/MISS and the Brier score."""
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "data", root / "data")
    shutil.copy(ROOT / "settlemark.toml", root / "settlemark.toml")
    cfg = load_config(ROOT / "settlemark.toml", root=root, output_root=tmp_path / "out")

    def extend(name, col, value):
        path = root / "data" / f"{name}.csv"
        df = pd.read_csv(path)
        last = pd.Timestamp(df["date"].iloc[-1])
        new = pd.date_range(last + days(1), "2027-01-14")
        add = pd.DataFrame({c: df[c].iloc[-1] for c in df.columns}, index=range(len(new)))
        add["date"] = new.strftime("%Y-%m-%d")
        add[col] = value(len(new)) if callable(value) else value
        pd.concat([df, add]).to_csv(path, index=False)

    extend("intents_volume", "usd", 150e6)  # $1.05B a week: P1 hits
    extend("all_dex_volume", "usd", 5e9)  # share 3%: P2 hits
    extend("intents_revenue", "usd", 1e3)  # tiny revenue: P8 misses, P4 hits
    extend("near_chain", "near_price_usd", lambda n: [3 + 0.01 * i for i in range(n)])
    s = P.score(cfg, dt.date(2027, 1, 13))
    st = {r["id"]: r["status"] for r in s["results"]}
    assert st["P1"] == "HIT" and st["P2"] == "HIT" and st["P4"] == "HIT" and st["P8"] == "MISS"
    assert st["P5"] == "PENDING"  # no RPC rows for 2027 yet
    assert s["resolved"] >= 4 and 0 <= s["brier"] <= 1
