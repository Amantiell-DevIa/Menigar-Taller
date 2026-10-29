"""Services page: specialties, featured services and the selector options (26 Oct 2026).

servicios.html opens with what MENIGAR repairs instead of the whole catalogue in 92 pages. The
blocks that depend on the catalogue are written here, between markers in servicios.html, so every
count, brand and title always matches data/catalogo-v2.json and the public titles of
data/catalogo-v2.js. The rest of the page is edited by hand.

The featured services are a choice of the company: change FEATURED (and their photos) and run
    python3 scripts/build_servicios.py
"""
from collections import Counter
from html import escape
import json
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / 'servicios.html'

# The six main specialties, with a representative photograph of the kind of piece (not of a vehicle
# match). «contain» keeps a product shot or a cut-out whole; «cover» fills the frame with a scene.
SPECIALTIES = [
    ('cuadro', '/assets/media/46/46a3bcf3b664035c-cuadros-analogicos-cuadros.webp', 'contain',
     'Cuadro de instrumentos abierto, con su placa electrónica a la vista', 'De turismos, furgonetas, motos, camiones y maquinaria agrícola.'),
    ('abs', '/assets/home/abs-modulo-497.webp', 'contain',
     'Módulo ABS con su grupo hidráulico, su motor y su centralita', 'Módulos ABS y ESP de turismos, furgonetas y motos.'),
    ('multimedia', '/assets/home/pantalla-medianav-recorte-652.webp', 'contain',
     'Pantalla multimedia encendida, con el menú de radio, teléfono y GPS', 'Pantallas táctiles, navegadores y radios multimedia.'),
    ('display', '/assets/bmw/aa76d38fccf4-display_bmw_serie1.jpg', 'cover',
     'Display encendido de un cuadro de instrumentos BMW Serie 1', 'Displays del cuadro y fallos del cuentakilómetros.'),
    ('cambio', '/assets/media/b6/b636239748b5504e-dsg-dq250-blanco.webp', 'contain',
     'Mecatrónica de un cambio automático DSG', 'Mecatrónicas y unidades de control del cambio automático.'),
    ('palanca', '/assets/media/ec/ec35762447a5cb0b-palanca-selectora-jeep-grand-cherokee.webp', 'contain',
     'Palanca selectora de un cambio automático', 'Palancas selectoras del cambio automático.'),
]
# General services, each with a photograph from its own ficha (or MENIGAR's own photo of that kind of piece).
FEATURED = [
    ('main-171', '/assets/media/ba/ba983ebdbaaa984e-cuadro-digital-cuadros.webp', 'cover', 'Cuadro de instrumentos digital encendido'),
    ('main-13323', '/assets/media/eb/eb432f107376d95f-abs-ate-mk100-fondo.webp', 'contain', 'Tres módulos ABS ATE MK100'),
    ('main-8674', '/assets/home/pantalla-medianav-recorte-652.webp', 'contain', 'Pantalla multimedia táctil encendida'),
    ('main-2834', '/assets/media/82/82d107ce2326c43f-display-seat-leon2.webp', 'cover', 'Display del cuadro de un Seat León con la información del viaje'),
    ('main-2646', '/assets/media/dc/dc5bc1f79683851a-boxer-odo.webp', 'cover', 'Cuentakilómetros con el fallo 399999 km'),
    ('main-8394', '/assets/media/02/028870dc622186ee-reparacion-cuadro-rayado.webp', 'cover', 'Pantalla TFT de un cuadro de instrumentos con arañazos'),
]
GENERIC_BRAND = re.compile(r'^(otras?|otros?|varios?|multimarca|general|todas? las marcas|sin marca)$', re.I)


def catalogue():
    records = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
    browser = (ROOT / 'data/catalogo-v2.js').read_text()
    families = json.loads(browser.split('window.MENIGAR_FAMILIES = ', 1)[1].split(';\nwindow.MENIGAR_CATALOG', 1)[0])
    public = {item['uid']: item.get('publicTitle') or item['title']
              for item in json.loads(browser.split('window.MENIGAR_CATALOG = ', 1)[1].rstrip().rstrip(';'))}
    return records, families, public


def number(value):
    return f'{value:,}'.replace(',', '.')


def plural(value, one, many):
    return f'{number(value)} {one if value == 1 else many}'


VARIANTS = (280, 480, 640)


def variants(src, folder='servicios', sizes=VARIANTS):
    """Light copies of the photograph in assets/<folder>/, so each screen downloads only the size it shows.
    Returns (url, width, height) for each copy, the largest last."""
    from PIL import Image
    source = ROOT / src.lstrip('/')
    if not source.is_file():
        raise SystemExit(f'Falta la imagen {src}')
    original = Image.open(source)
    original = original.convert('RGBA' if original.mode in ('RGBA', 'LA', 'P') else 'RGB')
    target = ROOT / 'assets' / folder
    target.mkdir(exist_ok=True)
    widths = sorted({min(width, original.width) for width in sizes})
    candidates = []
    for width in widths:
        height = round(original.height * width / original.width)
        path = target / f'{source.stem}-{width}.webp'
        if not path.exists() or path.stat().st_mtime < source.stat().st_mtime:
            original.resize((width, height), Image.LANCZOS).save(path, 'WEBP', quality=80, alpha_quality=90, method=6)
        candidates.append((f'/assets/{folder}/{path.name}', width, height))
    return candidates


def image(src, fit, alt, sizes, prefix='s'):
    candidates = variants(src)
    largest = candidates[-1]
    srcset = ', '.join(f'{url} {width}w' for url, width, _ in candidates)
    return (f'<img class="{prefix}-fit-{fit}" src="{largest[0]}" srcset="{srcset}" sizes="{sizes}" alt="{escape(alt)}" '
            f'width="{largest[1]}" height="{largest[2]}" loading="lazy" decoding="async">')


def build():
    records, families, public = catalogue()
    names = {family['key']: family['name'] for family in families}
    services = [record for record in records if not record.get('isInstruction')]
    counts = Counter(record['componentKey'] for record in services)
    by_uid = {record['uid']: record for record in services}

    tiles = []
    for key, src, fit, alt, text in SPECIALTIES:
        brands = Counter(record['brand'] for record in services if record['componentKey'] == key and record['brand'] and not GENERIC_BRAND.match(record['brand']))
        top = [brand for brand, _ in brands.most_common(3)]
        tiles.append(f'''<li><a class="s-family" href="/servicios.html?pieza={key}#resultados" data-catalog-link><span class="s-family-media">{image(src, fit, alt, "(max-width: 600px) 120px, (max-width: 1100px) 46vw, 380px")}</span>
<span class="s-family-body"><span class="s-family-name">{escape(names[key])}</span><span class="s-family-text">{escape(text)}</span>
<span class="s-family-meta">{plural(counts[key], "ficha", "fichas")} · {escape(", ".join(top))} y más</span></span><span class="s-family-go" aria-hidden="true">→</span></a></li>''')
    minor = [family for family in families if family['key'] not in {key for key, *_ in SPECIALTIES} and counts[family['key']]]
    minor_html = ''.join(f'<li><a href="/servicios.html?pieza={family["key"]}#resultados" data-catalog-link>{escape(family["name"])}</a></li>' for family in minor)
    specialties = (f'<ul class="s-families">{"".join(tiles)}</ul>\n'
                   f'<div class="s-minor"><p>También reparamos</p><ul>{minor_html}</ul></div>')

    cards = []
    for uid, src, fit, alt in FEATURED:
        record = by_uid[uid]
        cards.append(f'''<li><a class="s-featured-card" href="{escape(record["localPath"])}"><span class="s-featured-media">{image(src, fit, alt, "(max-width: 600px) 78vw, (max-width: 1100px) 46vw, 380px")}</span>
<span class="s-featured-body"><span class="s-featured-family">{escape(names[record["componentKey"]])}</span><span class="s-featured-title">{escape(public[uid])}</span><span class="s-featured-go">Ver servicio <span aria-hidden="true">→</span></span></span></a></li>''')
    featured = f'<ul class="s-featured">{"".join(cards)}</ul>'

    # The selectors work before the catalogue arrives: app.js replaces these options with its own.
    brands = sorted({record['brand'] for record in services if record['brand'] and not GENERIC_BRAND.match(record['brand'])},
                    key=lambda value: (value.casefold().replace('š', 's').replace('ë', 'e'), value))
    brand_options = ''.join(f'<option value="{escape(brand)}">{escape(brand)}</option>' for brand in brands)
    family_options = ''.join(f'<option value="{family["key"]}">{escape(family["name"])}</option>' for family in families if counts[family['key']])
    total = len(services)
    return {'especialidades': specialties, 'destacados': featured, 'opciones-marca': brand_options,
            'opciones-pieza': family_options, 'total': f'<strong>{number(total)}</strong> fichas de reparación'}


def build_home():
    """The homepage's specialty cards (28 Oct 2026): the same six specialties, names and photographs as the
    services page, each opening it on that specialty."""
    _, families, _ = catalogue()
    names = {family['key']: family['name'] for family in families}
    arrow = '<svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M5 12h14M13 6l6 6-6 6"/></svg>'
    cards = ''.join(f'<li><a class="h-cat" href="/servicios.html?pieza={key}#resultados"><span class="h-cat-media">'
                    f'{image(src, fit, alt, "(max-width: 600px) 44vw, (max-width: 1100px) 30vw, 180px", "h")}</span>'
                    f'<span class="h-cat-name">{escape(names[key])}</span><span class="h-cat-go" aria-hidden="true">{arrow}</span></a></li>'
                    for key, src, fit, alt, _ in SPECIALTIES)
    return {'portada-especialidades': f'<ul class="h-cat-grid">{cards}</ul>'}


def fill(path, blocks):
    page = path.read_text()
    for name, html in blocks.items():
        pattern = re.compile(rf'(<!-- generado:{name} -->).*?(<!-- /generado:{name} -->)', re.S)
        if not pattern.search(page):
            raise SystemExit(f'Falta el marcador generado:{name} en {path.name}')
        page = pattern.sub(lambda match: match.group(1) + html + match.group(2), page)
    path.write_text(page)


def write():
    fill(PAGE, build())
    fill(ROOT / 'index.html', build_home())
    print('servicios.html e index.html actualizados')

if __name__ == '__main__':
    write()
