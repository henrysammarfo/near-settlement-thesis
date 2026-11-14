"""Write THESIS.md and the live page from results.json. No number is typed by hand."""

from __future__ import annotations

import csv
import html
import json
import re
import shutil
from pathlib import Path
from string import Template

from .charts import CHARTS
from .config import Config

CHART_ALT = {
    "01_volume_vs_price": "Bar chart of weekly NEAR Intents volume rising, with the NEAR price line falling",
    "02_share_of_dex_volume": "Line chart of NEAR Intents share of all onchain DEX volume rising",
    "03_weekly_changes_scatter": "Scatter plot of weekly NEAR price changes against weekly Intents volume changes, showing no clear pattern",
    "04_value_capture": "Bar chart comparing yearly Intents revenue, NEAR gas fees and total Intents fees",
    "05_active_accounts": "Line chart of NEAR daily active accounts falling, with the NEAR price",
    "06_stablecoins": "Line chart of stablecoins on NEAR",
}
SVG_SIZE = re.compile(r'<svg[^>]*?width="([\d.]+)pt"[^>]*?height="([\d.]+)pt"', re.S)


def chart_html(name: str, site_charts: Path) -> str:
    """A <picture> that swaps light and dark SVGs, with intrinsic size so the layout never shifts."""
    m = SVG_SIZE.search((site_charts / f"{name}-light.svg").read_text()[:2000])
    w, h = (round(float(m.group(1)) * 2), round(float(m.group(2)) * 2)) if m else (1296, 662)
    return (
        f'<a class="zoom" href="charts/{name}-light.svg" target="_blank" rel="noopener" aria-label="Open chart full size">'
        f'<picture><source srcset="charts/{name}-dark.svg" media="(prefers-color-scheme: dark)">'
        f'<img src="charts/{name}-light.svg" alt="{html.escape(CHART_ALT[name])}" width="{w}" height="{h}" loading="lazy" decoding="async"></picture></a>'
    )


def money_m(x: float) -> str:
    return f"${x / 1e6:,.1f}M"


def money_b(x: float) -> str:
    return f"${x / 1e9:,.2f}B"


def signed(x: float) -> str:
    return f"{x:+.2f}".replace("-", "\u2212")


def signed_md(x: float) -> str:
    return f"{x:+.2f}"


def falsifier_value(fid: str, v: float) -> str:
    if fid == "F2":
        return f"{v:+.2f} pts"
    if fid == "F5":
        return f"{v:,.0f}x"
    return f"{v:+.2f}"


def bigquery_note(path: Path, repo: str) -> str:
    if not path.exists():
        return "No BigQuery results are included in this build."
    with path.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if not r["note"]]
    if not rows:
        return "No complete BigQuery days are included in this build."
    counts = [int(r["receipt_actions"]) for r in rows]
    return (
        "A cross check on the BigQuery public dataset (`queries/01_receipt_actions_daily.sql`, run by hand in the free sandbox) counted "
        f"{min(counts):,} to {max(counts):,} receipt actions a day from {rows[0]['day']} to {rows[-1]['day']} "
        f"([data/bigquery/receipt_actions_daily.csv]({repo}/blob/main/data/bigquery/receipt_actions_daily.csv)). "
        "It is a 7 day snapshot, so it cannot test a trend yet."
    )


def bigquery_note_html(path: Path, repo: str) -> str:
    """The BigQuery note for the page: same facts as bigquery_note, with an HTML link."""
    if not path.exists():
        return "No BigQuery results are included in this build."
    with path.open(newline="") as f:
        rows = [r for r in csv.DictReader(f) if not r["note"]]
    if not rows:
        return "No complete BigQuery days are included in this build."
    counts = [int(r["receipt_actions"]) for r in rows]
    url = html.escape(f"{repo}/blob/main/data/bigquery/receipt_actions_daily.csv")
    return (
        f"A by hand cross check on the NEAR BigQuery public dataset counted {min(counts):,} to {max(counts):,} receipt actions a day "
        f'from {rows[0]["day"]} to {rows[-1]["day"]} (<a class="src" href="{url}" rel="noopener">CSV</a>). It is a 7 day snapshot, not a trend.'
    )


def numbers(R: dict) -> dict[str, str]:
    """Formatted numbers keyed by template placeholder (plain text, no links)."""
    return {
        "corr": signed_md(R["corr_weekly_change_intents_vs_near_price"]),
        "ci": f"{R['corr_ci90'][0]:+.2f} to {R['corr_ci90'][1]:+.2f}",
        "btc": signed_md(R["corr_weekly_change_intents_vs_btc"]),
        "dexc": signed_md(R["corr_weekly_change_intents_vs_all_dex"]),
        "share0": f"{R['share_first_13w_pct']:.3f}%",
        "share1": f"{R['share_prev_13w_pct']:.2f}%",
        "share2": f"{R['share_last_13w_pct']:.2f}%",
        "iv0": money_m(R["intents_weekly_volume_first_4w"]),
        "iv1": money_m(R["intents_weekly_volume_last_4w"]),
        "p0": f"${R['near_price_first_4w']:.2f}",
        "p1": f"${R['near_price_last_4w']:.2f}",
        "lvl": signed_md(R["corr_levels_log_intents_vs_log_price"]),
        "lag1": signed_md(R["lag_price_leads_intents"]),
        "lag2": signed_md(R["lag_intents_leads_price"]),
        "aa": signed_md(R["corr_weekly_change_active_accounts_vs_near_price"]),
        "iv365": money_b(R["intents_volume_365d"]),
        "fee365": money_m(R["intents_fees_365d"]),
        "rev365": money_m(R["intents_revenue_365d"]),
        "chain365": money_m(R["near_chain_fees_365d"]),
        "mcap": money_b(R["near_market_cap"]),
        "mrev": f"{R['mcap_to_intents_revenue']:.0f}x",
        "mchain": f"{R['mcap_to_chain_fees']:,.0f}x",
        "bps": f"{R['revenue_take_rate_bps']:.1f}",
        "fbps": f"{R['fee_take_rate_bps']:.1f}",
        "st0": money_m(R["near_stablecoins_1y_ago"]),
        "st1": money_m(R["near_stablecoins_now"]),
        "aa0": f"{R['near_active_accounts_first_13w']:,.0f}",
        "aa1": f"{R['near_active_accounts_last_13w']:,.0f}",
    }


LINKS = {
    "corr": "intents_volume",
    "btc": "btc_price",
    "dexc": "all_dex_volume",
    "share0": "all_dex_volume",
    "share1": "all_dex_volume",
    "share2": "all_dex_volume",
    "iv0": "intents_volume",
    "iv1": "intents_volume",
    "p0": "near_chain",
    "p1": "near_chain",
    "lvl": "near_chain",
    "aa": "near_chain",
    "iv365": "intents_volume",
    "fee365": "intents_fees",
    "rev365": "intents_revenue",
    "chain365": "near_chain",
    "mcap": "near_chain",
    "st0": "near_stablecoins",
    "st1": "near_stablecoins",
    "aa0": "near_chain",
    "aa1": "near_chain",
}


def render_thesis(cfg: Config, R: dict) -> str:
    n = numbers(R)
    S = R["sources"]
    md = {k: (f"[{v}]({S[LINKS[k]]})" if k in LINKS else v) for k, v in n.items()}
    fals = "\n".join(
        f"| {f['id']} {f['name']} | {f['test']} | {falsifier_value(f['id'], f['value'])} | "
        f"{'MET (counts against us)' if f['met'] else 'not met'} |"
        for f in R["falsifiers"]
    )
    tmpl = cfg.paths.template.read_text()
    return tmpl.format(
        **md,
        fals=fals,
        weeks=R["weeks"],
        wbtc=R["weeks_btc"],
        start=R["window_start"],
        end=R["window_end"],
        fetched=R["fetched_at_utc"],
        met=sum(f["met"] for f in R["falsifiers"]),
        nf=len(R["falsifiers"]),
        bq=bigquery_note(cfg.paths.bigquery_csv, cfg.project["repo"]),
    )


def _a(text: str, url: str) -> str:
    return f'<a class="src" href="{html.escape(url)}" rel="noopener">{html.escape(text)}</a>'


def render_site(cfg: Config, R: dict) -> str:
    n = numbers(R)
    S = R["sources"]
    L = {
        k: _a(v.replace("-", "\u2212") if k in ("corr", "btc", "dexc", "lvl", "aa", "ci") else v, S[LINKS[k]])
        if k in LINKS
        else html.escape(v)
        for k, v in n.items()
    }
    rows = []
    for f in R["falsifiers"]:
        status = '<span class="pill bad">Met</span>' if f["met"] else '<span class="pill ok">Not met</span>'
        rows.append(
            f"<tr><td><b>{f['id']}</b> {html.escape(f['name'])}</td><td>{html.escape(f['test'])}</td>"
            f'<td class="num">{html.escape(falsifier_value(f["id"], f["value"]).replace("-", chr(0x2212)))}</td><td>{status}</td></tr>'
        )
    met = sum(f["met"] for f in R["falsifiers"])
    ci_lo, ci_hi = R["corr_ci90"]
    ctx = {
        **L,
        "ci": f"{signed(ci_lo)} to {signed(ci_hi)}",
        "lag1": signed(R["lag_price_leads_intents"]),
        "lag2": signed(R["lag_intents_leads_price"]),
        "falsifier_rows": "\n".join(rows),
        "met": str(met),
        "nf": str(len(R["falsifiers"])),
        "weeks": str(R["weeks"]),
        "wbtc": str(R["weeks_btc"]),
        "start": R["window_start"],
        "end": R["window_end"],
        "fetched": R["fetched_at_utc"],
        "repo": cfg.project["repo"],
        "live": cfg.project["live_url"],
        "pocket": cfg.project["other_project"],
        # Hero counters: the final value is in the HTML; JS only animates up to it.
        "k_iv1": f"{R['intents_weekly_volume_last_4w'] / 1e6:.1f}",
        "k_share": f"{R['share_last_13w_pct']:.2f}",
        "k_corr": f"{R['corr_weekly_change_intents_vs_near_price']:.2f}",
        "k_corr_txt": signed(R["corr_weekly_change_intents_vs_near_price"]),
        "k_mrev": f"{R['mcap_to_intents_revenue']:.0f}",
        "u_iv": html.escape(S["intents_volume"]),
        "u_dex": html.escape(S["all_dex_volume"]),
        "u_rev": html.escape(S["intents_revenue"]),
        "bq": bigquery_note_html(cfg.paths.bigquery_csv, cfg.project["repo"]),
        "meter": "".join(
            f'<i class="m" style="--i:{i}"></i>' if f["met"] else f'<i style="--i:{i}"></i>' for i, f in enumerate(R["falsifiers"])
        ),
        **{f"chart_{c[:2]}": chart_html(c, cfg.paths.site / "charts") for c in CHARTS},
    }
    return Template(cfg.paths.site_template.read_text()).substitute(ctx)


def render_all(cfg: Config) -> None:
    R = json.loads((cfg.paths.results / "results.json").read_text())
    cfg.paths.thesis.write_text(render_thesis(cfg, R))
    site = cfg.paths.site
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(render_site(cfg, R))
    brand_src = cfg.paths.root / "brand"
    if brand_src.exists():
        dest = site / "brand"
        dest.mkdir(exist_ok=True)
        for f in sorted(brand_src.glob("*.svg")):
            shutil.copy(f, dest / f.name)
