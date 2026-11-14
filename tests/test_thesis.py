import csv, json, os, subprocess, sys
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FILES = ["intents_volume", "intents_fees", "intents_revenue", "all_dex_volume", "near_stablecoins",
         "near_tvl", "near_chain", "near_price", "btc_price"]

def rows(name):
    with open(os.path.join(ROOT, "data", name + ".csv")) as f:
        return list(csv.DictReader(f))

def test_every_data_file_has_rows_dates_and_sources():
    for n in FILES:
        r = rows(n)
        assert len(r) > 100, n
        for x in (r[0], r[-1]):
            assert x["source_url"].startswith("https://"), n
            assert x["fetched_at_utc"].endswith("Z"), n
            assert len(x["date"]) == 10, n

def test_dates_sorted_and_unique():
    for n in FILES:
        d = [x["date"] for x in rows(n)]
        assert d == sorted(d) and len(d) == len(set(d)), n

def test_no_negative_volumes():
    for n in ("intents_volume", "all_dex_volume", "intents_fees", "intents_revenue"):
        assert all(float(x["usd"]) >= 0 for x in rows(n)), n

def test_build_regenerates_charts_and_thesis(tmp_path):
    charts = os.path.join(ROOT, "charts")
    for f in os.listdir(charts):
        os.remove(os.path.join(charts, f))
    subprocess.run([sys.executable, "scripts/build.py"], cwd=ROOT, check=True, capture_output=True)
    subprocess.run([sys.executable, "scripts/render.py"], cwd=ROOT, check=True, capture_output=True)
    made = sorted(os.listdir(charts))
    assert len(made) == 6 and all(f.endswith(".png") and os.path.getsize(os.path.join(charts, f)) > 5000 for f in made)
    t = open(os.path.join(ROOT, "THESIS.md")).read()
    for h in ("## The claim", "## Evidence for", "## Evidence against", "## What would change our mind", "## Limits"):
        assert h in t
    assert "{" not in t.split("## Limits")[0], "unfilled placeholder"
    r = json.load(open(os.path.join(ROOT, "results", "results.json")))
    assert -1 <= r["corr_weekly_change_intents_vs_near_price"] <= 1
    assert len(r["falsifiers"]) == 5
