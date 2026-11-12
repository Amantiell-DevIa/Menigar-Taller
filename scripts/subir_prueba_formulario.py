#!/usr/bin/env python3
"""Sube el formulario de prueba al servidor de Hostytec por FTP seguro (FTPS).

Lo ejecuta una persona en su terminal: el script pide el usuario y la contraseña del FTP
y no los guarda ni los muestra. Antes de cada paso que cambia el servidor, enseña qué va
a hacer y espera un «si».

Pasos:
 1. Inventario de lo que hay hoy en /httpdocs/pruebas/ y en /pruebas.menigar.com/ (se
    guarda en la carpeta privada, para poder comparar o deshacer).
 2. Sube el código PHP, la configuración nueva y lo público del paquete.
 3. Retira lo que sobra de una instalación anterior:
    - aparta la configuración antigua del subdominio de pruebas;
    - aparta la carpeta de datos antigua, que deja de verse; no se borra;
    - borra el catálogo copiado (fichas.sqlite3) y los archivos públicos de /pruebas/
      que ya no forman parte del paquete.
 4. Comprueba desde fuera que todo responde como debe.

Uso:
  python3 scripts/subir_prueba_formulario.py PAQUETE CARPETA_PRIVADA --host SERVIDOR_FTP
    PAQUETE          lo crea scripts/build_prueba_formulario.py
    CARPETA_PRIVADA  la crea scripts/crear_config_prueba.py (config-subpath.php)
    SERVIDOR_FTP     el nombre del servidor de Hostytec (está en las notas privadas)
"""
from __future__ import annotations

import argparse
import ftplib
import getpass
import hashlib
import io
import json
import re
import ssl
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

PUBLIC = '/httpdocs/pruebas'
APP = '/pruebas.menigar.com'
SITE = 'https://www.menigar.com/pruebas'
SERVER_ROOT = '/var/www/vhosts/menigar.com'
RETIRED = '-retirado-' + datetime.now().strftime('%Y%m%d-%H%M')


def ask(question: str) -> bool:
    return input(question + ' Escribe «si» para seguir: ').strip().lower() in {'si', 'sí'}


class Remote:
    def __init__(self, host: str, user: str, password: str):
        self.ftp = ftplib.FTP_TLS(context=ssl.create_default_context(), timeout=60)
        self.ftp.connect(host, 21)
        self.ftp.login(user, password)
        self.ftp.prot_p()

    def walk(self, path: str) -> dict[str, int]:
        """Every file under path with its size; {} if path does not exist."""
        found: dict[str, int] = {}
        try:
            entries = list(self.ftp.mlsd(path, facts=['type', 'size']))
        except ftplib.error_perm:
            return found
        for name, facts in entries:
            if name in {'.', '..'}:
                continue
            full = path.rstrip('/') + '/' + name
            if facts.get('type') == 'dir':
                found.update(self.walk(full))
            elif facts.get('type') == 'file':
                found[full] = int(facts.get('size', 0))
        return found

    def exists(self, path: str) -> bool:
        parent, name = path.rsplit('/', 1)
        try:
            return any(entry == name for entry, _ in self.ftp.mlsd(parent or '/'))
        except ftplib.error_perm:
            return False

    def mkdirs(self, path: str) -> None:
        current = ''
        for part in [p for p in path.split('/') if p]:
            current += '/' + part
            try:
                self.ftp.mkd(current)
            except ftplib.error_perm:
                pass

    def put(self, path: str, data: bytes) -> None:
        self.mkdirs(path.rsplit('/', 1)[0])
        self.ftp.storbinary('STOR ' + path, io.BytesIO(data))

    def remove_empty_dirs(self, root: str) -> None:
        for name, facts in list(self.ftp.mlsd(root, facts=['type'])):
            if facts.get('type') == 'dir' and name not in {'.', '..'}:
                child = root.rstrip('/') + '/' + name
                self.remove_empty_dirs(child)
                try:
                    self.ftp.rmd(child)
                except ftplib.error_perm:
                    pass


def http(url: str, headers: dict | None = None) -> tuple[int, bytes]:
    request = urllib.request.Request(url, headers={'User-Agent': 'MENIGAR comprobacion de subida', **(headers or {})})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('paquete', type=Path)
    parser.add_argument('privada', type=Path)
    parser.add_argument('--host', required=True, help='servidor FTP de Hostytec')
    args = parser.parse_args()

    manifest = json.loads((args.paquete / 'MANIFIESTO.json').read_text())
    config_file = args.privada / 'config-subpath.php'
    config_text = config_file.read_text()
    data_dir = re.search(r'"dataDir": "([^"]+)"', config_text).group(1)
    if not data_dir.startswith(SERVER_ROOT + APP + '/private/'):
        sys.exit('La carpeta de datos de la configuración no está en la zona privada del subdominio.')
    data_ftp = data_dir.removeprefix(SERVER_ROOT)
    uploads = {name: (args.paquete / name).read_bytes() for name in manifest['files']}
    for name, data in uploads.items():
        if hashlib.sha256(data).hexdigest() != manifest['files'][name]['sha256']:
            sys.exit(f'{name} no coincide con el manifiesto: vuelve a crear el paquete.')

    print(f'Paquete: {len(uploads)} archivos. Datos nuevos en {data_ftp}.')
    user = input('Usuario del FTP de Hostytec: ').strip()
    remote = Remote(args.host, user, getpass.getpass('Contraseña del FTP (no se muestra ni se guarda): '))
    print('Conectado por FTPS con certificado verificado.')

    # 1. Inventory, kept privately so the previous state can be compared or restored.
    before = {'fecha': datetime.now().isoformat(timespec='seconds'), 'publico': remote.walk(PUBLIC), 'subdominio': remote.walk(APP)}
    log = args.privada / ('inventario-antes-' + datetime.now().strftime('%Y%m%d-%H%M') + '.json')
    log.write_text(json.dumps(before, indent=2, ensure_ascii=False))
    stale = sorted(path for path in before['publico'] if path.removeprefix('/httpdocs/') not in {n.removeprefix('httpdocs/') for n in uploads})
    print(f'Inventario guardado en {log}: {len(before["publico"])} archivos en {PUBLIC}, {len(before["subdominio"])} en {APP}.')

    # 2. Upload code, settings and public files.
    if not ask(f'\nPaso 2: subir el código PHP a {APP}/backend/, la configuración a {APP}/private/config-subpath.php '
               f'y {sum(n.startswith("httpdocs/") for n in uploads)} archivos públicos a {PUBLIC}/.'):
        sys.exit('Cancelado: no se ha cambiado nada.')
    remote.mkdirs(data_ftp + '/uploads')
    remote.mkdirs(data_ftp + '/spool')
    for name, data in uploads.items():
        if name.startswith('pruebas.menigar.com/'):
            remote.put('/' + name, data)
    remote.put(APP + '/private/config-subpath.php', config_text.encode())
    for name, data in uploads.items():
        if name.startswith('httpdocs/'):
            remote.put('/' + name, data)
    print('Subido.')

    # 3. Retire what a previous install left behind.
    retire = [path for path in [APP + '/private/config.php', APP + '/private/data'] if remote.exists(path)]
    catalogue = [path for path in [APP + '/private/fichas.sqlite3'] if remote.exists(path)]
    print('\nPaso 3: retirar lo que sobra de la instalación anterior.')
    for path in retire:
        print(f'  apartar  {path}  ->  {path}{RETIRED}')
    for path in catalogue + stale:
        print(f'  borrar   {path}')
    if (retire or catalogue or stale) and ask('Se apartan las carpetas y se borran solo esos archivos.'):
        for path in retire:
            remote.ftp.rename(path, path + RETIRED)
        for path in catalogue + stale:
            if not (path.startswith(PUBLIC + '/') or path in catalogue):
                raise RuntimeError('Ruta fuera de lo previsto: ' + path)
            remote.ftp.delete(path)
        remote.remove_empty_dirs(PUBLIC)
        print('Hecho.')
    remote.ftp.quit()

    # 4. Check from outside.
    time.sleep(2)
    checks = []
    status, body = http(SITE + '/')
    checks.append(('El formulario abre en /pruebas/', status == 200 and b'solicitud.js' in body))
    status, body = http(SITE + '/api/config')
    config = json.loads(body or b'{}') if status == 200 else {}
    checks.append(('El formulario acepta solicitudes en modo prueba', config.get('mode') == 'review' and config.get('submissions') is True))
    checks.append(('La zona del equipo pide usuario', http(SITE + '/equipo/solicitudes')[0] == 401))
    checks.append(('El logo nítido existe', http(SITE + '/assets/marca/menigar-logo-2x.webp')[0] == 200))
    checks.append(('Las páginas antiguas de /pruebas/ ya no están', http(SITE + '/servicios/')[0] in (403, 404)))
    for name in ['httpdocs/pruebas/solicitud.js', 'httpdocs/pruebas/solicitud.html']:
        served = http('https://www.menigar.com/' + name.removeprefix('httpdocs/'))[1]
        checks.append((f'{name.split("/")[-1]} es exactamente el del paquete', hashlib.sha256(served).hexdigest() == manifest['files'][name]['sha256']))
    print('\nComprobación desde fuera:')
    for label, ok in checks:
        print(('  OK     ' if ok else '  FALLA  ') + label)
    print('\nLa web principal y WordPress no se han tocado.' if all(ok for _, ok in checks) else '\nRevisa lo que falla antes de avisar al equipo.')


if __name__ == '__main__':
    main()
