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
    from . import bigquery as bq
    from .leadlag import leadlag
    from .peers import compare

    R["leadlag"] = leadlag(cfg, frames, series["chain"], bq.weekly_activity(cfg))
    R["peers"] = compare(cfg, R["window_end"], R["near_market_cap"])
    R["bigquery"] = {"dataset": cfg.raw["bigquery"]["dataset"], "queries": bq.status(cfg)}
    R["provenance"].update(
        {
            "leadlag": ["intents_volume", "near_chain", "near_rpc", "bigquery/05_weekly_activity"],
            "peers": ["intents_volume", "intents_fees", "intents_revenue", "near_chain", "peers/*"],
            "bigquery": ["bigquery/manifest.json"],
        }
    )
    if (cfg.paths.data / "predictions.json").exists():
        # Score as of the data fetch date, so the build stays a pure function of data/.
        R["predictions"] = score(cfg, dt.date.fromisoformat(R["fetched_at_utc"][:10]))
    if (cfg.paths.data / "predictions_2.json").exists():
        R["predictions_2"] = score(cfg, dt.date.fromisoformat(R["fetched_at_utc"][:10]), which=2)
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
        choices=["fetch", "build", "rebuild", "check", "predictions", "bigquery", "bigquery-import", "anchor"],
        help="fetch data, build outputs from data, both, check that the committed outputs rebuild exactly, or freeze/score predictions",
    )
    ap.add_argument("query", nargs="?", help="bigquery: query key in settlemark.toml (e.g. 05) or 'all'; anchor: 'verify' or 'show'")
    ap.add_argument("csv", nargs="?", help="bigquery-import: CSV downloaded from the BigQuery console")
    ap.add_argument(
        "--max-gb", type=float, default=None, help="bigquery: refuse queries that would scan more than this (default from settlemark.toml)"
    )
    ap.add_argument("--dry-run", action="store_true", help="bigquery: only report how many GB each query would scan")
    ap.add_argument("--scanned-gb", type=float, default=None, help="bigquery-import: GB the console reported for the run")
    ap.add_argument("--run-at", default=None, help="bigquery-import: when the console run finished, e.g. 2026-11-15T06:00:00Z")
    ap.add_argument("--freeze", action="store_true", help="predictions: write data/predictions.json once (refuses to overwrite)")
    ap.add_argument("--set", type=int, default=1, choices=[1, 2], help="predictions: which frozen set (1 or 2)")
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
            from . import bigquery as bq

            if not args.query:
                for s in bq.status(cfg):
                    logger.info(
                        "%s %-34s %s",
                        s["key"],
                        s["csv"],
                        f"{s['rows']} rows, {s['scanned_gb']} GB" if s["committed"] else "not committed yet",
                    )
            else:
                keys = [q.key for q in bq.queries(cfg)] if args.query == "all" else [args.query]
                for k in keys:
                    out = bq.run(cfg, k, args.max_gb, dry_run=args.dry_run)
                    logger.info("%s: %s", k, f"would scan {out:.1f} GB" if args.dry_run else f"wrote {out}")
        if args.command == "bigquery-import":
            from . import bigquery as bq

            if not (args.query and args.csv and args.scanned_gb is not None):
                raise ValueError("usage: python -m settlemark bigquery-import 05 results.csv --scanned-gb 123.4 [--run-at ...]")
            logger.info("wrote %s", bq.import_csv(cfg, args.query, args.csv, args.scanned_gb, args.run_at))
        if args.command == "anchor":
            from . import anchor

            report = anchor.verify(cfg, live=(args.query == "verify"))
            print(json.dumps(report, indent=2))
            if not report["ok"]:
                return 1
        if args.command == "predictions":
            if args.freeze:
                R = json.loads((cfg.paths.results / "results.json").read_text())
                logger.info("froze %s", freeze(cfg, R, which=args.set))
            if args.score or not args.freeze:
                print(json.dumps(score(cfg, which=args.set), indent=2))
    except (ConfigError, FetchError, SchemaError, StatsError, ValueError, FileExistsError) as e:
        logger.error("%s: %s", type(e).__name__, e)
        return 1
    logger.info("done in %.1fs", time.monotonic() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
