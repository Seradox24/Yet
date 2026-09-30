# Yet Analytics SQL LRS — despliegue de la plataforma

SQL LRS `v0.9.7` con PostgreSQL `16.15`. Las imágenes están fijadas por digest.
Nginx del host termina HTTPS y envía a `127.0.0.1:18083`; PostgreSQL no publica
puertos. El puerto interno de SQL LRS sigue siendo `8080`.

## Estructura del servidor

La documentación actual del VPS utiliza `/srv/plataforma/`. Para Yet se adopta
la siguiente ruta, pendiente de crear durante la futura instalación:

```text
/srv/plataforma/
├── servicios/
│   ├── svc-keycloak/          # existente
│   └── svc-lrsql/             # clon de este repositorio
│       ├── compose.yaml
│       ├── .env.example
│       ├── .env.prod          # privado, permisos 600
│       ├── nginx/
│       └── scripts/
├── moodle/                   # existente, independiente
├── documentacion/
│   ├── contenido/
│   └── public/               # sitio compilado; sin secretos ni respaldos
└── respaldos/
    └── svc-lrsql/            # dumps privados
```

No seguir las rutas históricas `/opt/lms/` de las guías originales de Moodle.
El puerto propuesto `18083` corresponde a la reserva histórica para LRS y es
independiente de Moodle (`18080`) y Keycloak (`18081`). Confirmar que esté libre
antes del primer arranque: no se comprobó su disponibilidad en vivo.

Se conservan proyecto Compose `yet-lrsql`, red `yet-lrsql-internal` y volumen
`yet-lrsql-postgres-data`. La carpeta del clon no cambia estos nombres.
Los datos activos viven en el volumen Docker, fuera del repositorio. No copiar
el clon completo ni `.env.prod` a `documentacion/public/`.

## Requisitos y preparación futura

Linux amd64, Bash 4+, Docker Engine, Compose v2.20+ (o v5) con `up --wait`,
Git, curl, OpenSSL y Nginx del host. Dominio y certificado propios pendientes
de definir. El usuario operador debe tener acceso a Docker.

```bash
sudo install -d -o "$USER" -g "$(id -gn)" /srv/plataforma/servicios/svc-lrsql
git clone --branch main --single-branch https://github.com/Seradox24/Yet.git /srv/plataforma/servicios/svc-lrsql
cd /srv/plataforma/servicios/svc-lrsql
umask 077
cp .env.example .env.prod
chmod 600 .env.prod
```

El destino de `git clone` debe estar vacío. Si existe una instalación, utilizar
la actualización descrita abajo sin borrar configuración ni volumen.
Reemplazar todos los valores `GENERATE_ME` y `example.com`. Generar cada secreto
por separado con `openssl rand -hex 32` (mínimo 32 caracteres).
Usar líneas `KEY=value` sin comillas, espacios ni comentarios al final.

| Variables | Uso |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base propia de SQL LRS |
| `LRSQL_ADMIN_USER`, `LRSQL_ADMIN_PASSWORD` | Cuenta administrativa inicial |
| `LRSQL_API_KEY`, `LRSQL_API_SECRET` | Credenciales xAPI iniciales |
| `LRSQL_HTTP_PORT` | Puerto loopback del host, propuesto `18083` |
| `LRSQL_PUBLIC_URL` | Origen HTTPS público, sin ruta ni barra final |
| `LRSQL_LOG_LEVEL` | Nivel de logs, predeterminado `INFO` |

La URL pública configura CORS y la URL de autoridad. No habilitar todos los
orígenes para resolver problemas del proxy. Un futuro consumidor desde otro
origen de navegador requerirá una lista explícita; el envío entre servidores
no necesita CORS. No hay integración automática con Moodle o Keycloak.

Las variables `*_DEFAULT` inicializan cuentas y claves; cambiar el archivo
no constituye un procedimiento de rotación. Cambiar `POSTGRES_PASSWORD` con
un volumen existente tampoco modifica la contraseña almacenada en PostgreSQL.

## Validación y levantamiento futuro

Ejecutar desde el clon:

```bash
bash scripts/preflight.sh       # valida configuración y Docker; no inicia servicios
ss -ltn '( sport = :18083 )'    # antes del primer arranque, no debe haber listener
bash scripts/deploy.sh
```

El despliegue descarga imágenes, espera hasta 240 segundos a que los servicios
estén saludables y verifica administración y lectura autenticada de statements
por loopback. Si falla, revisar logs: no elimina automáticamente datos ni
contenedores. Todas las órdenes Compose deben incluir `--env-file .env.prod`.

## Nginx del host

1. Elegir dominio, configurar DNS y obtener el certificado mediante el
   procedimiento del servidor antes de habilitar el bloque TLS.
2. Adaptar `nginx/yet-lrsql.conf.example`: dominio, certificados y puerto.
   Deben coincidir con `LRSQL_PUBLIC_URL` y `LRSQL_HTTP_PORT`.
3. Copiar a `/etc/nginx/sites-available/<dominio-lrs>` y enlazar desde
   `/etc/nginx/sites-enabled/<dominio-lrs>` sin reemplazar otros sitios.
4. Ejecutar `sudo nginx -t`; solo si pasa, `sudo systemctl reload nginx`.

La plantilla redirige HTTP a HTTPS y conserva las rutas sin reescritura.
No abrir `18083` en el firewall. Administración: `https://<dominio-lrs>/admin`;
xAPI: `https://<dominio-lrs>/xapi`. Validar login y API por HTTPS: la salud interna
no demuestra que DNS, TLS ni el proxy funcionen.

## Operación y actualización

```bash
cd /srv/plataforma/servicios/svc-lrsql
docker compose --env-file .env.prod ps
docker compose --env-file .env.prod logs --tail 100
bash scripts/check.sh
```

Antes de actualizar, respaldar PostgreSQL y registrar `git rev-parse HEAD`.
Luego ejecutar `git pull --ff-only` y `bash scripts/deploy.sh`. Revisar cambios
de versión y migraciones antes de actualizar imágenes. Volver a una revisión
Git anterior no revierte migraciones de datos.
`docker compose --env-file .env.prod down` conserva el volumen.
No utilizar `down --volumes` ni limpiezas globales de Docker.

Prueba opcional con PowerShell 7 desde el clon y un equipo con acceso al endpoint:

```powershell
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public -WriteStatement
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public -XapiVersion 2.0.0
```

Sin `-Public`, prueba loopback del equipo donde se ejecuta. La versión
predeterminada es `1.0.3`; SQL LRS admite también `2.0.0`. `-WriteStatement`
agrega un evento persistente: utilizar primero una instalación de prueba.

## Respaldo

Ejemplo manual desde el clon:

```bash
umask 077
mkdir -p /srv/plataforma/respaldos/svc-lrsql
docker compose --env-file .env.prod exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /srv/plataforma/respaldos/svc-lrsql/lrsql-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Confirmar éxito y tamaño del dump, copiarlo fuera del VPS y guardar `.env.prod`
por un canal privado. Ensayar `pg_restore` en una base aislada antes de almacenar
datos reales; no restaurar encima de la base activa. Automatización, retención
y restauración verificada quedan para la operación del servidor.

## Fuentes y validación

- [Configuración oficial v0.9.7](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/env_vars.md).
- [Docker oficial](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/docker.md).
- [Versiones xAPI](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/xapi_versioning.md).
- Estructura contrastada con la copia local de
  `documentacion/docsite Dev/diagramas/estado-servidor-2026-09-30.md` y
  `src/data/platform.ts`. Es una instantánea; no una nueva inspección SSH.

Revisión del 30-09-2026: Compose, sintaxis de scripts y manifests de imágenes
verificados. El motor Docker local no está disponible: arranque, migraciones,
salud real, escritura xAPI y Nginx/TLS quedan pendientes del ensayo en servidor.
El repositorio queda preparado; su funcionamiento en ejecución aún no está certificado.

El preflight se ensayó con datos ficticios y Docker/permisos simulados: acepta
una configuración válida y rechaza valores de ejemplo, puerto inválido, URL
con ruta, variables duplicadas, secretos cortos y expansión shell. La búsqueda
de valores de ejemplo ignora comentarios para no bloquear la plantilla ya editada.
