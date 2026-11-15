-- Weekly NEAR mainnet transactions and distinct signing accounts, weeks starting Monday.
-- Fixed dates (2024-12-09 to the week ending 2026-11-08, the last full week of the thesis window), so a rerun
-- returns the same rows. Reads two columns of one table. Dry run first: `python -m settlemark bigquery 05 --dry-run`.
SELECT DATE_TRUNC(block_date, WEEK(MONDAY)) AS week_start,
       COUNT(*) AS transactions,
       COUNT(DISTINCT signer_account_id) AS signers
FROM `bigquery-public-data.crypto_near_mainnet_us.transactions`
WHERE block_date >= DATE '2024-12-09' AND block_date < DATE '2026-11-09'
GROUP BY week_start
ORDER BY week_start
