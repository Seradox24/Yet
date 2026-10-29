#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec python3 "$repo_dir/scripts/stt.py" "$@" verify
