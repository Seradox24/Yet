# Yet independiente — verificación del 29 de octubre de 2026

Instalación nueva autorizada por el propietario; sin migrar datos ni conectar
Moodle o AuthSom. Se conservan las fuentes locales y el nombre del repositorio.

## Revisión y adaptación

La base `736e366af7ee5a96fc6941834e38020079f7126c` fijaba rutas de otra plataforma
en `initialize-server.sh` y nombres globales en `compose.yaml`. Se sustituyeron
por perfil explícito y recursos derivados de COMPOSE_PROJECT_NAME, conservando
la identidad histórica cuando no se selecciona otra instancia. Los consumidores,
precedencia, bootstrap, compatibilidad y recuperación se documentan en README.

El Compose existente se reutiliza; no se añade otro stack ni se accede a tablas
de otros servicios. Los scripts Bash delegan en Python 3 sin ejecutar el perfil
como shell. Nginx se genera desde el mismo dominio/puerto del backend.

SQL LRS 0.9.11 sustituye 0.9.7 por los cambios de seguridad de upstream;
PostgreSQL permanece en la familia 16, usando el runtime Alpine 3.24.
Imágenes seleccionadas y comprobadas en el registro oficial:

| Imagen | Digest |
| --- | --- |
| yetanalytics/lrsql:v0.9.11 | sha256:bf5661ab216d07175f6e429951bf53c79f6070d54812285ea4c208f991cf0a04 |
| postgres:16.15-alpine3.24 | sha256:0cefaabd882e42bcb2a2f3dc56d3ce4770560ba62fd7f197f1a2e008fd5731ab |

## Pruebas aisladas

La prueba funcional completa pasó sobre `ae94341`, desde `/` en Linux, con dos
proyectos/raíces/puertos/credenciales diferentes y un tercer destino de restauración:

- Escritura y lectura de xAPI 1.0.3/2.0.0, cuatro statements por instancia.
- Login administrativo, cierre de sesión y rechazo de contraseñas/API inválidas.
- Persistencia de los cuatro statements después de reiniciar LRS.
- Rechazo de credenciales cruzadas y de colisiones de puerto y datos.
- Dump consistente, checksums, recuperación con las credenciales originales y
  recuperación de los cuatro statements. Rechazo de restauración sobre datos existentes.
- Retiro de todos los proyectos temporales y sus recursos identificados.

La revisión de instalación `d36e6a4` añade una corrección de inspección de mounts
sin origen y pruebas de fallo de copia/puertos dinámicos. Pasaron **11 pruebas en
Linux**, incluidas configuración ausente, ejemplos, duplicados, expansión,
variables exportadas, permisos, conservación de nombres históricos, aislamiento,
re inicialización, colisión y checksum corrupto. Una copia fallida reinicia LRS y
queda `.partial`, sin retención ni promoción. El reinicio espera salud mediante
`up --wait`; `restart --wait` no existe en el Compose instalado.

## Instalación comprobada

| Comprobación | Resultado |
| --- | --- |
| Origen público | https://lrs.minayao.site |
| Administración / xAPI | `/admin`, `/xapi`; autenticación local y Basic por API |
| Proyecto / backend | `stt-yet-prod`, `127.0.0.1:18083` |
| Persistencia | Bind propio en `datos/yet/prod/postgres`, bajo la raíz STT |
| Salud | PostgreSQL y LRS healthy |
| Límites | LRS 2 CPU/1536 MiB, PostgreSQL 1 CPU/512 MiB; heap 60% máximo |
| Logs | Tres archivos de 10 MiB por contenedor |
| Exposición | PostgreSQL sin publicar; backend inaccesible externamente |
| HTTPS | Certificado público confiable, TLS 1.3; vence 27 de enero de 2027 |
| HTTP | Redirección 301 al mismo dominio HTTPS |
| Renovación | Certbot dry-run con deploy hooks correcto; Nginx validado y recargado |
| Aplicación | Login real, rechazo de credenciales inválidas, lectura de ambas versiones xAPI y assets JS/CSS correctos |
| CORS | Origen propio permitido; otro origen rechazado/sin autorización CORS |
| Datos | Cero statements productivos; no se agregaron eventos sintéticos |
| Git | Transferencia por bundle; sin remoto ni token GitHub en la VPS |

La paginación se comprobó con datos desechables. La base productiva vacía no
genera un enlace `more`; no se afirma una prueba de paginación con datos reales.

El perfil y los secretos se separan por servicio/entorno. Credenciales locales
en la carpeta privada `Credenciales-STT`, con ACL restringida a su propietario,
SYSTEM y Administradores. En Linux, secretos 0700 y archivos privados 0600.
Ningún secreto forma parte de este registro ni del contenido público.

## Respaldo, recuperación y continuidad

La ejecución de `stt-yet-prod-backup.service` terminó con Result=success y
ExecMainStatus=0. Copia `20261029_211123` (UTC), con dump, perfiles privados,
imágenes, revisión, bundle y SHA256SUMS correcto. El timer propio está habilitado
a las **04:50 America/Santiago**, conservando siete copias completas.

La copia productiva se restauró en otro proyecto y raíz temporal, con puerto
loopback diferente. Pasaron login y xAPI con las credenciales originales; la
base recuperada conserva cero statements. La producción no se detuvo para ese
ensayo. Los contenedores, red y datos temporales se retiraron.

La evidencia privada queda en el área de operaciones del servicio: unit.log,
integration.log, install.log, verification.json, recovery.log y renewal-test.log.
Las respuestas de los nueve sitios vecinos coinciden con el estado previo:
200 en principal/doc/Portainer/RAMotors, 303 en Moodle, 302 en AuthSom/Kuma/correo,
401 en Glances. No se cambiaron sus configuraciones ni contenedores.

Pendientes explícitos: copia externa, productores xAPI/Moodle e integración OIDC.
Docsite se entrega en PR separado, con fuentes y dist, sin integrar ni publicar.
Las actualizaciones requieren copia correcta, revisión/digests explícitos y
restauración ensayada; un retorno de imagen no revierte una migración de esquema.
