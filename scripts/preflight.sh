#!/usr/bin/env bash
set -Eeuo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
for tool in docker curl stat; do
  command -v "$tool" >/dev/null || { echo "Falta $tool" >&2; exit 1; }
done
docker compose version >/dev/null
test -f .env.prod || { echo "Falta .env.prod" >&2; exit 1; }
test "$(stat -Lc '%a' .env.prod)" = 600 || { echo "Aplique chmod 600 al archivo de secretos" >&2; exit 1; }
if grep -Eq '^[A-Z][A-Z0-9_]*=.*(GENERATE_ME|example\.com)' .env.prod; then
  echo ".env.prod todavía contiene valores de ejemplo." >&2
  exit 1
fi
# Leer datos sin ejecutar el archivo como código shell.
declare -A values=()
while IFS= read -r line || [[ -n "$line" ]]; do
  [[ "$line" =~ ^[[:space:]]*$ || "$line" =~ ^[[:space:]]*# ]] && continue
  if [[ ! "$line" =~ ^([A-Z][A-Z0-9_]*)=([a-zA-Z0-9_:/.,@%+=-]+)$ ]]; then
    echo "Use KEY=value sin comillas, espacios ni caracteres de expansión." >&2
    exit 1
  fi
  key="${BASH_REMATCH[1]}"
  [[ ! -v "values[$key]" ]] || { echo "Variable duplicada: $key" >&2; exit 1; }
  values[$key]="${BASH_REMATCH[2]}"
done < .env.prod
for key in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD LRSQL_ADMIN_USER LRSQL_ADMIN_PASSWORD LRSQL_API_KEY LRSQL_API_SECRET LRSQL_HTTP_PORT LRSQL_PUBLIC_URL; do
  [[ -n "${values[$key]:-}" ]] || { echo "Falta $key" >&2; exit 1; }
done
[[ "${values[LRSQL_HTTP_PORT]}" =~ ^[1-9][0-9]{0,4}$ ]] && (( values[LRSQL_HTTP_PORT] <= 65535 )) || {
  echo "LRSQL_HTTP_PORT debe ser un puerto válido." >&2; exit 1;
}
[[ "${values[LRSQL_PUBLIC_URL]}" =~ ^https://[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || {
  echo "LRSQL_PUBLIC_URL debe ser un origen HTTPS sin ruta ni barra final." >&2; exit 1;
}
for key in POSTGRES_PASSWORD LRSQL_ADMIN_PASSWORD LRSQL_API_KEY LRSQL_API_SECRET; do
  (( ${#values[$key]} >= 32 )) || { echo "$key requiere al menos 32 caracteres." >&2; exit 1; }
done
if [[ -n "${values[POSTGRES_DATA_PATH]:-}" ]]; then
  [[ "${values[POSTGRES_DATA_PATH]}" = /* && -d "${values[POSTGRES_DATA_PATH]}" ]] || {
    echo "POSTGRES_DATA_PATH debe ser un directorio absoluto existente." >&2; exit 1;
  }
fi
docker compose --env-file .env.prod config --quiet
docker info >/dev/null
echo "Configuración válida; no se iniciaron servicios."
