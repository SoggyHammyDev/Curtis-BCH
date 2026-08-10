# Curtis BCH — Umbrel Fixed Build 0.1.3

This build follows the known-working AxeBCH BCHN/CKPool startup pattern from the user's Umbrel.

## Ports
- Web UI: `24781`
- Mining / Stratum: `6387`
- BCH P2P host port: `28447` -> container `28333`

## Fixes in 0.1.3
- Proxy now targets unique hostname `curtis-bch-app`, eliminating the shared `app` alias routing collision.
- BCHN upgraded to `ghcr.io/willitmod/bitcoin-cash-node:v29.0.0-wm3`.
- Added BCHN entrypoint and RPC/ZMQ setup on `28332` / `28334`.
- CKPool now explicitly starts with `ckpool -k -B -L -c /config/ckpool.conf`.
- CKPool config is mounted read-only, matching the proven working stack.
- CKPool uses `bchn:28332` and `tcp://bchn:28334`.
- Stratum remains on host port `6387`.
- P2P remains on host port `28447` to avoid the existing AxeBCH node on `28333`.

## First boot
CKPool requires a payout address. If no Curtis BCH payout address has been saved yet, CKPool may stop cleanly until a valid address is configured. The web app and BCHN can still start; after setting the payout address, restart Curtis BCH from Umbrel.

## GitHub
The included workflow publishes:
`ghcr.io/soggyhammydev/curtis-bch-app:0.1.0`

Make the GHCR package public.
