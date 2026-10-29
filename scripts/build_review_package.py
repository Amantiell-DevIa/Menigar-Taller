#!/usr/bin/env python3
"""Create an allowlisted review package, optionally with PHP, never a deployment.

No WordPress files, SQL dumps, local requests, captures or credentials enter it.
Configuration, hosting validation and activation remain separate gates.
"""
from __future__ import annotations
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import urlsplit
import zipfile

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = Path('/Users/kaykostar/Documents/MENIGAR/nueva-web-revision-2026-10-15')
ROOT_FILES = ['index.html', 'servicios.html', 'solicitud.html', 'como-funciona.html', 'garantia.html', 'sobre-nosotros.html',
              'ayuda.html', 'privacidad.html', 'condiciones.html', 'cookies.html',
              'style.css', 'solicitud.css', 'hyundai.css', 'bmw.css', 'reparaciones.css', 'garantia.css', 'servicios.css', 'paginas.css',
              'app.js', 'solicitud.js', 'resumen.js', 'robots.txt', 'sitemap.xml']
ROOT_FILES += ['resumen.html', 'receipt.js', 'opciones-hero.html', 'laboratorio.html', 'laboratorio.js', 'favicon.ico', 'apple-touch-icon.png']
DATA_FILES = ['catalogo-v2.js', 'home-index.js', 'family-media.js']


def build(destination, with_backend=False, review_gate=False):
    if review_gate and not with_backend:
        raise ValueError('The private review gate requires --with-backend')
    destination.mkdir(mode=0o700, parents=True, exist_ok=True)
    public = destination / 'public'
    public.mkdir(exist_ok=True)
    catalogue = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
    selected = [ROOT / f for f in ROOT_FILES] + [ROOT / 'data' / f for f in DATA_FILES]
    selected += [ROOT / row['localPath'].lstrip('/') / 'index.html' for row in catalogue]
    selected += [p for p in (ROOT / 'assets').rglob('*') if p.is_file() and not p.name.startswith('.')
                 and p.suffix.lower() in {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg', '.ico', '.pdf', '.css', '.woff2'}]
    # The OFL licence travels with the self-hosted typeface; the routers do not serve .txt files.
    selected += sorted((ROOT / 'assets/fonts').rglob('LICENSE*.txt'))
    manifest = []
    for source in selected:
        if not source.is_file():
            raise FileNotFoundError(source)
        relative = source.relative_to(ROOT)
        target = public / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        manifest.append({'path': str(relative), 'bytes': target.stat().st_size,
                         'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    backend_files = []
    if with_backend:
        private_sources = ['Intake.php','Http.php','Views.php','Notifications.php','Backup.php','README.md',
                           'bin/common.php','bin/check.php','bin/notify.php','bin/backup.php','bin/restore.php']
        if review_gate:
            private_sources += ['ReviewGate.php', 'review-router.php', 'review.htaccess.example']
        for relative in private_sources:
            target = destination / 'backend' / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(ROOT / 'backend' / relative, target)
            backend_files.append(target)
        target = destination / 'backend/legacy-media-routes.json'
        shutil.copyfile(ROOT / 'data/legacy-media-routes.json', target)
        backend_files.append(target)
        template = destination / 'private/config.example.php'
        template.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'backend/config.example.php', template)
        backend_files.append(template)
        controller = public / 'api/index.php'
        controller.parent.mkdir(exist_ok=True)
        shutil.copyfile(ROOT / 'api/index.php', controller)
        media_controller = public / 'api/legacy-media.php'
        shutil.copyfile(ROOT / 'api/legacy-media.php', media_controller)
        rules = public / '.htaccess'
        rules.write_text('''# Backend routing only; legacy redirects remain separately proposed.
Options -Indexes
<IfModule mod_mime.c>
AddType font/woff2 .woff2
</IfModule>
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule .* - [E=HTTP_AUTHORIZATION:%{HTTP:Authorization}]
RewriteRule ^(?:backend|private|var|scripts|tests)(?:/|$) - [R=404,L]
RewriteRule ^api/(?:index|legacy-media)\\.php$ - [L]
RewriteRule ^(?:api|equipo)(?:/|$) api/index.php [L]
</IfModule>
<IfModule mod_headers.c>
Header always set X-Content-Type-Options "nosniff"
<FilesMatch "^(?:solicitud|resumen)\\.html$">
Header always set Cache-Control "no-store"
Header always set Referrer-Policy "no-referrer"
</FilesMatch>
</IfModule>
''')
        public_controllers = [controller, media_controller]
        if review_gate:
            review_controller = public / 'api/review.php'
            shutil.copyfile(ROOT / 'api/review.php', review_controller)
            public_controllers.append(review_controller)
            shutil.copyfile(ROOT / 'backend/review.htaccess.example', rules)
        for target in [*public_controllers, rules]:
            manifest.append({'path': str(target.relative_to(public)), 'bytes': target.stat().st_size,
                             'sha256': hashlib.sha256(target.read_bytes()).hexdigest()})
    routes = {row['fromPath'].rstrip('/') or '/': row['to'] for row in json.loads((ROOT / 'data/redirects.json').read_text())}
    alias_path = ROOT / 'data/legacy-link-resolution.json'
    lookup = {r['uid']: r for r in catalogue}
    if alias_path.exists():
        for alias in json.loads(alias_path.read_text())['links']:
            if alias.get('resolvedUid') in lookup:
                routes[urlsplit(alias['originalUrl']).path.rstrip('/')] = lookup[alias['resolvedUid']]['localPath']
    extras = {'/home': '/index.html', '/envios': '/como-funciona.html', '/servicios': '/servicios.html',
              '/contacto': '/ayuda.html#contacto', '/preguntas-frecuentes': '/ayuda.html',
              '/garantias': '/garantia.html', '/politica-de-privacidad': '/privacidad.html',
              '/politica-de-cookies': '/cookies.html', '/avisos-legales': '/condiciones.html',
              '/reparacion-abs': '/servicios.html?familia=abs',
              '/reparacion-abs/home-abs-coches': '/servicios.html?familia=abs',
              '/reparacion-abs/home-abs-motos': '/servicios.html?familia=abs',
              '/reparacion-abs/contacto': '/ayuda.html#contacto',
              '/reparacion-abs/politica-de-privacidad': '/privacidad.html',
              '/reparacion-abs/politica-de-cookies': '/cookies.html',
              '/reparacion-abs/avisos-legales': '/condiciones.html'}
    routes.update(extras)
    candidates = [{'fromPath': path + '/', 'to': target, 'status': 301, 'enabled': False}
                  for path, target in sorted(routes.items())]
    (destination / 'redirecciones-propuestas.json').write_text(json.dumps(candidates, ensure_ascii=False, indent=2) + '\n')
    rules = ['# Proposed Apache rules. Review and test in the target Plesk stack before enabling.',
             '# This file is deliberately OUTSIDE public/. No redirects are enabled by this package.']
    for path, target in sorted(routes.items()):
        rules.append('RedirectMatch 301 "^' + re.escape(path) + '/?$" "' + target + '"')
    (destination / 'redirecciones-apache-propuestas.conf').write_text('\n'.join(rules) + '\n')
    media_routes = json.loads((ROOT / 'data/legacy-media-routes.json').read_text()) if with_backend else {}
    if with_backend:
        (destination / 'redirecciones-medios-propuestas.conf').write_text('''# Proposed per-directory rules: place BEFORE the generic /api routing.
# NOT active in public/.htaccess. Validate in protected hosting first.
<IfModule mod_rewrite.c>
RewriteEngine On
RewriteRule ^(?:(?:reparacion-abs/)?wp-content/uploads/|docs/) api/legacy-media.php [L]
</IfModule>
''')
    mode = 'private-gated-backend-review' if review_gate else 'private-backend-review' if with_backend else 'private-static-review'
    status = {'mode': mode, 'productionReady': False,
              'backendIncluded': with_backend, 'privateConfigIncluded': False,
              'reviewGateIncluded': review_gate, 'reviewGateConfigured': False,
              'reviewGateVerifiedOnHosting': False,
              'wordpressRuntimeIncluded': False, 'sourceRequestsOrCredentialsIncluded': False,
              'fileCount': len(manifest), 'bytes': sum(x['bytes'] for x in manifest),
              'proposedRedirectCount': len(candidates), 'files': manifest,
              'proposedMediaRedirectCount': len(media_routes),
              'pending': ['Private production configuration, staff notification delivery and workshop acceptance.',
                          'Hosting runtime/capacity validation and protected staging.',
                          'Commercial/legal validation, final synchronization, redirect and rollback tests.',
                          'Publication authorization.']}
    (destination / 'manifest.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    (destination / 'LEEME.md').write_text('''# MENIGAR · Paquete privado de revisión

La carpeta `public/` contiene la web y sus medios propios. Si se ha incluido el backend, su código está fuera de `public/` y únicamente sus controladores de entrada están en `public/api/`. No incluye WordPress, bases de datos, solicitudes locales ni credenciales reales. La configuración de ejemplo mantiene la recepción desactivada. No debe recibir clientes reales hasta completar las validaciones.

**No es una entrega aprobada para producción.** Antes de publicar se debe validar el backend del formulario, su almacenamiento privado y avisos, el alojamiento y el espacio, las condiciones del servicio, las redirecciones y la vuelta atrás. El entorno de revisión remoto necesita control de acceso; `noindex` y `robots.txt` no sustituyen una contraseña.

Las redirecciones propuestas están fuera de `public/` y permanecen desactivadas. También deben decidirse las páginas históricas de empleo y Top Repair, las dos fichas de origen sin contenido y los enlaces de origen sin destino válido. Ninguna propuesta de baja o borrado queda ejecutada.

`manifest.json` permite contrastar cada archivo por tamaño y SHA-256. Este paquete se regenera con `scripts/build_review_package.py` desde el proyecto; los originales privados de la copia externa permanecen separados.
''')
    if review_gate:
        with (destination / 'LEEME.md').open('a') as notice:
            notice.write('''
## Protección incluida para revisión

Este paquete se generó con `--with-backend --review-gate`. Su `.htaccess` envía todas las rutas, incluidos los estáticos, a `api/review.php`. La puerta utiliza una sesión independiente de los accesos Bearer del solicitante y Basic del equipo. No añada una contraseña HTTP Basic global por encima.

La puerta falla cerrada hasta configurar `reviewGate` en un archivo privado propio del destino. No se incluyen usuarios, contraseñas ni secretos reales. Solo funciona en modo `review`; no es el paquete para activar una web pública de producción.

**Pendiente en Plesk:** comprobar HTTPS, nueva raíz y configuración, paso de estáticos por Apache y transmisión de Authorization. Si nginx sirve archivos directamente, puede saltarse `.htaccess`: antes de alojar contenido, comprobar anónimo HTML, imagen, JS, PDF, API y PHP directo. Las pruebas PHP locales no acreditan esa configuración del servidor. Véanse las instrucciones de `backend/README.md`.
''')
    status['backendFiles'] = [{'path': str(path.relative_to(destination)), 'bytes': path.stat().st_size,
                               'sha256': hashlib.sha256(path.read_bytes()).hexdigest()} for path in backend_files]
    (destination / 'manifest.json').write_text(json.dumps(status, ensure_ascii=False, indent=2) + '\n')
    archive = destination.with_suffix('.zip')
    with zipfile.ZipFile(archive, 'w', zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        package_files = [public / entry['path'] for entry in manifest]
        package_files += backend_files
        package_files += [destination / name for name in ['manifest.json', 'LEEME.md',
                          'redirecciones-propuestas.json', 'redirecciones-apache-propuestas.conf']]
        if with_backend:
            package_files.append(destination / 'redirecciones-medios-propuestas.conf')
        for source in sorted(package_files):
            output.write(source, source.relative_to(destination))
    with zipfile.ZipFile(archive) as output:
        if output.testzip():
            raise ValueError('Archive integrity failed')
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_suffix('.zip.sha256').write_text(digest + '  ' + archive.name + '\n')
    print(json.dumps({'folder': str(destination), 'archive': str(archive), 'archiveBytes': archive.stat().st_size,
                      'files': len(manifest), 'publicBytes': status['bytes'], 'redirectsProposed': len(candidates),
                      'backendIncluded': with_backend, 'reviewGateIncluded': review_gate,
                      'productionReady': False}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument('--with-backend', action='store_true')
    parser.add_argument('--review-gate', action='store_true', help='Isolated review only; requires --with-backend and private configuration')
    args = parser.parse_args()
    build(args.output, args.with_backend, args.review_gate)
