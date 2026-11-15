# Settlemark predictions, written down before the data exists

Frozen 2026-11-15T00:24:38Z from data to 2026-11-13. Machine readable copy: `data/predictions.json`, sha256 `2c2ec155b5202d02bbb5c59f9714dd7b452f4564fd5e38f990c33c16e6136af3` (canonical JSON, sorted keys). The git commit that added this file is its timestamp; `tests/test_predictions.py` fails if the file changes.

Weeks end on Sunday, UTC. Scoring waits two days after each window for sources to publish, then runs `python -m settlemark predictions --score`. Misses are published like hits. The probability is ours, stated now, so the Brier score can grade our calibration.

| ID | Claim | What is measured | Pass if | Threshold | Window ends | Our probability |
|---|---|---|---|---|---|---|
| P1 | Usage holds whatever the price does | mean weekly NEAR Intents volume, weeks ending 2026-11-22 to 2026-12-13 | >= (at least 50% of the mean of the last 4 weeks at freeze) | $429,842,985 | 2026-12-13 | 0.85 |
| P2 | Intents keeps its share of onchain trading | mean weekly Intents share of all DEX volume, weeks ending 2026-11-22 to 2027-01-10 | >= (at least the mean of the 13 weeks before the latest 13 at freeze) | 1.0331% | 2027-01-10 | 0.70 |
| P3 | Usage does not simply follow price | correlation of weekly log changes, Intents volume against NEAR price, 8 weeks ending 2027-01-10 | <= (at most 0.5, the line THESIS.md already uses) | 0.5 | 2027-01-10 | 0.60 |
| P4 | Holders still capture little | NEAR market cap on 2027-01-10 over Intents revenue in the 364 days to that date | >= (at least 50x, the F5 line) | 50x | 2027-01-10 | 0.90 |
| P5 | Buybacks do not offset new supply | NEAR gained by buybacks.multisignature.near over NEAR added to total supply, blocks at 2026-11-16 and 2027-01-11 00:00 UTC | < (below 50%) | 50% | 2027-01-10 | 0.90 |
| P6 | Buybacks keep running at a real pace | same ratio as P5 | >= (at least 10%, a bit over half of the last 13 weeks at freeze (18.7%)) | 10% | 2027-01-10 | 0.75 |
| P7 | State inside Intents keeps growing | intents.near storage in bytes at the 2027-01-11 block over the 2026-11-16 block | >= (at least 1.05x (the last 52 weeks grew 3.98x)) | 1.05x | 2027-01-10 | 0.85 |
| P8 | Revenue does not collapse | Intents revenue in the 28 days ending 2026-12-13 | >= (at least half of the 91 day run rate at freeze, scaled to 28 days) | $806,057 | 2026-12-13 | 0.85 |

If P1 and P2 both miss, part 1 of the thesis (usage independent of price) is rejected.

If P4 or P5 misses, part 2 (holders capture little) is rejected and the case turns bullish.
