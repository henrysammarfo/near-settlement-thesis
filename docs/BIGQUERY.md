# The BigQuery path (optional, run by hand)

The one command rebuild uses free APIs only. The NEAR BigQuery public dataset is a second, independent check. It runs in the free BigQuery sandbox (no billing, 1 TB of scanning a month), but a 7 day query scans about 174 GB, so we keep queries short and run them by hand in the console.

* `queries/01_receipt_actions_daily.sql`: run on 2026-11-14, result in `data/bigquery/receipt_actions_daily.csv`.
* `queries/02_intents_receipts_daily.sql` and `queries/03_intents_signers_daily.sql`: ready to run; results not yet included. Column names follow the public schema; if the console rejects a column, check the table schema first.

Notes: `block_timestamp` is INT64 nanoseconds, so convert with `TIMESTAMP_MICROS(DIV(block_timestamp, 1000))`. Filter on `block_date` to limit the scan. Save results as CSV in `data/bigquery/` with the query file name in the `source_url` column.

## Runner

`python -m settlemark bigquery 04 --max-gb 400` runs `queries/04_intents_weekly.sql` (weekly receipts and senders reaching `intents.near`, the same weeks as `data/near_rpc.csv`). It needs `pip install google-cloud-bigquery` and `gcloud auth application-default login`. It always dry runs first and refuses to start a query above `--max-gb`, then writes `data/bigquery/04_intents_weekly.csv` with the scan size in every row. It is not part of the one command rebuild; the raw chain series there comes from archival RPC, which needs no account.
