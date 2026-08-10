#!/usr/bin/env sh
set -eu
python3 - <<'PY'
import yaml
for p in ['umbrel-app-store.yml','curtis-bch/umbrel-app.yml','curtis-bch/docker-compose.yml']:
    with open(p, encoding='utf-8') as f: yaml.safe_load(f)
    print('OK', p)
PY
docker compose -f curtis-bch/docker-compose.yml config >/dev/null
echo "Curtis BCH Umbrel package validates."
