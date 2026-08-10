# Curtis BCH 0.1.9

Testnet4 + persistent pool settings repair.

- Fixes BCHN Testnet4 startup by network-scoping port/rpcport/rpcbind/ZMQ.
- Mainnet and Testnet4 both use internal RPC 28332, P2P 28333, ZMQ 28334.
- Fixes GET /api/settings returning 400.
- Keeps separate Mainnet and Testnet4 payout/difficulty profiles.
- Restores Minimum / Starting / Maximum difficulty fields.
- Presets populate custom fields; manual changes are supported.
- Saves payout + diff settings together.
- Uses native `bitcoincash:` / `bchtest:` CashAddr with BCH-native EloPool.
- Keeps wallet disabled and prune as the only exposed BCHN tuning setting.
- Uses official BCHN 29.1.0 binaries and EloPool v1.0.0-stable.

After changing network or pool settings, restart Curtis BCH from Umbrel.
