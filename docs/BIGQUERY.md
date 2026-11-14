# Optional path: NEAR BigQuery public dataset

We did not run these, because BigQuery bills the query runner and we had no billing account. The free path (DefiLlama, NearBlocks, CoinGecko) produced every number in THESIS.md. With billing set up, these queries would cross check chart 5. Always filter on block_date to keep cost down.

```sql
-- Daily transactions and distinct signers, last 365 days
SELECT block_date, COUNT(*) AS txns, COUNT(DISTINCT signer_account_id) AS signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
GROUP BY block_date ORDER BY block_date;

-- Daily receipts sent to the Intents contract
SELECT block_date, COUNT(*) AS intents_receipts
FROM `bigquery-public-data.crypto_near_mainnet_us.receipt_actions`
WHERE block_date >= DATE_SUB(CURRENT_DATE(), INTERVAL 365 DAY)
  AND receiver_account_id = 'intents.near'
GROUP BY block_date ORDER BY block_date;
```
