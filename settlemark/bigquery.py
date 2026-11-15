"""The NEAR BigQuery public dataset: a main source, with committed results.

Every query in queries/ that settlemark.toml lists under [[bigquery.query]] has its result
committed in data/bigquery/, next to manifest.json, which records for each result the
sha256 of the SQL that produced it, the bytes scanned and when it ran. The build reads
only the committed files, so a fresh clone with no Google account rebuilds byte for byte.

Refreshing needs a Google account (the free sandbox is enough):

* `python -m settlemark bigquery all` (or one key, e.g. `05`) runs through the API with
  `pip install google-cloud-bigquery` and `gcloud auth application-default login`. It always
  dry runs first and refuses a query above `max_gb`.
* `python -m settlemark bigquery-import 05 results.csv --scanned-gb 12.3` takes a CSV
  downloaded from the BigQuery console after running the same SQL by hand, checks its
  columns, and writes it with provenance. Both paths write identical files.

`python -m settlemark check` fails if a required result is missing or if a query's SQL has
changed since its committed result was produced.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

from .config import Config
from .schema import DATE_RE, TS_RE, SchemaError


@dataclass(frozen=True)
class Query:
    key: str
    sql_path: Path
    csv_path: Path
    columns: tuple[tuple[str, str], ...]
    required: bool

    @property
    def header(self) -> list[str]:
        return [c for c, _ in self.columns] + ["fetched_at_utc", "source_url"]


def queries(cfg: Config) -> list[Query]:
    B = cfg.raw.get("bigquery", {})
    out = []
    for q in B.get("query", []):
        out.append(
            Query(
                key=q["key"],
                sql_path=find_query(cfg, q["key"]),
                csv_path=cfg.paths.data / "bigquery" / q["csv"],
                columns=tuple(tuple(c.split(":", 1)) for c in q["columns"]),
                required=bool(q.get("required", False)),
            )
        )
    return out


def by_key(cfg: Config, key: str) -> Query:
    for q in queries(cfg):
        if q.key == key:
            return q
    raise ValueError(f"no [[bigquery.query]] with key '{key}' in settlemark.toml")


def find_query(cfg: Config, key: str) -> Path:
    hits = sorted((cfg.paths.root / "queries").glob(f"{key}*.sql"))
    if len(hits) != 1:
        raise ValueError(f"query '{key}' matches {len(hits)} files in queries/")
    return hits[0]


def sql_text(path: Path) -> str:
    """The SQL without comments or layout, so editing a comment does not invalidate a result."""
    lines = [re.sub(r"--.*$", "", ln).strip() for ln in path.read_text().splitlines()]
    return " ".join(ln for ln in lines if ln)


def sql_sha256(path: Path) -> str:
    return hashlib.sha256(sql_text(path).encode()).hexdigest()


def manifest_path(cfg: Config) -> Path:
    return cfg.paths.data / "bigquery" / "manifest.json"


def read_manifest(cfg: Config) -> dict:
    p = manifest_path(cfg)
    return json.loads(p.read_text()) if p.exists() else {}


def _write_manifest(cfg: Config, m: dict) -> None:
    manifest_path(cfg).write_text(json.dumps(dict(sorted(m.items())), indent=2) + "\n")


def validate_rows(q: Query, header: list[str], rows: list[dict[str, str]]) -> None:
    if header != q.header:
        raise SchemaError(f"bigquery {q.key}: header {header} != expected {q.header}")
    if not rows:
        raise SchemaError(f"bigquery {q.key}: no rows")
    prev = ""
    for i, r in enumerate(rows, start=2):
        where = f"{q.csv_path.name} line {i}"
        if not r["source_url"].startswith("bigquery-public-data."):
            raise SchemaError(f"{where}: source_url must name the BigQuery table")
        if not TS_RE.match(r["fetched_at_utc"]):
            raise SchemaError(f"{where}: fetched_at_utc must be ISO UTC")
        for name, kind in q.columns:
            v = r[name]
            if kind == "date":
                if not DATE_RE.match(v) or v <= prev:
                    raise SchemaError(f"{where}: {name} must be YYYY-MM-DD and strictly increasing, got {v!r}")
                prev = v
            elif kind == "int" and not re.fullmatch(r"\d+", v):
                raise SchemaError(f"{where}: {name} must be a non negative integer, got {v!r}")


def load(cfg: Config, key: str) -> pd.DataFrame | None:
    """A committed result as a frame indexed by its date column, or None if not committed yet."""
    q = by_key(cfg, key)
    if not q.csv_path.exists():
        return None
    with q.csv_path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    validate_rows(q, list(reader.fieldnames or []), rows)
    df = pd.DataFrame(rows)
    date_col = q.columns[0][0]
    df[date_col] = pd.to_datetime(df[date_col])
    for name, kind in q.columns:
        if kind == "int":
            df[name] = df[name].astype("int64")
    return df.set_index(date_col)


def weekly_activity(cfg: Config) -> pd.DataFrame | None:
    """Query 05 re-indexed to the Sunday that ends each Monday-start week (the analysis weeks)."""
    df = load(cfg, "05")
    if df is None:
        return None
    return df.set_axis(df.index + pd.offsets.Day(6))[["transactions", "signers"]]


def crosscheck(weekly: pd.DataFrame, bq_weekly: pd.DataFrame | None) -> dict | None:
    """Query 05 against NearBlocks on the same weeks: do two independent sources agree?"""
    if bq_weekly is None or not len(bq_weekly):
        return None
    j = weekly[["tx", "aa"]].join(bq_weekly, how="inner").dropna()
    j = j[(j > 0).all(axis=1)]
    if len(j) < 30:
        return None
    lc = np.log(j.astype(float)).diff().dropna()
    head, tail = j.iloc[:13], j.iloc[-13:]
    pct = lambda c: float(100 * (tail[c].mean() / head[c].mean() - 1))  # noqa: E731
    return {
        "weeks": len(j),
        "first_week": str(j.index[0].date()),
        "last_week": str(j.index[-1].date()),
        "tx_ratio_median": float((j["transactions"] / j["tx"]).median()),
        "tx_change_corr": float(lc["transactions"].corr(lc["tx"])),
        "signers_vs_active_accounts_change_corr": float(lc["signers"].corr(lc["aa"])),
        "signers_first_13w": float(head["signers"].mean()),
        "signers_last_13w": float(tail["signers"].mean()),
        "signers_change_pct": pct("signers"),
        "bq_tx_change_pct": pct("transactions"),
        "nearblocks_tx_change_pct": pct("tx"),
        "nearblocks_aa_change_pct": pct("aa"),
    }


def status(cfg: Config) -> list[dict]:
    m = read_manifest(cfg)
    out = []
    for q in queries(cfg):
        e = m.get(q.key, {})
        have = q.csv_path.exists()
        rows = 0
        first = last = ""
        if have:
            df = load(cfg, q.key)
            rows, first, last = len(df), str(df.index[0].date()), str(df.index[-1].date())
        out.append(
            {
                "key": q.key,
                "sql": f"queries/{q.sql_path.name}",
                "csv": f"data/bigquery/{q.csv_path.name}",
                "required": q.required,
                "committed": have,
                "rows": rows,
                "first": first,
                "last": last,
                "scanned_gb": e.get("scanned_gb"),
                "run_at_utc": e.get("run_at_utc"),
                "method": e.get("method"),
                "sql_matches": (e.get("sql_sha256") == sql_sha256(q.sql_path)) if have else None,
            }
        )
    return out


def problems(cfg: Config) -> list[str]:
    out = []
    for s in status(cfg):
        if s["required"] and not s["committed"]:
            out.append(f"required BigQuery result missing: {s['csv']} (run `python -m settlemark bigquery {s['key']}`)")
        if s["committed"] and not s["sql_matches"]:
            out.append(f"{s['sql']} changed since {s['csv']} was produced; rerun it")
    return out


def _write(cfg: Config, q: Query, rows: list[dict], fetched: str, scanned_gb: float, method: str, job: str | None) -> Path:
    src = f"{cfg.raw['bigquery']['dataset']} via queries/{q.sql_path.name}"
    out_rows = [{**{c: str(r[c]) for c, _ in q.columns}, "fetched_at_utc": fetched, "source_url": src} for r in rows]
    validate_rows(q, q.header, out_rows)
    q.csv_path.parent.mkdir(parents=True, exist_ok=True)
    with q.csv_path.open("w", newline="") as f:
        w = csv.DictWriter(f, q.header, lineterminator="\n")
        w.writeheader()
        w.writerows(out_rows)
    m = read_manifest(cfg)
    m[q.key] = {
        "csv": q.csv_path.name,
        "sql": q.sql_path.name,
        "sql_sha256": sql_sha256(q.sql_path),
        "scanned_gb": round(float(scanned_gb), 1),
        "run_at_utc": fetched,
        "method": method,
        **({"job_id": job} if job else {}),
    }
    _write_manifest(cfg, m)
    return q.csv_path


def _norm(v: object) -> str:
    if isinstance(v, dt.date):
        return v.isoformat()
    return str(v)


def run(cfg: Config, key: str, max_gb: float | None = None, project: str | None = None, dry_run: bool = False) -> Path | float:
    try:
        from google.cloud import bigquery
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ValueError("install google-cloud-bigquery and run `gcloud auth application-default login` to refresh BigQuery") from e
    q = by_key(cfg, key)
    limit = float(max_gb if max_gb is not None else cfg.raw["bigquery"]["max_gb"])
    sql = q.sql_path.read_text()
    client = bigquery.Client(project=project)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    gb = dry.total_bytes_processed / 1e9
    if dry_run:
        return gb
    if gb > limit:
        raise ValueError(f"{q.sql_path.name} would scan {gb:.0f} GB, above the {limit:g} GB limit")
    job = client.query(sql)
    rows = [{c: ("" if r.get(c) is None else _norm(r.get(c))) for c, _ in q.columns} for r in job.result()]
    fetched = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    return _write(cfg, q, rows, fetched, gb, "api", job.job_id)


def import_csv(cfg: Config, key: str, src: Path, scanned_gb: float, run_at_utc: str | None = None) -> Path:
    """Import a CSV downloaded from the BigQuery console after running queries/<key>*.sql by hand."""
    q = by_key(cfg, key)
    with Path(src).open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        have = list(reader.fieldnames or [])
    need = [c for c, kind in q.columns if kind != "optional"]
    missing = [c for c in need if c not in have]
    if missing:
        raise SchemaError(f"{src}: missing columns {missing}; the console CSV must come from {q.sql_path.name}")
    for r in rows:
        for c, kind in q.columns:
            r.setdefault(c, "")
            if kind == "date":
                r[c] = r[c][:10]
    rows.sort(key=lambda r: r[q.columns[0][0]])
    fetched = run_at_utc or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if not TS_RE.match(fetched):
        raise SchemaError("--run-at must look like 2026-11-15T06:00:00Z")
    return _write(cfg, q, rows, fetched, scanned_gb, "console", None)
