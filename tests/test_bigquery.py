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
