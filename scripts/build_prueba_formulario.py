#!/usr/bin/env python3
"""Paquete del formulario de prueba para instalarlo en una subcarpeta del servidor.

Crea dos carpetas con los mismos nombres que en el FTP de Hostytec:

  httpdocs/pruebas/             lo público: formulario, resguardo y lo que necesitan,
                                con las direcciones ya ajustadas a la subcarpeta
  pruebas.menigar.com/backend/  el código PHP, fuera de la carpeta pública

No incluye la configuración, porque lleva la clave y los accesos del equipo: la crea
scripts/crear_config_prueba.py en una carpeta privada. Tampoco sube nada: eso lo hace
scripts/subir_prueba_formulario.py, que pide la contraseña del FTP a quien lo ejecuta.

Las páginas del sitio que no van en el paquete (Servicios, Cómo funciona, los textos
legales...) se enlazan a la web nueva de prueba en Vercel, que tampoco está en Google.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PUBLIC_FILES = [
    'solicitud.html', 'resumen.html', 'style.css', 'solicitud.css', 'app.js', 'solicitud.js',
    'receipt.js', 'resumen.js', 'data/catalogo-v2.js', 'favicon.ico', 'apple-touch-icon.png',
    'assets/equipo.css', 'assets/ayuda-referencia.svg',
    'assets/marca/menigar-logo-1x.webp', 'assets/marca/menigar-logo-2x.webp', 'assets/marca/menigar-logo-3x.webp',
    'assets/fonts/inter/InterVariable.woff2',
]
BACKEND_FILES = [
    'Intake.php', 'Http.php', 'Views.php', 'Notifications.php', 'OdooConnector.php', 'Backup.php', 'README.md',
    'bin/common.php', 'bin/check.php', 'bin/notify.php', 'bin/backup.php', 'bin/restore.php',
]
# Same policy as vercel.json, so the test pages behave like the new site.
CSP = ("default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; font-src 'self'; "
       "connect-src 'self'; frame-src https://www.youtube-nocookie.com https://www.google.com; "
       "frame-ancestors 'none'; form-action 'self'; base-uri 'none'")
ATTRIBUTE = re.compile(r'\b(href|src|action|poster)="(/[^"]*)"')
SRCSET = re.compile(r'\bsrcset="([^"]+)"')
CSS_URL = re.compile(r'url\((["\']?)(/[^)"\']+)\1\)')


def split_url(value: str) -> tuple[str, str]:
    """'/a/b.css?x#y' -> ('a/b.css', '?x#y')."""
    match = re.match(r'/([^?#]*)(.*)', value)
    return match.group(1), match.group(2)


class Rewriter:
    def __init__(self, base: str, website: str, packaged: set[str]):
        self.base, self.website, self.packaged = base, website.rstrip('/'), packaged
        self.missing: list[str] = []

    def url(self, value: str, page_allowed: bool = True) -> str:
        if value.startswith('//'):
            return value
        path, rest = split_url(value)
        if path in self.packaged:
            return self.base + '/' + path + rest
        if page_allowed and (path == '' or path.endswith('/')):
            return self.website + '/' + path + rest
        self.missing.append(value)
        return value

    def html(self, text: str) -> str:
        text = ATTRIBUTE.sub(lambda m: f'{m.group(1)}="{self.url(m.group(2))}"', text)
        def srcset(match: re.Match) -> str:
            parts = []
            for candidate in match.group(1).split(','):
                bits = candidate.strip().split(maxsplit=1)
                if bits and bits[0].startswith('/'):
                    bits[0] = self.url(bits[0], page_allowed=False)
                parts.append(' '.join(bits))
            return 'srcset="' + ', '.join(parts) + '"'
        return SRCSET.sub(srcset, text)

    def css(self, text: str) -> str:
        return CSS_URL.sub(lambda m: f'url({m.group(1)}{self.url(m.group(2), page_allowed=False)}{m.group(1)})', text)


def htaccess(base: str) -> str:
    return f"""# Generado por scripts/build_prueba_formulario.py: formulario de prueba en {base}/
Options -Indexes -MultiViews
DirectoryIndex solicitud.html

<IfModule mod_headers.c>
  Header always set X-Content-Type-Options "nosniff"
  Header always set Referrer-Policy "same-origin"
  Header always set X-Robots-Tag "noindex, nofollow"
  <FilesMatch "\\.html$">
    Header always set Content-Security-Policy "{CSP}"
    Header always set Cache-Control "no-cache"
  </FilesMatch>
</IfModule>

<IfModule mod_rewrite.c>
  RewriteEngine On
  RewriteBase {base}/
  # PHP only sees the login of the team area and the receipt key if Apache passes them on.
  RewriteCond %{{HTTP:Authorization}} .
  RewriteRule ^ - [E=HTTP_AUTHORIZATION:%{{HTTP:Authorization}}]
  RewriteRule ^(?:api|equipo)(?:/|$) api/index.php [L,QSA]
</IfModule>
"""


def api_entry(app_root: str, config_name: str) -> str:
    source = (ROOT / 'api/index.php').read_text(encoding='utf-8')
    marker = 'declare(strict_types=1);\n'
    if marker not in source or 'MENIGAR_APP_ROOT' not in source:
        raise RuntimeError('api/index.php ya no tiene la forma esperada')
    header = (marker + '// Generado por scripts/build_prueba_formulario.py: la aplicación y la configuración\n'
              '// están fuera de la carpeta pública.\n'
              f"define('MENIGAR_APP_ROOT', {json.dumps(app_root)});\n"
              f"putenv('MENIGAR_CONFIG=' . MENIGAR_APP_ROOT . {json.dumps('/private/' + config_name)});\n")
    return source.replace(marker, header, 1)


def digest(path: Path) -> dict:
    return {'bytes': path.stat().st_size, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}


def build(destination: Path, base: str = '/pruebas', website: str = 'https://menigar-taller.vercel.app',
          app_root: str = '/var/www/vhosts/menigar.com/pruebas.menigar.com', config_name: str = 'config-subpath.php',
          public_dir: str = 'httpdocs/pruebas', app_dir: str = 'pruebas.menigar.com') -> dict:
    base = '/' + base.strip('/')
    if destination.exists():
        shutil.rmtree(destination)
    public = destination / public_dir
    backend = destination / app_dir / 'backend'
    rewriter = Rewriter(base, website, set(PUBLIC_FILES))
    manifest = {'base': base, 'website': website, 'appRoot': app_root, 'config': f'{app_dir}/private/{config_name}', 'files': {}}

    def write(relative_root: Path, relative: str, data: bytes) -> None:
        target = relative_root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        manifest['files'][str(target.relative_to(destination))] = digest(target)

    for relative in PUBLIC_FILES:
        source = ROOT / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        data = source.read_bytes()
        if relative.endswith('.html'):
            data = rewriter.html(data.decode('utf-8')).encode('utf-8')
        elif relative.endswith('.css'):
            data = rewriter.css(data.decode('utf-8')).encode('utf-8')
        write(public, relative, data)
    for licence in sorted((ROOT / 'assets/fonts/inter').glob('LICENSE*')):
        write(public, str(licence.relative_to(ROOT)), licence.read_bytes())
    write(public, '.htaccess', htaccess(base).encode())
    write(public, 'robots.txt', b'User-agent: *\nDisallow: /\n')
    write(public, 'api/index.php', api_entry(app_root, config_name).encode())
    for relative in BACKEND_FILES:
        source = ROOT / 'backend' / relative
        if not source.is_file():
            raise FileNotFoundError(source)
        write(backend, relative, source.read_bytes())

    if rewriter.missing:
        raise RuntimeError('Direcciones a archivos que no van en el paquete: ' + ', '.join(sorted(set(rewriter.missing))))
    check(destination, manifest, public_dir)
    (destination / 'MANIFIESTO.json').write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
    (destination / 'LEEME.txt').write_text(readme(manifest, public_dir, app_dir), encoding='utf-8')
    return manifest


def check(destination: Path, manifest: dict, public_dir: str) -> None:
    """Fails if the package could expose a secret or keeps the old public team shortcut."""
    everywhere = ['publicStaffAccess', 'serveCatalogFallback', 'odoo.json', 'fichas.sqlite3']
    public_only = ['staffUsers', 'secret', 'password_hash', '$2y$']
    for relative in manifest['files']:
        if Path(relative).name.startswith('config') and relative.endswith('.php'):
            raise RuntimeError('La configuración no puede ir en el paquete: ' + relative)
        if relative.endswith(('.woff2', '.webp', '.ico', '.png')):
            continue
        text = (destination / relative).read_text(encoding='utf-8', errors='ignore')
        words = everywhere + (public_only if relative.startswith(public_dir + '/') else [])
        for word in words:
            if word in text:
                raise RuntimeError(f'{relative} contiene «{word}»')


def readme(manifest: dict, public_dir: str, app_dir: str) -> str:
    return f"""Formulario de prueba de MENIGAR — paquete de subida

Dónde va cada carpeta en el FTP de Hostytec:
  {public_dir}/      ->  /{public_dir}/          (sustituye a lo que hay)
  {app_dir}/backend/  ->  /{app_dir}/backend/
  configuración      ->  /{manifest['config']}  (la crea scripts/crear_config_prueba.py, no viaja aquí)

Dirección para probar: https://www.menigar.com{manifest['base']}/
Zona del equipo:       https://www.menigar.com{manifest['base']}/equipo/solicitudes  (pide usuario y contraseña)

MANIFIESTO.json tiene el tamaño y la huella SHA-256 de cada archivo para comprobar la subida.
Se sube con scripts/subir_prueba_formulario.py, que pide la contraseña del FTP sin guardarla.
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('destino', type=Path)
    parser.add_argument('--base', default='/pruebas')
    parser.add_argument('--web-nueva', default='https://menigar-taller.vercel.app')
    parser.add_argument('--app-root', default='/var/www/vhosts/menigar.com/pruebas.menigar.com')
    args = parser.parse_args()
    manifest = build(args.destino, args.base, args.web_nueva, args.app_root)
    print(f"Paquete creado en {args.destino}: {len(manifest['files'])} archivos.")


if __name__ == '__main__':
    main()
