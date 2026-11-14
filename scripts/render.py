"""Write THESIS.md and site/index.html from results/results.json. No number is typed by hand."""
import json, os, shutil
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
R = json.load(open(os.path.join(ROOT, "results", "results.json")))
S = R["sources"]
def m(x): return f"${x/1e6:,.1f}M"
def b(x): return f"${x/1e9:,.2f}B"
def c(x): return f"{x:+.2f}"
L = lambda text, key: f"[{text}]({S[key]})"
met = sum(f["met"] for f in R["falsifiers"])
N = {
 "corr": L(c(R["corr_weekly_change_intents_vs_near_price"]), "intents_volume"),
 "ci": f"{R['corr_ci90'][0]:+.2f} to {R['corr_ci90'][1]:+.2f}",
 "btc": L(c(R["corr_weekly_change_intents_vs_btc"]), "btc_price"),
 "dexc": L(c(R["corr_weekly_change_intents_vs_all_dex"]), "all_dex_volume"),
 "share0": L(f"{R['share_first_13w_pct']:.3f}%", "all_dex_volume"),
 "share1": L(f"{R['share_prev_13w_pct']:.2f}%", "all_dex_volume"),
 "share2": L(f"{R['share_last_13w_pct']:.2f}%", "all_dex_volume"),
 "iv0": L(m(R["intents_weekly_volume_first_4w"]), "intents_volume"),
 "iv1": L(m(R["intents_weekly_volume_last_4w"]), "intents_volume"),
 "p0": L(f"${R['near_price_first_4w']:.2f}", "near_chain"),
 "p1": L(f"${R['near_price_last_4w']:.2f}", "near_chain"),
 "lvl": L(c(R["corr_levels_log_intents_vs_log_price"]), "near_chain"),
 "lag1": c(R["lag_price_leads_intents"]), "lag2": c(R["lag_intents_leads_price"]),
 "aa": L(c(R["corr_weekly_change_active_accounts_vs_near_price"]), "near_chain"),
 "iv365": L(b(R["intents_volume_365d"]), "intents_volume"),
 "fee365": L(m(R["intents_fees_365d"]), "intents_fees"),
 "rev365": L(m(R["intents_revenue_365d"]), "intents_revenue"),
 "chain365": L(m(R["near_chain_fees_365d"]), "near_chain"),
 "mcap": L(b(R["near_market_cap"]), "near_chain"),
 "mrev": f"{R['mcap_to_intents_revenue']:.0f}x", "mchain": f"{R['mcap_to_chain_fees']:,.0f}x",
 "bps": f"{R['revenue_take_rate_bps']:.1f}", "fbps": f"{R['fee_take_rate_bps']:.1f}",
 "st0": L(m(R["near_stablecoins_1y_ago"]), "near_stablecoins"), "st1": L(m(R["near_stablecoins_now"]), "near_stablecoins"),
 "aa0": L(f"{R['near_active_accounts_first_13w']:,.0f}", "near_chain"), "aa1": L(f"{R['near_active_accounts_last_13w']:,.0f}", "near_chain"),
 "weeks": R["weeks"], "wbtc": R["weeks_btc"], "start": R["window_start"], "end": R["window_end"], "fetched": R["fetched_at_utc"],
 "met": met, "nf": len(R["falsifiers"]),
}
import csv as _csv
bq = os.path.join(ROOT, "data", "bigquery", "receipt_actions_daily.csv")
if os.path.exists(bq):
    rr = [r for r in _csv.DictReader(open(bq)) if not r["note"]]
    N["bq"] = (f"A cross check on the BigQuery public dataset (`queries/01_receipt_actions_daily.sql`, run by hand in the free sandbox) counted "
               f"{min(int(r['receipt_actions']) for r in rr):,} to {max(int(r['receipt_actions']) for r in rr):,} receipt actions a day from {rr[0]['day']} to {rr[-1]['day']} "
               f"([data/bigquery/receipt_actions_daily.csv](https://github.com/henrysammarfo/near-settlement-thesis/blob/main/data/bigquery/receipt_actions_daily.csv)). It is a 7 day snapshot, so it cannot test a trend yet.")
else:
    N["bq"] = "No BigQuery results are included in this build."
fals = "\n".join(f"| {f['name']} | {f['test']} | {'MET (counts against us)' if f['met'] else 'not met'} |" for f in R["falsifiers"])
T = open(os.path.join(ROOT, "scripts", "THESIS.template.md")).read()
out = T.format(**N, fals=fals)
open(os.path.join(ROOT, "THESIS.md"), "w").write(out)
# Static site
os.makedirs(os.path.join(ROOT, "site", "charts"), exist_ok=True)
for f in sorted(os.listdir(os.path.join(ROOT, "charts"))):
    shutil.copy(os.path.join(ROOT, "charts", f), os.path.join(ROOT, "site", "charts", f))
import html, re
def md2html(md):
    h = html.escape(md)
    h = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', h)
    h = re.sub(r"!\<a href=\"([^\"]+)\"\>([^<]*)\</a\>", r'<img alt="\2" src="\1">', h)
    lines, outl, table = h.split("\n"), [], False
    for ln in lines:
        if ln.startswith("|"):
            cells = [x.strip() for x in ln.strip("|").split("|")]
            if set("".join(cells)) <= set("- :"): continue
            if not table: outl.append("<table>"); table = True
            outl.append("<tr>" + "".join(f"<td>{x}</td>" for x in cells) + "</tr>"); continue
        if table: outl.append("</table>"); table = False
        if ln.startswith("### "): outl.append(f"<h3>{ln[4:]}</h3>")
        elif ln.startswith("## "): outl.append(f"<h2>{ln[3:]}</h2>")
        elif ln.startswith("# "): outl.append(f"<h1>{ln[2:]}</h1>")
        elif ln.startswith("- "): outl.append(f"<li>{ln[2:]}</li>")
        elif ln.strip(): outl.append(f"<p>{ln}</p>")
    if table: outl.append("</table>")
    h = "\n".join(outl)
    return re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", h)
page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>NEAR Settlement Thesis</title><style>body{{font:16px/1.6 system-ui,sans-serif;max-width:900px;margin:2rem auto;padding:0 1rem;color:#1a202c}}
img{{max-width:100%;border:1px solid #e2e8f0;border-radius:8px;margin:.5rem 0}}table{{border-collapse:collapse;width:100%;font-size:14px}}td{{border:1px solid #e2e8f0;padding:6px}}
a{{color:#2b6cb0}}h1{{line-height:1.2}}</style></head><body>
<p><small>Data fetched {N['fetched']}. Rebuilt by <code>make rebuild</code>. Repo: <a href="https://github.com/henrysammarfo/near-settlement-thesis">henrysammarfo/near-settlement-thesis</a></small></p>
{md2html(out)}</body></html>"""
open(os.path.join(ROOT, "site", "index.html"), "w").write(page)
print("rendered THESIS.md and site/index.html")
