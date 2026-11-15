"""Deeper evidence on top of analysis.py: raw chain reads, the valuation model and robustness checks.

Everything here reads validated CSVs only (data/near_rpc.csv comes from archival RPC, see
chain.py) and returns plain numbers that go into results.json under "chain", "valuation"
and "robustness".
"""

from __future__ import annotations

import csv

import numpy as np
import pandas as pd

from . import chain
from .analysis import Frames, load
from .config import Config
from .stats import StatsError, bootstrap_corr_ci, pearson
from .valuation import breakeven_weekly_volume, dcf, growth_path, implied_growth


def load_chain(cfg: Config) -> pd.DataFrame:
    rows = chain.read(cfg.paths.data / "near_rpc.csv")
    df = pd.DataFrame(rows)
    df["week_start"] = pd.to_datetime(df["week_start"])
    df = df.set_index("week_start")
    for c in ("block_height", "intents_storage_bytes"):
        df[c] = df[c].astype("int64")
    for c in ("total_supply_near", "buyback_wallet_near"):
        df[c] = df[c].astype(float)
    return df


def _bigquery_vs_nearblocks(cfg: Config, nearblocks_tx: pd.Series) -> dict:
    p = cfg.paths.bigquery_csv
    if not p.exists():
        return {}
    with p.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if not r["note"]]
    pairs = []
    for r in rows:
        d = pd.Timestamp(r["day"])
        if d in nearblocks_tx.index and nearblocks_tx[d] > 0:
            pairs.append(int(r["receipt_actions"]) / float(nearblocks_tx[d]))
    if not pairs:
        return {}
    return {"bq_days": len(pairs), "bq_receipts_per_nearblocks_tx_min": min(pairs), "bq_receipts_per_nearblocks_tx_max": max(pairs)}


def deep(cfg: Config, R: dict, frames: Frames) -> tuple[dict, dict]:
    v = cfg.valuation
    w, chg = frames.weekly, frames.changes
    ch = load_chain(cfg)
    rev_df, _, _ = load(cfg, "intents_revenue")
    nb, _, _ = load(cfg, "near_chain")
    rev = rev_df["usd"]
    vol_df, _, _ = load(cfg, "intents_volume")
    last_day = pd.Timestamp(R["window_end"])

    # Align raw chain weeks to analysis weeks: the block at Monday 00:00 closes the week ending Sunday.
    ch = ch[ch.index <= last_day + pd.Timedelta(days=1)]
    if len(ch) < 60:
        raise StatsError(f"need at least 60 weekly chain samples, got {len(ch)}")
    end_idx = ch.index - pd.Timedelta(days=1)
    chw = ch.set_axis(end_idx)
    supply = chw["total_supply_near"]
    bb = chw["buyback_wallet_near"]
    store = chw["intents_storage_bytes"]
    now = chw.index[-1]
    y1 = now - pd.Timedelta(weeks=52)
    q1 = now - pd.Timedelta(weeks=13)
    iss_52 = float(supply[now] - supply[y1])
    iss_13 = float(supply[now] - supply[q1])
    bb_13 = float(bb[now] - bb[q1])
    bb_52 = float(bb[now] - bb[y1])
    first_bb = bb[bb > 0].index.min()

    # USD value of NEAR that reached the buyback wallet, week by week, at that week's closing price.
    price_w = w["p"]
    d_bb = bb.diff().loc[q1 + pd.Timedelta(days=1) : now]
    px = price_w.reindex(d_bb.index)
    if px.isna().any():
        raise StatsError("missing weekly price for a buyback week")
    bb_usd_13 = float((d_bb * px).sum())
    rev_13 = float(rev.loc[q1 + pd.Timedelta(days=1) : now].sum())
    buyback_share = bb_usd_13 / rev_13 if rev_13 > 0 else float("nan")

    # Raw chain usage: intents.near state size. Its weekly growth against price and volume.
    st = store[store > 0]
    st_chg = np.log(st).diff().dropna()
    j = pd.concat([st_chg.rename("st"), chg["p"], chg["iv"]], axis=1).dropna()
    price_now = float(nb["near_price_usd"].loc[:last_day].iloc[-1])
    supply_now = float(supply[now])
    fdv = price_now * supply_now
    mcap_nb = float(nb["market_cap_usd"].loc[:last_day].iloc[-1])

    C = {
        "first_block_height": int(ch["block_height"].iloc[0]),
        "last_block_height": int(ch["block_height"].iloc[-1]),
        "samples": len(ch),
        "last_sample_week_start": str(ch.index[-1].date()),
        "supply_now_near": supply_now,
        "supply_52w_ago_near": float(supply[y1]),
        "issuance_52w_near": iss_52,
        "issuance_52w_pct": iss_52 / float(supply[y1]) * 100,
        "issuance_13w_near": iss_13,
        "buyback_wallet_first_week": str(first_bb.date()) if pd.notna(first_bb) else "",
        "buyback_wallet_now_near": float(bb[now]),
        "buyback_13w_near": bb_13,
        "buyback_52w_near": bb_52,
        "buyback_wallet_weeks_down": int((bb.diff() < 0).sum()),
        "buyback_coverage_13w_pct": bb_13 / iss_13 * 100,
        "buyback_coverage_52w_pct": bb_52 / iss_52 * 100,
        "buyback_13w_usd": bb_usd_13,
        "intents_revenue_13w_usd": rev_13,
        "buyback_share_of_revenue_13w_pct": buyback_share * 100,
        "intents_storage_now_gb": float(store[now]) / 1e9,
        "intents_storage_52w_ago_gb": float(store[y1]) / 1e9,
        "intents_storage_growth_52w_x": float(store[now]) / float(store[y1]),
        "corr_weekly_change_storage_vs_near_price": pearson(j.st, j.p),
        "corr_weekly_change_storage_vs_intents_volume": pearson(j.st, j.iv),
        "storage_weeks": len(j),
        "near_price_now": price_now,
        "fdv_usd": fdv,
        "nearblocks_mcap_to_fdv_pct": mcap_nb / fdv * 100,
        **_bigquery_vs_nearblocks(cfg, nb["txns"]),
    }

    # Valuation on holder cash flow = buybacks actually observed on chain, annualised.
    cash0 = bb_usd_13 * 52 / 13
    r6 = rev.loc[last_day - pd.Timedelta(days=181) : last_day].sum()
    r6_prev = rev.loc[last_day - pd.Timedelta(days=363) : last_day - pd.Timedelta(days=182)].sum()
    g_obs = float((r6 / r6_prev) ** 2 - 1) if r6_prev > 0 else float("nan")
    g_bull = float(min(max(g_obs, 0.0), v.bull_growth_cap))
    scen = {"bear": 0.0, "base": g_bull / 2, "bull": g_bull}
    per = {k: dcf(cash0, g, v.discount_rate, v.terminal_growth, v.explicit_years, v.fade_years) / supply_now for k, g in scen.items()}
    grid = [
        {
            "r": r,
            **{k: dcf(cash0, g, r, v.terminal_growth, v.explicit_years, v.fade_years) / supply_now for k, g in scen.items()},
        }
        for r in (v.discount_low, v.discount_rate, v.discount_high)
    ]
    # The tester starts from the last 13 weeks, so its default output equals holder_cash_flow_usd.
    vol_13 = float(vol_df["usd"].loc[q1 + pd.Timedelta(days=1) : now].sum())
    take = rev_13 / vol_13
    iss_usd = iss_52 * price_now
    V = {
        "holder_cash_flow_usd": cash0,
        "weekly_volume_13w_usd": vol_13 / 13,
        "revenue_take_rate_13w_bps": take * 1e4,
        "buyback_share_13w_pct": buyback_share * 100,
        "supply_near": supply_now,
        "issuance_52w_near": iss_52,
        "near_price": price_now,
        "market_cap_usd": R["near_market_cap"],
        "f5_line": float(cfg.falsifiers.mcap_to_revenue_min),
        "explicit_years": v.explicit_years,
        "fade_years": v.fade_years,
        "revenue_run_rate_usd": float(rev.loc[last_day - pd.Timedelta(days=90) : last_day].sum()) * 365 / 91,
        "revenue_growth_obs_annual_pct": g_obs * 100,
        "growth_bear_pct": scen["bear"] * 100,
        "growth_base_pct": scen["base"] * 100,
        "growth_bull_pct": scen["bull"] * 100,
        "discount_rate_pct": v.discount_rate * 100,
        "terminal_growth_pct": v.terminal_growth * 100,
        "value_per_token_bear": per["bear"],
        "value_per_token_base": per["base"],
        "value_per_token_bull": per["bull"],
        "value_base_pct_of_price": per["base"] / price_now * 100,
        "value_bull_pct_of_price": per["bull"] / price_now * 100,
        "implied_growth_pct": implied_growth(fdv, cash0, v.discount_rate, v.terminal_growth, v.explicit_years, v.fade_years) * 100,
        "fdv_to_holder_cash_flow": fdv / cash0,
        "issuance_usd_per_year": iss_usd,
        "breakeven_weekly_volume_usd": breakeven_weekly_volume(iss_usd, take, buyback_share),
        "breakeven_to_current_volume_x": breakeven_weekly_volume(iss_usd, take, buyback_share) / (vol_13 / 13),
        "sensitivity": grid,
        "growth_path_base_pct": [g * 100 for g in growth_path(scen["base"], v.terminal_growth, v.explicit_years, v.fade_years)],
    }

    # Robustness of the part 1 result.
    half = len(chg) // 2
    roll, roll_dates = [], []
    k = cfg.robustness.rolling_weeks
    for i in range(k, len(chg) + 1):
        seg = chg.iloc[i - k : i]
        roll.append(pearson(seg.iv, seg.p))
        roll_dates.append(chg.index[i - 1])
    late = chg.iloc[cfg.analysis.compare_weeks :]
    last_q = chg.iloc[-cfg.analysis.compare_weeks :]
    q = cfg.analysis.compare_weeks
    rank = chg[["iv", "p"]].rank()
    Rb = {
        "corr_first_half": pearson(chg.iv.iloc[:half], chg.p.iloc[:half]),
        "corr_second_half": pearson(chg.iv.iloc[half:], chg.p.iloc[half:]),
        "corr_excluding_first_13w": pearson(late.iv, late.p),
        "corr_ci90_excluding_first_13w": list(
            bootstrap_corr_ci(late.iv, late.p, cfg.analysis.bootstrap_resamples, cfg.analysis.bootstrap_seed, cfg.analysis.ci_level)
        ),
        "corr_last_13w": pearson(last_q.iv, last_q.p),
        "spearman": pearson(rank.iv, rank.p),
        "rolling_weeks": k,
        "rolling_corr_max": max(roll),
        "rolling_corr_min": min(roll),
        "rolling_windows": len(roll),
        "rolling_windows_above_0_5": sum(x > 0.5 for x in roll),
        "price_change_last_13w_pct": float((w.p.iloc[-1] / w.p.iloc[-q - 1] - 1) * 100),
        "volume_change_last_13w_pct": float((w.iv.iloc[-4:].mean() / w.iv.iloc[-q - 4 : -q].mean() - 1) * 100),
    }
    series = {
        "chain": chw,
        "rolling": pd.Series(roll, index=pd.DatetimeIndex(roll_dates)),
        "buyback_start": first_bb,
    }
    return {"chain": C, "valuation": V, "robustness": Rb}, series
