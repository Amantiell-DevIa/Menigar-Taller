"""Real HTTP integration: private staging gate plus unchanged Bearer/Basic APIs.

Only isolated temporary data and fake users. No existing preview configuration,
mail, hosting account or production endpoint is used.
"""
import base64
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import re
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

from test_php_intake import PHP, ROOT, SANDBOX, Client, available_port
import test_php_intake as intake_test_helpers


class GateService:
    def __init__(self, directory, packaged=False):
        self.root = Path(directory)
        self.base = 'http://127.0.0.1:' + str(available_port())
        self.password = 'staff-fake-' + uuid.uuid4().hex
        self.review_password = 'review-fake-' + uuid.uuid4().hex
        self.config_path = self.root / 'config.php'
        self.config = {'mode': 'review', 'acceptSubmissions': True, 'baseUrl': self.base,
            'secret': uuid.uuid4().hex + uuid.uuid4().hex, 'dataDir': str(self.root / 'data'),
            'termsVersion': 'test-v1', 'minFreeBytes': 0, 'storageBudgetBytes': 512 * 1024 * 1024,
            'requestsPerHour': 10000, 'staffUsers': {'test-staff': self.hash(self.password)},
            'reviewGate': {'enabled': True, 'users': {'reviewer': self.hash(self.review_password)},
                'stateDir': str(self.root / 'review-access'), 'allowLoopbackHttp': True,
                'attemptsPer15Minutes': 10, 'maxAgeSeconds': 28800, 'idleSeconds': 1800},
            'notifications': {'transport': 'spool', 'to': '', 'from': ''}}
        self.write_config()
        (self.root / 'sessions').mkdir()
        self.public = ROOT
        router = ROOT / 'backend/dev-router.php'
        if packaged:
            # A minimal package-layout fixture uses the actual public front controller.
            app = self.root / 'package'; self.public = app / 'public'
            shutil.copytree(ROOT / 'backend', app / 'backend')
            (self.public / 'api').mkdir(parents=True)
            for name in ['index.php', 'review.php']:
                shutil.copyfile(ROOT / 'api' / name, self.public / 'api' / name)
            for name in ['index.html','resumen.html','receipt.js','style.css']:
                shutil.copyfile(ROOT / name, self.public / name)
            # Small static fixtures exercise the same path allowlist and MIME behavior.
            (self.public / 'assets').mkdir()
            (self.public / 'assets/probe.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"/>')
            (self.public / 'assets/probe.pdf').write_bytes(b'%PDF-1.4\n%%EOF')
            (self.public / 'api/should-not-run.php').write_text('<?php echo "BYPASS";')
            router = self.root / 'package-router.php'
            router.write_text("<?php require " + repr(str(self.public / 'api/review.php')) + ";")
        self.log = (self.root / 'php.log').open('ab')
        command = [PHP, '-d', 'display_errors=0', '-d', 'log_errors=1', '-d', 'post_max_size=15M',
            '-d', 'upload_max_filesize=10M', '-d', 'memory_limit=256M', '-d', 'max_file_uploads=20',
            '-d', 'disable_functions=mail,exec,system,shell_exec,proc_open',
            '-d', 'session.save_path=' + str(self.root / 'sessions'), '-S', self.base.removeprefix('http://'),
            '-t', str(self.public), str(router)]
        if SANDBOX.exists() and shutil.which('sandbox-exec'):
            command = ['sandbox-exec', '-f', str(SANDBOX), *command]
        self.proc = subprocess.Popen(command, env={**os.environ, 'MENIGAR_CONFIG': str(self.config_path),
            'MENIGAR_REVIEW_GATE': '1', 'PHP_CLI_SERVER_WORKERS': '2'}, stdout=self.log, stderr=self.log, start_new_session=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.proc.poll() is not None: raise RuntimeError('Isolated gate server stopped')
            try:
                urllib.request.urlopen(self.base + '/', timeout=1)
            except urllib.error.HTTPError as error:
                if error.code == 401: break
            except (urllib.error.URLError, TimeoutError): pass
            time.sleep(.05)
        else: self.stop(); raise RuntimeError('Isolated gate did not start')

    @staticmethod
    def hash(password):
        return subprocess.check_output([PHP, '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);', password], text=True)

    def write_config(self):
        temporary = self.config_path.with_suffix('.next')
        temporary.write_text("<?php return json_decode(<<<'GATE_TEST'\n" + json.dumps(self.config) + "\nGATE_TEST\n, true);")
        temporary.chmod(0o600); temporary.replace(self.config_path)

    def stop(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM); self.proc.wait(timeout=10)
        self.log.close()


class GateClient(Client):
    def __init__(self, service):
        self.service = service
        self.cookies = http.cookiejar.CookieJar()
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(self.cookies))

    def login(self, password=None, next_path='/', csrf=None, origin=None):
        status, page, _ = self.request('/_revision/acceso')
        if status != 401: raise AssertionError((status, page))
        token = re.search(rb'name="csrf" value="([a-f0-9]+)"', page).group(1).decode()
        body = urllib.parse.urlencode({'user':'reviewer', 'password':password or self.service.review_password,
            'csrf':csrf or token, 'next':next_path}).encode()
        return self.request('/_revision/acceso', body, {'Origin':origin or self.service.base,
            'Accept':'application/json', 'Content-Type':'application/x-www-form-urlencoded'})

    def load_config(self):
        status, self.config, _ = self.request('/api/config')
        if status != 200: raise AssertionError((status, self.config))


@unittest.skipUnless(Path(PHP).is_file(), 'Set MENIGAR_PHP to a PHP 8.3 runtime')
class ReviewGateTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='menigar-review-gate-')
        cls.service = GateService(cls.temp.name, packaged=True)

    @classmethod
    def tearDownClass(cls):
        cls.service.stop(); cls.temp.cleanup()

    def setUp(self): self.client = GateClient(self.service)

    def test_01_all_types_and_direct_php_fail_closed_without_cookie(self):
        for path in ['/', '/index.html', '/resumen.html', '/style.css', '/receipt.js',
            '/assets/probe.svg', '/assets/probe.pdf', '/api/config', '/api/index.php',
            '/api/review.php', '/api/should-not-run.php', '/equipo/solicitudes', '/backend/README.md']:
            status, body, headers = self.client.request(path)
            self.assertEqual(status, 401, path)
            self.assertIn('no-store', headers['Cache-Control'])
            self.assertNotIn(b'BYPASS', body if isinstance(body, bytes) else json.dumps(body).encode())
        status, body, _ = self.client.request('/api/config', headers={'Authorization':'Bearer ' + 'a' * 43})
        self.assertEqual(status, 401); self.assertTrue(body['reviewAccessRequired'])

    def test_02_login_errors_are_real_errors_csrf_origin_and_cookie_flags(self):
        self.assertEqual(self.client.login(password='wrong')[0], 401)
        self.assertEqual(self.client.login(csrf='invalid')[0], 403)
        self.assertEqual(self.client.login(origin='https://other.invalid')[0], 403)
        status, data, headers = self.client.login()
        self.assertEqual(status, 200); self.assertTrue(data['authenticated'])
        self.assertIn('HttpOnly', headers.get('Set-Cookie', ''))
        self.assertIn('SameSite=Strict', headers.get('Set-Cookie', ''))
        self.assertEqual(self.client.request('/style.css')[0], 200)
        self.assertEqual(self.client.request('/assets/probe.pdf')[0], 200)
        self.assertEqual(self.client.request('/backend/README.md')[0], 404)
        self.assertEqual(self.client.request('/api/should-not-run.php')[0], 404)

    def test_03_cookie_gate_plus_bearer_and_staff_basic_preserve_separate_auth(self):
        self.assertEqual(self.client.login()[0], 200); self.client.load_config()
        fixture = intake_test_helpers.PhpIntakeTests.fixture(self)
        status, saved, _ = self.client.submit(*fixture)
        self.assertEqual(status, 201, saved)
        bearer = {'Authorization':'Bearer ' + saved['requestId']}
        self.assertEqual(self.client.request('/api/resumen')[0], 404)
        status, summary, _ = self.client.request('/api/resumen', headers=bearer)
        self.assertEqual(status, 200); self.assertEqual(summary['reference'], saved['reference'])
        file_id = summary['units'][0]['attachments'][0]['id']
        status, downloaded, _ = self.client.request('/api/archivos/' + file_id, headers=bearer)
        self.assertEqual(status, 200); self.assertEqual(hashlib.sha256(downloaded).digest(), hashlib.sha256(fixture[1][0][3]).digest())
        self.assertEqual(self.client.request('/equipo/solicitudes')[0], 401)
        self.assertEqual(self.client.request('/equipo/solicitudes', headers=bearer)[0], 401)
        basic = {'Authorization':'Basic ' + base64.b64encode(('test-staff:' + self.service.password).encode()).decode()}
        self.assertEqual(self.client.request('/equipo/solicitudes', headers=basic)[0], 200)
        self.assertEqual(self.client.request('/api/resumen', headers=basic)[0], 404)
        outsider = GateClient(self.service)
        self.assertEqual(outsider.request('/api/resumen', headers=bearer)[0], 401)
        self.assertEqual(outsider.request('/equipo/solicitudes', headers=basic)[0], 401)
        self.assertNotIn(saved['requestId'], (self.service.root / 'php.log').read_text())

    def test_04_external_redirects_and_fragment_cannot_enter_next(self):
        for next_path in ['https://example.invalid', '//example.invalid', '/\\example.invalid', '/foo#secret', '/%0d%0aLocation:bad']:
            status, data, _ = self.client.login(next_path=next_path)
            self.assertEqual(status, 200); self.assertEqual(data['next'], '/')
        status, data, _ = self.client.login(next_path='/solicitud.html?pieza=main-3198')
        self.assertEqual(status, 200); self.assertEqual(data['next'], '/solicitud.html?pieza=main-3198')
        _, page, headers = self.client.request('/_revision/acceso')
        self.assertIn("connect-src 'self'", headers['Content-Security-Policy'])
        self.assertIn(b'const fragment = location.hash', page)

    def test_05_logout_revokes_gate_without_changing_app_auth(self):
        self.client.login(); _, page, _ = self.client.request('/_revision/acceso')
        csrf = re.search(rb'name="csrf" value="([a-f0-9]+)"', page).group(1).decode()
        status, _, _ = self.client.request('/_revision/salir', urllib.parse.urlencode({'csrf':csrf}).encode(),
            {'Origin':self.service.base, 'Content-Type':'application/x-www-form-urlencoded'})
        self.assertEqual(status, 200); self.assertEqual(self.client.request('/api/config')[0], 401)

    def test_06_credential_rotation_expires_existing_gate_cookie(self):
        self.client.login()
        old = self.service.config['reviewGate']['users']['reviewer']
        try:
            self.service.config['reviewGate']['users']['reviewer'] = self.service.hash('replacement-fake-password')
            self.service.write_config()
            self.assertEqual(self.client.request('/style.css')[0], 401)
        finally:
            self.service.config['reviewGate']['users']['reviewer'] = old; self.service.write_config()

    def test_07_absent_corrupt_disabled_and_production_configs_are_closed(self):
        original = self.service.config_path.read_text()
        try:
            self.service.config_path.unlink()
            self.assertEqual(self.client.request('/style.css')[0], 503)
            self.service.config_path.write_text('<?php return "not-an-array";')
            self.assertEqual(self.client.request('/api/config')[0], 503)
            for change in [{'reviewGate':{'enabled':False}}, {'mode':'production'}, {'baseUrl':'https://wrong.invalid'}]:
                config = {**self.service.config, **change}
                self.service.config_path.write_text("<?php return json_decode('" + json.dumps(config).replace('\\','\\\\').replace("'", "\\'") + "', true);")
                self.assertEqual(self.client.request('/index.html')[0], 503)
        finally: self.service.config_path.write_text(original); self.service.config_path.chmod(0o600)

    def test_08_failed_attempt_limit_survives_new_cookies(self):
        old = self.service.config['reviewGate']['attemptsPer15Minutes']
        try:
            self.client.login() # Reset the IP bucket before exercising failure attempts.
            self.service.config['reviewGate']['attemptsPer15Minutes'] = 2; self.service.write_config()
            self.assertEqual(GateClient(self.service).login(password='incorrect-one')[0], 401)
            self.assertEqual(GateClient(self.service).login(password='incorrect-two')[0], 401)
            self.assertEqual(GateClient(self.service).login()[0], 429)
        finally:
            self.service.config['reviewGate']['attemptsPer15Minutes'] = old; self.service.write_config()
            for path in (self.service.root / 'review-access/attempts').glob('*.json'): path.unlink()


if __name__ == '__main__': unittest.main()
