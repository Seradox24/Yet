#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

test -f .env.prod || { echo "Falta .env.prod" >&2; exit 1; }
env_value() { sed -n "s/^$1=//p" .env.prod | tail -n 1; }
http_port="$(env_value LRSQL_HTTP_PORT)"
api_key="$(env_value LRSQL_API_KEY)"
api_secret="$(env_value LRSQL_API_SECRET)"
test -n "$http_port" && test -n "$api_key" && test -n "$api_secret" || {
  echo "Faltan variables obligatorias en .env.prod" >&2
  exit 1
}

docker compose --env-file .env.prod config --quiet
docker compose --env-file .env.prod ps
base_url="http://127.0.0.1:${http_port}"
curl --fail --silent --show-error "${base_url}/admin" >/dev/null
curl --fail --silent --show-error \
  -u "${api_key}:${api_secret}" \
  -H 'X-Experience-API-Version: 1.0.3' \
  "${base_url}/xapi/about" >/dev/null
echo "SQL LRS responde correctamente por loopback."
