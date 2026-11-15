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
    if not only or "near_rpc" in only:
        counts["near_rpc"] = fetch_chain(cfg, fetched_at, use_cache)
    return counts


def fetch_chain(cfg: Config, fetched_at: str, use_cache: bool = True) -> int:
    """One archival RPC block per week: total supply, buyback wallet balance, intents.near storage."""
    from . import chain

    c = cfg.chain
    ccfg = chain.ChainConfig(
        endpoints=tuple(c["endpoints"]),
        buyback_account=c["buyback_account"],
        intents_account=c["intents_account"],
        first_week=c["first_week"],
        timeout_seconds=cfg.http.timeout_seconds,
    )
    rpc = chain.Rpc(ccfg, cfg.paths.cache.parent / "rpc" if use_cache else None)
    rows = chain.sample(rpc, ccfg, fetched_at)
    chain.write(rows, cfg.paths.data / "near_rpc.csv")
    return len(rows)
