#!/usr/bin/env bash
set -Eeuo pipefail

repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"

bash scripts/preflight.sh
docker compose --env-file .env.prod pull
docker compose --env-file .env.prod up -d --wait --wait-timeout 240
bash scripts/check.sh
docker compose --env-file .env.prod ps
