#!/usr/bin/env python3
"""Configuración privada del formulario de prueba: clave nueva y un acceso por persona.

Escribe en una carpeta PRIVADA (fuera del proyecto, permisos 600):

  config-subpath.php   la configuración que va a /pruebas.menigar.com/private/
  accesos-equipo.txt   usuario y contraseña de cada persona, para dárselos en mano

Las contraseñas se generan al azar y solo se guardan en ese archivo; en la configuración
va su huella (password_hash de PHP), nunca la contraseña. El script no muestra ninguna
en pantalla.
"""
from __future__ import annotations

import argparse
import json
import os
import secrets
import subprocess
from datetime import date
from pathlib import Path

DEFAULT_PHP = '/Users/kaykostar/Documents/MENIGAR/restauracion-prueba-2026-10-15/runtime/php-8.3.30/bin/php'
ALPHABET = 'abcdefghjkmnpqrstuvwxyz23456789'  # sin letras que se confunden (l, 1, o, 0, i)


def new_password() -> str:
    return '-'.join(''.join(secrets.choice(ALPHABET) for _ in range(4)) for _ in range(4))


def hashes(passwords: dict[str, str], php: str) -> dict[str, str]:
    code = '$p = json_decode(stream_get_contents(STDIN), true); $o = []; foreach ($p as $u => $w) $o[$u] = password_hash($w, PASSWORD_DEFAULT); echo json_encode($o);'
    result = subprocess.run([php, '-r', code], input=json.dumps(passwords), capture_output=True, text=True, check=True)
    return json.loads(result.stdout)


def config(args: argparse.Namespace, staff: dict[str, str]) -> dict:
    app_root = args.app_root.rstrip('/')
    return {
        'mode': 'review',
        'acceptSubmissions': True,
        'baseUrl': args.base_url.rstrip('/'),
        'basePath': '/' + args.base.strip('/'),
        'allowedOrigins': [args.base_url.rstrip('/')] + [o.strip().rstrip('/') for o in args.otros_origenes.split(',') if o.strip()],
        'secret': secrets.token_hex(32),
        'dataDir': f'{app_root}/private/{args.datos}',
        'termsVersion': 'borrador-revision',
        'maxFileBytes': 5 * 1024 * 1024,
        'maxTotalBytes': 15 * 1024 * 1024,
        'maxFilesPerUnit': 5,
        'maxTotalFiles': 50,
        'maxUnits': 10,
        'minFreeBytes': 50 * 1024 * 1024,
        'storageBudgetBytes': 128 * 1024 * 1024,
        'requestsPerHour': 30,
        'staffUsers': staff,
        'notifications': {
            'transport': args.transporte,
            'immediate': True,
            'richEmail': True,
            'to': [address.strip() for address in args.para.split(',') if address.strip()],
            'from': args.de,
        },
    }


def write_private(path: Path, text: str) -> None:
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.tmp')
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as handle:
        handle.write(text)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('destino', type=Path, help='carpeta privada, fuera del proyecto')
    parser.add_argument('--usuarios', default='abraham,ricardo,jose-luis')
    parser.add_argument('--para', default='informacion@menigar.com', help='destinatarios del aviso, separados por comas (p. ej. el buzón del laboratorio y una copia)')
    parser.add_argument('--de', default='informacion@menigar.com')
    parser.add_argument('--base-url', default='https://www.menigar.com')
    parser.add_argument('--otros-origenes', default='https://menigar.com', help='la misma web con otra dirección (sin www)')
    parser.add_argument('--base', default='/pruebas')
    parser.add_argument('--app-root', default='/var/www/vhosts/menigar.com/pruebas.menigar.com')
    parser.add_argument('--datos', default='data-' + date.today().isoformat(), help='carpeta nueva de datos: la prueba empieza vacía')
    parser.add_argument('--transporte', default='sendmail', choices=['sendmail', 'spool'])
    parser.add_argument('--php', default=os.environ.get('MENIGAR_PHP', DEFAULT_PHP))
    args = parser.parse_args()

    if Path(__file__).resolve().parents[1] in args.destino.resolve().parents:
        raise SystemExit('La carpeta privada no puede estar dentro del proyecto.')
    users = [name.strip() for name in args.usuarios.split(',') if name.strip()]
    passwords = {name: new_password() for name in users}
    settings = config(args, hashes(passwords, args.php))
    source = "<?php\n// Configuración privada del formulario de prueba. No publicar ni copiar al proyecto.\nreturn json_decode(<<<'MENIGAR_CONFIG'\n" + json.dumps(settings, indent=2, ensure_ascii=False) + "\nMENIGAR_CONFIG\n, true);\n"
    write_private(args.destino / 'config-subpath.php', source)
    lines = ['Accesos a la zona del equipo del formulario de prueba de MENIGAR',
             f'Dirección: {args.base_url.rstrip("/")}/{args.base.strip("/")}/equipo/solicitudes', '',
             'Dáselos a cada persona en mano o por teléfono, no por correo ni WhatsApp.', '']
    lines += [f'{name}: {password}' for name, password in passwords.items()]
    write_private(args.destino / 'accesos-equipo.txt', '\n'.join(lines) + '\n')
    print(f'Configuración y accesos creados en {args.destino} ({len(users)} usuarios). Las contraseñas están solo en accesos-equipo.txt.')


if __name__ == '__main__':
    main()
