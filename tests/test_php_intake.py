"""HTTP acceptance tests against the real PHP backend and hosting-sized limits.

All names, files and credentials belong to an isolated temporary test service.
PHP is sandboxed on this Mac; mail() is disabled and notifications only spool.
"""
from concurrent.futures import ThreadPoolExecutor
import base64
import copy
import hashlib
import http.cookiejar
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import sqlite3
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.parse
import urllib.request
import uuid

ROOT = Path(__file__).resolve().parents[1]
PHP = os.environ.get('MENIGAR_PHP') or shutil.which('php') or '/Users/kaykostar/Documents/MENIGAR/restauracion-prueba-2026-10-15/runtime/php-8.3.30/bin/php'
SANDBOX = Path('/Users/kaykostar/Documents/MENIGAR/restauracion-prueba-2026-10-15/control/network.sb')


def available_port():
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        return sock.getsockname()[1]


class Service:
    def __init__(self, directory, config=None, port=None):
        self.root = Path(directory)
        self.base = 'http://127.0.0.1:' + str(port or available_port())
        self.config_path = self.root / 'config.php'
        self.password = 'test-only-' + uuid.uuid4().hex
        password_hash = subprocess.check_output([PHP, '-r', 'echo password_hash($argv[1], PASSWORD_DEFAULT);', self.password], text=True)
        self.config = config or {'mode': 'review', 'acceptSubmissions': True, 'baseUrl': self.base,
            'secret': uuid.uuid4().hex + uuid.uuid4().hex, 'dataDir': str(self.root / 'data'),
            'termsVersion': 'test-v1', 'minFreeBytes': 0, 'storageBudgetBytes': 512 * 1024 * 1024,
            'requestsPerHour': 10000, 'staffUsers': {'test-staff': password_hash},
            'notifications': {'transport': 'spool', 'to': '', 'from': ''}}
        self.write_config()
        self.log = (self.root / 'php.log').open('ab')
        (self.root / 'sessions').mkdir(exist_ok=True)
        command = [PHP, '-d', 'display_errors=0', '-d', 'log_errors=1', '-d', 'post_max_size=15M',
            '-d', 'upload_max_filesize=10M', '-d', 'memory_limit=256M', '-d', 'max_execution_time=60',
            '-d', 'max_file_uploads=20', '-d', 'disable_functions=mail,exec,system,shell_exec,proc_open',
            '-d', 'session.save_path=' + str(self.root / 'sessions'),
            '-S', self.base.removeprefix('http://'), '-t', str(ROOT), str(ROOT / 'backend/dev-router.php')]
        if SANDBOX.exists() and shutil.which('sandbox-exec'):
            command = ['sandbox-exec', '-f', str(SANDBOX), *command]
        env = {**os.environ, 'MENIGAR_CONFIG': str(self.config_path), 'PHP_CLI_SERVER_WORKERS': '4'}
        self.proc = subprocess.Popen(command, env=env, stdout=self.log, stderr=self.log, start_new_session=True)
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            if self.proc.poll() is not None:
                raise RuntimeError('PHP test server stopped; inspect isolated log')
            try:
                urllib.request.urlopen(self.base + '/api/config', timeout=1).read()
                break
            except Exception:
                time.sleep(.05)
        else:
            self.stop()
            raise RuntimeError('PHP test server did not start')

    def write_config(self):
        source = "<?php\nreturn json_decode(<<<'MENIGAR_TEST_CONFIG'\n" + json.dumps(self.config) + "\nMENIGAR_TEST_CONFIG\n, true);\n"
        temporary = self.config_path.with_suffix('.next')
        temporary.write_text(source)
        temporary.chmod(0o600)
        temporary.replace(self.config_path)

    def stop(self):
        if self.proc.poll() is None:
            os.killpg(self.proc.pid, signal.SIGTERM)
            self.proc.wait(timeout=10)
        self.log.close()

    def cli(self, name, *args):
        return subprocess.run([PHP, '-d', 'disable_functions=mail', str(ROOT / 'backend/bin' / name),
            '--config', str(self.config_path), '--public-root', str(ROOT), *args], capture_output=True, text=True)


class Client:
    def __init__(self, service):
        self.service = service
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        status, self.config, _ = self.request('/api/config')
        if status != 200:
            raise RuntimeError('Client configuration unavailable')

    def request(self, path, body=None, headers=None, method=None):
        request = urllib.request.Request(self.service.base + path, data=body, headers=headers or {}, method=method)
        try:
            response = self.opener.open(request, timeout=45)
        except urllib.error.HTTPError as error:
            response = error
        with response:
            raw = response.read()
            value = json.loads(raw) if 'application/json' in response.headers.get('Content-Type', '') else raw
            return response.status, value, response.headers

    def json(self, path, payload, headers=None):
        return self.request(path, json.dumps(payload).encode(), {'Origin': self.service.base, 'X-CSRF-Token': self.config['csrfToken'], 'Content-Type': 'application/json', **(headers or {})})

    def submit(self, payload, files=None, headers=None):
        boundary = 'menigar-test-' + uuid.uuid4().hex
        chunks = [('Content-Disposition: form-data; name="payload"\r\n\r\n' + json.dumps(payload)).encode()]
        for key, name, mime, blob in files or []:
            chunks.append(('Content-Disposition: form-data; name="files[' + key + ']"; filename="' + name + '"\r\nContent-Type: ' + mime + '\r\n\r\n').encode() + blob)
        body = b''.join(b'--' + boundary.encode() + b'\r\n' + part + b'\r\n' for part in chunks) + b'--' + boundary.encode() + b'--\r\n'
        return self.request('/api/solicitudes', body, {'Origin': self.service.base, 'X-CSRF-Token': self.config['csrfToken'], 'Content-Type': 'multipart/form-data; boundary=' + boundary, **(headers or {})})


@unittest.skipUnless(Path(PHP).is_file(), 'Set MENIGAR_PHP to a PHP 8.3 runtime')
class PhpIntakeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='menigar-php-tests-')
        cls.service = Service(cls.temp.name)

    @classmethod
    def tearDownClass(cls):
        cls.service.stop()
        cls.temp.cleanup()

    def setUp(self):
        self.client = Client(self.service)

    def fixture(self, pdf=b'%PDF-1.4\n% isolated test\n%%EOF'):
        unit = {'componentKey': 'abs', 'componentName': 'ABS / ESP', 'reference': '0012-ABC',
                'symptoms': 'Prueba ficticia: fallo intermitente', 'accessories': 'Un cable',
                'attachments': [{'uploadKey': 'u0a0', 'name': 'prueba.pdf', 'mime': 'application/pdf', 'size': len(pdf)}]}
        payload = {'idempotencyKey': uuid.uuid4().hex, 'intent': 'consultation',
            'customer': {'type': 'particular', 'name': 'Prueba ficticia', 'email': 'prueba@example.invalid', 'phone': '600000000'},
            'vehicle': {'brand': 'Honda', 'model': 'Civic'},
            'units': [unit, {**unit, 'reference': 'OTRA-003', 'attachments': []}],
            'acceptance': {'privacyRead': True, 'conditionsRead': True, 'version': 'test-v1'}}
        return payload, [('u0a0', 'prueba.pdf', 'application/pdf', pdf)]

    def bearer(self, result):
        return {'Authorization': 'Bearer ' + result['requestId']}

    def staff(self):
        return {'Authorization': 'Basic ' + base64.b64encode(('test-staff:' + self.service.password).encode()).decode()}

    def db(self):
        db = sqlite3.connect(Path(self.service.config['dataDir']) / 'solicitudes.sqlite3')
        db.row_factory = sqlite3.Row
        return db

    def test_01_runtime_advertises_host_limits_and_binary_transport(self):
        config = self.client.config
        self.assertEqual(config['transport'], 'multipart')
        self.assertEqual(config['maxTotalBytes'], 14 * 1024 * 1024)
        self.assertEqual(config['maxTotalFiles'], 20)
        self.assertEqual(config['maxFileBytes'], 5 * 1024 * 1024)
        self.assertFalse(config['emailConfigured'])
        self.assertFalse(config['workshopIntegrationConfigured'])

    def test_02_two_units_persist_retries_do_not_duplicate_and_private_files_download(self):
        payload, files = self.fixture()
        status, saved, _ = self.client.submit(payload, files)
        self.assertEqual(status, 201, saved)
        status, second, _ = self.client.submit(payload, files)
        self.assertEqual(status, 200, second)
        self.assertEqual(saved['reference'], second['reference'])
        self.assertEqual(saved['summaryUrl'], '/resumen.html#' + saved['requestId'])
        status, stored, headers = self.client.request('/api/resumen', headers=self.bearer(saved))
        self.assertEqual(status, 200)
        self.assertIn('no-store', headers['Cache-Control'])
        self.assertEqual([u['reference'] for u in stored['units']], ['0012-ABC', 'OTRA-003'])
        file_id = stored['units'][0]['attachments'][0]['id']
        status, blob, headers = self.client.request('/api/archivos/' + file_id, headers=self.bearer(saved))
        self.assertEqual(status, 200)
        self.assertEqual(blob, files[0][3])
        self.assertIn('attachment;', headers['Content-Disposition'])
        self.assertEqual(self.client.request('/api/archivos/' + file_id)[0], 404)
        self.assertEqual(self.client.request('/api/resumen')[0], 404)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests WHERE reference=?', (saved['reference'],)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM files WHERE request_reference=?', (saved['reference'],)).fetchone()[0], 1)
            self.assertEqual(db.execute('SELECT count(*) FROM notifications WHERE request_reference=?', (saved['reference'],)).fetchone()[0], 1)
            raw_db = (Path(self.service.config['dataDir']) / 'solicitudes.sqlite3').read_bytes()
            self.assertNotIn(saved['requestId'].encode(), raw_db)
        self.assertNotIn(saved['requestId'], (Path(self.service.root) / 'php.log').read_text())

    def test_03_lost_response_can_be_recovered_by_the_original_idempotency_key(self):
        payload, files = self.fixture()
        _, saved, _ = self.client.submit(payload, files)
        fresh_client = Client(self.service)
        status, recovered, _ = fresh_client.json('/api/recuperar', {'idempotencyKey': payload['idempotencyKey']})
        self.assertEqual(status, 200)
        self.assertEqual(recovered['reference'], saved['reference'])
        self.assertEqual(recovered['requestId'], saved['requestId'])
        self.assertEqual(fresh_client.json('/api/recuperar', {'idempotencyKey': uuid.uuid4().hex})[0], 404)

    def test_04_changed_retry_is_rejected_without_overwriting_original_data(self):
        payload, files = self.fixture(); _, saved, _ = self.client.submit(payload, files)
        payload['units'][0]['reference'] = 'CAMBIADA'
        self.assertEqual(self.client.submit(payload, files)[0], 409)
        _, stored, _ = self.client.request('/api/resumen', headers=self.bearer(saved))
        self.assertEqual(stored['units'][0]['reference'], '0012-ABC')

    def test_05_invalid_origin_csrf_content_and_shipping_do_not_create_rows(self):
        payload, files = self.fixture()
        self.assertEqual(self.client.submit(payload, files, {'Origin': 'https://otro.example'})[0], 403)
        self.assertEqual(self.client.submit(payload, files, {'X-CSRF-Token': 'invalid'})[0], 419)
        self.assertEqual(self.client.submit(payload, [('u0a0','bad.pdf','application/pdf',b'<script>bad</script>')])[0], 422)
        payload['intent'] = 'repair'
        self.assertEqual(self.client.submit(payload, files)[0], 422)
        with self.db() as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests WHERE key_hash=?', (self.key_hash(payload['idempotencyKey']),)).fetchone()[0], 0)

    def key_hash(self, key):
        import hmac
        return hmac.new(self.service.config['secret'].encode(), ('idempotency:' + key).encode(), hashlib.sha256).hexdigest()

    def test_06_files_cannot_cross_request_boundaries(self):
        payload, files = self.fixture(); _, first, _ = self.client.submit(payload, files)
        payload['idempotencyKey'] = uuid.uuid4().hex
        _, other, _ = self.client.submit(payload, files)
        _, stored, _ = self.client.request('/api/resumen', headers=self.bearer(first))
        file_id = stored['units'][0]['attachments'][0]['id']
        self.assertEqual(self.client.request('/api/archivos/' + file_id, headers=self.bearer(other))[0], 404)

    def test_07_staff_access_and_review_preserve_customer_originals(self):
        payload, files = self.fixture(); payload['customer']['name'] = '<img src=x onerror=alert(1)>'
        _, saved, _ = self.client.submit(payload, files)
        self.assertEqual(self.client.request('/equipo/solicitudes')[0], 401)
        status, inbox, _ = self.client.request('/equipo/solicitudes', headers=self.staff())
        self.assertEqual(status, 200); self.assertIn(saved['reference'].encode(), inbox)
        path = '/equipo/solicitudes/' + saved['reference']
        status, page, _ = self.client.request(path, headers=self.staff())
        self.assertEqual(status, 200); self.assertIn(b'&lt;img', page); self.assertNotIn(b'<img src=x', page)
        with self.db() as db: before = db.execute('SELECT payload FROM requests WHERE reference=?', (saved['reference'],)).fetchone()[0]
        form = urllib.parse.urlencode({'csrf': self.client.config['csrfToken']}).encode()
        for _ in range(2):
            status, _, _ = self.client.request(path + '/revisada', form, {'Origin': self.service.base, 'Content-Type': 'application/x-www-form-urlencoded', **self.staff()})
            self.assertEqual(status, 200)
        with self.db() as db:
            after = db.execute('SELECT payload,reviewed_at FROM requests WHERE reference=?', (saved['reference'],)).fetchone()
            self.assertEqual(before, after['payload']); self.assertTrue(after['reviewed_at'])
            self.assertEqual(db.execute("SELECT count(*) FROM events WHERE request_reference=? AND kind='reviewed'", (saved['reference'],)).fetchone()[0], 1)

    def test_08_parallel_identical_requests_commit_once(self):
        payload, files = self.fixture()
        def submit(_): return Client(self.service).submit(copy.deepcopy(payload), files)
        results = list(ThreadPoolExecutor(4).map(submit, range(6)))
        self.assertEqual(sum(status == 201 for status, _, _ in results), 1)
        self.assertTrue(all(status in (200, 201) for status, _, _ in results), results)
        self.assertEqual(len({body['reference'] for _, body, _ in results}), 1)

    def test_09_large_binary_uploads_fit_the_real_post_limit(self):
        piece = b'%PDF-1.4\n%' + b'0' * (4 * 1024 * 1024) + b'\n%%EOF'
        payload, _ = self.fixture(piece)
        payload['units'][0]['attachments'] = [{'uploadKey': 'u0a' + str(n), 'name': str(n)+'.pdf', 'mime': 'application/pdf'} for n in range(3)]
        files = [('u0a'+str(n),str(n)+'.pdf','application/pdf',piece) for n in range(3)]
        status, result, _ = self.client.submit(payload, files)
        self.assertEqual(status, 201, result)
        self.assertLess(sum(len(f[3]) for f in files), 14*1024*1024)
        # The previous JSON/base64 representation would exceed this host's 15M POST limit.
        self.assertGreater(sum(len(base64.b64encode(f[3])) for f in files), 15*1024*1024)

    def test_10_over_limit_and_extra_or_missing_files_are_rejected(self):
        payload, files = self.fixture()
        self.assertEqual(self.client.submit(payload, files + [('u1a0','extra.pdf','application/pdf',files[0][3])])[0], 422)
        self.assertEqual(self.client.submit(payload, [])[0], 422)
        huge = b'%PDF-1.4\n%' + b'0' * (5*1024*1024)
        self.assertEqual(self.client.submit(payload, [('u0a0','too-big.pdf','application/pdf',huge)])[0], 422)

    def test_11_storage_budget_disables_new_writes_without_changing_previous_records(self):
        before = self.service.config['storageBudgetBytes']
        try:
            self.service.config['storageBudgetBytes'] = 1; self.service.write_config()
            payload, files = self.fixture()
            self.assertEqual(self.client.submit(payload, files)[0], 503)
            with self.db() as db: self.assertFalse(db.execute('SELECT 1 FROM requests WHERE key_hash=?', (self.key_hash(payload['idempotencyKey']),)).fetchone())
        finally:
            self.service.config['storageBudgetBytes'] = before; self.service.write_config()

    def test_12_review_notifications_spool_once_and_never_claim_real_delivery(self):
        payload, files = self.fixture(); _, saved, _ = self.client.submit(payload, files)
        first = self.service.cli('notify.php', '--limit', '100')
        self.assertEqual(first.returncode, 0, first.stderr)
        self.assertEqual(json.loads(first.stdout)['acceptedByMailServer'], 0)
        second = self.service.cli('notify.php', '--limit', '100')
        self.assertEqual(second.returncode, 0, second.stderr)
        with self.db() as db:
            notification = db.execute('SELECT state,attempts FROM notifications WHERE request_reference=?', (saved['reference'],)).fetchone()
            self.assertEqual(notification['state'], 'test_spooled'); self.assertEqual(notification['attempts'], 1)
        spool = json.loads((Path(self.service.config['dataDir']) / 'spool' / (saved['reference'] + '.json')).read_text())
        self.assertTrue(spool['testOnly']); self.assertNotIn('customer', spool)
        self.assertNotIn(saved['requestId'], json.dumps(spool))

    def test_13_uncertain_notification_is_not_automatically_resent(self):
        payload, files = self.fixture(); _, saved, _ = self.client.submit(payload, files)
        with self.db() as db: db.execute("UPDATE notifications SET state='sending',attempts=1 WHERE request_reference=?", (saved['reference'],)); db.commit()
        result = self.service.cli('notify.php')
        self.assertEqual(result.returncode, 0, result.stderr)
        with self.db() as db:
            row = db.execute('SELECT state,attempts FROM notifications WHERE request_reference=?', (saved['reference'],)).fetchone()
            self.assertEqual((row['state'],row['attempts']),('uncertain',1))

    def test_14_disabled_service_and_private_paths_do_not_accept_or_expose_data(self):
        try:
            self.service.config['acceptSubmissions'] = False; self.service.write_config()
            self.assertFalse(Client(self.service).config['submissions'])
            payload, files = self.fixture()
            self.assertEqual(self.client.submit(payload, files)[0], 503)
        finally:
            self.service.config['acceptSubmissions'] = True; self.service.write_config()
        for path in ['/backend/config.example.php','/backend/bin/notify.php','/var/solicitudes.sqlite3','/private/config.php','/data/media-local-manifest.json']:
            self.assertEqual(self.client.request(path)[0],404,path)

    def test_15_backup_restores_requests_files_and_original_access_tokens(self):
        payload, files = self.fixture(); _, saved, _ = self.client.submit(payload, files)
        output = Path(self.temp.name) / ('backup-' + uuid.uuid4().hex + '.zip')
        result = self.service.cli('backup.php', '--output', str(output))
        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout)
        destination = Path(self.temp.name) / ('restore-' + uuid.uuid4().hex)
        restore = subprocess.run([PHP, str(ROOT/'backend/bin/restore.php'), '--archive', str(output), '--sha256', info['sha256'], '--destination', str(destination), '--base-url', self.service.base],capture_output=True,text=True)
        self.assertEqual(restore.returncode,0,restore.stderr)
        restored = json.loads(restore.stdout)
        self.assertFalse(restored['acceptSubmissions']); self.assertEqual(restored['notifications'],'spool')
        with sqlite3.connect(destination/'solicitudes.sqlite3') as db:
            row = db.execute('SELECT payload,token_hash FROM requests WHERE reference=?',(saved['reference'],)).fetchone()
            self.assertEqual(row[1],hashlib.sha256(saved['requestId'].encode()).hexdigest())
            stored=json.loads(row[0]); file_id=stored['units'][0]['attachments'][0]['id']
            self.assertEqual((destination/'uploads'/saved['reference']/(file_id+'.bin')).read_bytes(),files[0][3])
        # Boot the recovered data through the same real application, preserving
        # the receipt key while keeping submissions and outbound mail disabled.
        original = copy.deepcopy(self.service.config)
        try:
            self.service.config['dataDir'] = str(destination)
            self.service.config['acceptSubmissions'] = False
            self.service.write_config()
            status, recovered, _ = self.client.request('/api/resumen',headers=self.bearer(saved))
            self.assertEqual(status,200,recovered); self.assertEqual(recovered['reference'],saved['reference'])
        finally:
            self.service.config=original; self.service.write_config()

    def test_16_backup_checksum_mismatch_cannot_create_a_restore(self):
        path=Path(self.temp.name)/('invalid-'+uuid.uuid4().hex+'.zip');path.write_bytes(b'not a backup')
        destination=Path(self.temp.name)/('invalid-restore-'+uuid.uuid4().hex)
        result=subprocess.run([PHP,str(ROOT/'backend/bin/restore.php'),'--archive',str(path),'--sha256','0'*64,'--destination',str(destination),'--base-url',self.service.base],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0); self.assertFalse(destination.exists())

    def test_17_exact_attachment_total_and_over_limit_post_are_handled(self):
        def pdf(size): return b'%PDF-1.4\n%' + b'0'*(size-16) + b'\n%%EOF'
        payload,_=self.fixture()
        sizes=[5*1024*1024,5*1024*1024,4*1024*1024]
        payload['units'][0]['attachments']=[{'uploadKey':'u0a'+str(i),'name':str(i)+'.pdf','mime':'application/pdf'} for i in range(3)]
        files=[('u0a'+str(i),str(i)+'.pdf','application/pdf',pdf(size)) for i,size in enumerate(sizes)]
        self.assertEqual(sum(len(x[3]) for x in files),14*1024*1024)
        status,result,_=self.client.submit(payload,files);self.assertEqual(status,201,result)
        payload['idempotencyKey']=uuid.uuid4().hex
        over=[*files[:2],(*files[2][:3],files[2][3]+b'0')]
        self.assertEqual(self.client.submit(payload,over)[0],422)
        status,body,_=self.client.request('/api/solicitudes',b'0'*(15*1024*1024+10),{'Content-Type':'multipart/form-data; boundary=oversized','Origin':self.service.base,'X-CSRF-Token':self.client.config['csrfToken']})
        self.assertEqual(status,413,body)

    def test_18_unsafe_customer_upload_names_never_become_server_paths(self):
        payload,files=self.fixture();payload['units'][0]['attachments'][0]['name']='../../private/config.php'
        status,saved,_=self.client.submit(payload,files);self.assertEqual(status,201,saved)
        _,data,_=self.client.request('/api/resumen',headers=self.bearer(saved))
        attachment=data['units'][0]['attachments'][0]
        self.assertEqual(attachment['name'],'config.php')
        self.assertEqual(attachment['downloadName'],'config.pdf')
        with self.db() as db:
            path=db.execute('SELECT path FROM files WHERE id=?',(attachment['id'],)).fetchone()[0]
            self.assertTrue(path.endswith('.bin'));self.assertNotIn('..',path)

    def test_19_production_http_is_rejected_even_with_forged_forwarded_headers(self):
        original=copy.deepcopy(self.service.config)
        try:
            self.service.config.update({'mode':'production','baseUrl':self.service.base.replace('http:','https:')})
            self.service.write_config()
            self.assertEqual(self.client.request('/api/config',headers={'X-Forwarded-Proto':'https'})[0],403)
        finally:
            self.service.config=original;self.service.write_config()

    def test_20_notification_failure_preserves_the_request_and_records_retry(self):
        payload,files=self.fixture();_,saved,_=self.client.submit(payload,files)
        original=copy.deepcopy(self.service.config)
        try:
            self.service.config.update({'mode':'production','baseUrl':'https://example.invalid','notifications':{'transport':'sendmail','to':'staff@example.invalid','from':'web@example.invalid'}})
            self.service.write_config()
            # mail() is disabled in this CLI process, so no message can be sent.
            result=self.service.cli('notify.php','--limit','100')
            self.assertEqual(result.returncode,0,result.stderr)
            with self.db() as db:
                row=db.execute('SELECT state,attempts FROM notifications WHERE request_reference=?',(saved['reference'],)).fetchone()
                self.assertEqual((row['state'],row['attempts']),('retry',1))
                self.assertTrue(db.execute('SELECT 1 FROM requests WHERE reference=?',(saved['reference'],)).fetchone())
        finally:
            self.service.config=original;self.service.write_config()

    def test_21_legacy_public_media_redirect_without_intake_access_or_external_targets(self):
        class NoRedirect(urllib.request.HTTPRedirectHandler):
            def redirect_request(self, req, fp, code, msg, headers, newurl):
                return None
        opener=urllib.request.build_opener(NoRedirect())
        routes=json.loads((ROOT/'data/legacy-media-routes.json').read_text())
        samples=[next(k for k in routes if k.startswith('/wp-content/')),
                 next(k for k in routes if k.startswith('/reparacion-abs/')),
                 '/docs/peticion_reparacion 2026a.pdf']
        for path in samples:
            request=urllib.request.Request(self.service.base+urllib.parse.quote(path,safe='/')+'?redir=https://example.invalid',method='HEAD')
            with self.assertRaises(urllib.error.HTTPError) as context:
                opener.open(request,timeout=5)
            self.assertEqual(context.exception.code,301)
            self.assertEqual(context.exception.headers['Location'],routes[path])
            context.exception.close()
            status,body,headers=self.client.request(routes[path])
            self.assertEqual(status,200)
            self.assertGreater(len(body),0)
        self.assertEqual(self.client.request('/wp-content/uploads/not-a-real-file.jpg')[0],404)
        self.assertEqual(self.client.request('/docs/https%3A%2F%2Fexample.invalid')[0],404)
        self.assertEqual(self.client.request(samples[0],body=b'',method='POST')[0],404)

    def test_22_staff_stylesheet_is_served_by_the_private_review_router(self):
        status,body,headers=self.client.request('/assets/equipo.css')
        self.assertEqual(status,200)
        self.assertIn('text/css',headers['Content-Type'])
        self.assertTrue(body)

    def test_23_unknown_model_consultation_preserves_structured_unknown_and_clear_staff_summary(self):
        payload,files=self.fixture()
        payload['vehicle'].update({'model':'Civic hidden draft','modelUnknown':True})
        status,saved,_=self.client.submit(payload,files)
        self.assertEqual(status,201,saved)
        _,stored,_=self.client.request('/api/resumen',headers=self.bearer(saved))
        self.assertEqual(stored['vehicle']['model'],'')
        self.assertIs(stored['vehicle']['modelUnknown'],True)
        _,summary,_=self.client.request('/equipo/solicitudes/'+saved['reference'],headers=self.staff())
        self.assertIn('Modelo desconocido'.encode(),summary)
        self.assertNotIn(b'Civic hidden draft',summary)
        self.assertIn('Consultar mi pieza'.encode(),summary)

    def test_24_unknown_model_cannot_prepare_shipping_and_blank_requires_explicit_choice(self):
        payload,files=self.fixture()
        payload['vehicle'].update({'model':'','modelUnknown':True})
        payload['intent']='repair'
        payload['customer'].update({'taxId':'TEST-123','address':'Calle de prueba 1','city':'Madrid','postalCode':'28000','country':'España'})
        status,error,_=self.client.submit(payload,files)
        self.assertEqual(status,422,error)
        self.assertIn('necesitamos el modelo',error['error'])
        payload['intent']='consultation';payload['vehicle']['modelUnknown']=False
        self.assertEqual(self.client.submit(payload,files)[0],422)
        payload['vehicle']['modelUnknown']='true'
        self.assertEqual(self.client.submit(payload,files)[0],422)
        payload['vehicle'].update({'model':'Civic','modelUnknown':False})
        status,saved,_=self.client.submit(payload,files)
        self.assertEqual(status,201,saved)
        _,stored,_=self.client.request('/api/resumen',headers=self.bearer(saved))
        self.assertEqual(stored['vehicle']['model'],'Civic')
        self.assertIs(stored['vehicle']['modelUnknown'],False)

    def test_25_legacy_model_filler_is_normalized_without_breaking_old_consultation_clients(self):
        payload,files=self.fixture();payload['vehicle']['model']='Por identificar'
        status,saved,_=self.client.submit(payload,files)
        self.assertEqual(status,201,saved)
        _,stored,_=self.client.request('/api/resumen',headers=self.bearer(saved))
        self.assertEqual(stored['vehicle']['model'],'')
        self.assertIs(stored['vehicle']['modelUnknown'],True)

    def test_26_consultation_summary_omits_empty_shipping_fields_and_default_country(self):
        payload,files=self.fixture();payload['customer'].update({'country':'España','returnCountry':'España'})
        status,saved,_=self.client.submit(payload,files);self.assertEqual(status,201,saved)
        _,page,_=self.client.request('/equipo/solicitudes/'+saved['reference'],headers=self.staff())
        for label in ['NIF/CIF','Dirección','Devolución']:
            self.assertNotIn(('<dt>'+label+'</dt>').encode(),page)
        self.assertNotIn('<dd class="pre">España</dd>'.encode(),page)
        payload['idempotencyKey']=uuid.uuid4().hex
        payload['customer'].update({'taxId':'TEST-123','address':'Calle de prueba 1','city':'Madrid','postalCode':'28000'})
        status,saved,_=self.client.submit(payload,files);self.assertEqual(status,201,saved)
        _,page,_=self.client.request('/equipo/solicitudes/'+saved['reference'],headers=self.staff())
        self.assertIn('<dt>NIF/CIF</dt>'.encode(),page)
        self.assertIn('Calle de prueba 1, 28000, Madrid, España'.encode(),page)


if __name__ == '__main__':
    unittest.main()
