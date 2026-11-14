"""Fetch every input from free public APIs into data/*.csv.

Each CSV row carries the UTC fetch time and the exact source URL.
No API keys are used. Nothing here is estimated or invented.
"""
import csv, datetime as dt, json, os, sys, time, urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "data")
NOW = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

SOURCES = {
    "intents_volume": "https://api.llama.fi/summary/dexs/near-intents?dataType=dailyVolume",
    "intents_fees": "https://api.llama.fi/summary/fees/near-intents?dataType=dailyFees",
    "intents_revenue": "https://api.llama.fi/summary/fees/near-intents?dataType=dailyRevenue",
    "all_dex_volume": "https://api.llama.fi/overview/dexs?excludeTotalDataChartBreakdown=true&excludeTotalDataChart=false",
    "near_stablecoins": "https://stablecoins.llama.fi/stablecoincharts/Near",
    "near_tvl": "https://api.llama.fi/v2/historicalChainTvl/Near",
    "near_chain": "https://api.nearblocks.io/v1/charts",
    "near_price": "https://api.coingecko.com/api/v3/coins/near/market_chart?vs_currency=usd&days=365&interval=daily",
    "btc_price": "https://api.coingecko.com/api/v3/coins/bitcoin/market_chart?vs_currency=usd&days=365&interval=daily",
}


def get(url):
    last = None
    for i in range(4):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "near-settlement-thesis/1.0"})
            return json.load(urllib.request.urlopen(req, timeout=60))
        except Exception as e:  # retry on rate limits and timeouts
            last = e
            time.sleep(3 * (i + 1))
    raise RuntimeError(f"failed {url}: {last}")


def day(ts):
    ts = float(ts)
    if ts > 1e11:
        ts /= 1000
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).strftime("%Y-%m-%d")


def write(name, header, rows, url):
    path = os.path.join(DATA, name + ".csv")
    with open(path, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(header + ["fetched_at_utc", "source_url"])
        for r in rows:
            w.writerow(list(r) + [NOW, url])
    print(f"{name}: {len(rows)} rows")


def main():
    os.makedirs(DATA, exist_ok=True)
    for key in ("intents_volume", "intents_fees", "intents_revenue", "all_dex_volume"):
        u = SOURCES[key]
        d = get(u)
        rows = {}
        for ts, v in d["totalDataChart"]:
            rows[day(ts)] = v
        write(key, ["date", "usd"], sorted(rows.items()), u)

    u = SOURCES["near_stablecoins"]
    rows = [(day(x["date"]), x["totalCirculatingUSD"].get("peggedUSD", 0)) for x in get(u)]
    write("near_stablecoins", ["date", "usd"], rows, u)

    u = SOURCES["near_tvl"]
    rows = [(day(x["date"]), x["tvl"]) for x in get(u)]
    write("near_tvl", ["date", "usd"], rows, u)

    u = SOURCES["near_chain"]
    rows = []
    for x in get(u)["charts"]:
        rows.append((x["date"][:10], x["txns"], x["active_accounts"], x["new_accounts"],
                     x["txn_fee_usd"], x["near_price"], x["market_cap"]))
    write("near_chain", ["date", "txns", "active_accounts", "new_accounts", "txn_fee_usd", "near_price_usd", "market_cap_usd"], rows, u)

    for key in ("near_price", "btc_price"):
        u = SOURCES[key]
        d = get(u)
        rows = {}
        for ts, v in d["prices"]:
            rows[day(ts)] = v  # last value of the day wins
        write(key, ["date", "usd"], sorted(rows.items()), u)
        time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
