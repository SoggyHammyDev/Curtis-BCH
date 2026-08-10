#!/bin/sh
set -eu
rm -f /tmp/ckpool/*.pid 2>/dev/null || true
exec /usr/local/bin/ckpool -k -L -c /config/ckpool.conf
