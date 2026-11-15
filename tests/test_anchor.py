"""Prediction hashes on NEAR testnet match the committed files, and tampering is caught."""

import json
import shutil

from settlemark import anchor
from settlemark.config import ROOT, load_config


def test_committed_anchor_verifies_offline():
    r = anchor.verify(load_config())
    assert r["ok"], r["problems"]
    A = json.loads((ROOT / "data" / "anchors.json").read_text())["anchors"][-1]
    assert A["network"] == "testnet" and A["signer"].endswith(".testnet")
    args = json.loads(A["args"])
    md1 = (ROOT / "PREDICTIONS.md").read_text()
    md2 = (ROOT / "PREDICTIONS_2.md").read_text()
    assert args["sha256"]["data/predictions.json"] in md1
    assert args["sha256"]["data/predictions_2.json"] in md2


def test_live_check_uses_the_fetched_transaction():
    cfg = load_config()
    A = json.loads((ROOT / "data" / "anchors.json").read_text())["anchors"][-1]
    raw = json.loads((ROOT / "data" / "anchors" / f"{A['tx_hash']}.json").read_text())
    assert anchor.verify(cfg, live=True, fetch=lambda h, s: raw)["ok"]
    bad = json.loads(json.dumps(raw))
    bad["status"] = {"Failure": {}}
    r = anchor.verify(cfg, live=True, fetch=lambda h, s: bad)
    assert not r["ok"] and any("did not succeed" in p for p in r["problems"])


def test_editing_a_prediction_after_anchoring_is_caught(tmp_path):
    root = tmp_path / "repo"
    shutil.copytree(ROOT / "data", root / "data")
    cfg = load_config(ROOT / "settlemark.toml", root=root, output_root=tmp_path / "out")
    p = root / "data" / "predictions_2.json"
    P = json.loads(p.read_text())
    P["predictions"][0]["probability"] = 0.99
    p.write_text(json.dumps(P, indent=2) + "\n")
    r = anchor.verify(cfg)
    assert not r["ok"] and any("does not match" in x for x in r["problems"])
