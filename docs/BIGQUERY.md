# BigQuery: a main source with committed results

The NEAR BigQuery public dataset (`bigquery-public-data.crypto_near_mainnet_us`) feeds the thesis through committed results, so nobody needs a Google account to rebuild, and anyone with one can refresh. Code: [settlemark/bigquery.py](../settlemark/bigquery.py). Tests: [tests/test_bigquery.py](../tests/test_bigquery.py).

## What is committed

[data/bigquery/manifest.json](../data/bigquery/manifest.json) records, for each result: the CSV, the SQL file, a sha256 of the SQL (comments and layout ignored), the GB scanned, when it ran and how (`api` or `console`). Every CSV row repeats the run time and the query file. `python -m settlemark check` fails if a required result is missing or if its SQL changed after the result was produced ([settlemark/check.py](../settlemark/check.py)).

| Key | SQL | Result | Status |
|---|---|---|---|
| 01 | [queries/01_receipt_actions_daily.sql](../queries/01_receipt_actions_daily.sql) | [receipt_actions_daily.csv](../data/bigquery/receipt_actions_daily.csv) | committed, run 2026-11-14 in the console, 174 GB scanned ([manifest](../data/bigquery/manifest.json)) |
| 04 | [queries/04_intents_weekly.sql](../queries/04_intents_weekly.sql) | `04_intents_weekly.csv` (not in the repo) | pending: on 15 Nov the console estimated about 500 GB, more than was left of the free monthly quota; runs after the quota resets on 1 Dec. No result is committed, and the lead test does not use this query. |
| 05 | [queries/05_weekly_activity.sql](../queries/05_weekly_activity.sql) | [05_weekly_activity.csv](../data/bigquery/05_weekly_activity.csv) | committed, run 2026-11-15 06:58 UTC in the console, 65.09 GB scanned, 100 weeks |

Query 05 feeds the lead and lag test ([settlemark/leadlag.py](../settlemark/leadlag.py)) and a cross check against NearBlocks (`bigquery.weekly` in [results/results.json](../results/results.json)). On the overlapping 99 weeks, weekly transactions agree almost exactly (`tx_change_corr` is about 1). Distinct signers, which NearBlocks does not publish, fell 92% from the first 13 weeks to the last 13 (`signers_change_pct`, about 2.32M to 179K a week), in line with NearBlocks active accounts. There is no Intents lead on these signers in sample or out of sample (`leadlag.series_where_intents_leads` and `leadlag.series_where_oos_helps` are empty). Write up: [THESIS.md](../THESIS.md).

Queries 04 and 05 use fixed dates (2024-12-09 to the week ending 2026-11-08) in their SQL files, so a rerun of the same SQL returns the same rows.

## Refreshing

* API: `pip install google-cloud-bigquery`, `gcloud auth application-default login`, then `python -m settlemark bigquery 05 --dry-run` to see the scan size, and `python -m settlemark bigquery 05` (or `all`, or `npm run bigquery`). It refuses any query above `max_gb` in [settlemark.toml](../settlemark.toml) (400 GB), so the free 1 TB a month is not exceeded by accident.
* Console: open the SQL file, paste it in the BigQuery console, check the "This query will process" estimate, run it, download the result as CSV, then `python -m settlemark bigquery-import 05 ~/Downloads/results.csv --scanned-gb 123.4 --run-at 2026-11-15T06:00:00Z`. The importer checks the columns and writes the same files the API path writes.

Then `npm run build && npm test` and commit `data/bigquery/` with the outputs.

Notes: `block_timestamp` is INT64 nanoseconds, so convert with `TIMESTAMP_MICROS(DIV(block_timestamp, 1000))` (see the committed SQL). Filter on `block_date`, but expect large scans: query 01 (7 days) scanned 174 GB, recorded in the manifest.
