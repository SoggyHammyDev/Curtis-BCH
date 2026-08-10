# Curtis BCH 0.1.7

New in 0.1.7:
- Permanently disables the BCHN wallet (`disablewallet=1`).
- Adds Mainnet / Testnet4 switching in Node Settings.
- Testnet4 uses BCHN's network-specific data directory, keeping mainnet data separate.
- Adds a Connect a Miner dashboard card.
- Auto-detects the dashboard request's IPv4 address for the Stratum URL when available.
- Shows Stratum URL, username pattern, password, and copy buttons.

Ports:
- UI 24781
- Stratum 6387
- BCH P2P host 28447
- BCH RPC internal 28332

After changing Mainnet/Testnet4, restart Curtis BCH from Umbrel.
Use a `bchtest:` payout address for Testnet4.
