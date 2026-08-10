# Curtis BCH — Umbrel Community App Store

This package turns the full Curtis BCH UI revamp into an Umbrel community-store repository.

## Included
- Umbrel store manifest
- `curtis-bch/umbrel-app.yml`
- Umbrel `docker-compose.yml`
- BCHN + CKPool + Curtis BCH app stack
- First-boot BCHN/CKPool configuration
- Persistent node, pool, UI, and settings data
- Umbrel sync + pool widgets
- GHCR build/publish workflow for the Curtis BCH web image

## Publish/install
1. Put these files at the root of your GitHub repository.
2. Push to `main`.
3. GitHub Actions builds `ghcr.io/akacurtis/curtis-bch-app:0.1.0`.
4. In GitHub Packages, make the `curtis-bch-app` package public.
5. Add that GitHub repository as a Community App Store in Umbrel.
6. Install **Curtis BCH**.

Dashboard is exposed by Umbrel on app port `24781`.
Miners connect to `stratum+tcp://YOUR_UMBREL_IP:6387`.

## Existing BCH data
This app uses its own Umbrel app ID (`curtis-bch`), so a fresh install gets a new app-data directory. Do not delete an existing AxeBCH/BCH app until you have copied or backed up any node/pool state you want to preserve.

## Images
The node/pool image tags mirror the BCH stack previously observed working on the Umbrel host:
- `ghcr.io/willitmod/bitcoin-cash-node:v29.0.0-wm2`
- `ghcr.io/willitmod/wim-solo-ckpool:0.8.3-rc1-590fb2a`

The Curtis BCH dashboard image is built from `curtis-bch/web/` by the included GitHub Actions workflow.


## Assigned ports
- Web UI: `24781`
- Mining / Stratum: `6387`
