"""Archival RPC sampler against a fake chain: block search, skipped heights, missing accounts."""

import datetime as dt
import io
import itertools
import json
import urllib.error

from settlemark import chain

GENESIS = dt.datetime(2026, 1, 1, tzinfo=dt.UTC).timestamp()
HEAD = 40_000
SKIPPED = {1203, 1204, 20160}


def ts(h):
    return GENESIS + h * 600.0  # one block per 10 minutes keeps the fake chain small


class FakeResp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_factory(calls):
    def opener(req, timeout=None):
        body = json.loads(req.data)
        calls.append(body)
        m, p = body["method"], body["params"]
        if m == "block":
            h = HEAD if p.get("finality") else p["block_id"]
            if h in SKIPPED or h > HEAD:
                err = json.dumps({"error": {"cause": {"name": "UNKNOWN_BLOCK"}}}).encode()
                raise urllib.error.HTTPError(req.full_url, 422, "x", {}, io.BytesIO(err))
            hdr = {"height": h, "hash": f"H{h}", "timestamp": str(int(ts(h) * 1e9)), "total_supply": str((10**9 + h) * 10**24)}
            return FakeResp(json.dumps({"result": {"header": hdr}}).encode())
        if p["account_id"] == "buy.near" and p["block_id"] < 30_000:
            err = json.dumps({"error": {"cause": {"name": "UNKNOWN_ACCOUNT"}}}).encode()
            raise urllib.error.HTTPError(req.full_url, 422, "x", {}, io.BytesIO(err))
        return FakeResp(
            json.dumps({"result": {"amount": str(p["block_id"] * 10**24), "locked": "0", "storage_usage": p["block_id"] * 2}}).encode()
        )

    return opener


def cfg():
    return chain.ChainConfig(
        endpoints=("https://rpc.test",), buyback_account="buy.near", intents_account="intents.near", first_week="2026-01-05"
    )


def test_block_at_finds_first_block_at_or_after_target(tmp_path):
    calls = []
    rpc = chain.Rpc(cfg(), tmp_path, opener=opener_factory(calls), sleep=lambda s: None)
    head = rpc.call("block", {"finality": "final"})[0]["header"]
    floor = rpc.call("block", {"block_id": 1})[0]["header"]
    for target_h in (1203.5, 5000.2, 20159.9):
        hdr, _ = chain.block_at(rpc, ts(target_h), head, floor)
        expect = next(h for h in range(int(target_h), HEAD) if h not in SKIPPED and ts(h) >= ts(target_h))
        assert hdr["height"] == expect
    assert len(calls) < 80


def test_sample_rows_and_missing_account(tmp_path):
    calls = []
    rpc = chain.Rpc(cfg(), tmp_path, opener=opener_factory(calls), sleep=lambda s: None)
    rows = chain.sample(rpc, cfg(), "2026-01-01T00:00:00Z", now=dt.datetime.fromtimestamp(ts(HEAD), dt.UTC))
    assert [r[0] for r in rows][:2] == ["2026-01-05", "2026-01-12"]
    for r in rows:
        assert ts(r[1] - 1) < dt.datetime.fromisoformat(r[0]).replace(tzinfo=dt.UTC).timestamp() <= ts(r[1])
    early = [r for r in rows if r[1] < 30_000]
    assert early and all(r[5] == 0.0 for r in early)
    out = tmp_path / "near_rpc.csv"
    chain.write(rows, out)
    assert len(chain.read(out)) == len(rows)
    # A second run is served from the immutable cache except the head lookup.
    calls.clear()
    rpc2 = chain.Rpc(cfg(), tmp_path, opener=opener_factory(calls), sleep=lambda s: None)
    chain.sample(rpc2, cfg(), "2026-01-01T00:00:00Z", now=dt.datetime.fromtimestamp(ts(HEAD), dt.UTC))
    assert len(calls) == 1


def test_committed_rpc_csv_is_weekly_and_monotonic():
    from settlemark.config import load_config

    rows = chain.read(load_config().paths.data / "near_rpc.csv")
    days = [dt.date.fromisoformat(r["week_start"]) for r in rows]
    assert all((b - a).days == 7 for a, b in itertools.pairwise(days))
    assert all(d.weekday() == 0 for d in days)
    heights = [int(r["block_height"]) for r in rows]
    supply = [float(r["total_supply_near"]) for r in rows]
    assert heights == sorted(heights) and supply == sorted(supply)
    assert all(r["block_time_utc"][:10] == r["week_start"] for r in rows)
