"""HTTP GET for JSON with retries, exponential backoff and an on disk cache.

The cache exists so that rerunning the pipeline during development does not hammer free
public APIs. It is keyed by URL, expires after `cache_ttl_hours`, and is never committed.
"""

from __future__ import annotations

import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from . import log
from .config import HttpConfig


class FetchError(RuntimeError):
    """Raised when a source cannot be fetched after every retry."""


def _cache_path(cache_dir: Path, url: str) -> Path:
    return cache_dir / (hashlib.sha256(url.encode()).hexdigest()[:24] + ".json")


def get_json(
    url: str,
    cfg: HttpConfig,
    cache_dir: Path | None = None,
    use_cache: bool = True,
    opener: Callable[..., Any] = urllib.request.urlopen,
    sleep: Callable[[float], None] = time.sleep,
) -> Any:
    """Return parsed JSON from `url`. `opener` and `sleep` are injectable for tests."""
    logger = log.get()
    if cache_dir is not None and use_cache:
        p = _cache_path(cache_dir, url)
        if p.exists() and (time.time() - p.stat().st_mtime) < cfg.cache_ttl_hours * 3600:
            logger.debug("cache hit %s", url)
            return json.loads(p.read_text())
    last: Exception | None = None
    for attempt in range(1, cfg.retries + 1):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": cfg.user_agent, "Accept": "application/json"})
            with opener(req, timeout=cfg.timeout_seconds) as resp:
                body = resp.read()
            data = json.loads(body)
            if cache_dir is not None:
                cache_dir.mkdir(parents=True, exist_ok=True)
                _cache_path(cache_dir, url).write_bytes(body)
            logger.debug("fetched %s (%d bytes, attempt %d)", url, len(body), attempt)
            return data
        except urllib.error.HTTPError as e:
            last = e
            if 400 <= e.code < 500 and e.code != 429:
                raise FetchError(f"{url} returned HTTP {e.code}; not retrying") from e
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as e:
            last = e
        wait = cfg.backoff_seconds * (2 ** (attempt - 1))
        logger.warning("attempt %d/%d failed for %s: %s; retrying in %.0fs", attempt, cfg.retries, url, last, wait)
        if attempt < cfg.retries:
            sleep(wait)
    raise FetchError(f"failed to fetch {url} after {cfg.retries} attempts: {last}")
