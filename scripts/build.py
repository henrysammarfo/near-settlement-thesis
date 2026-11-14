"""Turn data/*.csv into results/results.json, charts/*.png, THESIS.md numbers and site/index.html.

Every number written anywhere comes from this script, computed from data/.
"""
import json, os, datetime as dt
import numpy as np, pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
D = lambda *p: os.path.join(ROOT, *p)
os.makedirs(D("charts"), exist_ok=True); os.makedirs(D("results"), exist_ok=True)

def load(n):
    df = pd.read_csv(D("data", n + ".csv"), parse_dates=["date"]).set_index("date")
    return df, df["source_url"].iloc[0], df["fetched_at_utc"].iloc[0]

iv_df, U_IV, FETCHED = load("intents_volume")
dex_df, U_DEX, _ = load("all_dex_volume")
fee_df, U_FEE, _ = load("intents_fees")
rev_df, U_REV, _ = load("intents_revenue")
ch, U_CH, _ = load("near_chain")
st_df, U_ST, _ = load("near_stablecoins")
np_df, U_NP, _ = load("near_price")
btc_df, U_BTC, _ = load("btc_price")

iv, dex, fees, rev = iv_df["usd"], dex_df["usd"], fee_df["usd"], rev_df["usd"]
price = ch["near_price_usd"].astype(float); price = price[price > 0]
df = pd.DataFrame({"iv": iv, "dex": dex, "p": price,
                   "aa": ch["active_accounts"].astype(float), "tx": ch["txns"].astype(float)}).dropna()
df = df[df.iv > 0]
START = df.index.min()
# Weekly totals, dropping the first and last partial weeks.
w = df.resample("W-SUN").agg({"iv": "sum", "dex": "sum", "p": "last", "aa": "mean", "tx": "sum"}).iloc[1:-1]
w["share"] = w.iv / w.dex
chg = np.log(w[["iv", "p", "aa", "tx", "share", "dex"]]).diff().dropna()

# Bitcoin weekly returns (CoinGecko gives 365 days on the free tier).
btc = btc_df["usd"].resample("W-SUN").last()
both = pd.concat([chg["iv"], np.log(btc).diff().rename("btc")], axis=1).dropna()

def corr(a, b):
    return float(np.corrcoef(a, b)[0, 1])

def boot_ci(a, b, n=2000, seed=7):
    rng = np.random.default_rng(seed); a = np.asarray(a); b = np.asarray(b); out = []
    for _ in range(n):
        i = rng.integers(0, len(a), len(a)); out.append(np.corrcoef(a[i], b[i])[0, 1])
    return [float(np.percentile(out, 5)), float(np.percentile(out, 95))]

# Lead and lag: does last week's NEAR price change predict this week's Intents volume change, and the reverse?
lag_p_to_iv = corr(chg["p"].iloc[:-1].values, chg["iv"].iloc[1:].values)
lag_iv_to_p = corr(chg["iv"].iloc[:-1].values, chg["p"].iloc[1:].values)

last = df.index.max()
yr = last - pd.Timedelta(days=364)
rev365 = float(rev.loc[yr:last].sum()); fee365 = float(fees.loc[yr:last].sum())
chainfee365 = float(ch["txn_fee_usd"].astype(float).loc[yr:last].sum())
iv365 = float(iv.loc[yr:last].sum())
mcap = float(ch["market_cap_usd"].astype(float).loc[:last].iloc[-1])
share_first = float(w.share.iloc[:13].mean()); share_prev = float(w.share.iloc[-26:-13].mean()); share_last = float(w.share.iloc[-13:].mean())
p_first = float(w.p.iloc[:4].mean()); p_last = float(w.p.iloc[-4:].mean())
iv_first = float(w.iv.iloc[:4].mean()); iv_last = float(w.iv.iloc[-4:].mean())
st = st_df["usd"]; st_now = float(st.iloc[-1]); st_yr = float(st.loc[:yr].iloc[-1])

R = {
    "fetched_at_utc": FETCHED, "window_start": str(START.date()), "window_end": str(last.date()), "weeks": int(len(w)),
    "corr_weekly_change_intents_vs_near_price": corr(chg.iv, chg.p),
    "corr_ci90": boot_ci(chg.iv, chg.p),
    "corr_weekly_change_share_vs_near_price": corr(chg.share, chg.p),
    "corr_weekly_change_intents_vs_btc": corr(both.iv, both.btc), "weeks_btc": int(len(both)),
    "corr_weekly_change_intents_vs_all_dex": corr(chg.iv, chg.dex),
    "corr_weekly_change_active_accounts_vs_near_price": corr(chg.aa, chg.p),
    "corr_levels_log_intents_vs_log_price": corr(np.log(w.iv), np.log(w.p)),
    "lag_price_leads_intents": lag_p_to_iv, "lag_intents_leads_price": lag_iv_to_p,
    "share_first_13w_pct": share_first * 100, "share_prev_13w_pct": share_prev * 100, "share_last_13w_pct": share_last * 100,
    "near_price_first_4w": p_first, "near_price_last_4w": p_last,
    "intents_weekly_volume_first_4w": iv_first, "intents_weekly_volume_last_4w": iv_last,
    "intents_volume_365d": iv365, "intents_fees_365d": fee365, "intents_revenue_365d": rev365,
    "near_chain_fees_365d": chainfee365, "near_market_cap": mcap,
    "mcap_to_intents_revenue": mcap / rev365, "mcap_to_chain_fees": mcap / chainfee365,
    "revenue_take_rate_bps": rev365 / iv365 * 1e4, "fee_take_rate_bps": fee365 / iv365 * 1e4,
    "near_active_accounts_first_13w": float(w.aa.iloc[:13].mean()), "near_active_accounts_last_13w": float(w.aa.iloc[-13:].mean()),
    "near_stablecoins_now": st_now, "near_stablecoins_1y_ago": st_yr,
}
# Falsifiers, fixed in code before reading the verdict. They were written on 2026-11-14, not weeks earlier.
F = [
    ("F1 Intents usage moves with NEAR price", "weekly change correlation above 0.5", R["corr_weekly_change_intents_vs_near_price"] > 0.5),
    ("F2 Intents is losing ground", "share of all DEX volume, last 13 weeks below the 13 weeks before", share_last < share_prev),
    ("F3 NEAR price leads Intents usage", "lagged correlation above 0.3", lag_p_to_iv > 0.3),
    ("F4 Intents is just crypto beta", "weekly change correlation with Bitcoin above 0.5", R["corr_weekly_change_intents_vs_btc"] > 0.5),
    ("F5 Holders capture the flow", "market cap below 50x yearly Intents revenue (if met, the 'small capture' half is wrong)", R["mcap_to_intents_revenue"] < 50),
]
R["falsifiers"] = [{"name": a, "test": b, "met": bool(c)} for a, b, c in F]
R["sources"] = {"intents_volume": U_IV, "all_dex_volume": U_DEX, "intents_fees": U_FEE, "intents_revenue": U_REV,
                "near_chain": U_CH, "near_stablecoins": U_ST, "near_price_coingecko": U_NP, "btc_price": U_BTC}
json.dump(R, open(D("results", "results.json"), "w"), indent=2)

# Charts
plt.rcParams.update({"figure.dpi": 110, "axes.spines.top": False, "font.size": 10})
def save(fig, name, src):
    fig.text(0.01, 0.01, f"Source: {src} (fetched {FETCHED})", fontsize=7, color="#666")
    fig.tight_layout(rect=(0, 0.03, 1, 1)); fig.savefig(D("charts", name)); plt.close(fig)

fig, ax = plt.subplots(figsize=(9, 4.5)); ax.bar(w.index, w.iv / 1e6, width=5, color="#2b6cb0", label="NEAR Intents weekly volume ($M)")
ax.set_ylabel("Intents weekly volume, $M"); ax2 = ax.twinx(); ax2.plot(w.index, w.p, color="#d69e2e", lw=2, label="NEAR price ($)"); ax2.set_ylabel("NEAR price, $")
ax.set_title("1. Intents volume went up while the NEAR price went down"); fig.legend(loc="upper left", bbox_to_anchor=(0.07, 0.9))
save(fig, "01_volume_vs_price.png", "DefiLlama near-intents, NearBlocks charts")

fig, ax = plt.subplots(figsize=(9, 4.5)); ax.plot(w.index, w.share * 100, color="#2f855a", lw=2)
ax.set_ylabel("% of all onchain DEX volume"); ax.set_title("2. NEAR Intents share of all DEX volume tracked by DefiLlama (weekly)")
save(fig, "02_share_of_dex_volume.png", "DefiLlama near-intents and DEX overview")

fig, ax = plt.subplots(figsize=(6, 5)); ax.scatter(chg.p * 100, chg.iv * 100, s=14, color="#2b6cb0")
ax.axhline(0, color="#aaa", lw=.5); ax.axvline(0, color="#aaa", lw=.5)
ax.set_xlabel("NEAR price, weekly change %"); ax.set_ylabel("Intents volume, weekly change %")
ax.set_title(f"3. Weekly changes: correlation {R['corr_weekly_change_intents_vs_near_price']:.2f}")
save(fig, "03_weekly_changes_scatter.png", "DefiLlama, NearBlocks")

fig, ax = plt.subplots(figsize=(8, 4.5)); vals = [rev365, chainfee365, fee365]
labels = ["Intents revenue\n(protocol keeps)", "NEAR chain gas fees", "Intents fees\n(all, incl. solvers)"]
ax.barh(labels, [v / 1e6 for v in vals], color=["#c53030", "#718096", "#2b6cb0"])
for i, v in enumerate(vals): ax.text(v / 1e6, i, f" ${v/1e6:.2f}M", va="center")
ax.set_xlabel("$M over the last 365 days"); ax.set_title(f"4. Value capture: market cap is {R['mcap_to_intents_revenue']:.0f}x yearly Intents revenue")
save(fig, "04_value_capture.png", "DefiLlama fees/revenue, NearBlocks")

fig, ax = plt.subplots(figsize=(9, 4.5)); ax.plot(w.index, w.aa, color="#6b46c1", lw=2, label="NEAR active accounts (daily avg)")
ax.set_ylabel("active accounts per day"); ax2 = ax.twinx(); ax2.plot(w.index, w.p, color="#d69e2e", lw=1.5, label="NEAR price ($)")
ax.set_title("5. Base chain activity (NearBlocks) next to price"); fig.legend(loc="upper right", bbox_to_anchor=(0.9, 0.9))
save(fig, "05_active_accounts.png", "NearBlocks charts")

fig, ax = plt.subplots(figsize=(9, 4.5)); s = st.loc["2024-01-01":]; ax.plot(s.index, s / 1e6, color="#2c7a7b", lw=2)
ax.set_ylabel("$M"); ax.set_title("6. Stablecoins on NEAR (DefiLlama)")
save(fig, "06_stablecoins.png", "DefiLlama stablecoins")
print(json.dumps({k: v for k, v in R.items() if k not in ("sources",)}, indent=1, default=str))
