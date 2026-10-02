# Yet Analytics SQL LRS — despliegue de la plataforma

SQL LRS `v0.9.7` con PostgreSQL `16.15`. Las imágenes están fijadas por digest.
El proyecto contiene el servicio, sus scripts y la configuración inicial; puede
instalarse con Docker Compose en cualquier host Linux compatible. El backend se
publica en loopback y PostgreSQL no expone puertos; Nginx del host termina HTTPS.
El puerto interno de SQL LRS es `8080`.

## Estructura de referencia

La plataforma usa `/srv/plataforma/` como estructura central. Yet ocupa las
siguientes rutas:

```text
/srv/plataforma/
├── servicios/svc-lrsql/                  # clon de este repositorio
│   ├── compose.yaml
│   ├── .env.example
│   ├── .env.prod                         # enlace al archivo privado
│   ├── nginx/
│   └── scripts/
├── secretos/servicios/svc-lrsql.env      # privado, permisos 600
├── datos/servicios/svc-lrsql/postgres/   # persistencia de PostgreSQL
├── respaldos/svc-lrsql/                  # dumps privados
└── operaciones/svc-lrsql/                # registros privados de operación
```

Se conservan el proyecto Compose `yet-lrsql`, la red `yet-lrsql-internal` y el
volumen `yet-lrsql-postgres-data`; la carpeta del clon no cambia estos nombres.
Sin `POSTGRES_DATA_PATH`, los datos viven en el volumen Docker; en la estructura
central se usa un bind mount a `datos/servicios/svc-lrsql/postgres/`. No cambiar
de volumen a bind mount en una instalación existente sin migrar los datos.
No copiar el clon ni `.env.prod` a la documentación publicada.

## Requisitos e instalación

Linux amd64, Bash 4+, Docker Engine, Compose v2.20+ (o v5) con `up --wait`,
Git, curl, OpenSSL y Nginx 1.25.1+ del host (la plantilla usa `http2 on`).
El dominio y el certificado se definen en cada entorno. El usuario operador
debe tener acceso a Docker.

```bash
sudo install -d -o "$USER" -g "$(id -gn)" /srv/plataforma/servicios/svc-lrsql
git clone --branch main --single-branch https://github.com/Seradox24/Yet.git /srv/plataforma/servicios/svc-lrsql
cd /srv/plataforma/servicios/svc-lrsql
bash scripts/initialize-server.sh https://DOMINIO-LRS USUARIO-ADMIN
```

El destino de `git clone` debe estar vacío. Si existe una instalación, usar la
actualización descrita abajo sin borrar configuración ni datos. Reemplazar los
argumentos por el dominio público y el usuario administrador definitivos. El
script genera secretos independientes, prepara datos, respaldos y operaciones,
y crea `.env.prod` como enlace a `/srv/plataforma/secretos/servicios/svc-lrsql.env`.
Requiere permisos sobre esas rutas y rechaza sobrescribir configuraciones.
Para una instalación fuera de esta convención, copiar `.env.example` como
`.env.prod`, aplicar `chmod 600` y reemplazar `GENERATE_ME` y `example.com`.
Generar cada secreto por separado con `openssl rand -hex 32` (mínimo 32
caracteres). Usar líneas `KEY=value` sin comillas, espacios ni comentarios al final.

| Variable | Uso |
| --- | --- |
| `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD` | Base propia de SQL LRS |
| `LRSQL_ADMIN_USER`, `LRSQL_ADMIN_PASSWORD` | Cuenta administrativa inicial |
| `LRSQL_API_KEY`, `LRSQL_API_SECRET` | Credenciales xAPI iniciales |
| `LRSQL_HTTP_PORT` | Puerto loopback del host; la plantilla usa `18083` |
| `LRSQL_PUBLIC_URL` | Origen HTTPS público, sin ruta ni barra final |
| `LRSQL_LOG_LEVEL` | Nivel de logs, predeterminado `INFO` |
| `POSTGRES_DATA_PATH` | Opcional: directorio absoluto para PostgreSQL; omitir para usar el volumen nombrado |

La URL pública configura CORS y la URL de autoridad. No habilitar todos los
orígenes para resolver problemas del proxy; un consumidor desde otro origen de
navegador requiere una lista explícita y el envío entre servidores no necesita
CORS. No hay integración automática con Moodle o Keycloak.

Las variables `*_DEFAULT` inicializan cuentas y claves: cambiar el archivo no
constituye un procedimiento de rotación. Cambiar `POSTGRES_PASSWORD` con un
volumen existente tampoco modifica la contraseña almacenada en PostgreSQL.

## Validación e inicio

Ejecutar desde el clon:

```bash
bash scripts/preflight.sh       # valida configuración y Docker; no inicia servicios
ss -ltn '( sport = :18083 )'    # ajustar al puerto configurado; no debe haber listener
bash scripts/deploy.sh
```

El despliegue descarga las imágenes, espera hasta 240 segundos a que los
servicios estén saludables y verifica la administración y la lectura autenticada
de statements por loopback. Si falla, revisar los logs: no elimina
automáticamente datos ni contenedores. Todas las órdenes Compose deben incluir
`--env-file .env.prod`.

## Nginx del host

1. Elegir dominio, configurar DNS y obtener el certificado según el
   procedimiento del entorno antes de habilitar el bloque TLS. Para Certbot
   webroot, habilitar primero un bloque HTTP con la ubicación
   `/.well-known/acme-challenge/` de la plantilla y raíz `/var/www/html`,
   todavía sin el bloque TLS. Luego ejecutar
   `sudo certbot certonly --webroot -w /var/www/html -d <dominio-lrs>`.
   Configurar un deploy hook que ejecute `nginx -t && systemctl reload nginx`
   tras cada renovación y comprobar con
   `sudo certbot renew --cert-name <dominio-lrs> --dry-run --run-deploy-hooks --no-random-sleep-on-renew`.
2. Adaptar `nginx/yet-lrsql.conf.example`: dominio, certificados y puerto.
   Deben coincidir con `LRSQL_PUBLIC_URL` y `LRSQL_HTTP_PORT`.
3. Copiar a `/etc/nginx/sites-available/<dominio-lrs>` y enlazar desde
   `/etc/nginx/sites-enabled/<dominio-lrs>` sin reemplazar otros sitios.
4. Ejecutar `sudo nginx -t`; solo si pasa, `sudo systemctl reload nginx`.

La plantilla redirige HTTP a HTTPS y conserva las rutas sin reescritura. No
abrir el puerto loopback en el firewall. Administración:
`https://<dominio-lrs>/admin`; xAPI: `https://<dominio-lrs>/xapi`. Validar el
login y la API por HTTPS: la salud interna no demuestra que DNS, TLS ni el
proxy funcionen.

## Operación y actualización

```bash
cd /srv/plataforma/servicios/svc-lrsql
docker compose --env-file .env.prod ps
docker compose --env-file .env.prod logs --tail 100
bash scripts/check.sh
```

Antes de actualizar, respaldar PostgreSQL y registrar `git rev-parse HEAD`.
Luego ejecutar `git pull --ff-only` y `bash scripts/deploy.sh`. Revisar cambios
de versión y migraciones antes de actualizar imágenes; volver a una revisión
Git anterior no revierte migraciones de datos.
`docker compose --env-file .env.prod down` conserva el volumen; no utilizar
`down --volumes` ni limpiezas globales de Docker.

Prueba opcional con PowerShell 7 desde el clon y un equipo con acceso al endpoint:

```powershell
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public -WriteStatement
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -Public -XapiVersion 2.0.0
```

Sin `-Public`, prueba el loopback del equipo donde se ejecuta. La versión
predeterminada es `1.0.3`; SQL LRS admite también `2.0.0`. `-WriteStatement`
agrega un evento persistente: utilizar primero una instalación de prueba.

Los registros de cada despliegue y el estado de las comprobaciones se conservan
fuera del repositorio, en la documentación operativa del servidor.

## Respaldo

Ejemplo manual desde el clon:

```bash
umask 077
mkdir -p /srv/plataforma/respaldos/svc-lrsql
docker compose --env-file .env.prod exec -T postgres sh -c 'pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -Fc' > /srv/plataforma/respaldos/svc-lrsql/lrsql-$(date -u +%Y%m%dT%H%M%SZ).dump
```

Confirmar el éxito y el tamaño del dump, copiarlo fuera del servidor y guardar
`.env.prod` por un canal privado. Ensayar `pg_restore` en una base aislada antes
de almacenar datos reales; no restaurar sobre la base activa. Automatización,
retención y restauración verificada quedan para la operación del servidor.

## Referencias

- [Configuración oficial v0.9.7](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/env_vars.md).
- [Docker oficial](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/docker.md).
- [Versiones xAPI](https://github.com/yetanalytics/lrsql/blob/v0.9.7/doc/xapi_versioning.md).
