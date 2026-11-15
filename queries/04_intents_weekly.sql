-- Weekly receipts and distinct senders reaching intents.near, the same weeks as data/near_rpc.csv.
-- Fixed dates (2024-12-09 to the week ending 2026-11-08) so a rerun returns the same rows.
-- Senders are mostly solvers and relayers, not end users: read it as contract activity, not people.
SELECT DATE_TRUNC(block_date, WEEK(MONDAY)) AS week_start,
       COUNT(*) AS intents_receipts,
       COUNT(DISTINCT receipt_predecessor_account_id) AS senders
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date >= DATE '2024-12-09' AND block_date < DATE '2026-11-09'
  AND receipt_receiver_account_id = 'intents.near'
GROUP BY week_start
ORDER BY week_start
