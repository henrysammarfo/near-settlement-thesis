# THESIS: NEAR is becoming a settlement layer, and its token has not caught up

Every number below is computed by `scripts/build.py` from the CSV files in `data/` and written into this file by `scripts/render.py`. Each linked number points at the public API it came from. Data fetched {fetched}. Window: {start} to {end} ({weeks} full weeks). Not financial advice.

## The claim

NEAR Intents has turned NEAR into a cross chain settlement layer whose usage grows on its own, independent of the NEAR price. The long term case for NEAR rests on that flow. The weak point today is that the token captures very little of it.

Two parts, tested separately:

1. **Usage is independent of price.** If Intents were just NEAR speculation, its weekly volume would rise and fall with the NEAR price. We expect it not to.
2. **Value capture is small.** The flow is large next to the fees that reach the network and its holders.

## Evidence for

- Weekly NEAR Intents volume went from {iv0} a week (first 4 weeks) to {iv1} a week (last 4 weeks). Over the same span the NEAR price went from {p0} to {p1}. ![chart 1](charts/01_volume_vs_price.png)
- Intents share of all onchain DEX volume tracked by DefiLlama: {share0} in the first 13 weeks, {share1} in the 13 weeks before the latest, {share2} in the latest 13 weeks. ![chart 2](charts/02_share_of_dex_volume.png)
- Correlation between weekly changes in Intents volume and weekly NEAR price changes is {corr} over {weeks} weeks (90% bootstrap interval {ci}). That is close to zero. ![chart 3](charts/03_weekly_changes_scatter.png)
- Neither leads the other: last week's NEAR price change against this week's Intents change gives {lag1}, and the reverse gives {lag2}.
- It is not just crypto beta either: correlation of weekly Intents changes with Bitcoin weekly returns is {btc} over {wbtc} weeks. It does follow the overall DEX market somewhat ({dexc}), which is what a settlement venue should do.
- Over the last 365 days Intents settled {iv365} and charged {fee365} in total fees.

## Evidence against

- **Holders capture little.** Over the last 365 days the Intents protocol kept {rev365} as revenue (about {bps} basis points of volume; all fees were {fbps} basis points). NEAR chain gas fees were {chain365}. NEAR's market cap is {mcap}: {mrev} yearly Intents revenue and {mchain} yearly chain fees. ![chart 4](charts/04_value_capture.png)
- **Levels point the wrong way for holders.** The correlation of log weekly Intents volume with log NEAR price is {lvl}: usage grew while the price fell. Usage alone has not supported the price.
- **The base chain shrank while Intents grew.** NearBlocks daily active accounts averaged {aa0} in the first 13 weeks of the window and {aa1} in the latest 13 weeks. Part of that drop may be bot or airdrop traffic leaving, and relayed signers are undercounted, but it is not the picture of a busier chain. Weekly changes correlate {aa} with price changes. ![chart 5](charts/05_active_accounts.png)
- **Stablecoins on NEAR shrank:** {st0} a year ago, {st1} now. A settlement layer for money should hold more dollars, not fewer. ![chart 6](charts/06_stablecoins.png)
- Volume counts can flatter. DefiLlama may count both legs or confidential flow; another entry in this track, [near-thesis](https://github.com/soldanoandrea/near-thesis), found public swaps match only part of DefiLlama's reported volume on sampled days. Our share numbers inherit that.

## What would change our mind

These tests are fixed in `scripts/build.py`. They were written on 2026-11-14, the day of the analysis, so they are not a pre registration made weeks in advance. Met: {met} of {nf}.

| Falsifier | Test | Result now |
|---|---|---|
{fals}

We would also change our mind if Intents share of DEX volume falls for two quarters in a row, if the weekly correlation with NEAR price rises above 0.5 over any 26 week window, or if a fee switch or buyback raises holder capture so that market cap falls below 50x yearly revenue (that would make the case bullish rather than conditional).

## Verdict

Part 1 is supported by this data: Intents usage moves independently of the NEAR price and has taken a growing share of onchain DEX volume. Part 2 is also supported, and it is the bear case: the token captures a small slice of that flow, stablecoins on NEAR shrank, and the base chain shows no matching growth. NEAR is a long term buy only if value capture improves. Watch the revenue line in chart 4, not the price.

## Limits

- Free public APIs only: DefiLlama, NearBlocks and CoinGecko. The NEAR BigQuery dataset and the Intents Explorer API were not used (BigQuery needs Google Cloud billing; the Explorer needs a partner token). `docs/BIGQUERY.md` gives the optional queries.
- Correlations of weekly changes over about two years are noisy. The early Intents weeks are tiny, so log changes there are large.
- NearBlocks active accounts can miss signers hidden behind relayers.
- CoinGecko's free tier gives 365 days, so the Bitcoin test covers fewer weeks than the NEAR test.
- If a source changes its methodology, rerunning `make rebuild` changes the numbers. That is intended: nothing here is frozen by hand.
