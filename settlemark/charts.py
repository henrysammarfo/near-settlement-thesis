"""Draw the six thesis charts in the Settlemark style.

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


def draw_all(fr: Frames, R: dict, charts_dir: Path, site_charts_dir: Path) -> list[Path]:
    charts_dir.mkdir(parents=True, exist_ok=True)
    site_charts_dir.mkdir(parents=True, exist_ok=True)
    # The PNG is also published on the site so links to the first version of the page keep working.
    light = {c: [charts_dir / f"{c}.png", site_charts_dir / f"{c}.png", site_charts_dir / f"{c}-light.svg"] for c in CHARTS}
    dark = {c: [site_charts_dir / f"{c}-dark.svg"] for c in CHARTS}
    draw(fr, R, LIGHT, light)
    draw(fr, R, DARK, dark)
    plt.rcdefaults()
    return [p for v in (*light.values(), *dark.values()) for p in v]
