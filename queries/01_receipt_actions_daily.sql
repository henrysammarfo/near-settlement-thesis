-- Receipt actions per day on NEAR mainnet, last 7 days. Run in the BigQuery sandbox (no billing).
-- Scanned about 174 GB on 2026-11-14. Result saved to data/bigquery/receipt_actions_daily.csv
SELECT DATE(TIMESTAMP_MICROS(DIV(block_timestamp, 1000))) AS day, COUNT(*) AS receipt_actions
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date >= DATE '2026-11-08'
GROUP BY day ORDER BY day
