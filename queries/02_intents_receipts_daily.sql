-- Receipt actions sent to the NEAR Intents contract per day, last 7 days.
SELECT block_date AS day, COUNT(*) AS intents_actions
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date >= DATE '2026-11-08' AND receipt_receiver_account_id = 'intents.near'
GROUP BY day ORDER BY day
