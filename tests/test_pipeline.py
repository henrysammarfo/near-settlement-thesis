"""Integration: build every output from the committed CSVs into a temp folder and check it."""

import hashlib
import json
import re
from pathlib import Path

import pandas as pd
import pytest

from settlemark.__main__ import build
from settlemark.config import ROOT, load_config
from settlemark.sources import DATASETS, read_csv


@pytest.fixture(scope="module")
def out(tmp_path_factory):
    o = tmp_path_factory.mktemp("build")
    cfg = load_config(output_root=o)
    R = build(cfg)
    return cfg, R, o


def test_all_committed_data_validates():
    cfg = load_config()
    for ds in DATASETS:
        assert len(read_csv(ds, cfg.paths.data)) >= 100, ds.name


def test_outputs_exist(out):
    _cfg, _R, o = out
    pngs = sorted(p.name for p in (o / "charts").glob("*.png"))
    svgs = sorted(p.name for p in (o / "site" / "charts").glob("*.svg"))
    assert len(pngs) == 9 and len(svgs) == 18
    assert len(list((o / "site" / "charts").glob("*.png"))) == 9
    assert all((o / "charts" / p).stat().st_size > 20000 for p in pngs)
    assert (o / "site" / "index.html").exists() and (o / "site" / "brand" / "mark.svg").exists()


def test_thesis_structure_and_no_placeholders(out):
    _, _, o = out
    t = (o / "THESIS.md").read_text()
    for h in (
        "## The claim",
        "## Evidence for",
        "## Evidence against",
        "## Raw chain evidence",
        "## Valuation",
        "## Is part 1 robust?",
        "## Predictions written down in advance",
        "## What would change our mind",
        "## Verdict",
        "## Limits",
    ):
        assert h in t
    assert not re.search(r"\{[a-z0-9_]+\}", t), "unfilled placeholder"
    html = (o / "site" / "index.html").read_text()
    assert "${" not in html and "{fals}" not in html


def test_results_ranges(out):
    _, R, _ = out
    for k, v in R.items():
        if k.startswith(("corr_", "lag_")) and isinstance(v, float):
            assert -1 <= v <= 1, k
    lo, hi = R["corr_ci90"]
    assert lo <= R["corr_weekly_change_intents_vs_near_price"] <= hi
    assert len(R["falsifiers"]) == 5 and all(isinstance(f["met"], bool) for f in R["falsifiers"])


def test_numbers_trace_back_to_csv(out):
    """Recompute key numbers straight from the CSVs, independently of the pipeline."""
    _, R, _ = out
    iv = pd.read_csv(ROOT / "data/intents_volume.csv", parse_dates=["date"]).set_index("date")["usd"]
    rev = pd.read_csv(ROOT / "data/intents_revenue.csv", parse_dates=["date"]).set_index("date")["usd"]
    end = pd.Timestamp(R["window_end"])
    start = end - pd.Timedelta(days=364)
    assert R["intents_volume_365d"] == pytest.approx(iv.loc[start:end].sum())
    assert R["intents_revenue_365d"] == pytest.approx(rev.loc[start:end].sum())
    st = pd.read_csv(ROOT / "data/near_stablecoins.csv")["usd"]
    assert R["near_stablecoins_now"] == pytest.approx(st.iloc[-1])


def test_numbers_in_thesis_match_results(out):
    _, R, o = out
    t = (o / "THESIS.md").read_text()
    assert f"{R['mcap_to_intents_revenue']:.0f}x" in t
    assert f"{R['corr_weekly_change_intents_vs_near_price']:+.2f}" in t
    assert f"${R['intents_weekly_volume_last_4w'] / 1e6:,.1f}M" in t


def test_build_is_deterministic(out, tmp_path):
    _cfg, _, o = out
    build(load_config(output_root=tmp_path))

    def digest(base: Path):
        files = sorted(p for p in base.rglob("*") if p.is_file() and ".cache" not in p.parts)
        return {str(p.relative_to(base)): hashlib.sha256(p.read_bytes()).hexdigest() for p in files}

    assert digest(o) == digest(tmp_path)


def test_committed_results_match_a_fresh_build(out):
    _, R, _ = out
    committed = json.loads((ROOT / "results/results.json").read_text())
    assert committed == json.loads(json.dumps(R))


def test_site_data_matches_results(out):
    """The interactive charts read site/data.json; it must agree with results.json."""
    _, R, o = out
    d = json.loads((o / "site" / "data.json").read_text())
    w = d["weekly"]
    assert len(w["date"]) == R["weeks"] == len(w["intents_volume_usd"]) == len(w["near_price_usd"])
    first4 = sum(w["intents_volume_usd"][:4]) / 4
    assert first4 == pytest.approx(R["intents_weekly_volume_first_4w"], rel=1e-6)
    assert d["value_capture_365d"]["Intents revenue"] == pytest.approx(R["intents_revenue_365d"])
    html = (o / "site" / "index.html").read_text()
    assert (o / "site" / "app.js").exists() and 'src="app.js"' in html
    assert f"{R['intents_weekly_volume_last_4w'] / 1e6:.1f}" in html
    assert (o / "site" / "brand" / "fonts" / "inter.woff2").exists()
