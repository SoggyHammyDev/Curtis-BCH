#!/bin/sh
set -eu
CONF=/data/bitcoin.conf
mkdir -p /data
touch "$CONF"

set_conf() {
  key="$1"; value="$2"
  if grep -q "^${key}=" "$CONF"; then
    sed -i "s|^${key}=.*|${key}=${value}|" "$CONF"
  else
    printf '%s=%s\n' "$key" "$value" >> "$CONF"
  fi
}

set_conf server 1
set_conf txindex 0
set_conf rpcuser "${BCH_RPC_USER:-bch}"
set_conf rpcpassword "${BCH_RPC_PASS:?BCH_RPC_PASS is required}"
set_conf rpcallowip "0.0.0.0/0"
set_conf rpcbind "0.0.0.0"
set_conf rpcport 28332
set_conf port 28333
set_conf zmqpubhashblock "tcp://0.0.0.0:28334"
ensure_conf() {
  key="$1"; value="$2"
  if ! grep -q "^${key}=" "$CONF"; then
    printf '%s=%s\n' "$key" "$value" >> "$CONF"
  fi
}
ensure_conf prune "${PRUNE_MIB:-5500}"
ensure_conf dbcache "${DBCACHE_MIB:-1024}"
ensure_conf maxmempool "${MAX_MEMPOOL_MIB:-128}"
ensure_conf rpcthreads "${RPC_THREADS:-8}"

exec bitcoind -datadir=/data -printtoconsole
