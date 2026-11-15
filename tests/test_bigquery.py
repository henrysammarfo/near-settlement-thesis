"""BigQuery results are committed, validated and tied to the SQL that made them."""

import shutil

import pandas as pd
import pytest

from settlemark import bigquery as B
from settlemark.config import ROOT, load_config
from settlemark.schema import SchemaError


def _copy(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "data", root / "data")
    shutil.copytree(ROOT / "queries", root / "queries")
    shutil.copy(ROOT / "settlemark.toml", root / "settlemark.toml")
    return load_config(ROOT / "settlemark.toml", root=root, output_root=tmp_path / "out"), root


def test_committed_results_are_valid_and_current():
    cfg = load_config()
    assert B.problems(cfg) == []
    st = {s["key"]: s for s in B.status(cfg)}
    assert st["01"]["committed"] and st["01"]["required"] and st["01"]["sql_matches"]
    assert st["01"]["rows"] == 7 and st["01"]["scanned_gb"] == 174.0


def test_comment_edits_keep_the_hash_but_sql_edits_break_it(tmp_path):
    cfg, root = _copy(tmp_path)
    q = root / "queries" / "01_receipt_actions_daily.sql"
    q.write_text("-- a new comment\n" + q.read_text())
    assert B.problems(cfg) == []
    q.write_text(q.read_text().replace("2026-11-08", "2026-11-01"))
    assert any("changed since" in p for p in B.problems(cfg))


def test_missing_required_result_fails(tmp_path):
    cfg, root = _copy(tmp_path)
    (root / "data" / "bigquery" / "receipt_actions_daily.csv").unlink()
    assert any("required BigQuery result missing" in p for p in B.problems(cfg))


def test_console_import_round_trip_and_week_alignment(tmp_path):
    cfg, root = _copy(tmp_path)
    src = tmp_path / "console.csv"
    weeks = pd.date_range("2024-12-09", periods=60, freq="7D")
    src.write_text(
        "week_start,transactions,signers\n" + "".join(f"{d.date()},{1000 + i},{100 + i}\n" for i, d in enumerate(reversed(weeks)))
    )
    out = B.import_csv(cfg, "05", src, 12.3, "2026-11-15T06:00:00Z")
    assert out.exists()
    m = B.read_manifest(cfg)["05"]
    assert (
        m["scanned_gb"] == 12.3
        and m["method"] == "console"
        and m["sql_sha256"] == B.sql_sha256(root / "queries" / "05_weekly_activity.sql")
    )
    w = B.weekly_activity(cfg)
    assert w.index[0] == pd.Timestamp("2024-12-15") and w.index[0].day_of_week == 6  # Monday week start, Sunday label
    assert w["transactions"].iloc[0] == 1059  # rows were sorted by date
    assert B.problems(cfg) == []


def test_console_import_rejects_wrong_columns(tmp_path):
    cfg, _root = _copy(tmp_path)
    src = tmp_path / "bad.csv"
    src.write_text("week,txs\n2024-12-09,5\n")
    with pytest.raises(SchemaError):
        B.import_csv(cfg, "05", src, 1.0)


def test_leadlag_uses_bigquery_weekly_when_present(tmp_path):
    from settlemark.analysis import analyse
    from settlemark.deep import deep
    from settlemark.leadlag import leadlag

    cfg, _root = _copy(tmp_path)
    src = tmp_path / "console.csv"
    weeks = pd.date_range("2024-12-09", "2026-11-02", freq="7D")
    src.write_text(
        "week_start,transactions,signers\n"
        + "".join(f"{d.date()},{5000 + (i * 37) % 900},{700 + (i * 53) % 300}\n" for i, d in enumerate(weeks))
    )
    B.import_csv(cfg, "05", src, 12.3, "2026-11-15T06:00:00Z")
    R, F = analyse(cfg)
    _D, S = deep(cfg, R, F)
    L = leadlag(cfg, F, S["chain"], B.weekly_activity(cfg))
    names = {t["series"] for t in L["tests"] if "xcorr" in t}
    assert {"bq_signers", "bq_txs"} <= names


def test_query_05_is_committed_and_feeds_the_lead_test():
    import json

    from settlemark.config import ROOT

    R = json.loads((ROOT / "results" / "results.json").read_text())
    q = {x["key"]: x for x in R["bigquery"]["queries"]}
    assert q["05"]["committed"] and q["05"]["required"] and q["05"]["sql_matches"] and q["05"]["rows"] == 100
    assert q["05"]["scanned_gb"] == 65.1 and q["05"]["run_at_utc"] == "2026-11-15T06:58:10Z"
    assert not q["04"]["committed"]
    series = {t["series"] for t in R["leadlag"]["tests"] if "xcorr" in t}
    assert {"bq_signers", "bq_txs"} <= series
    W = R["bigquery"]["weekly"]
    assert W["tx_change_corr"] > 0.99 and W["signers_change_pct"] < 0
    thesis = (ROOT / "THESIS.md").read_text()
    assert "Query 04" in thesis and "1 Dec" in thesis and "not independent evidence" in thesis


def test_crosscheck_needs_overlap():
    import numpy as np
    import pandas as pd

    from settlemark.bigquery import crosscheck

    idx = pd.date_range("2025-01-05", periods=40, freq="W-SUN")
    rng = np.random.default_rng(3)
    w = pd.DataFrame({"tx": rng.uniform(1e6, 2e6, 40), "aa": rng.uniform(1e5, 2e5, 40)}, index=idx)
    b = pd.DataFrame({"transactions": w["tx"] * 1.0, "signers": w["aa"] * 3}, index=idx)
    out = crosscheck(w, b)
    assert abs(out["tx_ratio_median"] - 1) < 1e-12 and out["weeks"] == 40
    assert crosscheck(w, b.iloc[:10]) is None and crosscheck(w, None) is None
