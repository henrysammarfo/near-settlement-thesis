"""Prediction hashes anchored on NEAR testnet, and the check that they match the files.

`data/anchors.json` lists each anchoring transaction. `data/anchors/<tx>.json` keeps the
raw RPC response for it, so `python -m settlemark anchor show` verifies offline: the
arguments inside the committed transaction must equal what `payload()` builds from the
committed prediction files today. `python -m settlemark anchor verify` also refetches the
transaction from a public testnet RPC and checks it executed successfully.
"""

from __future__ import annotations

import base64
import json
import urllib.request
from pathlib import Path

from .config import Config
from .predictions import SETS, sha256_of

RPC = "https://rpc.testnet.near.org"


def payload(cfg: Config) -> dict:
    files, frozen = {}, {}
    for name, _md, _b in SETS.values():
        p = cfg.paths.data / name
        if p.exists():
            P = json.loads(p.read_text())
            files[f"data/{name}"] = sha256_of(P)
            frozen[f"data/{name}"] = P["created_at_utc"]
    return {"project": "settlemark", "repo": cfg.project["repo"], "sha256": files, "frozen_utc": frozen}


def args_json(cfg: Config) -> str:
    return json.dumps(payload(cfg), sort_keys=True, separators=(",", ":"))


def _fn_args(tx: dict) -> str:
    for a in tx["transaction"]["actions"]:
        if isinstance(a, dict) and "FunctionCall" in a:
            return base64.b64decode(a["FunctionCall"]["args"]).decode()
    raise ValueError("transaction has no function call")


def _succeeded(tx: dict) -> bool:
    st = tx.get("status", {})
    return isinstance(st, dict) and "SuccessValue" in st


def rpc_tx(tx_hash: str, sender: str, rpc: str = RPC, timeout: float = 30.0) -> dict:
    body = json.dumps(
        {
            "jsonrpc": "2.0",
            "id": "settlemark",
            "method": "tx",
            "params": {"tx_hash": tx_hash, "sender_account_id": sender, "wait_until": "FINAL"},
        }
    )
    req = urllib.request.Request(rpc, body.encode(), {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        d = json.loads(r.read())
    if "error" in d:
        raise ValueError(f"RPC error: {d['error']}")
    return d["result"]


def verify(cfg: Config, live: bool = False, fetch=rpc_tx) -> dict:
    p = cfg.paths.data / "anchors.json"
    if not p.exists():
        return {"ok": False, "problems": ["data/anchors.json is missing"]}
    A = json.loads(p.read_text())
    want = args_json(cfg)
    out, problems = [], []
    for a in A["anchors"]:
        raw = cfg.paths.data / "anchors" / f"{a['tx_hash']}.json"
        txs = [("committed", json.loads(raw.read_text()))] if raw.exists() else []
        if not raw.exists():
            problems.append(f"{raw.name} missing")
        if live:
            txs.append(("live", fetch(a["tx_hash"], a["signer"])))
        for where, tx in txs:
            got = _fn_args(tx)
            if tx["transaction"]["hash"] != a["tx_hash"] or tx["transaction"]["signer_id"] != a["signer"]:
                problems.append(f"{where}: transaction hash or signer differs from anchors.json")
            if tx["transaction"]["receiver_id"] != a["receiver"]:
                problems.append(f"{where}: receiver differs from anchors.json")
            if not _succeeded(tx):
                problems.append(f"{where}: transaction did not succeed")
            if got != a["args"]:
                problems.append(f"{where}: arguments differ from anchors.json")
        out.append({"tx_hash": a["tx_hash"], "network": a["network"], "explorer_url": a["explorer_url"], "checked": [w for w, _ in txs]})
    latest = A["anchors"][-1]["args"] if A["anchors"] else ""
    if latest != want:
        problems.append("the latest anchor does not match the committed prediction files (a file changed after anchoring)")
    return {"ok": not problems, "expected_args": json.loads(want), "anchors": out, "problems": problems}


def record(cfg: Config, tx: dict, network: str = "testnet", rpc: str = RPC) -> Path:
    """Append a finished anchoring transaction (an RPC `tx` result) to data/anchors.json."""
    t = tx["transaction"]
    fc = next(a["FunctionCall"] for a in t["actions"] if isinstance(a, dict) and "FunctionCall" in a)
    block_hash = tx["transaction_outcome"]["block_hash"]
    body = json.dumps({"jsonrpc": "2.0", "id": "s", "method": "block", "params": {"block_id": block_hash}})
    with urllib.request.urlopen(urllib.request.Request(rpc, body.encode(), {"Content-Type": "application/json"}), timeout=30) as r:
        hdr = json.loads(r.read())["result"]["header"]
    import datetime as dt

    when = dt.datetime.fromtimestamp(int(hdr["timestamp_nanosec"]) / 1e9, dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    entry = {
        "network": network,
        "signer": t["signer_id"],
        "receiver": t["receiver_id"],
        "method": fc["method_name"],
        "tx_hash": t["hash"],
        "block_hash": block_hash,
        "block_height": hdr["height"],
        "block_time_utc": when,
        "explorer_url": f"https://testnet.nearblocks.io/txns/{t['hash']}",
        "args": base64.b64decode(fc["args"]).decode(),
    }
    p = cfg.paths.data / "anchors.json"
    A = json.loads(p.read_text()) if p.exists() else {"anchors": []}
    A["anchors"].append(entry)
    p.write_text(json.dumps(A, indent=2) + "\n")
    raw = cfg.paths.data / "anchors" / f"{t['hash']}.json"
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(json.dumps(tx, indent=2, sort_keys=True) + "\n")
    return p
