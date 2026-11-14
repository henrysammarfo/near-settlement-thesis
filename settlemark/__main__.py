"""Command line: python -m settlemark {fetch,build,rebuild} [-v] [--no-cache]."""

from __future__ import annotations

import argparse
import json
import sys
import time

from . import log
from .analysis import analyse
from .charts import draw_all
from .config import ConfigError, load_config
from .http import FetchError
from .render import render_all
from .schema import SchemaError
from .stats import StatsError


def build(cfg) -> dict:
    logger = log.get()
    R, frames = analyse(cfg)
    cfg.paths.results.mkdir(parents=True, exist_ok=True)
    (cfg.paths.results / "results.json").write_text(json.dumps(R, indent=2, sort_keys=False) + "\n")
    logger.info("results.json: %d keys, window %s to %s, %d weeks", len(R), R["window_start"], R["window_end"], R["weeks"])
    files = draw_all(frames, R, cfg.paths.charts, cfg.paths.site / "charts")
    logger.info("charts: %d files", len(files))
    render_all(cfg)
    logger.info("rendered %s and %s", cfg.paths.thesis.name, cfg.paths.site / "index.html")
    return R


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="settlemark", description="Rebuild the Settlemark NEAR settlement thesis.")
    ap.add_argument("command", choices=["fetch", "build", "rebuild"], help="fetch data, build outputs from data, or both")
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
    except (ConfigError, FetchError, SchemaError, StatsError, ValueError) as e:
        logger.error("%s: %s", type(e).__name__, e)
        return 1
    logger.info("done in %.1fs", time.monotonic() - t0)
    return 0


if __name__ == "__main__":
    sys.exit(main())
