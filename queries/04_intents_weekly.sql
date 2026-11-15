-- Weekly receipts and distinct senders reaching intents.near, the same weeks as data/near_rpc.csv.
-- Partition filter on block_date keeps the scan to the receipt_actions columns used. Run with
-- `python -m settlemark bigquery 04 --max-gb 400` (dry run first; refuses above the limit).
SELECT DATE_TRUNC(block_date, WEEK(MONDAY)) AS week_start,
       COUNT(*) AS intents_receipts,
       COUNT(DISTINCT receipt_predecessor_account_id) AS senders
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date >= DATE '2024-12-09' AND receipt_receiver_account_id = 'intents.near'
GROUP BY week_start ORDER BY week_start
