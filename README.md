# Curtis BCH — Umbrel Fixed Build 0.1.4

0.1.4 fixes the first-launch JavaScript errors from the full UI redesign.

## Fixes
- Backend version now honors `APP_VERSION` instead of serving legacy `0.9.18`.
- Added a compatibility DOM layer for legacy controller IDs used by `app.js`.
- Guarded direct event bindings against missing optional UI controls.
- Added a bridge for redesigned payout/inactive-worker controls.
- Keeps the 0.1.3 Umbrel networking fixes:
  - Web UI `24781`
  - Stratum `6387`
  - BCH P2P `28447`
  - unique proxy target `curtis-bch-app`
  - BCH RPC `28332`
  - BCH ZMQ `28334`
  - explicit CKPool config startup

The GitHub workflow publishes `ghcr.io/soggyhammydev/curtis-bch-app:0.1.4` and `latest`.
