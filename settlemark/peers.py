"""NEAR Intents against other cross chain routers: volume, fees, take rate and holder capture.

Every router is read from the same public source (DefiLlama's free summary API) over the
same days, so the comparison uses one methodology for all of them. Market caps come from
CoinGecko, only for routers with their own token. Files: data/peers/<slug>_<metric>.csv,
each validated like every other dataset and carrying its source URL on every row.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any

import pandas as pd

from . import log
from .config import Config
from .http import get_json
from .schema import Schema
from .sources import USD, Dataset, Row, _dedupe, parse_llama_chart, read_csv, to_day, write_csv
from .stats import StatsError, days

METRICS = ("volume", "fees", "revenue", "market_cap")


def parse_market_caps(d: Any) -> list[Row]:
    return _dedupe([(to_day(ts), v) for ts, v in d["market_caps"] if v is not None])


def _dataset(slug: str, metric: str) -> Dataset:
    parse = parse_market_caps if metric == "market_cap" else parse_llama_chart
    provider = "CoinGecko" if metric == "market_cap" else "DefiLlama"
    return Dataset(f"{slug}_{metric}", parse, Schema(f"{slug}_{metric}", USD, 60), provider)


def protocols(cfg: Config) -> list[dict]:
    return list(cfg.raw.get("peers", {}).get("protocol", []))


def peers_dir(cfg: Config) -> Path:
    return cfg.paths.data / "peers"


def fetch_peers(cfg: Config, fetched_at: str, use_cache: bool = True) -> int:
    logger = log.get()
    out = peers_dir(cfg)
    out.mkdir(parents=True, exist_ok=True)
    pause = float(cfg.raw["peers"].get("coingecko_pause_seconds", 2.0))
    n = 0
    for p in protocols(cfg):
        for metric in METRICS:
            url = p.get(metric)
            if not url:
                continue
            ds = _dataset(p["slug"], metric)
            rows = ds.parse(get_json(url, cfg.http, cfg.paths.cache, use_cache=use_cache))
            write_csv(ds, rows, url, fetched_at, out)
            logger.info("%-22s %5d rows  %s", ds.name, len(rows), ds.provider)
            n += 1
            if metric == "market_cap":
                time.sleep(pause)
    return n


MAIN = {"volume": "intents_volume", "fees": "intents_fees", "revenue": "intents_revenue"}


def _series(cfg: Config, slug: str, metric: str, main: bool = False) -> tuple[pd.Series, str]:
    if main:
        from .analysis import load

        df, url, _ = load(cfg, MAIN[metric])
        return df["usd"], url
    rows = read_csv(_dataset(slug, metric), peers_dir(cfg))
    s = pd.Series({pd.Timestamp(r["date"]): float(r["usd"]) for r in rows})
    return s, rows[0]["source_url"]


def window_rows(cfg: Config, start: pd.Timestamp, end: pd.Timestamp, near_market_cap: float) -> tuple[list[dict], dict]:
    """Volume, fees, revenue and capture for every router over the same days, start to end inclusive."""
    wd = int((end - start).days) + 1
    rows, sources = [], {}
    for p in protocols(cfg):
        vals, src = {}, {}
        for metric in ("volume", "fees", "revenue"):
            s, src[metric] = _series(cfg, p["slug"], metric, bool(p.get("main")))
            seg = s.loc[start:end]
            if len(seg) < wd - 2:  # allow a missing day or two, never a gap that changes the story
                raise StatsError(f"{p['slug']} {metric}: {len(seg)} days in the {wd} day window")
            vals[metric] = float(seg.sum())
        mcap = None
        if p.get("main"):
            mcap = near_market_cap
        elif p.get("market_cap"):
            s, src["market_cap"] = _series(cfg, p["slug"], "market_cap")
            mcap = float(s.loc[:end].iloc[-1])
        annual_rev = vals["revenue"] * 365 / wd
        rows.append(
            {
                "slug": p["slug"],
                "name": p["name"],
                "model": p["model"],
                "volume_usd": vals["volume"],
                "fees_usd": vals["fees"],
                "revenue_usd": vals["revenue"],
                "fee_bps": vals["fees"] / vals["volume"] * 1e4,
                "revenue_bps": vals["revenue"] / vals["volume"] * 1e4,
                "revenue_share_of_fees_pct": vals["revenue"] / vals["fees"] * 100 if vals["fees"] > 0 else 0.0,
                "annual_revenue_usd": annual_rev,
                "market_cap_usd": mcap,
                "mcap_to_annual_revenue": (mcap / annual_rev) if (mcap and annual_rev > 0) else None,
            }
        )
        sources[p["slug"]] = src
    rows.sort(key=lambda r: -r["volume_usd"])
    return rows, sources


def compare(cfg: Config, window_end: str, near_market_cap: float) -> dict:
    """Same window for every router, ending on the thesis window end so the build is reproducible."""
    if not protocols(cfg) or not peers_dir(cfg).exists():
        return {}
    wd = int(cfg.raw["peers"]["window_days"])
    end = pd.Timestamp(window_end)
    start = end - days(wd - 1)
    rows, sources = window_rows(cfg, start, end, near_market_cap)
    me = next(r for r in rows if r["slug"] == "near_intents")
    others = [r for r in rows if r["slug"] != "near_intents"]
    token_peers = [r for r in others if r["mcap_to_annual_revenue"] is not None]
    first = next(p for p in protocols(cfg) if not p.get("main"))
    fetched = read_csv(_dataset(first["slug"], "volume"), peers_dir(cfg))[0]["fetched_at_utc"]
    return {
        "fetched_at_utc": fetched,
        "window_days": wd,
        "window_start": str(start.date()),
        "window_end": str(end.date()),
        "rows": rows,
        "sources": sources,
        "intents_volume_rank": [r["slug"] for r in rows].index("near_intents") + 1,
        "routers": len(rows),
        "intents_share_of_peer_volume_pct": me["volume_usd"] / sum(r["volume_usd"] for r in rows) * 100,
        "intents_fee_bps": me["fee_bps"],
        "intents_revenue_bps": me["revenue_bps"],
        "peer_fee_bps_median": float(pd.Series([r["fee_bps"] for r in others]).median()),
        "peer_revenue_bps_median": float(pd.Series([r["revenue_bps"] for r in others]).median()),
        "cheaper_than": sum(r["fee_bps"] > me["fee_bps"] for r in others),
        "near_mcap_to_annual_revenue": me["mcap_to_annual_revenue"],
        "token_peer_mcap_to_annual_revenue_median": (
            float(pd.Series([r["mcap_to_annual_revenue"] for r in token_peers]).median()) if token_peers else None
        ),
        "near_premium_to_token_peers_x": (
            me["mcap_to_annual_revenue"] / float(pd.Series([r["mcap_to_annual_revenue"] for r in token_peers]).median())
            if token_peers
            else None
        ),
    }
