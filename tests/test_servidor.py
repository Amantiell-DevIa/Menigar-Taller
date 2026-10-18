"""HTTP acceptance checks for saved requests, files and retry behaviour."""
import base64
import copy
import importlib.util
import json
import sqlite3
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location('menigar_server', ROOT / 'servidor.py')
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)


class IntakeHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.storage = Path(cls.temp.name)
        server_module.init_db(cls.storage)
        cls.server = server_module.ThreadingHTTPServer(('127.0.0.1', 0), server_module.make_handler(cls.storage))
        cls.base = 'http://127.0.0.1:' + str(cls.server.server_port)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)
        cls.temp.cleanup()

    def fixture(self, key):
        unit = {'componentKey': 'abs', 'componentName': 'ABS / ESP', 'reference': '0012-ABC',
                'symptoms': 'Prueba local: fallo intermitente', 'accessories': 'Un cable',
                'attachments': [{'name': 'prueba.pdf', 'mime': 'application/pdf',
                                 'data': base64.b64encode(b'%PDF-1.4\n% local test').decode()}]}
        return {'idempotencyKey': key, 'intent': 'consultation',
                'customer': {'type': 'particular', 'name': 'Prueba local', 'email': 'prueba@example.test', 'phone': '600000000'},
                'vehicle': {'brand': 'Honda', 'model': 'Civic'}, 'units': [unit, {**unit, 'reference': 'OTRA-003', 'attachments': []}],
                'acceptance': {'privacyRead': True, 'conditionsRead': True}}

    def request(self, path, payload=None, headers=None):
        request = urllib.request.Request(self.base + path, data=None if payload is None else json.dumps(payload).encode(),
                                         headers={'Content-Type': 'application/json', **(headers or {})})
        try:
            with urllib.request.urlopen(request) as response:
                return response.status, response.read(), response.headers
        except urllib.error.HTTPError as error:
            return error.code, error.read(), error.headers

    def test_persist_two_units_retry_and_retrieve_attachment(self):
        payload = self.fixture('test-two-units-20261013')
        status, body, _ = self.request('/api/solicitudes', payload)
        self.assertEqual(status, 201)
        saved = json.loads(body)
        self.assertEqual(len(saved['unitReferences']), 2)
        self.assertFalse(saved['emailSent'])
        status2, body2, _ = self.request('/api/solicitudes', payload)
        self.assertEqual(status2, 200)
        self.assertEqual(json.loads(body2)['reference'], saved['reference'])
        with sqlite3.connect(self.storage / 'solicitudes.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM units WHERE request_token=?', (saved['requestId'],)).fetchone()[0], 2)
        status, data, headers = self.request(saved['downloadUrl'])
        self.assertEqual(status, 200)
        self.assertEqual(headers['Cache-Control'], 'no-store')
        stored = json.loads(data)
        self.assertEqual(stored['units'][0]['reference'], '0012-ABC')
        file_id = stored['units'][0]['attachments'][0]['id']
        status, blob, _ = self.request('/api/solicitudes/' + saved['requestId'] + '/archivo/' + file_id)
        self.assertEqual(status, 200)
        self.assertTrue(blob.startswith(b'%PDF-'))
        self.assertEqual(self.request('/api/solicitudes/' + 'x'*43 + '/archivo/' + file_id)[0], 404)
        self.assertEqual(self.request('/var/solicitudes.sqlite3')[0], 404)
        self.assertEqual(self.request('/var/uploads/' + file_id)[0], 404)
        self.assertEqual(self.request('/data/cache/pages_page_1.json')[0], 404)
        self.assertEqual(self.request('/servidor.py')[0], 404)

    def test_changed_retry_is_not_a_second_request(self):
        payload = self.fixture('test-idempotency-conflict')
        self.assertEqual(self.request('/api/solicitudes', payload)[0], 201)
        payload['units'][0]['reference'] = 'CAMBIADA'
        self.assertEqual(self.request('/api/solicitudes', payload)[0], 409)

    def test_invalid_upload_is_not_saved(self):
        payload = self.fixture('test-invalid-upload-2026')
        payload['units'][0]['attachments'][0]['data'] = base64.b64encode(b'<script>bad</script>').decode()
        self.assertEqual(self.request('/api/solicitudes', payload)[0], 422)
        with sqlite3.connect(self.storage / 'solicitudes.sqlite3') as db:
            self.assertEqual(db.execute('SELECT count(*) FROM requests WHERE idempotency_key=?', (payload['idempotencyKey'],)).fetchone()[0], 0)

    def test_origin_and_shipping_validation(self):
        payload = self.fixture('test-origin-validation')
        self.assertEqual(self.request('/api/solicitudes', payload, {'Origin': 'https://otro.example'})[0], 403)
        self.assertEqual(self.request('/api/config', headers={'Host': 'otro.example'})[0], 403)
        payload['intent'] = 'repair'
        self.assertEqual(self.request('/api/solicitudes', payload)[0], 422)

    def test_summary_escapes_user_content(self):
        payload = self.fixture('test-escape-summary-2026')
        payload['customer']['name'] = '<img src=x onerror=alert(1)>'
        status, body, _ = self.request('/api/solicitudes', payload)
        self.assertEqual(status, 201)
        status, summary, _ = self.request(json.loads(body)['summaryUrl'])
        self.assertEqual(status, 200)
        self.assertNotIn(b'<img src=x', summary)
        self.assertIn(b'&lt;img', summary)

    def test_unknown_model_is_structured_and_summary_explains_it(self):
        payload=self.fixture('test-unknown-model-20261017')
        payload['vehicle'].update({'model':'Civic hidden draft','modelUnknown':True})
        status,body,_=self.request('/api/solicitudes',payload)
        self.assertEqual(status,201,body)
        saved=json.loads(body)
        _,body,_=self.request(saved['downloadUrl'])
        vehicle=json.loads(body)['vehicle']
        self.assertEqual(vehicle['model'],'');self.assertIs(vehicle['modelUnknown'],True)
        _,summary,_=self.request(saved['summaryUrl'])
        self.assertIn('Modelo desconocido'.encode(),summary)
        self.assertNotIn(b'Civic hidden draft',summary)

    def test_unknown_model_shipping_and_implicit_blank_are_rejected(self):
        payload=self.fixture('test-unknown-shipping-20261017')
        payload['intent']='repair'
        payload['customer'].update({'taxId':'TEST-123','address':'Calle de prueba 1','city':'Madrid','postalCode':'28000','country':'España'})
        payload['vehicle'].update({'model':'','modelUnknown':True})
        self.assertEqual(self.request('/api/solicitudes',payload)[0],422)
        payload['intent']='consultation';payload['vehicle']['modelUnknown']=False
        self.assertEqual(self.request('/api/solicitudes',payload)[0],422)
        payload['vehicle']['modelUnknown']='true'
        self.assertEqual(self.request('/api/solicitudes',payload)[0],422)
        payload['vehicle']['model']='Por identificar'
        status,body,_=self.request('/api/solicitudes',payload)
        self.assertEqual(status,201,body)
        _,data,_=self.request(json.loads(body)['downloadUrl'])
        self.assertIs(json.loads(data)['vehicle']['modelUnknown'],True)
        self.assertEqual(json.loads(data)['vehicle']['model'],'')

    def test_consultation_summary_does_not_treat_default_country_as_address(self):
        payload=self.fixture('test-consultation-shipping-fields')
        payload['customer'].update({'country':'España','returnCountry':'España'})
        status,body,_=self.request('/api/solicitudes',payload);self.assertEqual(status,201,body)
        _,summary,_=self.request(json.loads(body)['summaryUrl'])
        for label in ['Identificación fiscal','Dirección','Devolución']:
            self.assertNotIn(('<dt>'+label+'</dt>').encode(),summary)
        self.assertNotIn('<dd>España</dd>'.encode(),summary)
        payload['idempotencyKey']='test-consultation-real-shipping'
        payload['customer'].update({'taxId':'TEST-123','address':'Calle de prueba 1','city':'Madrid','postalCode':'28000'})
        status,body,_=self.request('/api/solicitudes',payload);self.assertEqual(status,201,body)
        _,summary,_=self.request(json.loads(body)['summaryUrl'])
        self.assertIn('<dt>Identificación fiscal</dt>'.encode(),summary)
        self.assertIn('Calle de prueba 1, 28000, Madrid, España'.encode(),summary)


if __name__ == '__main__':
    unittest.main()
