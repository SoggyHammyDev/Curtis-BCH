# Curtis BCH 0.1.8

Pool-settings repair release.

- Visible "Save payout address" button now POSTs directly to `/api/pool/settings`.
- Visible save status now reports success/failure instead of writing to a hidden compatibility element.
- Pool Settings is payout-address only for now.
- Automatically migrates stale CKPool RPC `bchn:8332` to `bchn:28332`.
- Refreshes CKPool RPC credentials from the current Umbrel app password.
- Adds current BCHN ZMQ endpoint `tcp://bchn:28334`.
- Removes unsupported CKPool `-B` startup flag.
- Preserves any real payout address already configured.
- Keeps wallet disabled, Mainnet/Testnet4 support, IPv4 miner connection card, sync display and prune persistence fixes.

After saving a payout address, restart Curtis BCH so CKPool reloads `ckpool.conf`.
