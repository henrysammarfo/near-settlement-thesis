"""Draw the nine thesis charts in the Settlemark style.

Each chart is written three ways: charts/NN_name.png (light, for GitHub and THESIS.md) and
site/charts/NN_name-light.svg plus -dark.svg (crisp vector art for the live page, swapped by
the reader's colour scheme). Output is deterministic: no timestamps or random ids are embedded.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.dates as mdates
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

from .analysis import Frames
from .stats import days


@dataclass(frozen=True)
class Theme:
    name: str
    bg: str
    ink: str
    muted: str
    grid: str
    accent: str
    price: str
    good: str
    bad: str
    neutral: str


LIGHT = Theme("light", "#FFFFFF", "#0B1020", "#6B7280", "#ECEEF2", "#3D5AFE", "#E8A33D", "#12A378", "#E5484D", "#9AA3B2")
DARK = Theme("dark", "#0F1424", "#EEF1F8", "#8A93A6", "#1E2539", "#7C92FF", "#F2B65A", "#3DD6A3", "#FF6B6F", "#5C667D")

CHARTS = (
    "01_volume_vs_price",
    "02_share_of_dex_volume",
    "03_weekly_changes_scatter",
    "04_value_capture",
    "05_active_accounts",
    "06_stablecoins",
    "07_supply_vs_buybacks",
    "08_rolling_correlation",
    "09_value_per_token",
    "10_lead_lag",
    "11_router_take_rates",
)


def _style(t: Theme) -> None:
    plt.rcParams.update(
        {
            "figure.dpi": 144,
            "savefig.dpi": 144,
            "font.family": "DejaVu Sans",
            "font.size": 10,
            "figure.facecolor": t.bg,
            "axes.facecolor": t.bg,
            "savefig.facecolor": t.bg,
            "axes.edgecolor": t.grid,
            "axes.labelcolor": t.muted,
            "xtick.color": t.muted,
            "ytick.color": t.muted,
            "text.color": t.ink,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.spines.left": False,
            "axes.grid": True,
            "axes.grid.axis": "y",
            "grid.color": t.grid,
            "grid.linewidth": 0.8,
            "xtick.major.size": 0,
            "ytick.major.size": 0,
            "axes.titlelocation": "left",
            "axes.titleweight": "bold",
            "axes.titlesize": 12.5,
            "axes.titlepad": 14,
            "legend.frameon": False,
            "svg.hashsalt": "settlemark",
            "svg.fonttype": "none",
            "axes.axisbelow": True,
        }
    )


def _money(x: float, _pos: int | None = None) -> str:
    return f"${x / 1e9:.1f}B" if abs(x) >= 1e9 else f"${x / 1e6:.0f}M" if abs(x) >= 1e6 else f"${x:,.0f}"


def _dates(ax) -> None:
    loc = mdates.AutoDateLocator(minticks=4, maxticks=8)
    ax.xaxis.set_major_locator(loc)
    ax.xaxis.set_major_formatter(mdates.ConciseDateFormatter(loc, show_offset=False))


def _finish(fig, t: Theme, source: str, fetched: str, out: list[Path]) -> None:
    fig.text(0.012, 0.015, f"Source: {source}. Fetched {fetched[:10]}. Settlemark", fontsize=7.5, color=t.muted)
    fig.tight_layout(rect=(0, 0.04, 1, 1))
    for p in out:
        meta = {"Date": None} if p.suffix == ".svg" else {"Software": None}
        fig.savefig(p, metadata=meta)
    plt.close(fig)


def draw(fr: Frames, R: dict, t: Theme, outputs: dict[str, list[Path]]) -> None:
    _style(t)
    w, chg, fetched = fr.weekly, fr.changes, R["fetched_at_utc"]

    fig, ax = plt.subplots(figsize=(9, 4.6))
    ax.bar(w.index, w.iv, width=5.2, color=t.accent, alpha=0.9, label="Intents weekly volume")
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    ax2 = ax.twinx()
    ax2.plot(w.index, w.p, color=t.price, lw=2.2, label="NEAR price (right)")
    ax2.grid(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.0f}"))
    _dates(ax)
    ax.set_title("Intents volume rose while the NEAR price fell", pad=30)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3, handlelength=1.2)
    _finish(fig, t, "DefiLlama near-intents, NearBlocks charts", fetched, outputs["01_volume_vs_price"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    ax.fill_between(w.index, w.share * 100, color=t.good, alpha=0.14, lw=0)
    ax.plot(w.index, w.share * 100, color=t.good, lw=2.2)
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.1f}%"))
    _dates(ax)
    ax.set_title("Intents share of all DEX volume, weekly")
    _finish(fig, t, "DefiLlama near-intents and DEX overview", fetched, outputs["02_share_of_dex_volume"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    ax.grid(True, axis="both")
    ax.axhline(0, color=t.neutral, lw=0.8)
    ax.axvline(0, color=t.neutral, lw=0.8)
    ax.scatter(chg.p * 100, chg.iv * 100, s=22, color=t.accent, alpha=0.75, edgecolors="none")
    ax.set_xlabel("NEAR price, weekly change %")
    ax.set_ylabel("Intents volume, weekly change %")
    ax.set_title(f"Weekly changes, r = {R['corr_weekly_change_intents_vs_near_price']:+.2f}")
    _finish(fig, t, "DefiLlama, NearBlocks", fetched, outputs["03_weekly_changes_scatter"])

    fig, ax = plt.subplots(figsize=(9, 3.9))
    labels = list(fr.value_capture)
    vals = list(fr.value_capture.values())
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.barh(labels, vals, color=[t.bad, t.neutral, t.accent], height=0.56)
    for i, v in enumerate(vals):
        ax.text(v, i, f"  ${v / 1e6:.2f}M", va="center", color=t.ink, fontsize=10, fontweight="bold")
    ax.xaxis.set_major_formatter(FuncFormatter(_money))
    ax.invert_yaxis()
    ax.set_xlim(0, max(vals) * 1.22)
    ax.set_title(f"Last 365 days. NEAR market cap is {R['mcap_to_intents_revenue']:.0f}x yearly Intents revenue")
    _finish(fig, t, "DefiLlama fees and revenue, NearBlocks", fetched, outputs["04_value_capture"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    ax.plot(w.index, w.aa, color=t.bad, lw=2.2, label="Active accounts per day")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x / 1e6:.1f}M" if x >= 1e6 else f"{x / 1e3:.0f}K"))
    ax2 = ax.twinx()
    ax2.plot(w.index, w.p, color=t.price, lw=1.6, alpha=0.9, label="NEAR price (right)")
    ax2.grid(False)
    ax2.spines["right"].set_visible(False)
    ax2.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.0f}"))
    _dates(ax)
    h1, l1 = ax.get_legend_handles_labels()
    h2, l2 = ax2.get_legend_handles_labels()
    ax.legend(h1 + h2, l1 + l2, loc="lower left", bbox_to_anchor=(0, 1.0), ncol=2, borderaxespad=0.3, handlelength=1.2)
    ax.set_title("The base chain got quieter", pad=30)
    _finish(fig, t, "NearBlocks charts", fetched, outputs["05_active_accounts"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    s = fr.stablecoins
    ax.fill_between(s.index, s, color=t.bad, alpha=0.12, lw=0)
    ax.plot(s.index, s, color=t.bad, lw=2.2)
    ax.yaxis.set_major_formatter(FuncFormatter(_money))
    _dates(ax)
    ax.set_title("Stablecoins on NEAR")
    _finish(fig, t, "DefiLlama stablecoins", fetched, outputs["06_stablecoins"])


def draw_deep(S: dict, R: dict, t: Theme, outputs: dict[str, list[Path]]) -> None:
    """Charts 7 to 9: raw chain supply and buybacks, rolling correlation, valuation scenarios."""
    _style(t)
    fetched, C, V, Rb = R["fetched_at_utc"], R["chain"], R["valuation"], R["robustness"]
    ch = S["chain"]
    start = S["buyback_start"] - days(7)
    seg = ch.loc[start:]
    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    added = (seg.total_supply_near - seg.total_supply_near.iloc[0]) / 1e6
    bought = (seg.buyback_wallet_near - seg.buyback_wallet_near.iloc[0]) / 1e6
    ax.fill_between(seg.index, added, color=t.bad, alpha=0.12, lw=0)
    ax.plot(seg.index, added, color=t.bad, lw=2.2, label="NEAR added to total supply")
    ax.fill_between(seg.index, bought, color=t.good, alpha=0.18, lw=0)
    ax.plot(seg.index, bought, color=t.good, lw=2.2, label="NEAR gained by the buyback wallet")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x:.0f}M"))
    _dates(ax)
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, borderaxespad=0.3, handlelength=1.2, fontsize=8.5)
    ax.set_title(f"Buybacks cover {C['buyback_coverage_13w_pct']:.1f}% of new supply (13 weeks)", pad=44, fontsize=11.5)
    _finish(fig, t, "NEAR archival RPC, one block per week", fetched, outputs["07_supply_vs_buybacks"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    roll = S["rolling"]
    ax.axhline(0.5, color=t.bad, lw=1.2, ls=(0, (4, 3)))
    ax.text(roll.index[0], 0.53, "0.5: part 1 fails above this line", color=t.bad, fontsize=8)
    ax.axhline(0, color=t.neutral, lw=0.8)
    ax.plot(roll.index, roll, color=t.accent, lw=2.2)
    ax.set_ylim(-1, 1)
    _dates(ax)
    ax.set_title(f"{Rb['rolling_weeks']} week rolling correlation, Intents vs price")
    _finish(fig, t, "DefiLlama, NearBlocks", fetched, outputs["08_rolling_correlation"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    names = ["Bear", "Base", "Bull"]
    vals = [V["value_per_token_bear"], V["value_per_token_base"], V["value_per_token_bull"]]
    ax.bar(names, vals, color=[t.bad, t.neutral, t.good], width=0.56)
    ax.axhline(C["near_price_now"], color=t.price, lw=2)
    ax.text(2.42, C["near_price_now"], f" price ${C['near_price_now']:.2f}", color=t.price, va="bottom", ha="right", fontsize=9)
    for i, v in enumerate(vals):
        ax.text(i, v, f"${v:.2f}", ha="center", va="bottom", color=t.ink, fontsize=10, fontweight="bold")
    ax.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"${x:.0f}"))
    ax.grid(False, axis="x")
    ax.set_title(f"Value per NEAR from buybacks, {V['discount_rate_pct']:.0f}% discount")
    _finish(fig, t, "Settlemark DCF on RPC buybacks", fetched, outputs["09_value_per_token"])


def draw_extra(R: dict, t: Theme, outputs: dict[str, list[Path]]) -> None:
    """Charts 10 and 11: does Intents lead usage, and Intents against other cross chain routers."""
    _style(t)
    fetched, L, P = R["fetched_at_utc"], R["leadlag"], R["peers"]

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    done = [x for x in L["tests"] if "xcorr" in x]
    colors = [t.accent, t.price, t.good, t.neutral, t.bad]
    width = 0.8 / max(len(done), 1)
    for i, x in enumerate(done):
        xs = [k + (i - (len(done) - 1) / 2) * width for k in x["xcorr_lags"]]
        ax.bar(xs, x["xcorr"], width=width * 0.92, color=colors[i % len(colors)], label=x["label"])
    n = min(x["weeks"] for x in done)
    band = 1.96 / n**0.5
    ax.axhspan(-band, band, color=t.neutral, alpha=0.15, lw=0)
    ax.axhline(0, color=t.neutral, lw=0.8)
    ax.axvline(0, color=t.muted, lw=0.8, ls=(0, (2, 2)))
    ax.set_ylim(-0.6, 0.6)
    ax.set_xticks(done[0]["xcorr_lags"])
    ax.set_xlabel("weeks Intents volume leads usage (negative: usage leads)")
    ax.grid(False, axis="x")
    ax.legend(loc="lower left", bbox_to_anchor=(0, 1.0), ncol=1, borderaxespad=0.3, handlelength=1.2, fontsize=8)
    ax.set_title("No lead stands out from noise (grey band)", pad=10 + 13 * len(done), fontsize=11.5)
    _finish(fig, t, "DefiLlama, NearBlocks, NEAR archival RPC", fetched, outputs["10_lead_lag"])

    fig, ax = plt.subplots(figsize=(5.4, 4.1))
    rows = sorted(P["rows"], key=lambda r: r["fee_bps"])
    names = [r["name"] for r in rows]
    y = range(len(rows))
    ax.barh([i + 0.2 for i in y], [r["fee_bps"] for r in rows], height=0.38, color=t.neutral, label="All fees")
    ax.barh([i - 0.2 for i in y], [r["revenue_bps"] for r in rows], height=0.38, color=t.accent, label="Kept as revenue")
    for i, r in enumerate(rows):
        c = t.accent if r["slug"] == "near_intents" else t.ink
        ax.text(r["fee_bps"] + 0.6, i + 0.2, f"{r['fee_bps']:.1f}", va="center", fontsize=8.5, color=t.muted)
        ax.text(r["revenue_bps"] + 0.6, i - 0.2, f"{r['revenue_bps']:.1f}", va="center", fontsize=8.5, color=c, fontweight="bold")
    ax.set_yticks(list(y), names)
    for lbl, r in zip(ax.get_yticklabels(), rows):
        if r["slug"] == "near_intents":
            lbl.set_color(t.accent)
            lbl.set_fontweight("bold")
    ax.grid(True, axis="x")
    ax.grid(False, axis="y")
    ax.set_xlabel("basis points of volume")
    ax.legend(loc="lower right", fontsize=8.5)
    ax.set_title(f"Take rates, {P['window_days']} days to {P['window_end']}")
    _finish(fig, t, "DefiLlama fees and volume APIs", P.get("fetched_at_utc", fetched), outputs["11_router_take_rates"])


def draw_all(fr: Frames, R: dict, charts_dir: Path, site_charts_dir: Path, deep_series: dict | None = None) -> list[Path]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    site_charts_dir.mkdir(parents=True, exist_ok=True)
    # The PNG is also published on the site so links to the first version of the page keep working.
    light = {c: [charts_dir / f"{c}.png", site_charts_dir / f"{c}.png", site_charts_dir / f"{c}-light.svg"] for c in CHARTS}
    dark = {c: [site_charts_dir / f"{c}-dark.svg"] for c in CHARTS}
    draw(fr, R, LIGHT, light)
    draw(fr, R, DARK, dark)
    if deep_series is not None:
        draw_deep(deep_series, R, LIGHT, light)
        draw_deep(deep_series, R, DARK, dark)
    if R.get("leadlag") and R.get("peers"):
        draw_extra(R, LIGHT, light)
        draw_extra(R, DARK, dark)
    plt.rcdefaults()
    return [p for v in (*light.values(), *dark.values()) for p in v]
