"""Predictions written down before the data exists, and the code that scores them.

`python -m settlemark predictions --freeze` writes data/predictions.json and PREDICTIONS.md
once, with thresholds computed from today's results. It refuses to overwrite them. The
sha256 of the JSON is printed in PREDICTIONS.md and checked by the tests, so any later edit
is visible. `python -m settlemark predictions --score` scores each prediction once its window
has closed and its data has been fetched; before that it reports PENDING. Every result is
published, misses included, together with the Brier score of the stated probabilities.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import load
from .config import Config
from .deep import load_chain
from .stats import log_changes, pearson

WEEK1_END = "2026-11-22"  # first full week after the freeze (weeks end Sunday UTC)
END_4W = "2026-12-13"
END_8W = "2027-01-10"
CHAIN_START = "2026-11-16"  # Monday 00:00 UTC block that opens the window
CHAIN_END = "2027-01-11"  # Monday 00:00 UTC block that closes it
GRACE_DAYS = 2  # sources publish a day late; score no earlier than this after the window


def _canon(obj: object) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":")).encode()


def sha256_of(obj: object) -> str:
    return hashlib.sha256(_canon(obj)).hexdigest()


def build_predictions(R: dict, created_at: str) -> dict:
    """Thresholds come from today's results by fixed rules; nothing is typed by hand."""
    V, C = R["valuation"], R["chain"]
    rows = [
        {
            "id": "P1",
            "claim": "Usage holds whatever the price does",
            "metric": "mean weekly NEAR Intents volume, weeks ending " + WEEK1_END + " to " + END_4W,
            "rule": "at least 50% of the mean of the last 4 weeks at freeze",
            "op": ">=",
            "threshold": round(0.5 * R["intents_weekly_volume_last_4w"], 2),
            "unit": "USD",
            "window_end": END_4W,
            "datasets": ["intents_volume"],
            "probability": 0.85,
        },
        {
            "id": "P2",
            "claim": "Intents keeps its share of onchain trading",
            "metric": "mean weekly Intents share of all DEX volume, weeks ending " + WEEK1_END + " to " + END_8W,
            "rule": "at least the mean of the 13 weeks before the latest 13 at freeze",
            "op": ">=",
            "threshold": round(R["share_prev_13w_pct"], 4),
            "unit": "percent",
            "window_end": END_8W,
            "datasets": ["intents_volume", "all_dex_volume"],
            "probability": 0.70,
        },
        {
            "id": "P3",
            "claim": "Usage does not simply follow price",
            "metric": "correlation of weekly log changes, Intents volume against NEAR price, 8 weeks ending " + END_8W,
            "rule": "at most 0.5, the line THESIS.md already uses",
            "op": "<=",
            "threshold": 0.5,
            "unit": "correlation",
            "window_end": END_8W,
            "datasets": ["intents_volume", "near_chain"],
            "probability": 0.60,
        },
        {
            "id": "P4",
            "claim": "Holders still capture little",
            "metric": "NEAR market cap on " + END_8W + " over Intents revenue in the 364 days to that date",
            "rule": "at least 50x, the F5 line",
            "op": ">=",
            "threshold": 50.0,
            "unit": "multiple",
            "window_end": END_8W,
            "datasets": ["near_chain", "intents_revenue"],
            "probability": 0.90,
        },
        {
            "id": "P5",
            "claim": "Buybacks do not offset new supply",
            "metric": "NEAR gained by buybacks.multisignature.near over NEAR added to total supply, blocks at "
            + CHAIN_START
            + " and "
            + CHAIN_END
            + " 00:00 UTC",
            "rule": "below 50%",
            "op": "<",
            "threshold": 50.0,
            "unit": "percent",
            "window_end": END_8W,
            "datasets": ["near_rpc"],
            "probability": 0.90,
        },
        {
            "id": "P6",
            "claim": "Buybacks keep running at a real pace",
            "metric": "same ratio as P5",
            "rule": "at least 10%, a bit over half of the last 13 weeks at freeze (" + f"{C['buyback_coverage_13w_pct']:.1f}%)",
            "op": ">=",
            "threshold": 10.0,
            "unit": "percent",
            "window_end": END_8W,
            "datasets": ["near_rpc"],
            "probability": 0.75,
        },
        {
            "id": "P7",
            "claim": "State inside Intents keeps growing",
            "metric": "intents.near storage in bytes at the " + CHAIN_END + " block over the " + CHAIN_START + " block",
            "rule": "at least 1.05x (the last 52 weeks grew " + f"{C['intents_storage_growth_52w_x']:.2f}x)",
            "op": ">=",
            "threshold": 1.05,
            "unit": "ratio",
            "window_end": END_8W,
            "datasets": ["near_rpc"],
            "probability": 0.85,
        },
        {
            "id": "P8",
            "claim": "Revenue does not collapse",
            "metric": "Intents revenue in the 28 days ending " + END_4W,
            "rule": "at least half of the 91 day run rate at freeze, scaled to 28 days",
            "op": ">=",
            "threshold": round(0.5 * V["revenue_run_rate_usd"] * 28 / 365, 2),
            "unit": "USD",
            "window_end": END_4W,
            "datasets": ["intents_revenue"],
            "probability": 0.85,
        },
    ]
    return {
        "created_at_utc": created_at,
        "data_window_end": R["window_end"],
        "results_fetched_at_utc": R["fetched_at_utc"],
        "rule_for_part1": "If P1 and P2 both miss, part 1 of the thesis (usage independent of price) is rejected.",
        "rule_for_part2": "If P4 or P5 misses, part 2 (holders capture little) is rejected and the case turns bullish.",
        "predictions": rows,
    }


def freeze(cfg: Config, R: dict, created_at: str | None = None) -> Path:
    out = cfg.paths.data / "predictions.json"
    if out.exists():
        raise FileExistsError(f"{out} already exists; predictions are frozen and are never rewritten")
    created_at = created_at or dt.datetime.now(dt.UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    P = build_predictions(R, created_at)
    out.write_text(json.dumps(P, indent=2) + "\n")
    (cfg.paths.root / "PREDICTIONS.md").write_text(render_md(P))
    return out


def render_md(P: dict) -> str:
    lines = [
        "# Settlemark predictions, written down before the data exists",
        "",
        f"Frozen {P['created_at_utc']} from data to {P['data_window_end']}. Machine readable copy: `data/predictions.json`, "
        f"sha256 `{sha256_of(P)}` (canonical JSON, sorted keys). The git commit that added this file is its timestamp; "
        "`tests/test_predictions.py` fails if the file changes.",
        "",
        "Weeks end on Sunday, UTC. Scoring waits two days after each window for sources to publish, then runs "
        "`python -m settlemark predictions --score`. Misses are published like hits. The probability is ours, stated now, "
        "so the Brier score can grade our calibration.",
        "",
        "| ID | Claim | What is measured | Pass if | Threshold | Window ends | Our probability |",
        "|---|---|---|---|---|---|---|",
    ]
    for p in P["predictions"]:
        lines.append(
            f"| {p['id']} | {p['claim']} | {p['metric']} | {p['op']} ({p['rule']}) | {_fmt(p['threshold'], p['unit'])} | {p['window_end']} | {p['probability']:.2f} |"
        )
    lines += ["", P["rule_for_part1"], "", P["rule_for_part2"], ""]
    return "\n".join(lines)


def _fmt(x: float, unit: str) -> str:
    if unit == "USD":
        return f"${x:,.0f}"
    if unit == "percent":
        return f"{x:g}%"
    if unit in ("multiple",):
        return f"{x:g}x"
    if unit == "ratio":
        return f"{x:g}x"
    return f"{x:g}"


def _weekly(cfg: Config) -> pd.DataFrame:
    iv, _, _ = load(cfg, "intents_volume")
    dex, _, _ = load(cfg, "all_dex_volume")
    ch, _, _ = load(cfg, "near_chain")
    d = pd.DataFrame({"iv": iv["usd"], "dex": dex["usd"], "p": ch["near_price_usd"]}).dropna()
    w = d.resample(cfg.analysis.week_rule).agg({"iv": "sum", "dex": "sum", "p": "last"})
    w["share"] = w.iv / w.dex * 100
    return w


def measure(cfg: Config, pid: str, today: dt.date) -> float | None:
    """The realised value of a prediction, or None while its data is not complete."""
    w = _weekly(cfg)
    last_complete = pd.Timestamp(today - dt.timedelta(days=GRACE_DAYS))
    if pid in ("P1", "P8"):
        end = pd.Timestamp(END_4W)
    else:
        end = pd.Timestamp(END_8W)
    if last_complete < end:
        return None
    start = pd.Timestamp(WEEK1_END)
    seg = w.loc[start:end]
    if pid == "P1":
        return float(seg.iv.mean())
    if pid == "P2":
        return float(seg.share.mean())
    if pid == "P3":
        c = log_changes(w.loc[start - pd.Timedelta(days=7) : end, ["iv", "p"]])
        return pearson(c.iv, c.p)
    if pid == "P4":
        rev, _, _ = load(cfg, "intents_revenue")
        ch, _, _ = load(cfg, "near_chain")
        return float(ch["market_cap_usd"].loc[:end].iloc[-1] / rev["usd"].loc[end - pd.Timedelta(days=363) : end].sum())
    if pid == "P8":
        rev, _, _ = load(cfg, "intents_revenue")
        return float(rev["usd"].loc[end - pd.Timedelta(days=27) : end].sum())
    chain = load_chain(cfg)
    a, b = pd.Timestamp(CHAIN_START), pd.Timestamp(CHAIN_END)
    if a not in chain.index or b not in chain.index:
        return None
    if pid in ("P5", "P6"):
        return float(
            (chain.buyback_wallet_near[b] - chain.buyback_wallet_near[a]) / (chain.total_supply_near[b] - chain.total_supply_near[a]) * 100
        )
    if pid == "P7":
        return float(chain.intents_storage_bytes[b] / chain.intents_storage_bytes[a])
    raise KeyError(pid)


OPS = {">=": np.greater_equal, "<=": np.less_equal, "<": np.less, ">": np.greater}


def score(cfg: Config, today: dt.date | None = None) -> dict:
    P = json.loads((cfg.paths.data / "predictions.json").read_text())
    today = today or dt.datetime.now(dt.UTC).date()
    out, briers = [], []
    for p in P["predictions"]:
        val = measure(cfg, p["id"], today)
        if val is None:
            status = "PENDING"
        else:
            hit = bool(OPS[p["op"]](val, p["threshold"]))
            status = "HIT" if hit else "MISS"
            briers.append((p["probability"] - (1.0 if hit else 0.0)) ** 2)
        out.append({"id": p["id"], "status": status, "value": val, "threshold": p["threshold"], "window_end": p["window_end"]})
    return {
        "scored_on": today.isoformat(),
        "sha256": sha256_of(P),
        "created_at_utc": P["created_at_utc"],
        "results": out,
        "resolved": len(briers),
        "brier": (sum(briers) / len(briers)) if briers else None,
    }
