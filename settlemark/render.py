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
    "07_supply_vs_buybacks": "Two area lines since buybacks began: NEAR added to total supply rising far faster than NEAR held by the buyback wallet",
    "08_rolling_correlation": "Line chart of the 26 week rolling correlation between Intents volume and NEAR price, staying below the 0.5 line",
    "09_value_per_token": "Bar chart of value per NEAR from buybacks in bear, base and bull cases against the current price line",
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
        f'from {rows[0]["day"]} to {rows[-1]["day"]} (<a class="lnk" href="{url}" rel="noopener">CSV</a>). It is a 7 day snapshot, not a trend.'
    )


def pct(x: float, d: int = 1) -> str:
    return f"{x:.{d}f}%"


def near_m(x: float) -> str:
    return f"{x / 1e6:,.2f}M NEAR"


def deep_numbers(R: dict) -> dict[str, str]:
    C, V, Rb = R["chain"], R["valuation"], R["robustness"]
    return {
        "blk0": f"{C['first_block_height']:,}",
        "blk1": f"{C['last_block_height']:,}",
        "nblk": str(C["samples"]),
        "sup1": f"{C['supply_now_near'] / 1e9:,.4f}B NEAR",
        "iss52": near_m(C["issuance_52w_near"]),
        "iss52p": pct(C["issuance_52w_pct"], 2),
        "iss13": near_m(C["issuance_13w_near"]),
        "bbstart": C["buyback_wallet_first_week"],
        "bbdown": str(C["buyback_wallet_weeks_down"]),
        "bbnow": near_m(C["buyback_wallet_now_near"]),
        "bb13": near_m(C["buyback_13w_near"]),
        "cov13": pct(C["buyback_coverage_13w_pct"]),
        "bbusd13": money_m(C["buyback_13w_usd"]),
        "rev13": money_m(C["intents_revenue_13w_usd"]),
        "bbshare": pct(C["buyback_share_of_revenue_13w_pct"], 0),
        "stor0": f"{C['intents_storage_52w_ago_gb']:.2f} GB",
        "stor1": f"{C['intents_storage_now_gb']:.2f} GB",
        "storx": f"{C['intents_storage_growth_52w_x']:.1f}x",
        "storp": signed_md(C["corr_weekly_change_storage_vs_near_price"]),
        "storv": signed_md(C["corr_weekly_change_storage_vs_intents_volume"]),
        "storw": str(C["storage_weeks"]),
        "pxnow": f"${C['near_price_now']:.2f}",
        "fdv": money_b(C["fdv_usd"]),
        "mcfdv": pct(C["nearblocks_mcap_to_fdv_pct"], 1),
        "bqr": (
            f"{C['bq_receipts_per_nearblocks_tx_min']:.1f} to {C['bq_receipts_per_nearblocks_tx_max']:.1f}" if "bq_days" in C else "n/a"
        ),
        "bqd": str(C.get("bq_days", 0)),
        "hcf": money_m(V["holder_cash_flow_usd"]),
        "vol13": money_m(V["weekly_volume_13w_usd"]),
        "take13": f"{V['revenue_take_rate_13w_bps']:.2f}",
        "gobs": pct(V["revenue_growth_obs_annual_pct"], 0),
        "gbase": pct(V["growth_base_pct"], 0),
        "gbull": pct(V["growth_bull_pct"], 0),
        "dr": pct(V["discount_rate_pct"], 0),
        "tg": pct(V["terminal_growth_pct"], 0),
        "ny1": str(V["explicit_years"]),
        "ny2": str(V["fade_years"]),
        "vbear": f"${V['value_per_token_bear']:.2f}",
        "vbase": f"${V['value_per_token_base']:.2f}",
        "vbull": f"${V['value_per_token_bull']:.2f}",
        "vbasep": pct(V["value_base_pct_of_price"], 0),
        "vbullp": pct(V["value_bull_pct_of_price"], 0),
        "gimp": pct(V["implied_growth_pct"], 0),
        "fdvhcf": f"{V['fdv_to_holder_cash_flow']:.0f}x",
        "issusd": money_m(V["issuance_usd_per_year"]),
        "bev": money_b(V["breakeven_weekly_volume_usd"]),
        "bevx": f"{V['breakeven_to_current_volume_x']:.1f}x",
        "c1h": signed_md(Rb["corr_first_half"]),
        "c2h": signed_md(Rb["corr_second_half"]),
        "cx13": signed_md(Rb["corr_excluding_first_13w"]),
        "cx13ci": f"{Rb['corr_ci90_excluding_first_13w'][0]:+.2f} to {Rb['corr_ci90_excluding_first_13w'][1]:+.2f}",
        "cl13": signed_md(Rb["corr_last_13w"]),
        "spear": signed_md(Rb["spearman"]),
        "rw": str(Rb["rolling_weeks"]),
        "rmax": signed_md(Rb["rolling_corr_max"]),
        "rmin": signed_md(Rb["rolling_corr_min"]),
        "rn": str(Rb["rolling_windows"]),
        "rabove": str(Rb["rolling_windows_above_0_5"]),
        "pr13": pct(Rb["price_change_last_13w_pct"], 0),
        "vr13": pct(Rb["volume_change_last_13w_pct"], 0),
    }


def sensitivity_md(R: dict) -> str:
    rows = ["| Discount rate | Bear | Base | Bull |", "|---|---|---|---|"]
    for g in R["valuation"]["sensitivity"]:
        rows.append(f"| {g['r'] * 100:.0f}% | ${g['bear']:.2f} | ${g['base']:.2f} | ${g['bull']:.2f} |")
    return "\n".join(rows)


def predictions_md(cfg: Config, R: dict) -> str:
    p = cfg.paths.data / "predictions.json"
    if not p.exists() or "predictions" not in R:
        return "No predictions are frozen in this build."
    P = json.loads(p.read_text())
    st = {r["id"]: r for r in R["predictions"]["results"]}
    rows = [
        f"Frozen {P['created_at_utc']}, sha256 `{R['predictions']['sha256'][:16]}`. Full text: [PREDICTIONS.md](PREDICTIONS.md). "
        f"Resolved {R['predictions']['resolved']} of {len(P['predictions'])}.",
        "",
        "| ID | Prediction | Pass if | Window ends | Probability | Status |",
        "|---|---|---|---|---|---|",
    ]
    for q in P["predictions"]:
        rows.append(
            f"| {q['id']} | {q['claim']}: {q['metric']} | {q['op']} {_pred_threshold(q)} | {q['window_end']} | {q['probability']:.2f} | {st[q['id']]['status']} |"
        )
    return "\n".join(rows)


def _pred_threshold(q: dict) -> str:
    from .predictions import _fmt

    return _fmt(q["threshold"], q["unit"])


def numbers(R: dict) -> dict[str, str]:
    """Formatted numbers keyed by template placeholder (plain text, no links)."""
    return {
        **(deep_numbers(R) if "chain" in R else {}),
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
    "sup1": "near_rpc",
    "iss52": "near_rpc",
    "bbnow": "near_rpc",
    "bb13": "near_rpc",
    "stor1": "near_rpc",
    "hcf": "near_rpc",
}


def thesis_context(cfg: Config, R: dict) -> dict[str, str]:
    n = numbers(R)
    S = R["sources"]
    md = {k: (f"[{v}]({S[LINKS[k]]})" if k in LINKS else v) for k, v in n.items()}
    fals = "\n".join(
        f"| {f['id']} {f['name']} | {f['test']} | {falsifier_value(f['id'], f['value'])} | "
        f"{'MET (counts against us)' if f['met'] else 'not met'} |"
        for f in R["falsifiers"]
    )
    return dict(
        **md,
        sens=sensitivity_md(R) if "valuation" in R else "",
        preds=predictions_md(cfg, R),
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


def render_thesis(cfg: Config, R: dict) -> str:
    return cfg.paths.template.read_text().format(**thesis_context(cfg, R))


def _a(text: str, url: str) -> str:
    return f'<a class="lnk" href="{html.escape(url)}" rel="noopener">{html.escape(text)}</a>'


SIGNED = ("storp", "storv", "c1h", "c2h", "cx13", "cx13ci", "cl13", "spear", "rmax", "rmin", "pr13", "vr13")


def sensitivity_html(R: dict) -> str:
    rows = ['<table class="sens num"><thead><tr><th>Discount rate</th><th>Bear</th><th>Base</th><th>Bull</th></tr></thead><tbody>']
    for g in R["valuation"]["sensitivity"]:
        rows.append(f"<tr><td>{g['r'] * 100:.0f}%</td><td>${g['bear']:.2f}</td><td>${g['base']:.2f}</td><td>${g['bull']:.2f}</td></tr>")
    rows.append("</tbody></table>")
    return "".join(rows)


def predictions_html(cfg: Config, R: dict) -> tuple[str, str]:
    p = cfg.paths.data / "predictions.json"
    if not p.exists() or "predictions" not in R:
        return "No predictions are frozen in this build.", ""
    from .predictions import _fmt

    P = json.loads(p.read_text())
    st = {r["id"]: r["status"] for r in R["predictions"]["results"]}
    chip = {"PENDING": "wait", "HIT": "ok", "MISS": "bad"}
    rows = []
    for q in P["predictions"]:
        s = st[q["id"]]
        rows.append(
            f'<div class="prow"><span class="fid">{q["id"]}</span><span class="fname"><b>{html.escape(q["claim"])}</b>'
            f"<small>{html.escape(q['metric'])}. Pass if {html.escape(q['op'])} {html.escape(_fmt(q['threshold'], q['unit']))} ({html.escape(q['rule'])}).</small></span>"
            f'<span class="pm">by {q["window_end"]} · p = {q["probability"]:.2f}</span>'
            f'<span class="chip {chip[s]}">{s.title()}</span></div>'
        )
    lead = (
        f"Frozen {html.escape(P['created_at_utc'])}, before any of these weeks happened. The git commit is the timestamp; sha256 "
        f"<code>{R['predictions']['sha256'][:16]}</code>. Each has our probability, so a Brier score grades us. "
        f'Resolved {R["predictions"]["resolved"]} of {len(P["predictions"])}. <a class="lnk" href="PREDICTIONS.md">Full text</a>.'
    )
    return lead, "\n".join(rows)


def render_site(cfg: Config, R: dict) -> str:
    n = numbers(R)
    S = R["sources"]
    L = {
        k: _a(v.replace("-", "\u2212") if k in ("corr", "btc", "dexc", "lvl", "aa", "ci") else v, S[LINKS[k]])
        if k in LINKS
        else html.escape(v.replace("-", "\u2212") if k in SIGNED else v)
        for k, v in n.items()
    }
    rows = []
    for f in R["falsifiers"]:
        chip = '<span class="chip bad">Met</span>' if f["met"] else '<span class="chip ok">Not met</span>'
        val = html.escape(falsifier_value(f["id"], f["value"]).replace("-", chr(0x2212)))
        rows.append(
            f'<li class="frow r"><span class="fid">{f["id"]}</span><span class="fname"><b>{html.escape(f["name"])}</b>'
            f'<small>{html.escape(f["test"])}</small></span><span class="fval num">{val}</span>{chip}</li>'
        )
    met = sum(f["met"] for f in R["falsifiers"])
    ci_lo, ci_hi = R["corr_ci90"]
    ctx = {
        **L,
        "ci": f"{signed(ci_lo)} to {signed(ci_hi)}",
        "lag1": signed(R["lag_price_leads_intents"]),
        "lag2": signed(R["lag_intents_leads_price"]),
        "falsifier_rows": "\n".join(rows),
        "x_growth": f"{R['intents_weekly_volume_last_4w'] / R['intents_weekly_volume_first_4w']:,.0f}",
        "x_aa_drop": f"{(R['near_active_accounts_last_13w'] / R['near_active_accounts_first_13w'] - 1) * 100:.0f}".replace("-", "\u2212"),
        "x_st_drop": f"{(R['near_stablecoins_now'] / R['near_stablecoins_1y_ago'] - 1) * 100:.0f}".replace("-", "\u2212"),
        "x_bps": f"{R['revenue_take_rate_bps']:.1f}",
        "x_btc": signed(R["corr_weekly_change_intents_vs_btc"]),
        "x_lag": signed(R["lag_price_leads_intents"]),
        "x_share0": f"{R['share_first_13w_pct']:.3f}%",
        "x_lvl": signed(R["corr_levels_log_intents_vs_log_price"]),
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
    if "valuation" in R:
        lead, prow = predictions_html(cfg, R)
        ctx.update(sens_html=sensitivity_html(R), pred_lead=lead, pred_rows=prow)
    return Template(cfg.paths.site_template.read_text()).substitute(ctx)


def render_all(cfg: Config) -> None:
    R = json.loads((cfg.paths.results / "results.json").read_text())
    cfg.paths.thesis.write_text(render_thesis(cfg, R))
    site = cfg.paths.site
    site.mkdir(parents=True, exist_ok=True)
    (site / "index.html").write_text(render_site(cfg, R))
    brand_src = cfg.paths.root / "brand"
    if brand_src.exists():
        shutil.copytree(brand_src, site / "brand", dirs_exist_ok=True)
    shutil.copy(cfg.paths.root / "templates" / "app.js", site / "app.js")
    model = cfg.paths.root / "templates" / "model.js"
    if model.exists():
        shutil.copy(model, site / "model.js")
    rpc = cfg.paths.data / "near_rpc.csv"
    if rpc.exists():
        (site / "data").mkdir(exist_ok=True)
        shutil.copy(rpc, site / "data" / "near_rpc.csv")
    preds = cfg.paths.root / "PREDICTIONS.md"
    if preds.exists():
        shutil.copy(preds, site / "PREDICTIONS.md")


def write_site_data(cfg: Config, frames, R: dict) -> Path:
    """site/data.json: the series the interactive charts draw, straight from the analysis frames."""
    w, chg = frames.weekly, frames.changes
    st = frames.stablecoins.resample(cfg.analysis.week_rule).last().dropna()

    def r(x, n=6):
        return [round(float(v), n) for v in x]

    data = {
        "fetched_at_utc": R["fetched_at_utc"],
        "weekly": {
            "date": [d.strftime("%Y-%m-%d") for d in w.index],
            "intents_volume_usd": r(w.iv, 2),
            "near_price_usd": r(w.p, 4),
            "share_pct": r(w.share * 100, 4),
            "active_accounts": r(w.aa, 1),
        },
        "weekly_changes": {
            "near_price_pct": r(chg.p * 100, 3),
            "intents_volume_pct": r(chg.iv * 100, 3),
            "date": [d.strftime("%Y-%m-%d") for d in chg.index],
        },
        "stablecoins": {"date": [d.strftime("%Y-%m-%d") for d in st.index], "usd": r(st, 0)},
        "value_capture_365d": frames.value_capture,
        "sources": R["sources"],
    }
    site = cfg.paths.site
    site.mkdir(parents=True, exist_ok=True)
    out = site / "data.json"
    out.write_text(json.dumps(data, separators=(",", ":")) + "\n")
    shutil.copy(cfg.paths.results / "results.json", site / "results.json")
    return out
