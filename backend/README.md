# MENIGAR · Recepción de solicitudes en PHP

Backend de recepción y consulta de solicitudes. Conserva datos y archivos por pieza, permite recuperar el resumen y ofrece una bandeja privada al equipo. **No crea órdenes, presupuestos, facturas ni pagos en MotorWin/Odoo.** La selección de ese sistema y su integración siguen pendientes.

## Modelo desconocido en una consulta

Desde la actualización del 17 de octubre, una consulta puede incluir `vehicle.modelUnknown: true` y `vehicle.model: ""`. El desconocimiento se guarda como un booleano, no como un nombre de modelo. Si no se aporta el indicador, se aplica `false` y se requiere el modelo; los borradores antiguos con «Por identificar» se normalizan. La modalidad `repair` exige un modelo identificado. Los resúmenes y la bandeja muestran «Modelo desconocido» cuando corresponde y conservan los datos de cada pieza por separado.

Los resúmenes de consulta omiten las filas fiscales o de envío vacías. El valor inicial del país por sí solo no constituye una dirección. Los datos reales aportados y los de la modalidad de preparación de envío se conservan.

## Estructura de una instalación

```text
menigar-web/
  public/                 raíz pública configurada en Plesk
    api/index.php         único controlador PHP público
    resumen.html          visor del cliente, sin datos incrustados
    receipt.js
    .htaccess             rutas /api y /equipo; redirecciones antiguas aparte
    ...web, imágenes y documentos...
  backend/                código de aplicación y utilidades CLI
  private/
    config.php            configuración real; no se incluye en el paquete
    data/                 SQLite, archivos privados y avisos de prueba
```

El paquete incluye solamente `private/config.example.php`, con recepción desactivada y sin secreto ni contraseñas. Copiarla a `config.php` y completar los valores en el destino privado. El backend también admite una ruta absoluta en la variable `MENIGAR_CONFIG`.

La configuración real, el secreto y `data/` se conservan entre versiones. Actualizar el código nunca debe sustituirlos por los de un entorno vacío o una copia antigua. El secreto estable permite recuperar envíos tras una interrupción; se incluye en las copias privadas.

## Requisitos comprobables

- PHP 8.3, PDO SQLite, SQLite3, Fileinfo, Mbstring y ZIP. El código no necesita Composer ni ejecutar comandos del sistema.
- Directorio de datos escribible fuera de la raíz pública; archivos privados y base con permisos restringidos.
- HTTPS para producción y `baseUrl` con el dominio canónico exacto. La aplicación rechaza HTTP y no confía en un `X-Forwarded-Proto` aportado por el visitante.
- Rutas Apache de `.htaccess` o su equivalente validado en el servidor. La presencia de PHP no prueba que el servidor ejecute las rutas correctamente.
- Cuota de alojamiento suficiente. `disk_free_space()` mide el disco físico, no la cuota de la cuenta: debe contrastarse con Plesk. El presupuesto de almacenamiento es una barrera adicional y no borra solicitudes.

La lectura de Plesk del 15 de octubre confirma PHP 8.3.35, FastCGI, PDO SQLite/MySQL, SQLite 3.26.0, `post_max_size=15M` y `upload_max_filesize=10M`. Los demás límites se leen en ejecución. La prueba local reproduce esos tamaños con PHP 8.3.30; falta la comprobación HTTP en el alojamiento de destino.

## Archivos y límites

El formulario consulta `/api/config` y envía `multipart/form-data`: un campo JSON `payload` y los archivos `files[u0a0]`, etc. No convierte los binarios a base64. El servidor comprueba formato real, tamaño, número y asociación de cada adjunto; rechaza archivos adicionales, ausentes o incompletos.

Con un límite POST de 15 MiB, reserva espacio para metadatos y comunica 14 MiB totales. El máximo por archivo sigue siendo 5 MiB; el total de archivos respeta `max_file_uploads` de PHP. Estos valores se muestran y validan en el cliente y en el servidor. Se admiten diez piezas, hasta cinco archivos por pieza dentro del límite total, y JPG/PNG/WebP/PDF.

Los archivos se guardan con nombres aleatorios `.bin` fuera de `public/`. La descarga requiere el acceso del solicitante o del empleado, coteja tamaño/huella y utiliza una extensión coherente con el formato real. Se conserva el nombre declarado como información de origen.

## Datos, reintentos y acceso

Cada envío usa una clave aleatoria. La misma clave y datos devuelven la misma referencia; una reutilización con datos cambiados devuelve 409. La transacción SQLite serializa el guardado; la solicitud, sus archivos y el aviso pendiente se confirman juntos. Un fallo de persistencia no deja una solicitud parcial.

`/api/recuperar` permite recuperar un envío cuya respuesta se perdió. Requiere la clave original, la sesión y un token CSRF. El formulario lo utiliza al restaurar un borrador que quedó pendiente de envío. No se deduplican reparaciones diferentes por NIF/CIF.

El resumen usa `/resumen.html#CLAVE_PRIVADA`. El fragmento no se envía al servidor en la URL; las lecturas posteriores usan `Authorization: Bearer`. La base conserva una huella del acceso, y los enlaces de aviso al empleado utilizan la referencia y requieren identificación. Los datos no se incluyen en mapas del sitio ni en archivos públicos.

El acceso del equipo usa usuarios individuales definidos en `staffUsers`, con `password_hash()`. `/equipo/solicitudes` muestra la bandeja y los adjuntos; marcar una solicitud como revisada registra quién lo hizo sin cambiar los datos del cliente. Esta acción no registra la llegada del paquete ni autoriza una reparación. La configuración de estos usuarios es independiente de las credenciales de Plesk.

Una contraseña HTTP Basic global del servidor puede interceptar el `Authorization: Bearer` del solicitante y bloquear su resumen antes de llegar a PHP. Reutilizar credenciales del equipo no resuelve ese conflicto. Para una revisión privada debe utilizarse un control independiente y probado; `robots.txt`/`noindex` no restringen el acceso.

## Puerta de revisión independiente

El generador admite `--with-backend --review-gate` para preparar una instalación aislada. Incluye `api/review.php`, `backend/ReviewGate.php`, `backend/review-router.php` y la plantilla `backend/review.htaccess.example`. La raíz nueva sigue siendo únicamente `public/`. No sustituir ni combinar estas reglas con el WordPress publicado.

En ese paquete, `.htaccess` envía todas las peticiones al controlador de revisión, incluidos HTML, imágenes, JavaScript, PDF, API y entradas PHP directas. La puerta exige una sesión propia `MENIGAR_REVIEW`; conserva separadamente la sesión del formulario y no consume ni modifica `Authorization`. Un cliente necesita además su Bearer para el resumen, y un empleado su Basic individual para la bandeja.

Completar en la configuración privada del destino: `mode=review`, `reviewGate.enabled=true`, usuarios de revisión con hashes creados mediante `password_hash()`, un secreto estable y aleatorio y un `stateDir` escribible fuera de la raíz pública. El ejemplo no incluye accesos ni secreto; el controlador devuelve 503 mientras falte una configuración válida. No reutilizar contraseñas de Plesk. No subir la configuración del ordenador. Los accesos reales deben establecerse por el responsable del entorno y compartirse por un medio privado.

La puerta requiere HTTPS, valida el host exacto, limita intentos y caduca la sesión por inactividad y tiempo máximo. Para un ensayo aislado en el ordenador admite HTTP solo con `allowLoopbackHttp=true`, host y conexión reales `127.0.0.1`. `backend/dev-router.php` solo la activa con `MENIGAR_REVIEW_GATE=1`; las revisiones locales existentes mantienen su funcionamiento habitual.

El acceso utiliza un formulario con CSRF y una cookie HttpOnly. Al abrir un resumen, su fragmento privado se conserva en el navegador durante el acceso mediante JavaScript; no entra en `next`, en el POST de acceso ni en una URL registrada en el servidor. La compatibilidad de ese recorrido debe comprobarse también en el navegador de destino. Tras caducar el acceso, recargar la página vuelve a mostrar la puerta; los borradores del formulario permanecen sujetos a sus reglas normales.

**Requisito del servidor:** si nginx sirve estáticos directamente, puede saltarse las reglas Apache. Antes de aceptar el entorno, comprobar sin cookie HTML, imagen, CSS/JS, PDF, API y PHP directo, y comprobar después los accesos del solicitante y del equipo. Configurar únicamente el nuevo sitio de revisión para que todo pase por la puerta; si no se dispone de esa opción, hace falta un control de red equivalente o intervención sobre ese sitio. Nunca dar por protegido el alojamiento porque la prueba con el servidor PHP local pasa.

Las pruebas HTTP aisladas se ejecutan con `python3 -m unittest discover -s tests -p test_php_review_gate.py -v`. Verifican bloqueo anónimo, CSRF, redirecciones internas, limitación de intentos, sesiones separadas, Bearer, Basic, descarga y fallo cerrado de configuración. No prueban Apache/nginx, FastCGI ni TLS en Plesk. La puerta rechaza modo `production`; para el lanzamiento público se genera y valida el paquete normal, conservando la configuración y datos que correspondan.

## Avisos al equipo

Destinatario indicado por MENIGAR: `informacion@menigar.com`. Responsable: atención al cliente. Se ha registrado como configuración prevista; la recepción real del aviso por ese buzón sigue pendiente de una prueba en el alojamiento. El remitente del ejemplo utiliza la misma dirección y también debe validarse allí.

```sh
php backend/bin/notify.php --config /RUTA/PRIVADA/config.php --public-root /RUTA/menigar-web/public --limit 30
```

En `review`, el transporte `spool` escribe un aviso simulado privado; nunca manda correo. En `production`, `sendmail` requiere remitente/destinatario válidos y usa el transporte del alojamiento. La respuesta positiva de `mail()` indica aceptación por ese transporte; **no prueba que el empleado haya recibido el mensaje**. Es necesario comprobar un aviso real con el buzón y el responsable acordados antes del lanzamiento.

Los avisos se guardan en una cola independiente: un fallo de correo conserva la solicitud y permite reintentos. La ejecución se protege con un bloqueo; los trabajos interrumpidos con resultado incierto quedan señalados para revisión y no se reenvían automáticamente. La bandeja permite ver su estado. No se han programado trabajos remotos ni habilitado envíos reales.

## Copia y recuperación

```sh
php backend/bin/backup.php --config /RUTA/PRIVADA/config.php --public-root /RUTA/menigar-web/public --output /RUTA/PRIVADA-EXTERNA/copia-fecha.zip
php backend/bin/restore.php --archive /RUTA/PRIVADA-EXTERNA/copia-fecha.zip --sha256 HUELLA_CONFIRMADA --destination /RUTA/PRIVADA-EXTERNA/recuperacion-nueva --base-url http://127.0.0.1:8781 --public-root /RUTA/menigar-web/public
```

La copia usa `SQLite3::backup()` para obtener una instantánea consistente, incluye los adjuntos referenciados y la configuración en JSON, y contrasta todas las huellas. No usa una simple copia del fichero activo ni `VACUUM INTO`, que exige una versión de SQLite posterior a la observada en el alojamiento. Véanse el [manual de PHP](https://www.php.net/manual/en/sqlite3.backup.php) y [SQLite 3.27](https://www.sqlite.org/releaselog/3_27_0.html).

El ZIP contiene datos privados y el secreto de acceso: se guarda fuera de la web y debe trasladarse a un destino privado externo. En un alojamiento casi lleno se debe confirmar primero el espacio temporal necesario o ejecutar la copia fuera del servidor. No se ha configurado una rotación o borrado automático de datos.

La recuperación exige la huella esperada, un directorio privado nuevo y una URL local. No ejecuta código PHP archivado. Comprueba integridad y claves foráneas; desactiva la recepción y fuerza los avisos de prueba. Después se debe abrir mediante la aplicación, consultar una solicitud y descargar sus archivos. La recuperación funcional forma parte de las pruebas.

## Comprobaciones y activación pendiente

```sh
php backend/bin/check.php --config /RUTA/PRIVADA/config.php --public-root /RUTA/menigar-web/public
python3 -m unittest discover -s tests -p test_php_intake.py -v
```

`check.php` verifica entorno y almacenamiento; no acredita la entrega de correo, la recepción del taller ni una integración externa. Las pruebas HTTP usan un servidor PHP real, datos ficticios, correo desactivado, reintentos concurrentes, cargas cercanas al límite y recuperación de una copia.

Antes de producción: completar la configuración privada y los accesos, confirmar condiciones y conservación, probar HTTP/HTTPS/rutas/adjuntos en el destino protegido, verificar un aviso con el empleado, probar la copia externa, las redirecciones y la vuelta atrás. El cambio de la web pública se realiza cuando estén cubiertos esos puntos y acordado el momento del lanzamiento.

Con FastCGI es necesario comprobar que Apache transmite `Authorization` a PHP, tanto para el resumen privado como para la bandeja del equipo. El paquete conserva esa cabecera mediante una regla y admite `REDIRECT_HTTP_AUTHORIZATION` tras una reescritura interna; la prueba PHP local no acredita el funcionamiento del FastCGI de Plesk. Véanse [PHP: identificación HTTP](https://www.php.net/manual/es/features.http-auth.php) y [Apache: CGIPassAuth](https://httpd.apache.org/docs/2.4/mod/core.html#cgipassauth).

El límite de almacenamiento de 128 MiB del ejemplo es una barrera de prueba, no una capacidad prevista para el taller. Antes del lanzamiento se debe medir el tamaño habitual de los adjuntos y acordar capacidad y conservación. Con la cuota observada casi llena no se debe subir a la vez un ZIP completo, su extracción y otra copia de WordPress sin calcular su espacio temporal.

## Direcciones antiguas de fotos y documentos

`scripts/build_legacy_media_routes.py` prepara 9.681 correspondencias exactas a partir de los manifiestos: 9.678 URL de imágenes y tres PDF. Se conserva el nombre original y su equivalencia en un índice; no se adivinan relaciones por similitud del nombre. La búsqueda se hace con una tabla exacta en PHP y una sola regla por prefijo, evitando miles de expresiones regulares en cada visita.

El paquete con backend incluye `api/legacy-media.php`, el índice privado `backend/legacy-media-routes.json` y `redirecciones-medios-propuestas.conf` fuera de `public/`. La regla permanece desactivada en el paquete. No necesita credenciales ni la base de solicitudes: solo permite GET/HEAD y redirige a archivos propios existentes. Las URL desconocidas no se asignan a otra pieza ni se redirigen a una dirección externa.

Estas correspondencias cubren los medios seleccionados para la web nueva, no toda la biblioteca histórica. Antes de retirar las carpetas antiguas se debe decidir qué otros archivos deben conservar su acceso público. No se borra ningún archivo antiguo ni se altera WordPress al generar este índice.
