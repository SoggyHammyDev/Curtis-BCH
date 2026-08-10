#!/bin/sh
set -eu

CONF=/data/bitcoin.conf
mkdir -p /data
touch "$CONF"

set_conf() {
  key="$1"
  value="$2"
  if grep -Fq "${key}=" "$CONF"; then
    awk -v k="$key" -v v="$value" '
      BEGIN { done=0 }
      index($0, k "=") == 1 && !done { print k "=" v; done=1; next }
      { print }
      END { if (!done) print k "=" v }
    ' "$CONF" > "$CONF.tmp"
    mv "$CONF.tmp" "$CONF"
  else
    printf '%s=%s\n' "$key" "$value" >> "$CONF"
  fi
}

ensure_conf() {
  key="$1"
  value="$2"
  if ! grep -Fq "${key}=" "$CONF"; then
    printf '%s=%s\n' "$key" "$value" >> "$CONF"
  fi
}

# Remove legacy unscoped network-only settings. BCHN rejects these on Testnet4.
sed -i \
  -e '/^port=/d' \
  -e '/^rpcport=/d' \
  -e '/^rpcbind=/d' \
  -e '/^zmqpubhashblock=/d' \
  "$CONF"

set_conf server 1
set_conf txindex 0
set_conf rpcuser "${BCH_RPC_USER:-bch}"
set_conf rpcpassword "${BCH_RPC_PASS:?BCH_RPC_PASS is required}"
set_conf rpcallowip "0.0.0.0/0"
set_conf disablewallet 1

# Same internal ports on both chains.
set_conf main.port 28333
set_conf test4.port 28333
set_conf main.rpcport 28332
set_conf test4.rpcport 28332
set_conf main.rpcbind "0.0.0.0"
set_conf test4.rpcbind "0.0.0.0"
set_conf main.zmqpubhashblock "tcp://0.0.0.0:28334"
set_conf test4.zmqpubhashblock "tcp://0.0.0.0:28334"

ensure_conf prune "${PRUNE_MIB:-5500}"
ensure_conf dbcache "${DBCACHE_MIB:-1024}"
ensure_conf maxmempool "${MAX_MEMPOOL_MIB:-128}"
ensure_conf rpcthreads "${RPC_THREADS:-8}"

exec bitcoind -datadir=/data -printtoconsole
