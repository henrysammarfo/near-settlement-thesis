"""Compute every number in the thesis from validated CSVs.

`analyse()` returns plain data: a results dict (written to results/results.json) and the
weekly frames the charts need. Each result key records which dataset it came from in
`results["provenance"]`, so any number can be traced back to its CSV and source URL.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import Config
from .sources import BY_NAME, read_csv
from .stats import bootstrap_corr_ci, lagged_corr, log_changes, pearson, weekly


@dataclass
class Frames:
    weekly: pd.DataFrame
    changes: pd.DataFrame
    stablecoins: pd.Series
    value_capture: dict[str, float]


def load(cfg: Config, name: str) -> tuple[pd.DataFrame, str, str]:
    """Validated dataset as a date indexed frame, plus its source URL and fetch time."""
    rows = read_csv(BY_NAME[name], cfg.paths.data)
    df = pd.DataFrame(rows)
    df["date"] = pd.to_datetime(df["date"])
    df = df.set_index("date")
    url, fetched = df["source_url"].iloc[0], df["fetched_at_utc"].iloc[0]
    num = df.drop(columns=["source_url", "fetched_at_utc"]).astype(float)
    return num, url, fetched


def analyse(cfg: Config) -> tuple[dict, Frames]:
    a, f = cfg.analysis, cfg.falsifiers
    iv_df, u_iv, fetched = load(cfg, "intents_volume")
    dex_df, u_dex, _ = load(cfg, "all_dex_volume")
    fee_df, u_fee, _ = load(cfg, "intents_fees")
    rev_df, u_rev, _ = load(cfg, "intents_revenue")
    ch, u_ch, _ = load(cfg, "near_chain")
    st_df, u_st, _ = load(cfg, "near_stablecoins")
    _np_df, u_np, _ = load(cfg, "near_price")
    btc_df, u_btc, _ = load(cfg, "btc_price")

    iv, dex, fees, rev = iv_df["usd"], dex_df["usd"], fee_df["usd"], rev_df["usd"]
    price = ch["near_price_usd"][ch["near_price_usd"] > 0]
    daily = pd.DataFrame({"iv": iv, "dex": dex, "p": price, "aa": ch["active_accounts"], "tx": ch["txns"]}).dropna()
    daily = daily[daily.iv > 0]
    w = weekly(daily, {"iv": "sum", "dex": "sum", "p": "last", "aa": "mean", "tx": "sum"}, a.week_rule)
    w["share"] = w.iv / w.dex
    chg = log_changes(w[["iv", "p", "aa", "tx", "share", "dex"]])

    btc_w = btc_df["usd"].resample(a.week_rule).last()
    both = pd.concat([chg["iv"], np.log(btc_w).diff().rename("btc")], axis=1).dropna()

    last = daily.index.max()
    yr = last - pd.Timedelta(days=a.year_days)
    rev365 = float(rev.loc[yr:last].sum())
    fee365 = float(fees.loc[yr:last].sum())
    chain365 = float(ch["txn_fee_usd"].loc[yr:last].sum())
    iv365 = float(iv.loc[yr:last].sum())
    mcap = float(ch["market_cap_usd"].loc[:last].iloc[-1])
    st = st_df["usd"]
    q, m = a.compare_weeks, a.endpoint_weeks
    if len(w) < 2 * q + 1:
        raise ValueError(f"only {len(w)} weeks of data; need at least {2 * q + 1}")

    share_first = float(w.share.iloc[:q].mean())
    share_prev = float(w.share.iloc[-2 * q : -q].mean())
    share_last = float(w.share.iloc[-q:].mean())
    lag_p_iv = lagged_corr(chg["p"], chg["iv"], a.lag_weeks)
    lag_iv_p = lagged_corr(chg["iv"], chg["p"], a.lag_weeks)

    R: dict = {
        "fetched_at_utc": fetched,
        "window_start": str(daily.index.min().date()),
        "window_end": str(last.date()),
        "weeks": len(w),
        "corr_weekly_change_intents_vs_near_price": pearson(chg.iv, chg.p),
        "corr_ci90": list(bootstrap_corr_ci(chg.iv, chg.p, a.bootstrap_resamples, a.bootstrap_seed, a.ci_level)),
        "corr_weekly_change_share_vs_near_price": pearson(chg.share, chg.p),
        "corr_weekly_change_intents_vs_btc": pearson(both.iv, both.btc),
        "weeks_btc": len(both),
        "corr_weekly_change_intents_vs_all_dex": pearson(chg.iv, chg.dex),
        "corr_weekly_change_active_accounts_vs_near_price": pearson(chg.aa, chg.p),
        "corr_levels_log_intents_vs_log_price": pearson(np.log(w.iv), np.log(w.p)),
        "lag_price_leads_intents": lag_p_iv,
        "lag_intents_leads_price": lag_iv_p,
        "share_first_13w_pct": share_first * 100,
        "share_prev_13w_pct": share_prev * 100,
        "share_last_13w_pct": share_last * 100,
        "near_price_first_4w": float(w.p.iloc[:m].mean()),
        "near_price_last_4w": float(w.p.iloc[-m:].mean()),
        "intents_weekly_volume_first_4w": float(w.iv.iloc[:m].mean()),
        "intents_weekly_volume_last_4w": float(w.iv.iloc[-m:].mean()),
        "intents_volume_365d": iv365,
        "intents_fees_365d": fee365,
        "intents_revenue_365d": rev365,
        "near_chain_fees_365d": chain365,
        "near_market_cap": mcap,
        "mcap_to_intents_revenue": mcap / rev365,
        "mcap_to_chain_fees": mcap / chain365,
        "revenue_take_rate_bps": rev365 / iv365 * 1e4,
        "fee_take_rate_bps": fee365 / iv365 * 1e4,
        "near_active_accounts_first_13w": float(w.aa.iloc[:q].mean()),
        "near_active_accounts_last_13w": float(w.aa.iloc[-q:].mean()),
        "near_stablecoins_now": float(st.iloc[-1]),
        "near_stablecoins_1y_ago": float(st.loc[:yr].iloc[-1]),
    }
    R["falsifiers"] = [
        {
            "id": "F1",
            "name": "Intents usage moves with NEAR price",
            "test": f"weekly change correlation above {f.price_corr_max}",
            "value": R["corr_weekly_change_intents_vs_near_price"],
            "met": R["corr_weekly_change_intents_vs_near_price"] > f.price_corr_max,
        },
        {
            "id": "F2",
            "name": "Intents is losing ground",
            "test": f"share of all DEX volume, last {q} weeks below the {q} weeks before",
            "value": (share_last - share_prev) * 100,
            "met": share_last < share_prev,
        },
        {
            "id": "F3",
            "name": "NEAR price leads Intents usage",
            "test": f"lagged correlation above {f.lag_corr_max}",
            "value": lag_p_iv,
            "met": lag_p_iv > f.lag_corr_max,
        },
        {
            "id": "F4",
            "name": "Intents is just crypto beta",
            "test": f"weekly change correlation with Bitcoin above {f.btc_corr_max}",
            "value": R["corr_weekly_change_intents_vs_btc"],
            "met": R["corr_weekly_change_intents_vs_btc"] > f.btc_corr_max,
        },
        {
            "id": "F5",
            "name": "Holders capture the flow",
            "test": f"market cap below {f.mcap_to_revenue_min:g}x yearly Intents revenue (if met, the small capture half is wrong)",
            "value": R["mcap_to_intents_revenue"],
            "met": R["mcap_to_intents_revenue"] < f.mcap_to_revenue_min,
        },
    ]
    for x in R["falsifiers"]:
        x["met"] = bool(x["met"])
        x["value"] = float(x["value"])
    R["sources"] = {
        "intents_volume": u_iv,
        "all_dex_volume": u_dex,
        "intents_fees": u_fee,
        "intents_revenue": u_rev,
        "near_chain": u_ch,
        "near_stablecoins": u_st,
        "near_price_coingecko": u_np,
        "btc_price": u_btc,
    }
    iv_keys = [
        "corr_weekly_change_intents_vs_near_price",
        "intents_weekly_volume_first_4w",
        "intents_weekly_volume_last_4w",
        "intents_volume_365d",
    ]
    R["provenance"] = {
        **{k: ["intents_volume", "near_chain"] for k in iv_keys},
        "corr_weekly_change_intents_vs_btc": ["intents_volume", "btc_price"],
        "share_first_13w_pct": ["intents_volume", "all_dex_volume"],
        "share_prev_13w_pct": ["intents_volume", "all_dex_volume"],
        "share_last_13w_pct": ["intents_volume", "all_dex_volume"],
        "intents_fees_365d": ["intents_fees"],
        "intents_revenue_365d": ["intents_revenue"],
        "near_chain_fees_365d": ["near_chain"],
        "near_market_cap": ["near_chain"],
        "mcap_to_intents_revenue": ["near_chain", "intents_revenue"],
        "near_active_accounts_first_13w": ["near_chain"],
        "near_active_accounts_last_13w": ["near_chain"],
        "near_stablecoins_now": ["near_stablecoins"],
        "near_stablecoins_1y_ago": ["near_stablecoins"],
    }
    frames = Frames(
        weekly=w,
        changes=chg,
        stablecoins=st.loc["2024-01-01":],
        value_capture={"Intents revenue": rev365, "NEAR chain gas fees": chain365, "Intents fees (all)": fee365},
    )
    return R, frames
