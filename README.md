<p align="left"><img src="brand/wordmark.svg" alt="Settlemark" width="196" height="40"></p>

# Settlemark research note 01: the NEAR settlement thesis

**In plain words:** people now use NEAR Intents to move and swap money across many blockchains, and that use keeps growing whether the NEAR price goes up or down. But very little of that money reaches NEAR holders yet. This project tests both statements against public data, gives the evidence against as much room as the evidence for, and lets anyone rebuild every number and chart with one command.

* Live page: https://near-settlement-thesis.vercel.app/ (interactive charts drawn from `site/data.json`, which the rebuild writes; the first version stays at /v1)
* The thesis, every number linked to its source: [THESIS.md](THESIS.md)
* Built for NEAR HACKATHON 2026, track `thesis`. Not financial advice.

**Settlemark** is the name of this research product: ongoing, reproducible research on where onchain money settles, written for funds and serious holders. This repo is note 01.

## Headline results

Numbers from the current build. They change only when the public data changes. See [THESIS.md](THESIS.md) for links to each source.

| Question | Answer |
|---|---|
| Does Intents usage move with the NEAR price? | No. Weekly changes correlate at about zero (see THESIS.md for the value and its 90% interval). |
| Is Intents taking share of onchain trading? | Yes. Its share of all DEX volume rose from almost nothing to over 1%. |
| Do holders capture the flow? | Not yet. NEAR's market cap is hundreds of times yearly Intents revenue. |
| How many of our five falsifiers are met? | Shown live in THESIS.md and on the page. |

![Intents volume and NEAR price](charts/01_volume_vs_price.png)

## Other project by the same builder

Henry Sam Marfo also submitted **Pocket** (https://github.com/henrysammarfo/pocket), a separate and independent project, as required by HACKATHON.md Q-015.

## For reviewers: do X, see Y

Needs Python 3.11 or newer. No API keys. No accounts. No cost.

1. `git clone https://github.com/henrysammarfo/near-settlement-thesis && cd near-settlement-thesis`
2. `npm run setup` (or `make setup`). You see the Python packages install into `.venv`.
3. `npm run rebuild` (or `sh rebuild.sh`, or `make rebuild`). You see one log line per dataset, for example `intents_volume 704 rows DefiLlama`, then `results.json`, `charts: 24 files` and `rendered THESIS.md`. It took about 12 seconds on our machine.
4. `npm test` (or `make test`). You see `38 passed`, with no network needed.
5. `make lint`. You see ruff report no problems.
6. Open `site/index.html`. You see the same page as the live site.
7. To check any number: find its key in `results/results.json`, look up which CSV it came from in the `provenance` block of the same file, and open that CSV in `data/`. Every row carries its `source_url` and `fetched_at_utc`.

## How it is built

```
settlemark.toml        every tunable: windows, bootstrap seed, falsifier thresholds, source URLs
settlemark/
  http.py              JSON fetch with retries, exponential backoff, no retry on 4xx, and a local cache
  sources.py           the nine datasets: URL, parser and schema for each; atomic CSV writes
  schema.py            validation: header, ISO dates sorted and unique, finite numbers, bounds, provenance
  fetch.py             fetch, validate and write every dataset
  stats.py             Pearson correlation, bootstrap interval, lead and lag, log changes, weekly resampling
  analysis.py          every number and the five falsifiers, with provenance for each key
  charts.py            six charts in light and dark, deterministic output (no timestamps embedded)
  render.py            THESIS.md, the live page and site/data.json for its interactive charts
templates/app.js       the page script: hand written SVG charts with tooltips, reveals and counters
  __main__.py          the command line: python -m settlemark fetch | build | rebuild
templates/             THESIS.md and page templates (no numbers in them, only placeholders)
brand/                 the Settlemark mark and wordmark, hand written SVG
tests/                 unit tests for the statistics, schema, parsers and HTTP layer, plus integration tests
queries/, docs/        the optional BigQuery cross check
```

Design choices that matter for a thesis:

* **Weekly changes, not levels.** Two trending series always look correlated. We correlate weekly log changes, and report the levels correlation separately as evidence against.
* **Uncertainty is shown.** The main correlation comes with a 90% bootstrap interval (2,000 resamples, fixed seed, so it repeats exactly).
* **Falsifiers are code.** Five tests that would prove the thesis wrong are checked on every rebuild and shown whether or not they help.
* **No hand typed numbers.** Templates hold placeholders only. A test recomputes key numbers straight from the CSVs, another checks that two builds produce byte identical files, and another checks the committed results match a fresh build.

## Data sources

| File | Source |
|---|---|
| data/intents_volume.csv | DefiLlama, NEAR Intents daily volume |
| data/intents_fees.csv, data/intents_revenue.csv | DefiLlama, NEAR Intents daily fees and revenue |
| data/all_dex_volume.csv | DefiLlama, all onchain DEX volume |
| data/near_chain.csv | NearBlocks charts API: transactions, active accounts, fees, price, market cap |
| data/near_stablecoins.csv, data/near_tvl.csv | DefiLlama stablecoins and TVL on NEAR |
| data/near_price.csv, data/btc_price.csv | CoinGecko, 365 days |

**BigQuery is the optional path.** The track suggests the NEAR BigQuery public dataset and the Intents Explorer API. The one command rebuild uses only the free sources above so anyone can rerun it without an account. The BigQuery SQL is in `queries/`, runs in the free sandbox, and one result is saved in `data/bigquery/` (see `docs/BIGQUERY.md`). The Explorer API needs a partner token and was not used.

## Brand

The Settlemark mark shows three lines from different chains meeting in one point and settling into a single dot. Ink `#0B1020`, signal blue `#3D5AFE`, settled green `#3DD6A3`, with red `#E5484D` kept for evidence against. Files: `brand/mark.svg`, `brand/wordmark.svg`.

## License

MIT, see LICENSE.
