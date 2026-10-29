# Yet Analytics SQL LRS — instalación independiente

SQL LRS **0.9.11**, PostgreSQL **16.15-alpine3.24**, imágenes por digest y
Compose propio. El backend escucha solo en loopback; Nginx del host termina
HTTPS. No requiere Moodle, AuthSom ni carpetas de otros sistemas.

## Instalación nueva

Linux amd64, Python 3.10+, Git, Docker Engine/Compose con `up --wait`, Nginx
1.25.1+ y Certbot. No se necesita instalar librerías Python ni compilar upstream.
Revisar el cambio en rama/PR, transferir un bundle y clonar su rama explícita o
revisión exacta en la carpeta de servicio del destino. La VPS no necesita remoto,
token ni clave GitHub. No sustituir una instalación existente con `init`.

```sh
python3 scripts/stt.py init --root /ruta/plataforma --project proyecto-yet-prod \
  --url https://lrs.dominio.invalid --admin stt-admin --port 18083
python3 scripts/stt.py --env-file /ruta/plataforma/configuraciones/yet/prod/prod.env check
python3 scripts/stt.py --env-file /ruta/plataforma/configuraciones/yet/prod/prod.env up
```

`init` requiere raíz, proyecto y URL explícitos. `--service` y `--environment`
seleccionan el área (predeterminados `yet`, `prod`). Crea únicamente configuración,
secretos, datos, respaldos y registros propios. Rechaza configuración/datos
existentes y puertos ocupados; no inicia contenedores. Nunca imprime secretos.

## Perfil, carga y consumidores

El lanzador acepta un `--env-file` absoluto; sin opción usa `.env.prod` desde la
raíz del repositorio, conservando la entrada anterior. Lee `CLAVE=valor` como
datos sin expansión shell, interpolación ni comillas. Con `SECRET_ROOT`, carga
`SECRET_ROOT/secrets.env`; rechaza duplicados y las opciones administradas
exportadas por la consola. El perfil se valida antes de ejecutar Compose.

Compose recibe los archivos explícitos, valores validados, directorio del
componente y `-p COMPOSE_PROJECT_NAME`. No depende del directorio de la consola.
Los secretos separados contienen exactamente POSTGRES_PASSWORD,
LRSQL_ADMIN_PASSWORD, LRSQL_API_KEY y LRSQL_API_SECRET. En Unix: archivos 0600 y
directorio de secretos 0700. La variante anterior de archivo único sigue admitida.

| Opción | Consumidor y momento |
| --- | --- |
| COMPOSE_PROJECT_NAME | Compose al crear contenedores, red y volumen; sin valor conserva `yet-lrsql` |
| POSTGRES_IMAGE, LRSQL_IMAGE | Compose al desplegar; obligatoriamente versión con digest |
| POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD | Inicialización PostgreSQL y conexión LRS al iniciar |
| POSTGRES_DATA_PATH | Bind mount al desplegar; omitir conserva volumen nombrado |
| LRSQL_ADMIN_USER, LRSQL_ADMIN_PASSWORD | LRSQL_ADMIN_USER_DEFAULT/LRSQL_ADMIN_PASS_DEFAULT; cuenta inicial |
| LRSQL_API_KEY, LRSQL_API_SECRET | LRSQL_API_KEY_DEFAULT/LRSQL_API_SECRET_DEFAULT; credencial xAPI inicial |
| LRSQL_PUBLIC_URL | LRSQL_ALLOWED_ORIGINS y LRSQL_AUTHORITY_URL al iniciar; dominio del generador Nginx |
| LRSQL_HTTP_PORT | Puerto loopback publicado y proxy Nginx; puerto interno 8080 constante |
| LRSQL_LOG_LEVEL | Nivel al iniciar, por defecto INFO |
| POSTGRES_CPUS, POSTGRES_MEMORY | Límites Docker, predeterminados 1 CPU/512m |
| LRSQL_CPUS, LRSQL_MEMORY | Límites Docker, predeterminados 2 CPU/1536m |
| JAVA_TOOL_OPTIONS | JVM al iniciar; heap máximo 60% del límite, inicial 10% |
| SECRET_ROOT | Archivo privado al cargar el perfil |
| BACKUP_ROOT, BACKUP_KEEP | Destino y retención de copias completas; siete por defecto |
| OPS_ROOT | Área privada reservada para evidencia del operador |

Sin proyecto explícito se conservan la red `yet-lrsql-internal` y el volumen
`yet-lrsql-postgres-data`. Otro proyecto utiliza su propio prefijo. No cambiar el
proyecto, bind mount, nombre de base o imágenes de una instalación existente sin
revisar datos, compatibilidad y retorno. `init` no migra ni rota credenciales.
Editar valores DEFAULT o POSTGRES_PASSWORD no cambia cuentas almacenadas.
La rotación se realiza por las interfaces administrativas del servicio y SQL de
la base propia, se actualizan los archivos privados y se verifica por separado.

## Publicación HTTPS

Generar el vhost HTTP con `nginx` y, después del certificado, con `nginx --tls`.
El generador usa el mismo perfil del backend y no instala archivos del host.
ACME utiliza `/var/www/letsencrypt`. Instalar solo el vhost propio y ejecutar
`nginx -t` antes de cada recarga. Solicitar el certificado con Certbot webroot;
conservar el hook de recarga existente y comprobar la renovación simulada con
`--dry-run --run-deploy-hooks --no-random-sleep-on-renew`.

Administración `/admin`, xAPI `/xapi`. El proxy no reescribe rutas y sobrescribe
cabeceras forwarded. PostgreSQL no publica puertos. No abrir el puerto del backend
en UFW. CORS queda limitado al origen público; otros navegadores requieren una
adaptación explícita. No hay conexión automática a Moodle ni OIDC.

```sh
python3 scripts/stt.py --env-file /ruta/absoluta/prod.env verify
python3 scripts/stt.py --env-file /ruta/absoluta/prod.env verify --public
```

Comprueba login real, cierre de sesión, rechazo de claves/contraseñas inválidas,
lectura xAPI 1.0.3/2.0.0 y paginación si hay datos. `verify --write` agrega eventos:
usarlo exclusivamente en instancias desechables. No borra ni modifica statements
existentes. No ejecutar la prueba de escritura contra producción.

Compatibilidad: `preflight.sh`, `deploy.sh` y `check.sh` delegan en el lanzador y
aceptan `--env-file`. `initialize-server.sh URL ADMIN RAIZ PROYECTO` exige ahora
raíz/proyecto explícitos; los dos argumentos antiguos fallan sin crear archivos.
`smoke-test.ps1` admite `-EnvFile` y las opciones anteriores.

## Respaldo y recuperación

`stt.py --env-file PERFIL backup` exige ambos servicios saludables, toma un
bloqueo exclusivo y detiene únicamente LRS. Genera `pg_dump -Fc`, archivo privado
con ambos perfiles, referencias exactas de imágenes, revisión Git y bundle del
código. Reinicia LRS incluso si falla la copia. Solo después de verificar los
checksums completa la copia y aplica retención. Los `.partial` no cuentan como
copias correctas; investigar su causa sin usarlos para recuperación.

`stt.py --env-file PERFIL timer` instala unidades del proyecto para las 04:50
America/Santiago; `--calendar` permite otro horario diario explícito. No sustituye
unidades diferentes. Consultar el journal de `<proyecto>-backup.service`.
Los dumps incluyen cuentas, claves y eventos: conservarlos como secretos.

Restaurar siempre en una raíz nueva y proyecto aislado. Validar SHA256SUMS,
recuperar el bundle y usar exactamente las imágenes de `images.json`. Crear un
perfil con otro puerto/raíces pero el mismo administrador y recuperar sus secretos
desde `private.tar.gz` por canal privado. Leer solo los miembros conocidos
`profile.env` y `secrets.env`; no extraer rutas arbitrarias del archivo.

```sh
python3 scripts/stt.py --env-file /nueva/raiz/perfil.env restore --source /copia/completa
python3 scripts/stt.py --env-file /nueva/raiz/perfil.env verify
```

`restore` rechaza datos no vacíos, un proyecto con contenedores, colisiones,
checksums incorrectos e imágenes diferentes. No restaura sobre la base activa.
Verificar cuentas y statements antes de cambiar el proxy. La recuperación de los
certificados/vhost se hace según la operación del host; sus claves no están en Git.

Antes de actualizar: respaldo correcto y restauración ensayada, revisar cambios
upstream/migraciones, fijar imágenes y revisión nueva. Volver solo a una imagen o
commit no revierte un esquema. Ante fallo, detener el proyecto y deshabilitar su
vhost conservando datos/secretos. Nunca limpiar globalmente Docker ni usar
`down --volumes` en producción. Copiar los respaldos fuera de la VPS sigue siendo
responsabilidad del operador.

## Validación del repositorio

```sh
python3 -m unittest discover -s tests -v
python3 tests/integration.py
```

La segunda prueba crea dos instalaciones Linux desechables con identidades,
raíces, puertos y credenciales distintos. Escribe/lee ambas versiones xAPI,
comprueba persistencia, rechaza acceso cruzado y colisiones, respalda y restaura
en un tercer proyecto. Retira únicamente esos proyectos identificados y sus
volúmenes temporales. Ejecutarla desde cualquier directorio del host de pruebas.

Evidencia STT: `docs/STT_VERIFICACION_2026-10-29.md`. La documentación pública se
entrega como PR independiente de stt-docsite y no se publica por instalar Yet.

## Referencias

- https://github.com/yetanalytics/lrsql/releases/tag/v0.9.11
- https://github.com/yetanalytics/lrsql/compare/v0.9.7...v0.9.11
- https://github.com/yetanalytics/lrsql/blob/v0.9.11/doc/env_vars.md
- https://github.com/yetanalytics/lrsql/blob/v0.9.11/doc/xapi_versioning.md
