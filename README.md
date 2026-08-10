# Curtis BCH 0.1.5

Self-contained Curtis BCH Umbrel build.

- UI: 24781
- Stratum: 6387
- BCH P2P: 28447
- BCH RPC (internal): 28332
- BCH ZMQ (internal): 28334

The GitHub workflow builds three SoggyHammyDev GHCR images:
- curtis-bch-app
- curtis-bch-bchn
- curtis-bch-ckpool

BCHN is packaged from the official Bitcoin Cash Node release binaries.
CKPool is compiled from upstream open-source source code.

Before installing, let all three GitHub Actions matrix jobs complete and make all three GHCR packages public.
