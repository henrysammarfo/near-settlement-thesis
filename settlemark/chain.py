"""Raw chain evidence read straight from NEAR mainnet archival RPC, no indexer in between.

For one block per week (the first block at or after Monday 00:00 UTC, the start of each
week) we read:

* the block header: height, hash, timestamp and `total_supply`, so issuance is measured
  from the chain itself rather than taken from a blog post;
* `buybacks.multisignature.near`, the wallet the NEAR Foundation tokenomics programme
  sweeps bought back NEAR into (its native balance at that block);
* `intents.near`, the NEAR Intents verifier contract: its storage in bytes, which grows
  as more accounts and token balances live inside Intents.

Every row keeps the block height and hash, so anyone can re-read the same block from any
archival node and get the same numbers. Responses for a fixed block never change, so they
are cached on disk without expiry.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from . import log
from .schema import Column, Schema, validate

YOCTO = 10**24
SCHEMA = Schema(
    "near_rpc",
    (
        Column("week_start", "date"),
        Column("block_height", "int", min=1),
        Column("block_hash", "str"),
        Column("block_time_utc", "str"),
        Column("total_supply_near", "number", min=0),
        Column("buyback_wallet_near", "number", min=0),
        Column("intents_storage_bytes", "int", min=0),
    ),
    20,
)
HEADER = tuple(SCHEMA.header)


class RpcError(RuntimeError):
    """Raised when every RPC endpoint fails for a request."""


@dataclass(frozen=True)
class ChainConfig:
    endpoints: tuple[str, ...]
    buyback_account: str
    intents_account: str
    first_week: str
    timeout_seconds: float = 30
    retries: int = 3


class Rpc:
    """Minimal JSON-RPC client with endpoint fallback and an immutable on disk cache."""

    def __init__(
        self,
        cfg: ChainConfig,
        cache_dir: Path | None,
        opener: Callable[..., Any] = urllib.request.urlopen,
        sleep: Callable[[float], None] = time.sleep,
    ):
        self.cfg, self.cache_dir, self.opener, self.sleep = cfg, cache_dir, opener, sleep
        self.calls = 0

    def _key(self, method: str, params: Any) -> Path | None:
        if self.cache_dir is None or (isinstance(params, dict) and params.get("finality")):
            return None
        h = hashlib.sha256(json.dumps([method, params], sort_keys=True).encode()).hexdigest()[:32]
        return self.cache_dir / f"{h}.json"

    def call(self, method: str, params: Any) -> tuple[dict, str]:
        key = self._key(method, params)
        if key is not None and key.exists():
            cached = json.loads(key.read_text())
            return cached["result"], cached["rpc"]
        body = json.dumps({"jsonrpc": "2.0", "id": "settlemark", "method": method, "params": params}).encode()
        last: Exception | None = None
        for url in self.cfg.endpoints:
            for attempt in range(1, self.cfg.retries + 1):
                try:
                    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
                    try:
                        with self.opener(req, timeout=self.cfg.timeout_seconds) as resp:
                            out = json.loads(resp.read())
                    except urllib.error.HTTPError as he:
                        # NEAR RPC answers a missing block or account with HTTP 4xx and a JSON error body
                        payload = he.read()
                        try:
                            out = json.loads(payload)
                        except json.JSONDecodeError:
                            raise he from None
                        if "error" not in out:
                            raise he from None
                    self.calls += 1
                    if "error" in out:
                        err = out["error"]
                        cause = (err.get("cause") or {}).get("name", "")
                        if cause in ("UNKNOWN_ACCOUNT", "UNKNOWN_BLOCK"):
                            res = {"missing": cause}
                            break
                        raise RpcError(f"{method} {params}: {err.get('message')} {cause}")
                    res = out["result"]
                    break
                except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, RpcError) as e:
                    last = e
                    if attempt < self.cfg.retries:
                        self.sleep(1.5 * attempt)
            else:
                continue
            if method == "block" and "header" in res:
                res = {"header": res["header"]}
            if key is not None:
                key.parent.mkdir(parents=True, exist_ok=True)
                key.write_text(json.dumps({"result": res, "rpc": url}))
            return res, url
        raise RpcError(f"every endpoint failed for {method}: {last}")


def _ts(header: dict) -> float:
    return int(header["timestamp"]) / 1e9


def _header(rpc: Rpc, height: int, ceiling: int) -> tuple[dict | None, str]:
    """Header of the first existing block at or above `height` (NEAR skips some heights)."""
    h = height
    while h <= ceiling:
        res, url = rpc.call("block", {"block_id": h})
        if "missing" not in res:
            return res["header"], url
        h += 1
    return None, ""


def _header_below(rpc: Rpc, height: int, floor: int) -> tuple[dict | None, str]:
    """Header of the last existing block at or below `height` and above `floor`."""
    h = height
    while h > floor:
        res, url = rpc.call("block", {"block_id": h})
        if "missing" not in res:
            return res["header"], url
        h -= 1
    return None, ""


def block_at(rpc: Rpc, target: float, head: dict, floor: dict) -> tuple[dict, str]:
    """First block whose timestamp is at or after unix time `target`.

    Interpolation search inside a bracket [lo, hi] with time(lo) < target <= time(hi),
    switching to bisection when the bracket is small. About 6 to 10 reads per block.
    """
    lo, hi = floor, head
    url = ""
    while hi["height"] - lo["height"] > 1:
        span = hi["height"] - lo["height"]
        if span > 64:
            frac = (target - _ts(lo)) / max(_ts(hi) - _ts(lo), 1e-9)
            mid = lo["height"] + int(frac * span)
            mid = min(max(mid, lo["height"] + 1), hi["height"] - 1)
        else:
            mid = (lo["height"] + hi["height"]) // 2
        hdr, u = _header(rpc, mid, hi["height"] - 1)
        if hdr is None:
            hdr, u = _header_below(rpc, mid - 1, lo["height"])
            if hdr is None:
                break  # no block strictly between lo and hi: hi is the answer
        if _ts(hdr) >= target:
            hi, url = hdr, u
        else:
            lo = hdr
    if not url:
        _, url = rpc.call("block", {"block_id": hi["height"]})
    return hi, url


def week_starts(first: str, today: dt.date) -> list[dt.date]:
    d = dt.date.fromisoformat(first)
    d -= dt.timedelta(days=d.weekday())
    out = []
    while d <= today:
        out.append(d)
        d += dt.timedelta(days=7)
    return out


def sample(rpc: Rpc, cfg: ChainConfig, fetched_at: str, now: dt.datetime | None = None) -> list[tuple]:
    logger = log.get()
    head, _ = rpc.call("block", {"finality": "final"})
    head_hdr = head["header"]
    head_time = dt.datetime.fromtimestamp(_ts(head_hdr), dt.UTC)
    now = now or head_time
    rows = []
    prev_hdr: dict | None = None
    for wk in week_starts(cfg.first_week, min(now, head_time).date()):
        target = dt.datetime(wk.year, wk.month, wk.day, tzinfo=dt.UTC).timestamp()
        if target > _ts(head_hdr):
            break
        floor_hdr = (
            prev_hdr or _header(rpc, max(1, int(head_hdr["height"] - (_ts(head_hdr) - target) / 0.5) - 2_000_000), head_hdr["height"])[0]
        )
        if floor_hdr is None:
            raise RpcError(f"no block found before {wk}")
        if _ts(floor_hdr) >= target:
            raise RpcError(f"floor block {floor_hdr['height']} is not before {wk}")
        hdr, url = block_at(rpc, target, head_hdr, floor_hdr)
        prev_hdr = hdr
        bb, _ = rpc.call("query", {"request_type": "view_account", "block_id": hdr["height"], "account_id": cfg.buyback_account})
        it, _ = rpc.call("query", {"request_type": "view_account", "block_id": hdr["height"], "account_id": cfg.intents_account})
        bb_near = 0.0 if "missing" in bb else (int(bb["amount"]) + int(bb["locked"])) / YOCTO
        it_bytes = 0 if "missing" in it else int(it["storage_usage"])
        rows.append(
            (
                wk.isoformat(),
                hdr["height"],
                hdr["hash"],
                dt.datetime.fromtimestamp(_ts(hdr), dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
                round(int(hdr["total_supply"]) / YOCTO, 6),
                round(bb_near, 6),
                it_bytes,
                fetched_at,
                url,
            )
        )
    logger.info("near_rpc          %5d rows  NEAR archival RPC (%d calls)", len(rows), rpc.calls)
    return rows


def write(rows: list[tuple], path: Path) -> None:
    str_rows = [dict(zip(HEADER, [str(v) for v in r], strict=True)) for r in rows]
    validate(SCHEMA, list(HEADER), str_rows)
    tmp = path.with_suffix(".csv.tmp")
    with tmp.open("w", newline="") as f:
        w = csv.writer(f, lineterminator="\n")
        w.writerow(HEADER)
        w.writerows(rows)
    tmp.replace(path)


def read(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        validate(SCHEMA, reader.fieldnames or [], rows)
    return rows
