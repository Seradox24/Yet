# Yet Analytics SQL LRS — despliegue productivo

Despliegue reproducible de SQL LRS `v0.9.7` con PostgreSQL `16.15`, preparado para operar detrás del Nginx del host.

SQL LRS se publica exclusivamente en loopback. PostgreSQL permanece dentro de la red Docker y no expone ningún puerto al host.

## Requisitos

- Servidor Linux `amd64`.
- Docker Engine con Docker Compose v2.
- Nginx instalado en el host.
- DNS y certificado TLS para el dominio público.
- `curl` para las comprobaciones.

## Preparación

```bash
cp .env.example .env.prod
chmod 600 .env.prod
```

Editar `.env.prod` y reemplazar todos los valores `GENERATE_ME` y `example.com`. El archivo está ignorado por Git y nunca debe versionarse.

Se pueden generar valores aleatorios con:

```bash
openssl rand -base64 36 | tr -d '\n'
```

## Despliegue

```bash
chmod +x scripts/deploy.sh scripts/check.sh
./scripts/deploy.sh
./scripts/check.sh
```

El despliegue valida el Compose, descarga las imágenes, inicia los servicios y muestra su estado.

## Nginx del host

1. Copiar `nginx/yet-lrsql.conf.example` a la configuración del host.
2. Reemplazar `lrs.example.com` y las rutas de certificados.
3. Confirmar que el puerto coincide con `LRSQL_HTTP_PORT`.
4. Validar y recargar:

```bash
sudo nginx -t
sudo systemctl reload nginx
```

No se debe recargar Nginx cuando `nginx -t` falla.

## Accesos

- Administración: `https://lrs.example.com/admin`
- Endpoint xAPI: `https://lrs.example.com/xapi`

Reemplazar el dominio por el configurado en el servidor.

## Operación

```bash
docker compose --env-file .env.prod ps
docker compose --env-file .env.prod logs --tail 100
docker compose --env-file .env.prod up -d
docker compose --env-file .env.prod down
```

`down` conserva el volumen de PostgreSQL. No ejecutar `down --volumes` en producción.

La prueba ampliada de escritura y lectura puede ejecutarse con PowerShell:

```powershell
pwsh -NoProfile -File ./scripts/smoke-test.ps1 -WriteStatement
```

## Persistencia

PostgreSQL utiliza el volumen `yet-lrsql-postgres-data`. El respaldo y la restauración deben definirse y probarse antes de almacenar información real.
