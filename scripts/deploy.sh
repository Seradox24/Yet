#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

if [[ ! -f .env.prod ]]; then
  echo "Falta .env.prod. Copie .env.example, complete sus valores y aplique chmod 600." >&2
  exit 1
fi

if grep -Eq 'GENERATE_ME|example\.com' .env.prod; then
  echo ".env.prod todavía contiene valores de ejemplo." >&2
  exit 1
fi

docker compose --env-file .env.prod config --quiet
docker compose --env-file .env.prod pull
docker compose --env-file .env.prod up -d
docker compose --env-file .env.prod ps
