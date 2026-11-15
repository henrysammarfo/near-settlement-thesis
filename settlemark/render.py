"""Write THESIS.md and the live page from results.json. No number is typed by hand."""

from __future__ import annotations

import base64
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
    "10_lead_lag": "Bar chart of correlations between Intents volume changes and later usage changes at leads of minus four to four weeks against a grey 95 percent noise band",
    "11_router_take_rates": "Horizontal bars of fees and revenue in basis points of volume for NEAR Intents and four other cross chain routers",
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


def _p(x: float) -> str:
    return "<0.001" if x < 0.001 else f"{x:.2f}"


def extra_numbers(R: dict) -> dict[str, str]:
    """Placeholders for the lead and lag test and the router comparison."""
    out: dict[str, str] = {}
    L = R.get("leadlag")
    if L:
        T = {t["series"]: t for t in L["tests"] if "xcorr" in t}
        aa, st, tx = T["aa"], T.get("storage"), T["tx"]
        out.update(
            {
                "llw": str(aa["weeks"]),
                "llk": str(L["headline_lags"]),
                "llalpha": f"{L['alpha']:.2f}",
                "lln": str(L["tests_run"]),
                "llaap": _p(aa["headline_p"]),
                "llaaps": _p(aa["headline_p_shift"]),
                "llaarev": _p(aa["headline_reverse_p"]),
                "llaak": str(aa["best_lead_weeks"]),
                "llaar": signed_md(aa["best_lead_corr"]),
                "lltxp": _p(tx["headline_p"]),
                "llstp": _p(st["headline_p"]) if st else "n/a",
                "llstps": _p(st["headline_p_shift"]) if st else "n/a",
                "llmin": _p(L["min_headline_p"]),
                "llband": f"{L['band']:.2f}",
                "llbars": str(L["lead_bars"]),
                "llout": str(len(L["lead_bars_outside"])),
                "llexp": f"{0.05 * L['lead_bars']:.1f}",
                "lloutwhat": "; ".join(
                    f"{T[o['series']]['label']} at {o['lead']} week{'s' if o['lead'] != 1 else ''}, {signed_md(o['corr'])}"
                    for o in L["lead_bars_outside"]
                )
                or "none",
                **oos_numbers(L, T),
                "llsame": ", ".join(f"{T[o['series']]['label']} {signed_md(o['corr'])}" for o in L["same_week_outside"]) or "none",
                "llverdict": (
                    "Intents volume leads " + ", ".join(T[k]["label"] for k in L["series_where_intents_leads"])
                    if L["series_where_intents_leads"]
                    else "Intents volume does not lead any usage series we can measure"
                ),
            }
        )
    P = R.get("peers")
    if P:
        me = next(r for r in P["rows"] if r["slug"] == "near_intents")
        out.update(
            {
                "pedays": str(P["window_days"]),
                "pestart": P["window_start"],
                "peend": P["window_end"],
                "pen": str(P["routers"]),
                "perank": str(P["intents_volume_rank"]),
                "peshare": pct(P["intents_share_of_peer_volume_pct"]),
                "pevol": money_b(me["volume_usd"]),
                "pefee": f"{P['intents_fee_bps']:.1f}",
                "pefeemed": f"{P['peer_fee_bps_median']:.1f}",
                "perev": f"{P['intents_revenue_bps']:.1f}",
                "perevmed": f"{P['peer_revenue_bps_median']:.1f}",
                "pecheap": str(P["cheaper_than"]),
                "peothers": str(P["routers"] - 1),
                "pemrev": f"{P['near_mcap_to_annual_revenue']:.0f}x",
                "petok": f"{P['token_peer_mcap_to_annual_revenue_median']:.0f}x",
                "peprem": f"{P['near_premium_to_token_peers_x']:.0f}x",
            }
        )
    return out


def leadlag_md(R: dict) -> str:
    L = R.get("leadlag")
    if not L:
        return ""
    rows = [
        f"| Usage series | Weeks | Strongest lead (weeks, r) | p, Intents leads ({L['headline_lags']} lags) | Shift p | p, usage leads |",
        "|---|---|---|---|---|---|",
    ]
    for t in L["tests"]:
        if "xcorr" not in t:
            rows.append(f"| {t['label']} | {t['weeks']} | not run: {t['skipped']} | | | |")
            continue
        rows.append(
            f"| {t['label']} | {t['weeks']} | {t['best_lead_weeks']}, {signed_md(t['best_lead_corr'])} | {_p(t['headline_p'])} | "
            f"{_p(t['headline_p_shift'])} | {_p(t['headline_reverse_p'])} |"
        )
    return "\n".join(rows)


def oos_numbers(L: dict, T: dict) -> dict[str, str]:
    oo = {k: t["out_of_sample"] for k, t in T.items() if t.get("out_of_sample")}
    if not oo:
        return {
            k: "n/a" for k in ("lloostrain", "lloostest", "lloossplit", "lloosminp", "lloosbest", "lloosverdict", "lloosread", "llooswhere")
        }
    first = next(iter(oo.values()))
    best_k = min(oo, key=lambda k: oo[k]["mse_ratio"])
    minp = min(o["p_cw"] for o in oo.values())
    helps = L["series_where_oos_helps"]
    verdict = (
        "Out of sample, past Intents changes improve the forecast of " + ", ".join(T[k]["label"] for k in helps)
        if helps
        else "Out of sample, past Intents changes do not significantly improve any usage forecast"
    )
    return {
        "lloostrain": str(first["train_weeks"]),
        "lloostest": str(first["test_weeks"]),
        "lloossplit": T[best_k]["split_week"],
        "lloosminp": _p(minp),
        "lloosbest": f"{T[best_k]['label']}, {_gain(oo[best_k])} forecast error",
        "llooswhere": " in sample or out of sample" if not helps else " in sample, though out of sample shows a significant gain",
        "lloosread": (
            f"above {L['alpha']:.2f}. This does not rescue the leading indicator claim, and it does not weaken the null either: it is the same answer on weeks the fit never saw"
            if not helps
            else f"below {L['alpha']:.2f}. On unseen weeks Intents does help, which is stronger evidence than the in sample tests gave"
        ),
        "lloosverdict": verdict,
    }


def _gain(o: dict) -> str:
    g = o["oos_r2_gain_pct"]
    return f"{g:.1f}% less" if g >= 0 else f"{abs(g):.1f}% more"


def oos_md(R: dict) -> str:
    L = R.get("leadlag")
    rows = [
        "| Usage series | Fit weeks | Test weeks | Forecast error with Intents | Weeks Intents model was closer | Clark West p |",
        "|---|---|---|---|---|---|",
    ]
    for t in (L or {}).get("tests", []):
        o = t.get("out_of_sample")
        if o:
            rows.append(
                f"| {t['label']} | {o['train_weeks']} | {o['test_weeks']} | {_gain(o)} | {o['win_share'] * 100:.0f}% | {_p(o['p_cw'])} |"
            )
    return "\n".join(rows) if len(rows) > 2 else ""


def oos_html(R: dict) -> str:
    L = R.get("leadlag")
    rows = [
        '<div class="tscroll"><table class="sens num ll"><thead><tr><th>Usage series</th><th>Error with Intents</th><th>Closer weeks</th><th>p</th></tr></thead><tbody>'
    ]
    for t in (L or {}).get("tests", []):
        o = t.get("out_of_sample")
        if o:
            rows.append(
                f"<tr><td>{html.escape(t['label'])}</td><td>{_gain(o)}</td><td>{o['win_share'] * 100:.0f}%</td><td>{_p(o['p_cw'])}</td></tr>"
            )
    rows.append("</tbody></table></div>")
    return "".join(rows) if len(rows) > 2 else ""


def _cap(x: float | None) -> str:
    return "no token" if x is None else f"{x:.0f}x"


def peers_md(R: dict) -> str:
    P = R.get("peers")
    if not P:
        return ""
    rows = [
        "| Router | Model | Volume | Fees, bps | Revenue, bps | Revenue share of fees | Market cap to yearly revenue |",
        "|---|---|---|---|---|---|---|",
    ]
    for r in P["rows"]:
        rows.append(
            f"| {r['name']} | {r['model']} | {money_b(r['volume_usd'])} | {r['fee_bps']:.1f} | {r['revenue_bps']:.1f} | "
            f"{r['revenue_share_of_fees_pct']:.0f}% | {_cap(r['mcap_to_annual_revenue'])} |"
        )
    return "\n".join(rows)


def peers_html(R: dict) -> str:
    P = R.get("peers")
    if not P:
        return ""
    rows = [
        '<div class="tscroll"><table class="sens num peers"><thead><tr><th>Router</th><th>Volume</th><th>Fees<small>bps</small></th><th>Kept<small>bps</small></th>'
        "<th>Cap<small>to revenue</small></th></tr></thead><tbody>"
    ]
    for r in P["rows"]:
        me = ' class="me"' if r["slug"] == "near_intents" else ""
        rows.append(
            f"<tr{me}><td>{html.escape(r['name'])}<small>{html.escape(r['model'])}</small></td><td>{money_b(r['volume_usd'])}</td>"
            f"<td>{r['fee_bps']:.1f}</td><td>{r['revenue_bps']:.1f}</td><td>{_cap(r['mcap_to_annual_revenue'])}</td></tr>"
        )
    rows.append("</tbody></table></div>")
    return "".join(rows)


def bigquery_md(R: dict, repo: str) -> str:
    B = R.get("bigquery")
    if not B:
        return ""
    rows = ["| Query | Result | Rows | Scanned | Run |", "|---|---|---|---|---|"]
    for q in B["queries"]:
        if q["committed"]:
            rows.append(
                f"| [{q['sql']}]({q['sql']}) | [{q['csv']}]({q['csv']}) | {q['rows']} ({q['first']} to {q['last']}) | "
                f"{q['scanned_gb']:.0f} GB | {q['run_at_utc'][:10]}, {q['method']} |"
            )
        else:
            rows.append(f"| [{q['sql']}]({q['sql']}) | pending first run | | | |")
    return "\n".join(rows)


def bigquery_html(R: dict) -> str:
    B = R.get("bigquery")
    if not B:
        return ""
    done = [q for q in B["queries"] if q["committed"]]
    todo = [q for q in B["queries"] if not q["committed"]]
    parts = [
        f"{len(done)} of {len(B['queries'])} BigQuery results are committed with their scan size and a hash of the SQL "
        "(<code>data/bigquery/manifest.json</code>), so the page rebuilds with no Google account."
    ]
    if todo:
        parts.append(" Pending first run: " + ", ".join(f"<code>{html.escape(q['sql'])}</code>" for q in todo) + ".")
    return "".join(parts)


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


def predictions_2_md(cfg: Config, R: dict) -> str:
    p = cfg.paths.data / "predictions_2.json"
    if not p.exists() or "predictions_2" not in R:
        return ""
    P = json.loads(p.read_text())
    st = {r["id"]: r for r in R["predictions_2"]["results"]}
    rows = [
        f"Set 2, bolder calls: frozen {P['created_at_utc']}, after the hackathon deadline, sha256 `{R['predictions_2']['sha256'][:16]}`. "
        f"Full text: [PREDICTIONS_2.md](PREDICTIONS_2.md). Resolved {R['predictions_2']['resolved']} of {len(P['predictions'])}.",
        "",
        "| ID | Prediction | Pass if | Window ends | Probability | Status |",
        "|---|---|---|---|---|---|",
    ]
    for q in P["predictions"]:
        rows.append(
            f"| {q['id']} | {q['claim']}: {q['metric']} | {q['op']} {_pred_threshold(q)} | {q['window_end']} | {q['probability']:.2f} | {st[q['id']]['status']} |"
        )
    return "\n".join(rows)


def anchors_md(cfg: Config) -> str:
    p = cfg.paths.data / "anchors.json"
    if not p.exists():
        return "The prediction hashes are not anchored on chain yet."
    A = json.loads(p.read_text())
    a = A["anchors"][-1]
    return (
        f"Both hashes were written to NEAR {a['network']} in transaction [{a['tx_hash'][:12]}]({a['explorer_url']}) "
        f"(block {a['block_height']:,}, {a['block_time_utc']}) by `{a['signer']}` calling `{a['method']}` on `{a['receiver']}`. "
        "`python -m settlemark anchor verify` fetches that transaction from a public RPC and checks the hashes in its arguments "
        "against the committed files. Testnet only proves the hashes existed by that block; it is a public timestamp, not money."
    )


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
        **extra_numbers(R),
        sens=sensitivity_md(R) if "valuation" in R else "",
        preds=predictions_md(cfg, R),
        preds2=predictions_2_md(cfg, R),
        anchors=anchors_md(cfg),
        lltable=leadlag_md(R),
        oostable=oos_md(R),
        petable=peers_md(R),
        bqtable=bigquery_md(R, cfg.project["repo"]),
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
    p2 = cfg.paths.data / "predictions_2.json"
    if p2.exists() and "predictions_2" in R:
        P = {**P, "predictions": P["predictions"] + json.loads(p2.read_text())["predictions"]}
        st.update({r["id"]: r["status"] for r in R["predictions_2"]["results"]})
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
        f"P1 to P8 frozen {html.escape(P['created_at_utc'])}; P9 to P14, the bolder set, a few hours later. Both after the hackathon "
        f"deadline, both before any scored week began. sha256 <code>{R['predictions']['sha256'][:12]}</code>"
        + (f" and <code>{R['predictions_2']['sha256'][:12]}</code>" if "predictions_2" in R else "")
        + f". Each has our probability, so a Brier score grades us. Resolved {R['predictions']['resolved'] + R.get('predictions_2', {}).get('resolved', 0)} "
        f'of {len(P["predictions"])}. <a class="lnk" href="PREDICTIONS.md">Set 1</a> · <a class="lnk" href="PREDICTIONS_2.md">Set 2</a>'
        + _anchor_link(cfg)
        + "."
    )
    return lead, "\n".join(rows)


def _inline(path: Path) -> str:
    """JSON safe to place inside a <script type="application/json"> element."""
    if not path.exists():
        return ""
    data = json.loads(path.read_text())
    return json.dumps(data, separators=(",", ":")).replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")


def _anchor_link(cfg: Config) -> str:
    p = cfg.paths.data / "anchors.json"
    if not p.exists():
        return ""
    a = json.loads(p.read_text())["anchors"][-1]
    return f' · <a class="lnk" href="{html.escape(a["explorer_url"])}" rel="noopener">hashes on NEAR testnet</a>'


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
    ctx.update({k: html.escape(v.replace("-", "\u2212") if k in ("llaar",) else v) for k, v in extra_numbers(R).items()})
    ctx.update(peers_html=peers_html(R), bq_html=bigquery_html(R), oos_html=oos_html(R))
    ctx.update(inline_data=_inline(cfg.paths.site / "data.json"), inline_results=_inline(cfg.paths.site / "results.json"))
    # Fonts inlined as data URIs: Chrome blocks font files on file:// as cross origin, and README step 6 opens the page from disk.
    fonts = cfg.paths.root / "brand" / "fonts"
    ctx.update(
        {
            k: "data:font/woff2;base64," + base64.b64encode((fonts / f).read_bytes()).decode()
            for k, f in (("font_inter", "inter.woff2"), ("font_tight", "inter-tight.woff2"))
        }
    )
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
    for name in ("PREDICTIONS.md", "PREDICTIONS_2.md"):
        preds = cfg.paths.root / name
        if preds.exists():
            shutil.copy(preds, site / name)


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
