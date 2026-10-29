#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if (( $# != 4 )); then
  echo 'Uso: initialize-server.sh https://dominio usuario-admin raiz-absoluta proyecto-compose' >&2
  exit 1
fi
exec python3 "$repo_dir/scripts/stt.py" init --url "$1" --admin "$2" --root "$3" --project "$4"
