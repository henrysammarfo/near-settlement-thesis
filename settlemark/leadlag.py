"""Does NEAR Intents volume lead real network usage? The track's own hypothesis, tested.

Weekly log changes, the same weeks as part 1. For each usage series we report:

* cross correlations of Intents volume this week with usage k weeks later (k = -4..4);
* a Granger style F test: do past Intents changes improve a forecast of usage beyond
  usage's own past? Run at several lag orders, with the headline order fixed in
  settlemark.toml before looking, plus a distribution free circular shift p value;
* the same test in reverse (usage leading Intents).

Usage series: NearBlocks daily active accounts and transactions, the raw chain state size
of intents.near (archival RPC), and, when committed, weekly signers and transactions from
the NEAR BigQuery public dataset.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from .analysis import Frames
from .config import Config
from .stats import cross_corr, granger

LABELS = {
    "aa": "NearBlocks daily active accounts",
    "tx": "NearBlocks transactions",
    "storage": "intents.near state size (RPC)",
    "bq_signers": "BigQuery weekly distinct signers",
    "bq_txs": "BigQuery weekly transactions",
}


def usage_changes(frames: Frames, chain_weekly: pd.DataFrame | None, bq_weekly: pd.DataFrame | None) -> pd.DataFrame:
    chg = frames.changes
    out = {"iv": chg["iv"], "aa": chg["aa"], "tx": chg["tx"]}
    if chain_weekly is not None:
        st = chain_weekly["intents_storage_bytes"]
        st = st[st > 0].astype(float)
        out["storage"] = np.log(st).diff()
    if bq_weekly is not None and len(bq_weekly):
        out["bq_signers"] = np.log(bq_weekly["signers"].astype(float)).diff()
        out["bq_txs"] = np.log(bq_weekly["transactions"].astype(float)).diff()
    return pd.DataFrame(out)


def leadlag(cfg: Config, frames: Frames, chain_weekly: pd.DataFrame | None = None, bq_weekly: pd.DataFrame | None = None) -> dict:
    L = cfg.raw["leadlag"]
    K, main, alpha = int(L["max_lag"]), int(L["main_lags"]), float(L["alpha"])
    df = usage_changes(frames, chain_weekly, bq_weekly)
    tests = []
    for key in [k for k in LABELS if k in df.columns]:
        pair = df[["iv", key]].dropna()
        min_weeks = 3 * max(L["lags"]) + 2 * int(L["min_shift"]) + 5
        if len(pair) < min_weeks:
            tests.append({"series": key, "label": LABELS[key], "weeks": len(pair), "skipped": f"fewer than {min_weeks} weeks"})
            continue
        xc = cross_corr(pair.iv, pair[key], K)
        fwd = [granger(pair[key], pair.iv, p, int(L["min_shift"])) for p in L["lags"]]
        rev = [granger(pair.iv, pair[key], p, int(L["min_shift"])) for p in L["lags"]]
        head = next(g for g in fwd if g["lags"] == main)
        head_rev = next(g for g in rev if g["lags"] == main)
        best = max((x for x in xc if x[0] > 0), key=lambda x: abs(x[1]))
        tests.append(
            {
                "series": key,
                "label": LABELS[key],
                "weeks": len(pair),
                "first_week": str(pair.index[0].date()),
                "last_week": str(pair.index[-1].date()),
                "xcorr_lags": [k for k, _ in xc],
                "xcorr": [v for _, v in xc],
                "best_lead_weeks": best[0],
                "best_lead_corr": best[1],
                "intents_leads": fwd,
                "usage_leads": rev,
                "headline_lags": main,
                "headline_p": head["p_value"],
                "headline_p_shift": head["p_shift"],
                "headline_reverse_p": head_rev["p_value"],
                "intents_leads_significant": bool(head["p_value"] < alpha and head["p_shift"] < alpha),
                "usage_leads_significant": bool(head_rev["p_value"] < alpha and head_rev["p_shift"] < alpha),
                "any_order_below_alpha": [g["lags"] for g in fwd if g["p_value"] < alpha],
            }
        )
    done = [t for t in tests if "skipped" not in t]
    n_tests = sum(len(t["intents_leads"]) + len(t["usage_leads"]) for t in done)
    # The 95% band for one correlation under no link. Some bars cross it by chance: count them honestly.
    band = 1.96 / min(t["weeks"] for t in done) ** 0.5 if done else None
    lead_bars = [(t["series"], k, r) for t in done for k, r in zip(t["xcorr_lags"], t["xcorr"]) if k > 0]
    same_week = [(t["series"], r) for t in done for k, r in zip(t["xcorr_lags"], t["xcorr"]) if k == 0]
    return {
        "band": band,
        "lead_bars": len(lead_bars),
        "lead_bars_outside": [{"series": s_, "lead": k, "corr": r} for s_, k, r in lead_bars if band and abs(r) > band],
        "same_week_outside": [{"series": s_, "corr": r} for s_, r in same_week if band and abs(r) > band],
        "alpha": alpha,
        "headline_lags": main,
        "max_lag": K,
        "tests": tests,
        "tests_run": n_tests,
        "series_where_intents_leads": [t["series"] for t in done if t["intents_leads_significant"]],
        "series_where_usage_leads": [t["series"] for t in done if t["usage_leads_significant"]],
        "min_headline_p": min(t["headline_p"] for t in done) if done else None,
    }
