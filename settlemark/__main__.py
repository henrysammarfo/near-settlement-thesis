"""Command line: python -m settlemark {fetch,build,rebuild,check,predictions} [-v] [--no-cache]."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import time

from . import log
from .analysis import analyse
from .charts import draw_all
from .config import ConfigError, load_config
from .deep import deep
from .http import FetchError
from .predictions import freeze, score
from .render import render_all, write_site_data
from .schema import SchemaError
from .stats import StatsError


def _stable(x):
    """Round floats to 12 significant digits so results.json is byte identical across numpy and pandas versions."""
    if isinstance(x, float):
        return float(f"{x:.12g}")
    if isinstance(x, dict):
        return {k: _stable(v) for k, v in x.items()}
    if isinstance(x, list):
        return [_stable(v) for v in x]
    return x


def build(cfg) -> dict:
    logger = log.get()
    R, frames = analyse(cfg)
    D, series = deep(cfg, R, frames)
    R.update(D)
    R["sources"]["near_rpc"] = "data/near_rpc.csv"
    R["provenance"].update(
        {
            **{
                f"chain.{k}": ["near_rpc"]
                for k in D["chain"]
                if not k.startswith(("near_price", "fdv", "nearblocks", "bq_", "intents_revenue", "buyback_13w_usd", "buyback_share"))
            },
            "chain.buyback_13w_usd": ["near_rpc", "near_chain"],
            "chain.buyback_share_of_revenue_13w_pct": ["near_rpc", "near_chain", "intents_revenue"],
            "chain.fdv_usd": ["near_rpc", "near_chain"],
            "valuation": ["near_rpc", "near_chain", "intents_revenue", "intents_volume"],
            "robustness": ["intents_volume", "near_chain"],
        }
    )
    if (cfg.paths.data / "predictions.json").exists():
        # Score as of the data fetch date, so the build stays a pure function of data/.
        R["predictions"] = score(cfg, dt.date.fromisoformat(R["fetched_at_utc"][:10]))
    R = _stable(R)
    cfg.paths.results.mkdir(parents=True, exist_ok=True)
    (cfg.paths.results / "results.json").write_text(json.dumps(R, indent=2, sort_keys=False) + "\n")
    logger.info("results.json: %d keys, window %s to %s, %d weeks", len(R), R["window_start"], R["window_end"], R["weeks"])
    files = draw_all(frames, R, cfg.paths.charts, cfg.paths.site / "charts", series)
    logger.info("charts: %d files", len(files))
    write_site_data(cfg, frames, R)
    render_all(cfg)
    logger.info("rendered %s and %s", cfg.paths.thesis.name, cfg.paths.site / "index.html")
    return R


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="settlemark", description="Rebuild the Settlemark NEAR settlement thesis.")
    ap.add_argument(
        "command",
        choices=["fetch", "build", "rebuild", "check", "predictions", "bigquery"],
        help="fetch data, build outputs from data, both, check that the committed outputs rebuild exactly, or freeze/score predictions",
    )
    ap.add_argument("query", nargs="?", help="bigquery: query number or name prefix in queries/, e.g. 04")
    ap.add_argument("--max-gb", type=float, default=400.0, help="bigquery: refuse queries that would scan more than this")
    ap.add_argument("--freeze", action="store_true", help="predictions: write data/predictions.json once (refuses to overwrite)")
    ap.add_argument("--score", action="store_true", help="predictions: score every prediction whose window has closed")
    ap.add_argument("-v", "--verbose", action="store_true")
    ap.add_argument("--no-cache", action="store_true", help="ignore the local HTTP cache")
    ap.add_argument("--config", default=None, help="path to settlemark.toml")
    args = ap.parse_args(argv)
    logger = log.setup(args.verbose)
    t0 = time.monotonic()
    try:
        cfg = load_config(args.config) if args.config else load_config()
        if args.command in ("fetch", "rebuild"):
            from .fetch import fetch_all

            fetch_all(cfg, use_cache=not args.no_cache)
        if args.command in ("build", "rebuild"):
            build(cfg)
        if args.command == "check":
            from .check import check

            problems = check(cfg)
            for p in problems:
                logger.error("%s", p)
            if problems:
                return 1
            logger.info("check passed: committed outputs rebuild byte for byte and every number in THESIS.md is computed")
        if args.command == "bigquery":
            from .bigquery import run as bq_run

            if not args.query:
                raise ValueError("bigquery needs a query, e.g. python -m settlemark bigquery 04")
            logger.info("wrote %s", bq_run(cfg, args.query, args.max_gb))
        if args.command == "predictions":
            if args.freeze:
                R = json.loads((cfg.paths.results / "results.json").read_text())
                logger.info("froze %s", freeze(cfg, R))
            if args.score or not args.freeze:
                print(json.dumps(score(cfg), indent=2))
    except (ConfigError, FetchError, SchemaError, StatsError, ValueError, FileExistsError) as e:
        logger.error("%s: %s", type(e).__name__, e)
        return 1
    logger.info("done in %.1fs", time.monotonic() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
