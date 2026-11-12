"""The upload of the test form, run against an in-memory FTP server with a previous install on it."""
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_prueba_formulario as package  # noqa: E402
import subir_prueba_formulario as upload  # noqa: E402
import ftplib  # noqa: E402


class FakeFTP:
    """Files are {path: bytes}; directories are implied by paths or listed in dirs."""
    tree: dict = {}
    dirs: set = set()

    def __init__(self, *args, **kwargs):
        self.secure = False

    def connect(self, host, port): self.host = host
    def login(self, user, password): assert password == 'ftp-de-prueba'
    def prot_p(self): self.secure = True
    def quit(self): pass

    def _children(self, path):
        path = path.rstrip('/') or ''
        names = {}
        for full in list(self.tree) + list(self.dirs):
            if full.startswith(path + '/') and full != path:
                head = full[len(path) + 1:].split('/', 1)
                names[head[0]] = 'dir' if len(head) > 1 or full in self.dirs and len(head) == 1 and full not in self.tree else 'file'
        return names

    def mlsd(self, path, facts=None):
        if path.rstrip('/') and path.rstrip('/') not in self.dirs and not self._children(path):
            raise ftplib.error_perm('550 no existe')
        for name, kind in self._children(path).items():
            full = path.rstrip('/') + '/' + name
            yield name, {'type': kind, 'size': str(len(self.tree.get(full, b'')))}

    def mkd(self, path):
        if path in self.dirs:
            raise ftplib.error_perm('550 existe')
        self.dirs.add(path)

    def storbinary(self, command, handle):
        assert self.secure
        self.tree[command.removeprefix('STOR ')] = handle.read()

    def rename(self, old, new):
        for collection in (self.tree, ):
            for key in [k for k in collection if k == old or k.startswith(old + '/')]:
                collection[new + key[len(old):]] = collection.pop(key)
        for key in [d for d in self.dirs if d == old or d.startswith(old + '/')]:
            self.dirs.discard(key)
            self.dirs.add(new + key[len(old):])

    def delete(self, path):
        del self.tree[path]

    def rmd(self, path):
        if self._children(path):
            raise ftplib.error_perm('550 no vacía')
        self.dirs.discard(path)


class UploadTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='menigar-subida-')
        base = Path(self.temp.name)
        self.package = base / 'paquete'
        package.build(self.package)
        self.private = base / 'privado'
        self.private.mkdir()
        (self.private / 'config-subpath.php').write_text('<?php\nreturn json_decode(<<<\'X\'\n{"dataDir": "/var/www/vhosts/menigar.com/pruebas.menigar.com/private/data-2026-11-12"}\nX\n, true);\n')
        FakeFTP.tree = {
            '/httpdocs/index.php': b'wordpress',
            '/httpdocs/.htaccess': b'wordpress rules',
            '/httpdocs/pruebas/index.html': b'old home',
            '/httpdocs/pruebas/servicios/index.html': b'old page',
            '/httpdocs/pruebas/solicitud.html': b'old form',
            '/pruebas.menigar.com/private/config.php': b'old public config',
            '/pruebas.menigar.com/private/config-subpath.php': b'old subpath config',
            '/pruebas.menigar.com/private/data/solicitudes.sqlite3': b'5 test requests',
            '/pruebas.menigar.com/private/fichas.sqlite3': b'catalogue',
        }
        FakeFTP.dirs = {'/httpdocs', '/httpdocs/pruebas', '/httpdocs/pruebas/servicios', '/pruebas.menigar.com', '/pruebas.menigar.com/private', '/pruebas.menigar.com/private/data'}

    def tearDown(self):
        self.temp.cleanup()

    def run_upload(self, answers):
        manifest = json.loads((self.package / 'MANIFIESTO.json').read_text())
        def http(url, headers=None):
            if url.endswith('/api/config'):
                return 200, b'{"mode": "review", "submissions": true}'
            if url.endswith('/equipo/solicitudes'):
                return 401, b''
            if url.endswith('/servicios/'):
                return 404, b''
            name = 'httpdocs/' + url.split('www.menigar.com/', 1)[1] if 'www.menigar.com/pruebas/' in url and url.endswith(('.js', '.html')) else None
            if name and name in manifest['files']:
                return 200, (self.package / name).read_bytes()
            return 200, b'solicitud.js'
        output = io.StringIO()
        with mock.patch.object(upload.ftplib, 'FTP_TLS', FakeFTP), mock.patch.object(upload, 'http', http), \
             mock.patch('builtins.input', side_effect=answers), mock.patch.object(upload.getpass, 'getpass', return_value='ftp-de-prueba'), \
             mock.patch.object(upload.time, 'sleep'), mock.patch('sys.stdout', output), \
             mock.patch.object(sys, 'argv', ['subir', str(self.package), str(self.private), '--host', 'ftp.example.invalid']):
            try:
                upload.main()
            except SystemExit as stop:
                return output.getvalue() + str(stop)
        return output.getvalue()

    def test_upload_replaces_the_test_closes_the_old_one_and_never_touches_wordpress(self):
        log = self.run_upload(['usuario', 'si', 'si'])
        tree = FakeFTP.tree
        self.assertEqual(tree['/httpdocs/index.php'], b'wordpress')
        self.assertEqual(tree['/httpdocs/.htaccess'], b'wordpress rules')
        self.assertEqual(tree['/httpdocs/pruebas/solicitud.html'], (self.package / 'httpdocs/pruebas/solicitud.html').read_bytes())
        self.assertNotIn('/httpdocs/pruebas/index.html', tree)
        self.assertNotIn('/httpdocs/pruebas/servicios/index.html', tree)
        self.assertNotIn('/httpdocs/pruebas/servicios', FakeFTP.dirs)
        self.assertNotIn('/pruebas.menigar.com/private/fichas.sqlite3', tree)
        self.assertNotIn('/pruebas.menigar.com/private/config.php', tree)
        retired = [k for k in tree if k.startswith('/pruebas.menigar.com/private/config.php-retirado-')]
        self.assertEqual(len(retired), 1)
        kept = [k for k in tree if k.startswith('/pruebas.menigar.com/private/data-retirado-')]
        self.assertEqual([tree[k] for k in kept], [b'5 test requests'])
        self.assertIn('/pruebas.menigar.com/private/data-2026-11-12/spool', FakeFTP.dirs)
        self.assertIn('/pruebas.menigar.com/backend/Http.php', tree)
        self.assertNotIn('FALLA', log)
        self.assertNotIn('ftp-de-prueba', log)
        inventory = list(self.private.glob('inventario-antes-*.json'))
        self.assertEqual(len(inventory), 1)
        self.assertIn('/httpdocs/pruebas/servicios/index.html', json.loads(inventory[0].read_text())['publico'])

    def test_saying_no_at_the_first_question_changes_nothing(self):
        before = dict(FakeFTP.tree)
        log = self.run_upload(['usuario', 'no'])
        self.assertEqual(FakeFTP.tree, before)
        self.assertIn('Cancelado', log)

    def test_saying_no_to_the_cleanup_uploads_but_keeps_the_old_files(self):
        self.run_upload(['usuario', 'si', 'no'])
        self.assertIn('/httpdocs/pruebas/index.html', FakeFTP.tree)
        self.assertIn('/pruebas.menigar.com/private/config.php', FakeFTP.tree)
        self.assertIn('/pruebas.menigar.com/backend/Http.php', FakeFTP.tree)


if __name__ == '__main__':
    unittest.main()
