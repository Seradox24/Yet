#!/usr/bin/env bash
# Preparación para la convención /srv/plataforma; no arranca servicios.
set -Eeuo pipefail
repo_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_dir"
if (( $# != 2 )) || [[ ! "$1" =~ ^https://[a-zA-Z0-9]([a-zA-Z0-9.-]*[a-zA-Z0-9])?$ ]] || [[ ! "$2" =~ ^[a-zA-Z0-9_.@+-]+$ ]]; then
  echo "Uso: bash scripts/initialize-server.sh https://dominio usuario-admin" >&2
  exit 1
fi
command -v openssl >/dev/null
secret_file=/srv/plataforma/secretos/servicios/svc-lrsql.env
data_dir=/srv/plataforma/datos/servicios/svc-lrsql/postgres
test ! -e "$secret_file" && test ! -e .env.prod && test ! -L .env.prod || {
  echo "Ya existe configuración; no se reemplazó." >&2; exit 1;
}
umask 077
install -d -m 700 /srv/plataforma/secretos/servicios /srv/plataforma/respaldos/svc-lrsql /srv/plataforma/operaciones/svc-lrsql
install -d "$data_dir"
{
  printf 'POSTGRES_DB=lrsql\nPOSTGRES_USER=lrsql\nPOSTGRES_PASSWORD=%s\n' "$(openssl rand -hex 32)"
  printf 'LRSQL_ADMIN_USER=%s\nLRSQL_ADMIN_PASSWORD=%s\n' "$2" "$(openssl rand -hex 32)"
  printf 'LRSQL_API_KEY=%s\nLRSQL_API_SECRET=%s\n' "$(openssl rand -hex 32)" "$(openssl rand -hex 32)"
  printf 'LRSQL_HTTP_PORT=18083\nLRSQL_LOG_LEVEL=INFO\nLRSQL_PUBLIC_URL=%s\nPOSTGRES_DATA_PATH=%s\n' "$1" "$data_dir"
} > "$secret_file"
chmod 600 "$secret_file"
ln -s "$secret_file" .env.prod
echo "Configuración privada creada; los secretos no se muestran."
