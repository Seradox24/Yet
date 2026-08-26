# Ambiente Yet Analytics

## Objetivo

Levantar y evaluar un ambiente aislado de **Yet Analytics** utilizando Docker, documentando su instalación, configuración, operación y resultados.

## Estado actual

- Estado: ambiente operativo y validado
- Ambiente levantado: sí
- Docker configurado: sí
- Fecha de inicio: 2026-08-20

## Implementación actual

El ambiente está definido en `compose.yaml` con estos componentes:

| Servicio | Imagen | Exposición |
|---|---|---|
| `lrsql` | `yetanalytics/lrsql:v0.9.7` | `127.0.0.1:8080` por defecto |
| `postgres` | `postgres:16-alpine` | Solo red interna de Compose |

El servicio `lrsql` espera a que el `healthcheck` de PostgreSQL indique que la base de datos está disponible. Ambos servicios tienen comprobaciones de salud y los datos se guardan en el volumen nombrado `yet-lrsql-postgres-data`.

## Imagen seleccionada

- Imagen: `yetanalytics/lrsql`
- Versión propuesta: `v0.9.7`
- Registro: [Docker Hub](https://hub.docker.com/r/yetanalytics/lrsql)
- Código fuente: [GitHub](https://github.com/yetanalytics/lrsql)
- Licencia: Apache 2.0
- Arquitectura publicada: `linux/amd64`
- Tamaño comprimido aproximado: 142 MB

Se propone fijar la versión `v0.9.7` en lugar de utilizar `latest`. Al momento del análisis, ambas etiquetas apuntan al mismo digest, pero una versión fija evita actualizaciones inesperadas durante las pruebas.

## Análisis de la imagen

SQL LRS es un Learning Record Store de código abierto basado en SQL. La imagen publicada por Yet Analytics:

- Expone HTTP en el puerto `8080` y HTTPS en el puerto `8443`.
- Sirve la interfaz administrativa en `/admin`.
- Sirve los recursos xAPI bajo el prefijo `/xapi`.
- Arranca con SQLite mediante `/lrsql/bin/run_sqlite.sh` de forma predeterminada.
- Permite usar PostgreSQL mediante `/lrsql/bin/run_postgres.sh`.
- Admite configuración con variables `LRSQL_*` o mediante `config/lrsql.json`.
- Permite montar `/lrsql/config` para certificados, configuración JSON y plantillas de autoridad.

La imagen está construida sobre Alpine Linux y contiene un runtime de Java generado a partir de OpenJDK 21.

## Alternativas de levantamiento

### Opción A: SQLite

Es la opción más simple y requiere un solo contenedor. Para conservar la base de datos se debe montar un volumen en `/lrsql/db` y configurar:

```text
LRSQL_DB_NAME=db/lrsql.sqlite.db
```

Es útil para una prueba rápida, pero no será el ambiente principal porque limita la evaluación de concurrencia, operación y separación entre aplicación y base de datos.

### Opción B: PostgreSQL — recomendada

Utiliza dos contenedores:

```text
Navegador / cliente xAPI
          |
          v
SQL LRS :8080  --->  PostgreSQL :5432
```

Ventajas:

- Se aproxima mejor a un despliegue real.
- Mantiene la base de datos separada del LRS.
- Facilita revisar persistencia, consultas y respaldos.
- PostgreSQL está soportado oficialmente por SQL LRS.

El repositorio incluye un `docker-compose.yml` de demostración con PostgreSQL y ClamAV. No conviene copiarlo sin ajustes: utiliza etiquetas no fijadas, credenciales de ejemplo, publica PostgreSQL al host y solo declara `depends_on`, sin comprobar que la base esté lista.

## Diseño propuesto para el laboratorio

- SQL LRS: `yetanalytics/lrsql:v0.9.7`
- Base de datos: `postgres:16-alpine`; la documentación actual admite PostgreSQL 14 a 18
- Puerto publicado del LRS: `8080:8080`
- Puerto de PostgreSQL: únicamente interno, sin publicarlo al host inicialmente
- Persistencia: volumen nombrado para PostgreSQL
- Configuración sensible: archivo `.env` local
- Plantilla segura: archivo `.env.example` sin secretos reales
- Inicio: `docker compose up -d`
- Espera de base de datos: `healthcheck` de PostgreSQL y dependencia saludable
- Reinicio: política `unless-stopped`
- ClamAV: fuera de la primera fase; se incorporará al probar adjuntos

## Variables mínimas previstas

| Variable | Propósito |
|---|---|
| `LRSQL_ADMIN_USER_DEFAULT` | Usuario administrador inicial |
| `LRSQL_ADMIN_PASS_DEFAULT` | Contraseña del administrador inicial |
| `LRSQL_API_KEY_DEFAULT` | Identificador inicial para la API xAPI |
| `LRSQL_API_SECRET_DEFAULT` | Secreto inicial para la API xAPI |
| `LRSQL_DB_HOST` | Nombre del servicio PostgreSQL en Compose |
| `LRSQL_DB_PORT` | Puerto interno de PostgreSQL; por defecto `5432` |
| `LRSQL_DB_NAME` | Base de datos utilizada por SQL LRS |
| `LRSQL_DB_USER` | Usuario de PostgreSQL |
| `LRSQL_DB_PASSWORD` | Contraseña de PostgreSQL |
| `LRSQL_POOL_INITIALIZATION_FAIL_TIMEOUT` | Tiempo de espera inicial por PostgreSQL |

Las credenciales iniciales se utilizan para sembrar las tablas de cuentas y credenciales. No deben quedar escritas directamente en `compose.yaml` ni reutilizar los valores de ejemplo oficiales.

## Accesos previstos

- Administración: `http://localhost:8080/admin`
- Endpoint base xAPI: `http://localhost:8080/xapi`
- PostgreSQL: accesible solo desde la red interna de Compose

El primer laboratorio utilizará HTTP únicamente en `localhost`. HTTPS, certificados y proxy inverso quedan fuera de esta fase.

## Alcance inicial

- Identificar el producto o repositorio de Yet Analytics que se utilizará.
- Revisar sus requisitos y componentes.
- Diseñar un ambiente Docker reproducible.
- Definir puertos, volúmenes, variables de entorno y credenciales locales.
- Levantar y validar el servicio.
- Registrar pruebas, problemas encontrados y soluciones.

## Decisiones pendientes

- Producto exacto: Yet Analytics SQL LRS
- Repositorio: `yetanalytics/lrsql`
- Imagen Docker: `yetanalytics/lrsql:v0.9.7`
- Base de datos: PostgreSQL 16 Alpine
- Persistencia de datos: volumen nombrado de PostgreSQL
- Puerto local inicial: `8080`
- Método de autenticación inicial: administrador local y credencial xAPI
- ClamAV: pendiente para una fase posterior

## Estructura prevista

```text
yet/
├── README.md
├── compose.yaml           # Servicios SQL LRS y PostgreSQL
├── .env.example           # Plantilla sin secretos reales
├── .env                   # Configuración local; ignorada por Git
├── .gitignore
├── scripts/
│   └── smoke-test.ps1     # Verificación HTTP y xAPI
└── config/                # Futuro: JSON, certificados o autoridad
```

## Plan de trabajo

1. Investigar las alternativas de Yet Analytics y seleccionar una. **Completado**
2. Confirmar requisitos y compatibilidad con Docker. **Completado**
3. Seleccionar la versión de PostgreSQL y diseñar `compose.yaml`. **Completado**
4. Preparar variables de entorno de ejemplo. **Completado**
5. Levantar el ambiente. **Completado**
6. Ejecutar pruebas básicas de funcionamiento. **Completado**
7. Documentar resultados y conclusiones. **En curso**

## Registro de avances

### 2026-08-20

- Se creó este documento de seguimiento.
- Se analizó la imagen `yetanalytics/lrsql` y la documentación oficial.
- Se seleccionó `v0.9.7` como versión inicial propuesta.
- Se recomendó un ambiente de SQL LRS con PostgreSQL.
- Se decidió postergar ClamAV, HTTPS y proxy inverso para fases posteriores.
- Se creó `compose.yaml` con SQL LRS v0.9.7 y PostgreSQL 16 Alpine.
- Se agregó un `healthcheck` para evitar que el LRS arranque antes que PostgreSQL.
- Se crearon `.env.example` y `.gitignore`; no se generaron secretos reales.
- Docker Compose está instalado y su configuración fue validada.

### 2026-08-20 — levantamiento inicial

- Se inició Docker Desktop y se descargaron las imágenes seleccionadas.
- Se creó `.env` con credenciales aleatorias exclusivas del laboratorio. El archivo permanece ignorado por Git.
- Se levantaron SQL LRS y PostgreSQL mediante Docker Compose.
- PostgreSQL quedó operativo en la versión `16.15` y no publica su puerto al host.
- Se añadió un `healthcheck` HTTP al contenedor SQL LRS.
- Se creó `scripts/smoke-test.ps1` para repetir las verificaciones.
- Se validó la persistencia reiniciando ambos servicios y recuperando el mismo Statement.

## Comandos

### 1. Preparar las variables locales

En PowerShell, desde esta carpeta:

```powershell
Copy-Item -LiteralPath .env.example -Destination .env
```

Editar `.env` y reemplazar todos los valores que comienzan con `reemplazar_`. El archivo `.env` está excluido por `.gitignore`.

### 2. Validar la configuración

```powershell
docker compose config
```

### 3. Levantar el ambiente

Este paso todavía no se ha ejecutado:

```powershell
docker compose up -d
```

### 4. Revisar el estado y los registros

```powershell
docker compose ps
docker compose logs -f lrsql
```

### 5. Ejecutar pruebas rápidas

La comprobación de lectura valida la interfaz administrativa y `/xapi/about`:

```powershell
pwsh -NoProfile -File .\scripts\smoke-test.ps1
```

Para crear un Statement de prueba y recuperarlo inmediatamente:

```powershell
pwsh -NoProfile -File .\scripts\smoke-test.ps1 -WriteStatement
```

### 6. Detener el ambiente

```powershell
docker compose down
```

Este comando conserva el volumen de PostgreSQL. No utilizar `docker compose down -v` salvo que se quiera eliminar deliberadamente toda la información del laboratorio.

## Problemas y soluciones

- El Compose oficial es explícitamente una demostración y no espera a que PostgreSQL esté saludable. Nuestro diseño agregará un `healthcheck`.
- La imagen de Docker Hub solo muestra `linux/amd64`. En equipos ARM podría requerir emulación; se debe comprobar la arquitectura antes de levantarla.
- Usar `latest` hace que el ambiente pueda cambiar sin modificar archivos locales. Se utilizará una etiqueta versionada.
- Durante el inicio, SQL LRS crea un certificado autofirmado porque no se proporcionaron certificados propios. HTTPS no está publicado al host en esta fase.
- Los registros muestran advertencias de funciones obsoletas de Pedestal incluidas en SQL LRS v0.9.7. No impidieron el arranque ni las pruebas funcionales.

## Resultados de pruebas

| Prueba | Resultado |
|---|---|
| Validación de `compose.yaml` | Correcta |
| Salud de PostgreSQL | `healthy` |
| Salud de SQL LRS | `healthy` |
| Conexión SQL LRS → PostgreSQL | Correcta |
| `GET /admin` | HTTP `200` |
| `GET /xapi/about` | xAPI `2.0.0` y `1.0.3` |
| Crear y recuperar un Statement | Correcta |
| Persistencia después de reiniciar servicios | Correcta |

Statement utilizado para comprobar la persistencia:

```text
2264fcfb-21bd-4658-a307-1ad862fea8ac
```
