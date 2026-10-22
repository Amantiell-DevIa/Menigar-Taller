#!/usr/bin/env python3
"""Local MENIGAR review server. Private intake storage, not a production ERP."""
from __future__ import annotations

import argparse
import base64
import hashlib
import html
import json
import mimetypes
import os
import re
import secrets
import sqlite3
import threading
from datetime import datetime, timezone
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
MAX_FILE = 5 * 1024 * 1024
MAX_FILES = 5
MAX_TOTAL = 15 * 1024 * 1024
MAX_BODY = 25 * 1024 * 1024
LOCK = threading.Lock()
STATIC_ROOT_FILES = {
    'index.html', 'servicios.html', 'solicitud.html', 'envios.html', 'taller.html',
    'ayuda.html', 'privacidad.html', 'condiciones.html', 'cookies.html', 'opciones-hero.html', 'laboratorio.html', 'laboratorio.js',
    'style.css', 'solicitud.css', 'hyundai.css', 'bmw.css', 'reparaciones.css', 'app.js', 'solicitud.js', 'resumen.js',
    'hero-lab.jpg', 'robots.txt', 'sitemap.xml', 'favicon.svg', 'resumen.html', 'receipt.js',
}


class ValidationError(ValueError):
    pass


def text(value, limit=200):
    return str(value or '').strip()[:limit]


def validate(payload):
    if not isinstance(payload, dict):
        raise ValidationError('La solicitud debe contener datos válidos.')
    key = text(payload.get('idempotencyKey'), 100)
    if not re.fullmatch(r'[a-zA-Z0-9_-]{16,100}', key):
        raise ValidationError('Falta la identificación de este envío. Recarga e inténtalo de nuevo.')
    intent = payload.get('intent')
    if intent not in ('consultation', 'repair'):
        raise ValidationError('Selecciona el tipo de solicitud.')
    raw_customer = payload.get('customer')
    if not isinstance(raw_customer, dict):
        raise ValidationError('Completa los datos de contacto.')
    customer = {k: text(raw_customer.get(k), 300) for k in (
        'type', 'name', 'contact', 'email', 'phone', 'taxId', 'address', 'city',
        'province', 'postalCode', 'country', 'returnAddress', 'returnCity',
        'returnPostalCode', 'returnCountry',
    )}
    customer['returnDifferent'] = bool(raw_customer.get('returnDifferent'))
    if len(customer['name']) < 2:
        raise ValidationError('Indica tu nombre o razón social.')
    if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', customer['email']):
        raise ValidationError('Indica un correo electrónico válido.')
    if len(re.sub(r'\D', '', customer['phone'])) < 7:
        raise ValidationError('Indica un teléfono de contacto válido.')
    if customer['type'] == 'taller' and not customer['contact']:
        raise ValidationError('Indica la persona de contacto del taller.')
    if intent == 'repair':
        for field, label in (('taxId', 'identificación fiscal'), ('address', 'dirección'),
                             ('city', 'localidad'), ('postalCode', 'código postal'), ('country', 'país')):
            if not customer[field]:
                raise ValidationError('Completa ' + label + ' para preparar la solicitud de envío.')
        if customer['returnDifferent'] and any(not customer[k] for k in (
                'returnAddress', 'returnCity', 'returnPostalCode', 'returnCountry')):
            raise ValidationError('Completa los datos de la dirección de devolución.')
    raw_vehicle = payload.get('vehicle') or {}
    if not isinstance(raw_vehicle, dict):
        raise ValidationError('Revisa los datos del vehículo.')
    vehicle = {k: text(raw_vehicle.get(k), 120) for k in ('brand', 'model', 'plate', 'vin', 'year', 'km')}
    vehicle['modelUnknown'] = raw_vehicle.get('modelUnknown') is True or vehicle['model'].casefold() == 'por identificar'
    if vehicle['modelUnknown']:
        vehicle['model'] = ''
    if not vehicle['brand']:
        raise ValidationError('Indica la marca del vehículo.')
    if intent == 'repair' and vehicle['modelUnknown']:
        raise ValidationError('Para preparar el envío necesitamos el modelo. Si no lo conoces, elige «Consultar mi pieza».')
    if not vehicle['model'] and not vehicle['modelUnknown']:
        raise ValidationError('Indica el modelo o marca «No conozco el modelo» para una consulta.')
    raw_units = payload.get('units')
    if not isinstance(raw_units, list) or not 1 <= len(raw_units) <= 10:
        raise ValidationError('Añade entre una y diez unidades a la solicitud.')
    units, binaries, total = [], [], 0
    for index, raw in enumerate(raw_units):
        if not isinstance(raw, dict):
            raise ValidationError('Revisa los datos de cada pieza.')
        unit = {k: text(raw.get(k), 2000 if k in ('symptoms', 'accessories') else 200)
                for k in ('catalogUid', 'componentKey', 'componentName', 'manufacturer',
                          'reference', 'dtc', 'symptoms', 'accessories', 'vehicleBrand', 'vehicleModel')}
        unit['unknownReference'] = bool(raw.get('unknownReference'))
        if not unit['componentName']:
            raise ValidationError(f'Indica qué pieza quieres revisar en la unidad {index + 1}.')
        if len(unit['symptoms']) < 8:
            raise ValidationError(f'Describe qué sucede en la unidad {index + 1}.')
        if not unit['reference'] and not unit['unknownReference']:
            raise ValidationError(f'Indica la referencia o marca que no la conoces en la unidad {index + 1}.')
        attachments = raw.get('attachments') or []
        if not isinstance(attachments, list) or len(attachments) > MAX_FILES:
            raise ValidationError(f'Adjunta como máximo {MAX_FILES} archivos por unidad.')
        unit['attachments'] = []
        for file in attachments:
            if not isinstance(file, dict):
                raise ValidationError('Uno de los archivos no es válido.')
            name = Path(text(file.get('name'), 180)).name
            mime = text(file.get('mime'), 80)
            if mime not in ('image/jpeg', 'image/png', 'image/webp', 'application/pdf'):
                raise ValidationError('Solo se admiten fotos JPG, PNG, WebP e informes PDF.')
            try:
                blob = base64.b64decode(file.get('data', ''), validate=True)
            except (ValueError, TypeError):
                raise ValidationError('No se ha podido leer uno de los archivos.')
            if not blob or len(blob) > MAX_FILE:
                raise ValidationError('Cada archivo debe ocupar entre 1 byte y 5 MB.')
            valid_magic = {
                'image/jpeg': blob.startswith(b'\xff\xd8\xff'),
                'image/png': blob.startswith(b'\x89PNG\r\n\x1a\n'),
                'image/webp': blob.startswith(b'RIFF') and blob[8:12] == b'WEBP',
                'application/pdf': blob.startswith(b'%PDF-'),
            }
            if not valid_magic[mime]:
                raise ValidationError('El contenido de un archivo no coincide con su formato.')
            total += len(blob)
            if total > MAX_TOTAL:
                raise ValidationError('El conjunto de archivos no puede superar 15 MB.')
            file_id = secrets.token_urlsafe(24)
            meta = {'id': file_id, 'name': name or 'archivo', 'mime': mime, 'size': len(blob)}
            unit['attachments'].append(meta)
            binaries.append((file_id, blob))
        units.append(unit)
    acceptance = payload.get('acceptance') or {}
    if not isinstance(acceptance, dict) or not acceptance.get('privacyRead') or not acceptance.get('conditionsRead'):
        raise ValidationError('Revisa la información de privacidad y las condiciones de la solicitud.')
    normalized = {'intent': intent, 'customer': customer, 'vehicle': vehicle, 'units': units,
                  'acceptance': {'privacyRead': True, 'conditionsRead': True, 'version': 'review-2026-10-13'},
                  'contextQuery': text(payload.get('contextQuery'), 300)}
    return key, normalized, binaries


def init_db(storage):
    storage.mkdir(parents=True, exist_ok=True)
    (storage / 'uploads').mkdir(exist_ok=True)
    try:
        storage.chmod(0o700)
        (storage / 'uploads').chmod(0o700)
    except OSError:
        pass
    with sqlite3.connect(storage / 'solicitudes.sqlite3') as db:
        db.executescript('''
            CREATE TABLE IF NOT EXISTS requests (
                token TEXT PRIMARY KEY, reference TEXT UNIQUE NOT NULL,
                idempotency_key TEXT UNIQUE NOT NULL, content_hash TEXT NOT NULL,
                created_at TEXT NOT NULL, payload TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS units (
                id TEXT PRIMARY KEY, request_token TEXT NOT NULL,
                position INTEGER NOT NULL, payload TEXT NOT NULL,
                FOREIGN KEY(request_token) REFERENCES requests(token)
            );
            CREATE TABLE IF NOT EXISTS files (
                id TEXT PRIMARY KEY, request_token TEXT NOT NULL,
                name TEXT NOT NULL, mime TEXT NOT NULL, size INTEGER NOT NULL,
                FOREIGN KEY(request_token) REFERENCES requests(token)
            );
        ''')


def summary_html(reference, created, payload, token=''):
    esc = html.escape
    c, v = payload['customer'], payload['vehicle']
    vehicle_label = v['brand'] + ' · ' + ('Modelo desconocido' if v.get('modelUnknown') else v['model'])
    pieces = []
    for i, unit in enumerate(payload['units'], 1):
        files = ', '.join(f'<a href="/api/solicitudes/{token}/archivo/{esc(x["id"])}">{esc(x["name"])}</a>' for x in unit['attachments']) or 'Sin adjuntos'
        pieces.append(f'''<section class="piece"><h2>Unidad {i}: {esc(unit['componentName'])}</h2>
          <dl><dt>Identificador de unidad</dt><dd>{esc(reference)}-P{i}</dd>
          <dt>Fabricante de la pieza</dt><dd>{esc(unit['manufacturer'] or 'No indicado')}</dd>
          <dt>Referencia declarada</dt><dd>{esc(unit['reference'] or 'Por identificar')}</dd>
          <dt>Código de avería</dt><dd>{esc(unit['dtc'] or 'No indicado')}</dd>
          <dt>Síntomas</dt><dd class="pre">{esc(unit['symptoms'])}</dd>
          <dt>Accesorios declarados</dt><dd class="pre">{esc(unit['accessories'] or 'No indicados')}</dd>
          <dt>Vehículo de esta unidad</dt><dd>{esc((unit['vehicleBrand'] + ' ' + unit['vehicleModel']).strip() or vehicle_label)}</dd>
          <dt>Archivos</dt><dd>{files}</dd></dl></section>''')
    def address_label(returning=False):
        fields = ('returnAddress', 'returnPostalCode', 'returnCity') if returning else ('address', 'postalCode', 'city', 'province')
        parts = [c[field] for field in fields if c[field]]
        return ', '.join(x for x in (*parts, c['returnCountry' if returning else 'country']) if x) if parts else ''
    address = address_label()
    return_address = address_label(True) if c['returnDifferent'] else address
    shipping_rows = ''.join(f'<dt>{label}</dt><dd>{esc(value or "Pendiente de completar")}</dd>' for label, value in (
        ('Identificación fiscal', c['taxId']), ('Dirección', address), ('Devolución', return_address)) if payload['intent'] == 'repair' or value)
    return f'''<!doctype html><html lang="es"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
      <title>Resumen {esc(reference)} · MENIGAR</title><link rel="stylesheet" href="/solicitud.css">
      <script src="/resumen.js" defer></script></head><body class="receipt-page"><main class="receipt">
      <div class="receipt-tools"><a href="/">Volver a la web</a><button type="button" data-print>Imprimir o guardar PDF</button></div>
      <p class="receipt-brand">MENIGAR · Resumen de solicitud</p><h1>{esc(reference)}</h1>
      <p>Guardada en el entorno local de revisión el {esc(created[:10])}. No se ha enviado al taller.</p>
      <dl><dt>Tipo de solicitud</dt><dd>{'Consultar mi pieza' if payload['intent'] == 'consultation' else 'Preparar solicitud de envío'}</dd>
      <dt>Solicitante</dt><dd>{esc(c['name'])}</dd><dt>Contacto</dt><dd>{esc(c['contact'] or c['name'])}</dd>
      <dt>Email y teléfono</dt><dd>{esc(c['email'])} · {esc(c['phone'])}</dd>
      {shipping_rows}
      <dt>Vehículo</dt><dd>{esc(vehicle_label)}</dd>
      <dt>Año / kilómetros</dt><dd>{esc(v['year'] or 'No indicado')} / {esc(v['km'] or 'No indicados')}</dd>
      <dt>Matrícula / bastidor</dt><dd>{esc(v['plate'] or 'No indicada')} / {esc(v['vin'] or 'No indicado')}</dd></dl>
      {''.join(pieces)}<aside class="receipt-note"><h2>Siguiente paso</h2>
      <p>Este resumen permite revisar e identificar la solicitud. La referencia no es una orden de reparación.
      En esta vista previa no se ha confirmado un envío, una reparación ni un pago. Espera las instrucciones del taller antes de enviar material.</p></aside>
      </main></body></html>'''


def make_handler(storage):
    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(ROOT), **kwargs)

        def end_headers(self):
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Referrer-Policy', 'same-origin')
            self.send_header('X-Robots-Tag', 'noindex, nofollow')
            self.send_header('Content-Security-Policy', "default-src 'self'; img-src 'self' data: https://www.menigar.com https://abs.menigar.com; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; font-src 'self' https://fonts.gstatic.com; script-src 'self'; connect-src 'self'; frame-src https://www.youtube-nocookie.com https://www.google.com; form-action 'self'; base-uri 'self'; frame-ancestors 'none'")
            super().end_headers()

        def log_message(self, fmt, *args):
            # Receipt tokens and request bodies never belong in logs.
            safe = fmt % args
            safe = re.sub(r'/api/solicitudes/[^\s"]+', '/api/solicitudes/[privado]', safe)
            super().log_message('%s', safe)

        def json_response(self, code, data):
            blob = json.dumps(data, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(blob)))
            self.send_header('Cache-Control', 'no-store')
            self.end_headers()
            self.wfile.write(blob)

        def private_route(self, head=False):
            path = urlparse(self.path).path
            file_match = re.fullmatch(r'/api/solicitudes/([A-Za-z0-9_-]{30,80})/archivo/([A-Za-z0-9_-]{20,80})', path)
            if file_match:
                with sqlite3.connect(storage / 'solicitudes.sqlite3') as db:
                    file = db.execute('SELECT name,mime FROM files WHERE request_token=? AND id=?', (file_match[1], file_match[2])).fetchone()
                target = storage / 'uploads' / file_match[2]
                if not file or not target.is_file():
                    self.send_error(404)
                    return
                blob = target.read_bytes()
                self.send_response(200)
                self.send_header('Content-Type', file[1])
                self.send_header('Content-Disposition', 'attachment')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('Content-Length', str(len(blob)))
                self.end_headers()
                if not head:
                    self.wfile.write(blob)
                return
            match = re.fullmatch(r'/api/solicitudes/([A-Za-z0-9_-]{30,80})/(resumen|datos)', path)
            if not match:
                self.send_error(404)
                return
            with sqlite3.connect(storage / 'solicitudes.sqlite3') as db:
                row = db.execute('SELECT reference,created_at,payload FROM requests WHERE token=?', (match[1],)).fetchone()
            if not row:
                self.send_error(404)
                return
            payload = json.loads(row[2])
            if match[2] == 'datos':
                blob = json.dumps({'reference': row[0], 'createdAt': row[1], **payload}, ensure_ascii=False, indent=2).encode()
                mime = 'application/json; charset=utf-8'
            else:
                blob = summary_html(row[0], row[1], payload, match[1]).encode()
                mime = 'text/html; charset=utf-8'
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Cache-Control', 'no-store')
            self.send_header('Content-Length', str(len(blob)))
            self.end_headers()
            if not head:
                self.wfile.write(blob)

        def static_allowed(self):
            path = unquote(urlparse(self.path).path).lstrip('/')
            if not path:
                return True
            if path in STATIC_ROOT_FILES or path in ('data/catalogo-v2.js', 'data/catalogo-v2.json', 'data/home-index.js', 'data/family-media.js'):
                return True
            if any(part.startswith('.') or part == '..' for part in Path(path).parts):
                return False
            target = (ROOT / path).resolve()
            try:
                target.relative_to(ROOT)
            except ValueError:
                return False
            if path.startswith('assets/'):
                return target.suffix.lower() in ('.jpg', '.jpeg', '.png', '.svg', '.webp', '.ico', '.gif', '.pdf', '.woff2', '.css') and target.is_file()
            if path.startswith('reparaciones/'):
                return (target / 'index.html').is_file() if target.is_dir() else target.suffix == '.html' and target.is_file()
            return False

        def do_GET(self):
            if urlparse('http://' + self.headers.get('Host', '')).hostname not in ('localhost', '127.0.0.1'):
                return self.json_response(403, {'error': 'El servidor de revisión solo admite acceso local.'})
            path = urlparse(self.path).path
            if path == '/api/config':
                return self.json_response(200, {'mode': 'local_review', 'submissions': True,
                    'maxFileBytes': MAX_FILE, 'maxFilesPerUnit': MAX_FILES, 'maxTotalBytes': MAX_TOTAL,
                    'emailConfigured': False, 'workshopIntegrationConfigured': False})
            if path.startswith('/api/'):
                return self.private_route()
            if not self.static_allowed():
                return self.send_error(404)
            return super().do_GET()

        def do_HEAD(self):
            if urlparse(self.path).path.startswith('/api/'):
                return self.private_route(head=True)
            if not self.static_allowed():
                return self.send_error(404)
            return super().do_HEAD()

        def list_directory(self, path):
            self.send_error(404)
            return None

        def do_POST(self):
            if urlparse('http://' + self.headers.get('Host', '')).hostname not in ('localhost', '127.0.0.1'):
                return self.json_response(403, {'error': 'El servidor de revisión solo admite acceso local.'})
            if urlparse(self.path).path != '/api/solicitudes':
                return self.json_response(404, {'error': 'Ruta no disponible.'})
            origin = self.headers.get('Origin')
            if origin and origin != 'http://' + self.headers.get('Host', ''):
                return self.json_response(403, {'error': 'El origen de la solicitud no está permitido.'})
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self.json_response(415, {'error': 'El formato de la solicitud no es válido.'})
            try:
                size = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                size = 0
            if not 0 < size <= MAX_BODY:
                return self.json_response(413, {'error': 'La solicitud supera el tamaño permitido.'})
            try:
                raw = json.loads(self.rfile.read(size))
                key, payload, binaries = validate(raw)
                # Stable checksum independent of random attachment IDs.
                hash_payload = json.loads(json.dumps(payload))
                for unit in hash_payload['units']:
                    for file in unit['attachments']:
                        file.pop('id', None)
                digest = hashlib.sha256(json.dumps(hash_payload, sort_keys=True).encode() + b''.join(hashlib.sha256(b).digest() for _, b in binaries)).hexdigest()
                with LOCK, sqlite3.connect(storage / 'solicitudes.sqlite3') as db:
                    old = db.execute('SELECT token,reference,content_hash FROM requests WHERE idempotency_key=?', (key,)).fetchone()
                    if old:
                        if old[2] != digest:
                            return self.json_response(409, {'error': 'Este envío ya se guardó con otros datos. Inicia una solicitud nueva.'})
                        token, reference = old[0], old[1]
                        status = 200
                    else:
                        token = secrets.token_urlsafe(32)
                        created = datetime.now(timezone.utc).isoformat()
                        reference = 'SOL-' + datetime.now(ZoneInfo('Europe/Madrid')).strftime('%Y%m%d') + '-' + secrets.token_hex(3).upper()
                        saved = []
                        try:
                            for file_id, blob in binaries:
                                dest = storage / 'uploads' / file_id
                                dest.write_bytes(blob)
                                dest.chmod(0o600)
                                saved.append(dest)
                            db.execute('INSERT INTO requests VALUES (?,?,?,?,?,?)', (token, reference, key, digest, created, json.dumps(payload, ensure_ascii=False)))
                            for i, unit in enumerate(payload['units'], 1):
                                db.execute('INSERT INTO units VALUES (?,?,?,?)', (reference + '-P' + str(i), token, i, json.dumps(unit, ensure_ascii=False)))
                                for file in unit['attachments']:
                                    db.execute('INSERT INTO files VALUES (?,?,?,?,?)', (file['id'], token, file['name'], file['mime'], file['size']))
                            db.commit()
                        except Exception:
                            db.rollback()
                            for dest in saved:
                                dest.unlink(missing_ok=True)
                            raise
                        status = 201
                return self.json_response(status, {'reference': reference, 'requestId': token,
                    'unitReferences': [reference + '-P' + str(i) for i in range(1, len(payload['units']) + 1)],
                    'summaryUrl': '/api/solicitudes/' + token + '/resumen',
                    'downloadUrl': '/api/solicitudes/' + token + '/datos',
                    'status': 'saved_locally', 'emailSent': False, 'workshopIntegration': 'not_configured'})
            except ValidationError as error:
                return self.json_response(422, {'error': str(error)})
            except (json.JSONDecodeError, UnicodeDecodeError):
                return self.json_response(400, {'error': 'No se han podido leer los datos. No se ha guardado la solicitud.'})
            except Exception:
                return self.json_response(500, {'error': 'No se pudo guardar la solicitud. Conserva los datos y vuelve a intentarlo.'})

    return Handler


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=8765)
    parser.add_argument('--storage', type=Path, default=ROOT / 'var')
    args = parser.parse_args()
    init_db(args.storage)
    server = ThreadingHTTPServer(('127.0.0.1', args.port), make_handler(args.storage))
    print(f'MENIGAR · Revisión local: http://127.0.0.1:{args.port}', flush=True)
    print('Las solicitudes se guardan en este equipo. No se envían emails ni órdenes al taller.', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.server_close()


if __name__ == '__main__':
    main()
