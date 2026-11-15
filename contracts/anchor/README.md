# Anchor contract (NEAR testnet)

A small contract with no SDK and no dependencies. A compiled wasm is not committed in this repo, so we do not claim a byte size here. `anchor` logs its JSON arguments
(prefixed `settlemark anchor `) and stores the latest call under the key `latest`. Settlemark
calls it once with the sha256 of each frozen prediction file, so the hashes sit in a public
transaction with a block time. Verify with `python -m settlemark anchor verify`.

Build: `RUSTFLAGS="-C target-cpu=mvp -C link-arg=-s" cargo build --release --target wasm32-unknown-unknown`
