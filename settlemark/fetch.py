"""Fetch every declared dataset into data/*.csv."""

from __future__ import annotations

import datetime as dt
import time

from . import log
from .config import Config
from .http import get_json
from .sources import DATASETS, write_csv


def fetch_all(cfg: Config, use_cache: bool = True, only: list[str] | None = None) -> dict[str, int]:
    logger = log.get()
    cfg.paths.data.mkdir(parents=True, exist_ok=True)
    fetched_at = dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    counts: dict[str, int] = {}
    for ds in DATASETS:
        if only and ds.name not in only:
            continue
        url = cfg.sources[ds.name]
        data = get_json(url, cfg.http, cfg.paths.cache, use_cache=use_cache)
        rows = ds.parse(data)
        write_csv(ds, rows, url, fetched_at, cfg.paths.data)
        counts[ds.name] = len(rows)
        logger.info("%-17s %5d rows  %s", ds.name, len(rows), ds.provider)
        if ds.provider == "CoinGecko":
            time.sleep(cfg.http.pause_between_coingecko_calls_seconds)
    return counts
