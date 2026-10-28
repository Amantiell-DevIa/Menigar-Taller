#!/usr/bin/env python3
"""Build the public repair catalogue from the immutable local WordPress snapshots.

Offline and dependency-free: does not run either original extractor or download anything.
IDs remain scoped to each WordPress site. Original references and contextual service
conditions are retained; a catalogue match is never a diagnosis or a compatibility claim.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import unicodedata
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

from build_home_index import write_home_index
from public_copy import public_text

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'

FAMILIES = [
    {'key': 'cuadro', 'name': 'Cuadros de instrumentos', 'description': 'Donde ves la velocidad, las revoluciones y los testigos.'},
    {'key': 'abs', 'name': 'ABS y ESP', 'description': 'Módulos del sistema de frenado ABS y control de estabilidad ESP.'},
    {'key': 'display', 'name': 'Displays y cuentakilómetros', 'description': 'La pantalla de números o información dentro del cuadro.'},
    {'key': 'multimedia', 'name': 'Pantallas y multimedia', 'description': 'La pantalla de la radio, el navegador o el sistema multimedia.'},
    {'key': 'cambio', 'name': 'Electrónica de cambio', 'description': 'Unidades electrónicas de cajas de cambio automáticas.'},
    {'key': 'palanca', 'name': 'Palancas selectoras', 'description': 'Electrónica de la palanca selectora del cambio automático.'},
    {'key': 'bluetooth', 'name': 'Bluetooth Blue&Me', 'description': 'Módulos de conexión Bluetooth Blue&Me de Fiat.'},
    {'key': 'ecu', 'name': 'Centralitas de motor', 'description': 'Reparación y programación de unidades de control.'},
    {'key': 'clima', 'name': 'Centralitas de climatización', 'description': 'Electrónica de los sistemas de climatización.'},
    {'key': 'bsi', 'name': 'BSI y confort', 'description': 'Unidades electrónicas de carrocería y confort.'},
    {'key': 'inmo', 'name': 'Inmovilizadores', 'description': 'Sistemas de inmovilización y transponder, previa consulta.'},
]
FAMILY_NAMES = {family['key']: family['name'] for family in FAMILIES}
BRANDS = dict(zip(
    'alfa-romeo|alpine|aprilia|audi|benelli|bentley|bmw|bmw-motorrad|chevrolet|chrysler|citroen|dacia|dodge|ducati|ferrari|fiat|ford|gmc|harley-davidson|honda|hummer|hyundai|infiniti|iveco|jaguar|jeep|john-deere|kawasaki|kia|ktm|kymco|lamborghini|lancia|land-rover|ldv|lexus|lotus|man|maserati|massey-ferguson|mazda|mercedes|mg|mini|mitsubishi|moto-guzzi|motos-honda|motos-suzuki|nissan|opel|peugeot|piaggio|porsche|renault|rover|saab|santana|scania|seat|skoda|smart|ssangyong|subaru|suzuki|tata|toyota|triumph|vespa|volkswagen|volvo|vw|yamaha-moto'.split('|'),
    'Alfa Romeo|Alpine|Aprilia|Audi|Benelli|Bentley|BMW|BMW Motorrad|Chevrolet|Chrysler|Citroën|Dacia|Dodge|Ducati|Ferrari|Fiat|Ford|GMC|Harley-Davidson|Honda|Hummer|Hyundai|Infiniti|Iveco|Jaguar|Jeep|John Deere|Kawasaki|Kia|KTM|Kymco|Lamborghini|Lancia|Land Rover|LDV|Lexus|Lotus|MAN|Maserati|Massey Ferguson|Mazda|Mercedes-Benz|MG|Mini|Mitsubishi|Moto Guzzi|Honda Moto|Suzuki Moto|Nissan|Opel|Peugeot|Piaggio|Porsche|Renault|Rover|Saab|Santana|Scania|Seat|Škoda|Smart|SsangYong|Subaru|Suzuki|Tata|Toyota|Triumph|Vespa|Volkswagen|Volvo|Volkswagen|Yamaha'.split('|')
))
EXCLUDED = {
    '', 'inicio', 'home', 'home-abs-coches', 'home-abs-motos', 'servicios',
    'top-repair', 'ofertas-de-empleo', 'politica-de-privacidad', 'politica-de-cookies',
    'avisos-legales', 'aviso-legal', 'contacto', 'envios', 'garantias',
    'preguntas-frecuentes', 'faq', 'como-llegar', 'error-404', '404-2',
}
# The same old page published two or three times (reviewed 26 Oct 2026). Only the most complete
# copy becomes a ficha; links to the others open it and their old addresses redirect to it.
MERGED_COPIES = {
    'main-8607': 'main-8394',   # /cambio-iluminacion-del-cuadro-de-instrumentos/: the scratches page word for word
    'main-8241': 'main-8236',   # Fiat Qubo, qubo-2: one fault line and one photo fewer
    'abs-2475': 'abs-1936',     # BMW F 650 GS «Bosch 5.3»: four fault lines and one photo fewer, no Bosch 5.3 in its text
    'main-13359': 'main-8674',  # /reparacion-pantalla-multimedia/: six brands and one fault fewer
    'main-14038': 'main-8674',  # /reparacion-pantalla-navegador/: two brands fewer
    'main-9052': 'main-14508',  # Seat Full Link: the same page without its Alhambra section
}
SERVICE_PREFIXES = [
    ('reparacion-palanca-selectora', 'palanca'),
    ('reparacion-modulo-bluetooth', 'bluetooth'),
    ('reparacion-inmovilizadores', 'inmo'),
    ('reparacion-centralitas-clima', 'clima'),
    ('reparacion-bsi', 'bsi'),
    ('reparacion-abs', 'abs'),
    ('reparacion-error-fallo-5df5-abs', 'abs'),
    ('reparacion-fallo-abs', 'abs'),
    ('reparacion-electronica-cambio', 'cambio'),
    ('reparacion-cuadro-instrumentos', 'cuadro'),
    ('reparacion-cuentakilometros', 'cuadro'),
    ('cambio-iluminacion-del-cuadro', 'cuadro'),
    ('sustitucion-mph-por-kmh', 'cuadro'),
    ('reparacion-aranazos-en-pantalla-display-tft-del-cuadro', 'cuadro'),
    ('reparacion-fallo-iluminacion-cuadro', 'cuadro'),
    ('fallo-iluminacion-cuadro', 'cuadro'),
    ('reparacion-displays', 'display'),
    ('fallo-display', 'display'),
    ('fallo-cuentakilometros', 'display'),
    ('reparacion-fallo-oil-display', 'display'),
    ('reparacion-fallo-399999', 'display'),
    ('reparacion-pantalla', 'multimedia'),
    ('reparacion-puntos-negros', 'multimedia'),
    ('reparacion-burbuja', 'multimedia'),
    ('reparacion-centralita', 'ecu'),
    ('programacion-reparacion-centralitas', 'ecu'),
    ('reparacion-unidad-de-mando-hibrida', 'ecu'),
]


def unique(items):
    return list(dict.fromkeys(item for item in items if item))


def flat(raw):
    return ' '.join(html.unescape(re.sub(r'<[^>]+>', ' ', raw)).split()).strip()


def norm(text):
    return ''.join(c for c in unicodedata.normalize('NFKD', text.casefold()) if not unicodedata.combining(c))


def main_html(raw):
    # Older snapshots include the complete Live Composer header/footer in content.
    start = re.search(r'<div\b[^>]*\bid=["\']dslc-main["\'][^>]*>', raw, re.I)
    if start:
        raw = raw[start.end():]
    footer = re.search(r'<div\b[^>]*\bid=["\']dslc-footer["\']', raw, re.I)
    if footer:
        raw = raw[:footer.start()]
    raw = re.sub(r'<(style|script|textarea|select|form|nav)\b[^>]*>.*?</\1>', '', raw, flags=re.S | re.I)
    raw = re.sub(r'<!--.*?-->', '', raw, flags=re.S)
    return raw


def clean_lines(raw):
    text = re.sub(r'</?(?:p|div|li|h[1-6]|br|tr|table|ul|ol)\b[^>]*>', '\n', raw, flags=re.I)
    text = html.unescape(re.sub(r'<[^>]+>', ' ', text))
    lines = []
    for part in text.splitlines():
        line = ' '.join(part.split()).strip()
        if not line or line in {'<div', '</div', 'SI', 'NO'}:
            continue
        low = norm(line)
        if re.match(r'^(?:contacta con menigar|contacta para|nombre \(requerido\)|por favor, activa javascript|nombre y apellidos \*)', low):
            break
        if any(s in low for s in ['anchura del elemento', 'copyright ©', 'desarrollos digitales menigar', 'parque empresarial casablanca']):
            continue
        if re.match(r'^(?:[1-9]|1[0-2])/12\b', line):
            continue
        # Exact de-duplication removes responsive copies, keeping source wording intact.
        if line not in lines:
            lines.append(line)
    return lines


class Tables(HTMLParser):
    """Small tolerant table parser; retains complete cells, rather than row fragments."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tables = []
        self.table = None
        self.row = None
        self.cell = None
    def handle_starttag(self, tag, attrs):
        if tag == 'table': self.table = []
        elif tag == 'tr' and self.table is not None: self.row = []
        elif tag in {'td', 'th'} and self.row is not None: self.cell = []
        elif tag == 'br' and self.cell is not None: self.cell.append('\n')
    def handle_endtag(self, tag):
        if tag in {'td', 'th'} and self.cell is not None:
            if self.row is not None: self.row.append(' '.join(''.join(self.cell).split()))
            self.cell = None
        elif tag == 'tr' and self.row is not None:
            if self.table is not None: self.table.append(self.row)
            self.row = None
        elif tag == 'table' and self.table is not None:
            self.tables.append(self.table)
            self.table = None
    def handle_data(self, text):
        if self.cell is not None: self.cell.append(text)


# The token boundaries intentionally reject 07010 inside 94003-07010.
DTC_TOKEN = re.compile(r'(?<![A-Z0-9.\-])(?:[CPBU][0-9A-F]{4,6}|DF[0-9]{3,4}|5[DE][0-9A-F]{2,3}|0[0-9]{4}|163(?:49|50|52|55)|0[0-9A-F]{3}|3FE[03])(?![A-Z0-9.\-])', re.I)
DTC_CONTEXT = re.compile(r'(?:c[oó]digos?\s+(?:de\s+)?(?:error|aver[ií]a|fallo)|\bdtc\b|\berror\b|\bfallo\b|\bdefect)', re.I)
DIAGNOSTIC_WORDS = re.compile(r'bomba|sensor|presi[oó]n|unidad|centralita|comunicaci[oó]n|alimentaci[oó]n|bloque|rel[eé]|v[aá]lvula|fren|circuito|tensi[oó]n|motor|interrupci[oó]n', re.I)
CODE_AT_START = re.compile(r'^\s*[-•]?\s*([CPBU][0-9A-F]{4,6}|DF[0-9]{3,4}|5[DE][0-9A-F]{2,3}|0[0-9]{4}|163(?:49|50|52|55)|0[0-9A-F]{3}|3FE[03])(?:\s|\s*-\s*|:)', re.I)
REF_TOKEN = re.compile(r'(?<![A-Za-z0-9])(?:[0-9]{1,2}\.[0-9]{3,5}-[0-9]{3,5}\.[0-9]|[A-Za-z0-9]{2,8}(?:-[A-Za-z0-9]{2,12}){1,4}|[A-Z0-9]{5,24})(?![A-Za-z0-9])')
SPACED_REF = re.compile(r'(?<![A-Z0-9])(?:[0-9]\s+[0-9]{3}\s+[0-9]{3}\s+[0-9]{3}|[0-9A-Z]{3}\s+[0-9]{3}\s+[0-9]{3}(?:\s+[A-Z]{1,3})?)(?![A-Z0-9])')


def dtcs(lines, tables):
    codes = []
    details = []
    for line in lines:
        # Explicit fault labels, or code at the start of a diagnostic statement.
        if DTC_CONTEXT.search(line) or (CODE_AT_START.match(line) and DIAGNOSTIC_WORDS.search(line)):
            for match in DTC_TOKEN.finditer(line):
                code = match.group(0).upper()
                codes.append(code)
                details.append({'code': code, 'description': line})
    for table in tables:
        header = ' '.join(' '.join(row) for row in table[:2])
        if re.search(r'c[oó]digo.*(?:error|aver[ií]a|fallo)|\bdtc\b', header, re.I):
            for row in table:
                if row and DTC_TOKEN.fullmatch(row[0].strip()):
                    code = row[0].upper().strip()
                    codes.append(code)
                    details.append({'code': code, 'description': ' — '.join(row)})
    detail_map = {}
    for detail in details: detail_map.setdefault(detail['code'], detail)
    return unique(codes), list(detail_map.values())


def references(raw, lines, tables, codes):
    refs = []
    for table in tables:
        header = ' '.join(' '.join(row) for row in table[:2])
        if re.search(r'c[oó]digo.*(?:error|aver[ií]a|fallo)|\bdtc\b', header, re.I):
            continue
        for row in table:
            for cell in row:
                if not cell or re.search(r'referencia|modelo|a[nñ]o|marca|fabricante', cell, re.I):
                    continue
                # OEM reference tables are mostly cells of codes. Do not interpret
                # explanatory prose, costs, years or technical error descriptions as refs.
                if re.search(r'[a-záéíóúñ]', cell) or len(cell) > 140:
                    continue
                for value in SPACED_REF.findall(cell): refs.append(value)
                without_spaced = SPACED_REF.sub('', cell)
                for value in REF_TOKEN.findall(without_spaced):
                    if sum(c.isdigit() for c in value) >= 5 and not re.fullmatch(r'(?:19|20)\d{2}-(?:19|20)\d{2}', value):
                        refs.append(value)
    # Complete reference strings also occur outside tables. They are copied exactly.
    for line in lines:
        for value in SPACED_REF.findall(line): refs.append(value)
        for value in REF_TOKEN.findall(SPACED_REF.sub('', line)):
            digits = sum(c.isdigit() for c in value)
            if digits < 6 or value.upper() in codes:
                continue
            if re.fullmatch(r'(?:19|20)\d{2}-(?:19|20)\d{2}', value):
                continue
            if value in {'399999', '888888'}:
                continue
            refs.append(value)
    return unique(refs)


def taxonomy(source, url, variant):
    parts = urlparse(url).path.strip('/').split('/')
    root = parts[0] if parts else ''
    component = 'abs' if source == 'abs' else next((key for prefix, key in SERVICE_PREFIXES if root.startswith(prefix)), None)
    brand_slug = parts[1] if len(parts) > 1 else ''
    brand = BRANDS.get(brand_slug, '')
    if not brand:
        # Only title/path, never menus or prose listing compatible brands.
        hits = []
        haystack = norm(variant + ' ' + ' '.join(parts[-1:])).replace('-', ' ')
        for slug, name in sorted(BRANDS.items(), key=lambda x: -len(x[0])):
            if slug in {'motos-honda', 'motos-suzuki', 'vw'}: continue
            needle = norm(slug.replace('-', ' '))
            if re.search(r'(?<!\w)' + re.escape(needle) + r'(?!\w)', haystack): hits.append(name)
        hits = unique(hits)
        brand = hits[0] if len(hits) == 1 else ''
    is_brand_page = brand_slug in BRANDS and len(parts) == 2
    model = ''
    # A nested vehicle page is the strongest evidence for a model; generic service
    # and brand overview pages remain available without polluting the guided model list.
    if brand and len(parts) >= 3:
        model = variant
        if re.match(r'^(?:Reparaci[oó]n|Fallo|T[aá]ctil)\b', variant, re.I):
            brand_alias = brand_slug.replace('-', ' ')
            match = re.search(re.escape(brand_alias), variant, re.I)
            if not match and brand == 'Mercedes-Benz': match = re.search('Mercedes', variant, re.I)
            if match: model = variant[match.end():]
            else: model = ''
        aliases = [brand, brand_slug.replace('-', ' ')]
        if brand == 'Mercedes-Benz': aliases.append('Mercedes')
        for name in aliases:
            model = re.sub(r'\b' + re.escape(name) + r'\b', '', model, flags=re.I)
        model = re.sub(r'^(?:Reparaci[oó]n\s+)?(?:cuadro(?:s)?(?:\s+de\s+instrumentos)?|pantalla|display|ABS|m[oó]dulo)\s+', '', model, flags=re.I)
        model = re.split(r'\s*(?:\(?\b(?:19|20)\d{2}\b|\bATE\b|\bBOSCH\b|\bTRW\b|\bADVICS\b|\bNISSIN\b|\bMANDO\b|\bTEVES\b)', model, maxsplit=1, flags=re.I)[0]
        # Some ABS titles begin with OEM references followed by the actual vehicle.
        brand_match = re.search(r'\b' + re.escape(brand_slug.replace('-', ' ')) + r'\b', variant, re.I)
        if brand_match and brand_match.start() and re.search(r'\d{5,}', variant[:brand_match.start()]):
            model = re.split(r'\s*(?:\(?\b(?:19|20)\d{2}\b|\bATE\b|\bBOSCH\b|\bTRW\b)', variant[brand_match.end():], maxsplit=1, flags=re.I)[0]
        model = ' '.join(model.split()).strip(' -:,()')
    return component, brand, model, is_brand_page


def first_description(raw, lines):
    candidates = [flat(p) for p in re.findall(r'<p\b[^>]*>(.*?)</p>', raw, re.S | re.I)]
    for line in lines[1:] + candidates:
        if len(line) < 55 or not re.search(r'[a-záéíóúñ]', line): continue
        if any(word in norm(line) for word in ['copyright', 'contacta con', 'nombre (requerido)', 'ventajas menigar']): continue
        if len(line) <= 280: return line
        # A complete first sentence is preferable to cutting words or references.
        sentence = re.split(r'(?<=[.!?])\s+', line)[0]
        if len(sentence) <= 330: return sentence
    return ''


def extract_symptoms(raw, lines, codes):
    candidates = [flat(li) for li in re.findall(r'<li\b[^>]*>(.*?)</li>', raw, re.S | re.I)]
    # Common ABS descriptions use paragraphs rather than lists.
    candidates += [line for line in lines if re.search(r'fall[oa]|defecto|bloquead|no\s+(?:funciona|frena|enciende|comunica|arranca)|sin\s+(?:comunicaci[oó]n|iluminaci[oó]n)|presi[oó]n|desaparece|parpadea|l[ií]neas|p[ií]xeles|burbujas|se\s+apaga', line, re.I)]
    symptoms = []
    for line in candidates:
        line = line.strip(' -•')
        low = norm(line)
        if len(line) < 12 or len(line) > 260: continue
        if any(s in low for s in ['menu-item', 'contacta', 'contacte', 'presupuesto', 'ventajas menigar', 'codigo de error especificado', 'envi', 'estos son', 'reparamos', 'somos especialistas', 'realizamos', 'si quiere', 'si tiene', 'garantia', 'reparacion normal', 'problemas comunes', 'defectos comunes', 'nuestras instalaciones']): continue
        if not re.search(r'fall[oa]|defecto|bloquead|no\s+(?:funciona|frena|enciende|comunica|arranca)|sin\s+(?:comunicaci[oó]n|iluminaci[oó]n)|presi[oó]n|desaparece|parpadea|l[ií]neas|p[ií]xeles|burbujas|se\s+apaga|programaci[oó]n|clonaci[oó]n', line, re.I): continue
        if not re.search(r'[a-záéíóúñ]{3}', line): continue
        symptoms.append(line)
    return unique(symptoms)


def instruction_groups(raw):
    groups = []
    # Labels immediately preceding each shipping table contain its applicable brands.
    position = 0
    for match in re.finditer(r'<table\b[^>]*>.*?</table>', raw, re.S | re.I):
        before = clean_lines(raw[position:match.start()])
        parser = Tables(); parser.feed(match.group(0))
        if parser.tables:
            rows = parser.tables[0]
            if rows and re.search(r'c[oó]digo.*error', ' '.join(rows[0]), re.I):
                label = before[-1] if before else 'Aplicación indicada en la fuente'
                groups.append({'label': label, 'columns': rows[0], 'rows': rows[1:]})
        position = match.end()
    return groups


def catalogue_json(catalogue):
    """The catalogue as JSON with one record per line and no indentation. It holds the same data in about
    60 % of the bytes of indent=2 (GitHub warns above 50 MB), and a diff still points to the record that changed."""
    return '[\n' + ',\n'.join(json.dumps(record, ensure_ascii=False, separators=(',', ':')) for record in catalogue) + '\n]\n'


def build():
    all_pages = []
    fingerprints = {}
    for source, directory, glob_pattern in [('main', 'cache', 'pages_page_*.json'), ('abs', 'cache_abs', 'abs_page_*.json')]:
        for file in sorted((DATA / directory).glob(glob_pattern)):
            fingerprints[str(file.relative_to(ROOT))] = hashlib.sha256(file.read_bytes()).hexdigest()
            all_pages.extend((source, page) for page in json.loads(file.read_text(encoding='utf-8')))
    catalogue = []
    excluded = []
    for source, page in all_pages:
        url = page.get('link', '')
        slug = page.get('slug', '')
        variant = flat(page.get('title', {}).get('rendered', ''))
        if slug in EXCLUDED:
            excluded.append({'source': source, 'sourceId': page['id'], 'url': url, 'reason': 'Página institucional, navegación o legal; no es ficha de reparación.'})
            continue
        component, brand, model, is_brand_page = taxonomy(source, url, variant)
        if not component:
            excluded.append({'source': source, 'sourceId': page['id'], 'url': url, 'reason': 'Sin familia de servicio identificable en la URL de origen.'})
            continue
        raw = main_html(page.get('content', {}).get('rendered', ''))
        lines = clean_lines(raw)
        if not lines:
            excluded.append({'source': source, 'sourceId': page['id'], 'url': url, 'reason': 'Sin contenido de servicio en la captura.'})
            continue
        table_parser = Tables(); table_parser.feed(raw)
        code_list, code_details = dtcs(lines, table_parser.tables)
        refs = references(raw, lines, table_parser.tables, code_list)
        heading = re.search(r'<h1\b[^>]*>(.*?)</h1>', raw, re.I | re.S)
        title = flat(heading.group(1)) if heading else variant
        title = title or variant
        uid = f'{source}-{page["id"]}'
        if uid in MERGED_COPIES:
            excluded.append({'source': source, 'sourceId': page['id'], 'url': url, 'uid': uid,
                             'reason': 'Copia de otra página: se une a su ficha más completa.',
                             'mergedInto': MERGED_COPIES[uid], 'formerLocalPath': f'/reparaciones/{uid}-{slug}/'})
            continue
        is_instruction = slug == 'informacion-abs-ate-esp-mk61'
        instructions = unique(line for line in lines if re.search(r'env[ií]e|env[ií]enos|m[aá]ndenos|debe(?:r[aá])?\s+enviar|piezas.*enviar|protej|embal|conector.*(?:da[nñ]|prote)|compruebe.*c[oó]digo', line, re.I))
        warranty = next((line for line in lines if re.search(r'garant[ií]a.*\b\d+\s*(?:a[nñ]os?|meses?)', line, re.I)), '')
        # Prefer the qualified source sentence to the short marketing heading.
        timing_candidates = [line for line in lines if re.search(r'\b(?:24\s*h(?:oras?)?|48\s*h(?:oras?)?|\d+\s+d[ií]as?)\b', line, re.I) and re.search(r'repar|plazo|normal|frecuent', line, re.I)]
        timing = next((line for line in timing_candidates if re.search(r'frecuent|habitual|aproxim|depende', line, re.I)), next(iter(timing_candidates), ''))
        images = []
        for image in re.findall(r'<img\b[^>]*>', raw, re.I):
            attrs = dict(re.findall(r'([\w-]+)=["\']([^"\']*)["\']', image))
            image_url = html.unescape(attrs.get('src', ''))
            if not image_url.startswith('https://www.menigar.com/'): continue
            if any(s in norm(image_url) for s in ['logo', 'banner', 'telefono', 'trabaja_con', 'garantia', 'precio', 'google', 'estrella', 'fondo', 'envio']): continue
            images.append(image_url)
        record = {
            'uid': uid, 'source': source, 'sourceId': page['id'], 'url': url,
            'slug': slug, 'localPath': f'/reparaciones/{uid}-{slug}/',
            'brand': brand, 'model': model, 'variant': variant,
            'componentKey': component, 'componentName': FAMILY_NAMES[component],
            'title': title, 'description': first_description(raw, lines),
            'symptoms': extract_symptoms(raw, lines, code_list), 'references': refs,
            'dtcCodes': code_list, 'dtcDetails': code_details,
            'sourceText': '\n'.join(lines), 'instructions': instructions,
            'warranty': warranty, 'timing': timing,
            'isAggregator': is_brand_page or (not model and not refs and not code_list),
            'isInstruction': is_instruction, 'relatedInstructions': [],
            'sourceModified': page.get('modified', ''),
            'reviewStatus': 'source-imported',
        }
        if images: record['image'] = images[0]
        if is_instruction: record['instructionGroups'] = instruction_groups(raw)
        catalogue.append(record)
    # In the other service families a title can name a radio/gearbox rather than
    # a car. Reuse only vehicle model names evidenced by the vehicle catalogues.
    # Generic services remain searchable by brand and family without claiming fit.
    vehicle_models = {}
    for record in catalogue:
        if record['componentKey'] in {'cuadro', 'abs'} and record['brand'] and record['model']:
            vehicle_models.setdefault(record['brand'], set()).add(record['model'])
    for record in catalogue:
        if record['componentKey'] not in {'cuadro', 'abs'} and record['model']:
            candidates = sorted(vehicle_models.get(record['brand'], set()), key=lambda model: (-len(model), norm(model), model))
            match = next((model for model in candidates if re.search(r'(?<!\w)' + re.escape(norm(model)) + r'(?!\w)', norm(record['model']))), '')
            record['model'] = match
    catalogue.sort(key=lambda row: (row['componentKey'], norm(row['brand']), norm(row['model']), row['uid']))
    from pilot_hyundai import enrich_hyundai
    pilot_report = enrich_hyundai(catalogue, all_pages, ROOT, main_html)
    from bmw_source import enrich_bmw
    bmw_report = enrich_bmw(catalogue, ROOT)
    from source_sections import enrich_sources
    merged = [entry for entry in excluded if entry.get('mergedInto')]
    by_uid = {r['uid']: r for r in catalogue}
    assert sorted(entry['uid'] for entry in merged) == sorted(MERGED_COPIES), 'A merged copy is missing from the captures'
    assert all(entry['mergedInto'] in by_uid and entry['mergedInto'] not in MERGED_COPIES for entry in merged), 'A copy must merge into a ficha'
    sections_report = enrich_sources(catalogue, ROOT, merged)
    # Link MK61 shipping context without treating its tables as universal compatibility.
    instruction_uid = next((r['uid'] for r in catalogue if r['isInstruction']), None)
    if instruction_uid:
        for record in catalogue:
            if not record['isInstruction'] and record['componentKey'] == 'abs' and re.search(r'\bMK\s*61\b', record['title'] + ' ' + record['description'], re.I):
                record['relatedInstructions'].append(instruction_uid)
    assert len(catalogue) == len({r['uid'] for r in catalogue}), 'Duplicate scoped UID'
    assert len(catalogue) == len({r['localPath'] for r in catalogue}), 'Duplicate public path'
    honda = next(r for r in catalogue if r['uid'] == 'abs-3198')
    assert honda['brand'] == 'Honda' and honda['model'] == 'Civic' and 'Civic' in honda['title']
    picanto = next(r for r in catalogue if r['slug'] == 'picanto' and r['source'] == 'main')
    assert '07010' not in picanto['dtcCodes']
    assert not any(r['source'] == 'main' and code in {'0003', '0517', '0104'} for r in catalogue for code in r['dtcCodes']), 'Reference row misclassified as DTC'
    assert '94003-07010' in picanto['references'], 'Complete original reference was lost'
    assert '06.2109-6664.3' in honda['references'], 'Reference punctuation/leading zero was lost'
    assert all(isinstance(code, str) for r in catalogue for code in r['dtcCodes'])
    assert not any('07010' == code for r in catalogue for code in r['dtcCodes']), 'False fragment DTC'
    assert instruction_uid and len(next(r for r in catalogue if r['uid'] == instruction_uid)['instructionGroups']) == 6
    # Source snapshots are never rewritten by this builder.
    assert all(hashlib.sha256((ROOT / file).read_bytes()).hexdigest() == digest for file, digest in fingerprints.items())
    (DATA / 'catalogo-v2.json').write_text(catalogue_json(catalogue), encoding='utf-8')
    browser_omissions = {'sourceText', 'dtcDetails', 'instructionGroups', 'sourceSections',
                        'sourceCapture', 'sourceHtmlSha256', 'contentBlocks'}
    browser_catalogue = []
    for record in catalogue:
        item = {key: value for key, value in record.items() if key not in browser_omissions}
        # Editorial presentation never overwrites the archived search evidence.
        public_title = public_text(record.get('title'), record['uid'], 'title')
        if public_title != record.get('title'):
            item['publicTitle'] = public_title
        # Result cards use a single overview photo. Full galleries and source
        # provenance stay in the generated detail page and complete local JSON.
        if 'gallery' in item:
            item['gallery'] = [{key: image[key] for key in ('src', 'alt') if key in image}
                               for image in item['gallery'][:1]]
        if 'modelGroups' in item:
            item['modelGroups'] = [{key: value for key, value in group.items() if key != 'blocks'} | {
                'blocks': [{'images': [{key: image[key] for key in ('src', 'alt') if key in image}
                                       for image in block.get('images', [])[:1]],
                            'symptoms': block.get('symptoms', [])} for block in group.get('blocks', [])]
            } for group in item['modelGroups']]
        browser_catalogue.append(item)
    (DATA / 'catalogo-v2.js').write_text('// Generated offline by scripts/build_catalog.py. Do not edit by hand.\nwindow.MENIGAR_FAMILIES = ' + json.dumps(FAMILIES, ensure_ascii=False, separators=(',', ':')) + ';\nwindow.MENIGAR_CATALOG = ' + json.dumps(browser_catalogue, ensure_ascii=False, separators=(',', ':')) + ';\n', encoding='utf-8')
    write_home_index(catalogue, FAMILIES)
    # Planning manifest only: the prototype does not enable production redirects.
    redirects = [{'from': r['url'], 'fromPath': urlparse(r['url']).path, 'to': r['localPath'], 'status': 301, 'enabled': False, 'reviewRequired': True, 'uid': r['uid']} for r in catalogue]
    redirects += [{'from': entry['url'], 'fromPath': urlparse(entry['url']).path, 'to': by_uid[entry['mergedInto']]['localPath'], 'status': 301,
                   'enabled': False, 'reviewRequired': True, 'uid': entry['mergedInto'], 'mergedFrom': entry['uid']} for entry in merged]
    (DATA / 'redirects.json').write_text(json.dumps(redirects, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report = {
        'schemaVersion': 3, 'contentPilots': {'hyundai': pilot_report['scope']}, 'contentExpansions': {'bmw': bmw_report['scope'], 'sharedSourceSections': sections_report['totals']}, 'browserProjectionOmissions': sorted(browser_omissions), 'sourcePageCounts': dict(Counter(source for source, page in all_pages)),
        'recordCount': len(catalogue), 'bySource': dict(Counter(r['source'] for r in catalogue)),
        'byFamily': dict(Counter(r['componentKey'] for r in catalogue)),
        'brandCount': len({r['brand'] for r in catalogue if r['brand']}),
        'modelRecords': sum(bool(r['model']) for r in catalogue),
        'referenceCount': sum(len(r['references']) for r in catalogue),
        'dtcCodeCount': len({c for r in catalogue for c in r['dtcCodes']}),
        'instructionRecords': [r['uid'] for r in catalogue if r['isInstruction']],
        'relatedInstructionRecords': sum(bool(r['relatedInstructions']) for r in catalogue),
        'excluded': excluded, 'snapshotSha256': fingerprints,
        'checks': {'uniqueScopedIds': True, 'hondaCivicSelection': True, 'completePicantoReference': True, 'noFalse07010Dtc': True, 'leadingZerosAndPunctuation': True, 'mk61SixShippingGroups': True, 'snapshotsUnchanged': True},
        'limitations': ['Content is recovered from the supplied local snapshots, not a new live crawl.', 'Imported service conditions remain specific to the original page; no price, warranty or timing defaults are added.', 'Editorial and technical approval is needed before production publication.', 'Redirects are a disabled planning manifest and do not affect menigar.com.'],
    }
    (DATA / 'catalogo-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(json.dumps({k: report[k] for k in ['sourcePageCounts', 'recordCount', 'bySource', 'byFamily', 'brandCount', 'referenceCount', 'dtcCodeCount', 'checks']}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
