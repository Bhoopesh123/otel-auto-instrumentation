#!/bin/sh
set -eu

cd "$(dirname "$0")/.."

printf '%s\n' 'Building and starting the shopping stack…'
docker compose up --build -d

printf '%s\n' 'Waiting for the shop and Grafana to pass their health checks…'
docker compose exec -T shop python - <<'PY'
import time
from urllib.error import URLError
from urllib.request import urlopen

pending = {
    "Shop": "http://127.0.0.1:8000/health",
    "Grafana": "http://grafana:3000/api/health",
}
deadline = time.monotonic() + 90

while pending and time.monotonic() < deadline:
    for name, url in list(pending.items()):
        try:
            with urlopen(url, timeout=2) as response:
                if response.status == 200:
                    print(f"{name} health check passed.", flush=True)
                    del pending[name]
        except (URLError, TimeoutError):
            continue
    if pending:
        time.sleep(1)

if pending:
    raise SystemExit(f"Health check timed out for {', '.join(pending)}. See docker compose logs.")
PY

shop_address=$(docker compose port shop 8000)
grafana_address=$(docker compose port grafana 3000)
printf '\nShop:    http://localhost:%s\n' "${shop_address##*:}"
printf 'Grafana: http://localhost:%s\n' "${grafana_address##*:}"
