# The BigQuery path (optional, run by hand)

The one command rebuild uses free APIs only. The NEAR BigQuery public dataset is a second, independent check. It runs in the free BigQuery sandbox (no billing, 1 TB of scanning a month), but a 7 day query scans about 174 GB, so we keep queries short and run them by hand in the console.

* `queries/01_receipt_actions_daily.sql`: run on 2026-11-14, result in `data/bigquery/receipt_actions_daily.csv`.
* `queries/02_intents_receipts_daily.sql` and `queries/03_intents_signers_daily.sql`: ready to run; results not yet included. Column names follow the public schema; if the console rejects a column, check the table schema first.

Notes: `block_timestamp` is INT64 nanoseconds, so convert with `TIMESTAMP_MICROS(DIV(block_timestamp, 1000))`. Filter on `block_date` to limit the scan. Save results as CSV in `data/bigquery/` with the query file name in the `source_url` column.
