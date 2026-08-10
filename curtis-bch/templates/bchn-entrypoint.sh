#!/bin/sh
set -eu

DATADIR=/data
CONF="$DATADIR/bitcoin.conf"

mkdir -p "$DATADIR"

# Ensure required runtime values exist. Preserve user-tuned settings.
ensure_conf() {
  key="$1"
  value="$2"
  if ! grep -q "^${key}=" "$CONF" 2>/dev/null; then
    printf '%s=%s\n' "$key" "$value" >> "$CONF"
  fi
}

touch "$CONF"
ensure_conf server 1
ensure_conf rpcuser "${BCH_RPC_USER:-bch}"
ensure_conf rpcpassword "${BCH_RPC_PASS}"
ensure_conf rpcallowip "0.0.0.0/0"
ensure_conf rpcbind "0.0.0.0"
ensure_conf rpcport 28332
ensure_conf port 28333
ensure_conf zmqpubhashblock "tcp://0.0.0.0:28334"
ensure_conf prune 5500
ensure_conf dbcache 1024
ensure_conf maxmempool 128
ensure_conf rpcthreads 8

exec bitcoind -datadir="$DATADIR" -printtoconsole
