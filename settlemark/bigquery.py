"""Optional: run a query from queries/ on the NEAR BigQuery public dataset and save it as CSV.

Not part of `npm run rebuild`, because BigQuery needs a Google account. Needs
`pip install google-cloud-bigquery` and `gcloud auth application-default login`. Every run
starts with a dry run and refuses to scan more than --max-gb, so the sandbox's free 1 TB a
month is never exceeded by accident.
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

from .config import Config

TABLE = "bigquery-public-data.crypto_near_mainnet_us"


def find_query(cfg: Config, key: str) -> Path:
    hits = sorted((cfg.paths.root / "queries").glob(f"{key}*.sql"))
    if len(hits) != 1:
        raise ValueError(f"query '{key}' matches {len(hits)} files in queries/")
    return hits[0]


def run(cfg: Config, key: str, max_gb: float, project: str | None = None) -> Path:
    try:
        from google.cloud import bigquery
    except ImportError as e:  # pragma: no cover - optional dependency
        raise ValueError("install google-cloud-bigquery to use this command") from e
    path = find_query(cfg, key)
    sql = path.read_text()
    client = bigquery.Client(project=project)
    dry = client.query(sql, job_config=bigquery.QueryJobConfig(dry_run=True, use_query_cache=False))
    gb = dry.total_bytes_processed / 1e9
    if gb > max_gb:
        raise ValueError(f"{path.name} would scan {gb:.0f} GB, above --max-gb {max_gb:g}")
    rows = list(client.query(sql).result())
    out = cfg.paths.data / "bigquery" / (path.stem + ".csv")
    out.parent.mkdir(parents=True, exist_ok=True)
    fetched = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    with out.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        cols = list(rows[0].keys()) if rows else []
        w.writerow([*cols, "fetched_at_utc", "source_url", "scanned_gb"])
        for r in rows:
            w.writerow([*(r[c] for c in cols), fetched, f"{TABLE} via queries/{path.name}", f"{gb:.1f}"])
    return out
