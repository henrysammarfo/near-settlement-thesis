# BigQuery: a main source with committed results

The NEAR BigQuery public dataset (`bigquery-public-data.crypto_near_mainnet_us`) feeds the thesis through committed results, so nobody needs a Google account to rebuild, and anyone with one can refresh.

## What is committed

`data/bigquery/manifest.json` records, for each result: the CSV, the SQL file, a sha256 of the SQL (comments and layout ignored), the GB scanned, when it ran and how (`api` or `console`). Every CSV row repeats the run time and the query file. `python -m settlemark check` fails if a required result is missing or if its SQL changed after the result was produced.

| Key | SQL | Result | Status |
|---|---|---|---|
| 01 | `queries/01_receipt_actions_daily.sql` | `receipt_actions_daily.csv` | committed, run 2026-11-14 in the console, about 174 GB scanned |
| 04 | `queries/04_intents_weekly.sql` | `04_intents_weekly.csv` | waiting for its first run |
| 05 | `queries/05_weekly_activity.sql` | `05_weekly_activity.csv` | waiting for its first run; when it lands, the lead and lag test adds BigQuery weekly signers and transactions automatically |

Queries 04 and 05 use fixed dates (2024-12-09 to the week ending 2026-11-08), so a rerun returns the same rows.

## Refreshing

* API: `pip install google-cloud-bigquery`, `gcloud auth application-default login`, then `python -m settlemark bigquery 05 --dry-run` to see the scan size, and `python -m settlemark bigquery 05` (or `all`, or `npm run bigquery`). It refuses any query above `max_gb` in `settlemark.toml` (400 GB), so the free 1 TB a month is not exceeded by accident.
* Console: open the SQL file, paste it in the BigQuery console, check the "This query will process" estimate, run it, download the result as CSV, then `python -m settlemark bigquery-import 05 ~/Downloads/results.csv --scanned-gb 123.4 --run-at 2026-11-15T06:00:00Z`. The importer checks the columns and writes the same files the API path writes.

Then `npm run build && npm test` and commit `data/bigquery/` with the outputs.

Notes: `block_timestamp` is INT64 nanoseconds, so convert with `TIMESTAMP_MICROS(DIV(block_timestamp, 1000))`. Filter on `block_date`, but expect large scans: the 7 day query 01 still read about 174 GB.
