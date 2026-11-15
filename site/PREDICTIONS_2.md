# Settlemark predictions, set 2: bolder calls

Frozen 2026-11-15T05:43:57Z from data to 2026-11-13. Set 2, frozen after the hackathon deadline of 2026-11-14 23:59 UTC and before the first scored week began on 2026-11-16. Machine readable copy: `data/predictions_2.json`, sha256 `0d93f3f38b6e04d5bf3fdf7eddff80709568f871e8cdcae60da789dbacbedb3a` (canonical JSON, sorted keys). The hashes of both sets are anchored on NEAR testnet; see `data/anchors.json` and `python -m settlemark anchor verify`.

Set 1 ([PREDICTIONS.md](PREDICTIONS.md)) was frozen at 00:24 UTC on 2026-11-15, also after the deadline. Neither set is evidence the judges could see at the deadline; both are commitments that will be scored in public either way.

| ID | Claim | What is measured | Pass if | Threshold | Window ends | Our probability |
|---|---|---|---|---|---|---|
| P9 | Intents volume keeps compounding | mean weekly NEAR Intents volume, weeks ending 2026-11-22 to 2027-01-10 | >= (at least 1.1x the mean of the last 4 weeks at freeze) | $945,654,567 | 2027-01-10 | 0.40 |
| P10 | Intents sets a new share high | mean weekly Intents share of all DEX volume, weeks ending 2026-11-22 to 2027-01-10 | >= (at least the mean of the latest 13 weeks at freeze) | 1.4586% | 2027-01-10 | 0.50 |
| P11 | Intents carries half of all router volume | Intents share of the combined volume of the 5 routers in data/peers, 2026-11-16 to 2027-01-10 | >= (at least 50% (47.7% in the 91 days to freeze)) | 50% | 2027-01-10 | 0.45 |
| P12 | NEAR stays far pricier per revenue dollar than router tokens | NEAR market cap over annualised Intents revenue, divided by the median of the same ratio for routers with a token, 2026-11-16 to 2027-01-10 | >= (at least 5x (15.1x in the 91 days to freeze)) | 5x | 2027-01-10 | 0.85 |
| P13 | The base chain does not recover | mean NearBlocks daily active accounts, weeks ending 2026-11-22 to 2027-01-10 | < (below 1.4x the mean of the latest 13 weeks at freeze) | 99,221 accounts | 2027-01-10 | 0.80 |
| P14 | Buybacks scale up | same ratio as P5 | >= (at least 25%, above the last 13 weeks at freeze (18.7%)) | 25% | 2027-01-10 | 0.30 |

If P9, P10 and P11 all miss, the claim that Intents is still gaining ground is rejected.

If P12 misses, NEAR is no longer priced far above router tokens on revenue and part 2 weakens.
