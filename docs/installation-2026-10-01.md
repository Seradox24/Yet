# Instalación real — 1 de octubre de 2026

## Entorno y rutas

VPS `147.93.132.78`, Linux x86_64, Docker Engine 29.8.1, Compose 5.5.1.
Antes del arranque: puerto 18083 libre, aproximadamente 86 GB de disco y
6 GB de RAM disponibles. Moodle y Keycloak ya funcionaban en 18080 y 18081.

- Clon: `/srv/plataforma/servicios/svc-lrsql/`.
- Secretos: `/srv/plataforma/secretos/servicios/svc-lrsql.env`, permisos 600.
- `.env.prod`: enlace al archivo anterior.
- PostgreSQL: bind mount `/srv/plataforma/datos/servicios/svc-lrsql/postgres/`.
- Respaldos: `/srv/plataforma/respaldos/svc-lrsql/`.
- Logs privados: `/srv/plataforma/operaciones/svc-lrsql/`.
- Nginx: `/etc/nginx/sites-available/lrs.minayao.site`, enlazado en sites-enabled.
- URL: `https://lrs.minayao.site/admin`; API: `https://lrs.minayao.site/xapi`.
- Usuario administrador: `minayao.work@gmail.com`. Contraseña y claves xAPI
  permanecen en el archivo privado y no se registran en Git ni documentación pública.

Se siguió el README del repositorio y se contrastó en vivo con
`/srv/plataforma/servicios/README.md`. No se modificaron proyectos Moodle o Keycloak.

## Correcciones para próximos servidores

1. El README previo describía datos en volumen Docker y secretos dentro del clon.
   La convención real exige datos y secretos centralizados. Se agregó
   `POSTGRES_DATA_PATH`, conservando el volumen como valor predeterminado para
   no cambiar instalaciones existentes. Se añadió `initialize-server.sh`.
2. `stat -c` comprueba permisos del enlace, no del destino. El preflight usa
   `stat -Lc` para aceptar correctamente `.env.prod` enlazado a un archivo 600.
3. Nginx avisó que `listen ... http2` está obsoleto. La plantilla usa ahora
   `listen 443 ssl` y `http2 on`, compatible con Nginx 1.25.1 o posterior.
4. La renovación ACME necesita conservar una ubicación HTTP para webroot.
   Se agregó la ruta `/.well-known/acme-challenge/` antes de la redirección HTTPS.
5. Los archivos transferidos desde Windows deben tener finales LF. Se normalizaron
   los archivos editados antes de copiarlos; el clon Git ya aplica `.gitattributes`.

## Resultados

- Descarga de ambas imágenes fijadas por digest: correcta.
- Preflight con secretos centralizados y bind mount: correcto.
- `deploy.sh`: PostgreSQL y SQL LRS saludables; lectura autenticada por loopback correcta.
- Durante el arranque hubo healthchecks con conexión rechazada antes de que la
  aplicación abriera su puerto; se recuperaron dentro del tiempo de espera.
  No fueron fallos persistentes de instalación.
- Certificado Let's Encrypt emitido para el dominio; expiración 30-12-2026.
- Renovación simulada y deploy hook de recarga Nginx: correctos. El hook se
  instaló en `/etc/letsencrypt/renewal-hooks/deploy/20-reload-nginx-lrs.sh` y
  actúa únicamente cuando se renueva el dominio LRS. El temporizador Certbot
  está activo. Para pruebas manuales se usó `--no-random-sleep-on-renew`:
  sin esa bandera Certbot añadió una espera aleatoria de 405 segundos.
- `nginx -t` y recarga: correctos.
- La plantilla corregida pasó `nginx -t` sin el aviso de HTTP/2.
- Administración desde un equipo externo al VPS: HTTP 200 por HTTPS.
- Login administrativo HTTPS y respuesta CORS para el origen configurado: correctos.
- POST/GET HTTPS xAPI 1.0.3 y 2.0.0: correctos. Se conservaron dos statements
  de comprobación con actividad `urn:svc-lrsql:installation-check`.
- Petición a statements sin credenciales: rechazada con HTTP 401.
- Primer dump PostgreSQL generado (30 900 bytes, permisos 600); su índice
  es legible con `pg_restore --list`. Esto no equivale a ensayar restauración.
- Moodle y Keycloak continuaron saludables tras la instalación.

Guía sin credenciales creada en
`/srv/plataforma/documentacion/contenido/servicios/svc-lrsql.md`. No se recompiló
ni publicó automáticamente el sitio Astro.

Logs del servidor: `install-2026-10-01.log`, `nginx-2026-10-01.log` y
`verification-2026-10-01.log` dentro de la carpeta privada de operaciones.
No habilitar trazas shell (`set -x`) al generar o leer secretos.

## Pendientes operativos

Integración con Moodle/Keycloak, rotación de claves, automatización de respaldos
externos y ensayo de restauración aislado. El despliegue del LRS por sí solo
no envía registros desde Moodle. Mantener estos pendientes separados del
resultado positivo de arranque y las pruebas HTTP/xAPI realizadas.
