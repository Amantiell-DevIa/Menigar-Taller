"""Reusable, traceable source sections for every repair page.

The source's heading order and table membership are retained. No compatibility,
price or diagnosis is inferred from an image, reference or nearby paragraph.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote, urlsplit, urlencode
from public_copy import public_text, photo_caption, REVIEWED_INDEX_GROUPS

RUN = '2026-10-13-publico'


def url_path(value):
    u = urlsplit(value)
    return unquote(u.path).rstrip('/') or '/'


def scoped_blocks(page):
    from audit_wordpress_export import SourceBlocks, public_body

    class ContextBlocks(SourceBlocks):
        def context(self):
            return {**super().context(), 'insideTable': any(frame['tag'] == 'table' for frame in self.stack)}

    body, _ = public_body(page['content']['rendered'])
    parser = ContextBlocks(page['link'])
    parser.feed(body)
    return parser.finish()


def is_section_heading(block):
    text = block.get('text', '').strip()
    if block['kind'] != 'heading' or block['tag'] == 'h1' or not 3 < len(text) <= 115:
        return False
    if re.match(r'^(?:[-–•]|fall[oa]|sin |no |referencias?\b|c[oó]digos?\b|garant[ií]a|plazo|contact|ventajas|en menigar|reparamos|si |y |horario)', text, re.I):
        return False
    if re.fullmatch(r'[0-9A-Z. /-]{5,}', text) and re.search(r'\d', text):
        return False
    return True


def enrich_sources(catalogue, root, merged=()):
    prepared = root / 'data/wordpress_exports' / RUN / 'prepared'
    media = json.loads((root / 'data/media-local-manifest.json').read_text())
    local_media = media['urlIndex']
    omitted_images = {(x['sourceUid'], x['sourceOrder']) for x in media['omitted']}
    known_models = {}
    for row in catalogue:
        if row.get('brand') and row.get('model') and row['componentKey'] in {'cuadro', 'abs'}:
            known_models.setdefault(row['brand'], set()).add(row['model'])
    by_path = {url_path(row['url']): row for row in catalogue}
    by_uid = {row['uid']: row for row in catalogue}
    aliases_path = root / 'data/legacy-link-resolution.json'
    aliases = {}
    # A copy merged into its most complete ficha: links to the copy open that ficha.
    merged_into = {entry['uid']: entry['mergedInto'] for entry in merged}
    if aliases_path.exists():
        for alias in json.loads(aliases_path.read_text())['links']:
            resolved = merged_into.get(alias.get('resolvedUid'), alias.get('resolvedUid'))
            if resolved in by_uid and alias.get('resolution') == 'restored-wordpress-page-id':
                aliases[url_path(alias['originalUrl'])] = by_uid[resolved]
    for entry in merged:
        aliases[url_path(entry['url'])] = by_uid[entry['mergedInto']]
    info_paths = {'/': '/index.html', '/reparacion-abs': '/servicios.html?familia=abs',
                  '/envios': '/envios.html', '/contacto': '/ayuda.html#contacto',
                  '/preguntas-frecuentes': '/ayuda.html', '/garantias': '/garantia.html',
                  '/politica-de-privacidad': '/privacidad.html', '/politica-de-cookies': '/cookies.html',
                  '/avisos-legales': '/condiciones.html', '/aviso-legal': '/condiciones.html'}
    documents = {}
    docs_dir = root / 'assets/documentos'
    docs_dir.mkdir(exist_ok=True)
    backup_docs = Path('/Users/kaykostar/Documents/MENIGAR/respaldo-web-2026-10-14/archivos/httpdocs/docs')
    doc_manifest = []
    for name in ['peticion_reparacion 2026a.pdf', 'como_embalar.pdf', 'direccion_envio.pdf']:
        original = backup_docs / name
        if not original.exists():
            raise ValueError('Missing current public PDF: ' + name)
        digest = hashlib.sha256(original.read_bytes()).hexdigest()
        target = docs_dir / (digest[:12] + '-' + re.sub(r'[^a-z0-9._-]', '-', name.lower()))
        target.write_bytes(original.read_bytes())
        path = '/' + str(target.relative_to(root))
        documents['/docs/' + name] = path
        doc_manifest.append({'sourcePath': '/docs/' + name, 'localPath': path, 'sha256': digest, 'bytes': target.stat().st_size})
    (root / 'data/documentos-local-manifest.json').write_text(json.dumps(doc_manifest, ensure_ascii=False, indent=2) + '\n')
    all_pages, source_fingerprints = {}, {}
    rows, unresolved_links = [], []
    for record in catalogue:
        document = json.loads((prepared / 'documents' / record['source'] / ('pages-' + str(record['sourceId']) + '.json')).read_text())
        response_path = document['capture']['responsePath']
        if response_path not in all_pages:
            source = prepared.parent / response_path
            if hashlib.sha256(source.read_bytes()).hexdigest() != document['capture']['responseSha256']:
                raise ValueError('Archived response changed')
            all_pages[response_path] = {row['id']: row for row in json.loads(source.read_text())}
        page = all_pages[response_path][record['sourceId']]
        if hashlib.sha256(page['content']['rendered'].encode()).hexdigest() != document['sourceHtmlSha256']:
            raise ValueError('Archived page content changed')
        blocks = scoped_blocks(page)
        source_fingerprints[record['uid']] = document['sourceHtmlSha256']
        sections = [{'title': '', 'anchor': 'servicio', 'blocks': [], 'sourceHeadingOrder': None}]
        current = sections[0]
        exclusions = []
        for original in blocks:
            block = dict(original)
            if block.get('insideTable') and block['kind'] in {'heading', 'text'}:
                exclusions.append({'order': block['order'], 'reason': 'Already preserved in the complete table cell'})
                continue
            if block['kind'] == 'heading' and block['tag'] == 'h1':
                exclusions.append({'order': block['order'], 'reason': 'Page title shown above the service content'})
                continue
            if is_section_heading(block):
                # A later explicitly named problem section can rejoin its exact
                # generation heading; table cells are never used as headings.
                matches = [s for s in sections[1:] if record.get('brand') and s['title'].startswith(record['brand'] + ' ') and re.search(re.escape(s['title']) + r'(?![\w])', block['text'], re.I)]
                if block['text'].lower().startswith(('problemas comunes', 'fallos comunes')) and len(matches) == 1:
                    current = matches[0]
                    current['blocks'].append(block)
                    continue
                current = {'title': block['text'], 'anchor': 'detalle-' + str(block['order']),
                           'sourceHeadingOrder': block['order'], 'sourceModuleId': block['sourceModuleId'], 'blocks': []}
                sections.append(current)
                continue
            if block['kind'] == 'text' and current['title'] and re.match(r'^(?:En Menigar contamos|En Menigar somos|Contacte con nosotros)', block.get('text', ''), re.I):
                # Explicit company-wide closing copy is not a model description.
                current = {'title': '', 'anchor': 'informacion-' + str(block['order']),
                           'sourceHeadingOrder': None, 'blocks': []}
                sections.append(current)
            if block['kind'] == 'image':
                local = local_media.get(unquote(urlsplit(block['src']).path))
                if not local:
                    if urlsplit(block['src']).hostname == 's.w.org' and block.get('attributes', {}).get('alt'):
                        current['blocks'].append({**block, 'kind': 'text', 'text': block['attributes']['alt']})
                    reason = 'Decorative image explicitly omitted' if (record['uid'], block['order']) in omitted_images else 'Missing local image; needs review'
                    exclusions.append({'order': block['order'], 'reason': reason, 'url': block['src']})
                    continue
                block['originalSrc'], block['src'] = block['src'], local
                block['alt'] = block.get('attributes', {}).get('alt') or ('Imagen de ' + (current['title'] or record['title']))
                block.pop('attributes', None)
                block.pop('urls', None)
            elif block['kind'] == 'link':
                parsed = urlsplit(block['href'])
                if parsed.hostname in {'www.menigar.com', 'menigar.com'}:
                    path = url_path(block['href'])
                    target = by_path.get(path) or aliases.get(path)
                    block['originalHref'] = block['href']
                    if target:
                        block['href'] = target['localPath']
                        block['relatedServiceUid'] = target['uid']
                    elif unquote(parsed.path) in local_media:
                        block['href'] = local_media[unquote(parsed.path)]
                    elif unquote(parsed.path) in documents:
                        block['href'] = documents[unquote(parsed.path)]
                    elif path.endswith('/contacto') or path == '/newweb/contacto':
                        block['href'] = '/ayuda.html#contacto'
                    elif path == '/reparacion-abs/reparacion-abs':
                        block['href'] = '/servicios.html?familia=abs'
                    elif path in info_paths:
                        block['href'] = info_paths[path]
                    elif '/wp-content/uploads/' in path and re.search(r'(?:senal_peligro|logo_top_repair)', path, re.I):
                        block['omittedDecorativeLink'] = True
                    else:
                        unresolved_links.append({'uid': record['uid'], 'order': block['order'], 'url': block['href'], 'text': block.get('text', '')})
                        block['unresolvedLegacyLink'] = True
            if block['kind'] in {'text', 'heading', 'table', 'image', 'link', 'embed'}:
                current['blocks'].append(block)
        sections = [s for s in sections if s['title'] or s['blocks']]
        # Existing Hyundai/BMW pilots retain their reviewed specialist view.
        # Every remaining page uses this shared source-preserving representation.
        if not record.get('contentPilot') and not record.get('contentExpansion'):
            record['sourceSections'] = sections
            record['contentExpansion'] = 'source-v1'
            record['sourceHtmlSha256'] = document['sourceHtmlSha256']
            record['sourceCapture'] = {'run': RUN, **document['capture']}
            record['gallery'] = [{'src': b['src'], 'alt': b['alt'], 'originalSrc': b['originalSrc'],
                                  'sourceModuleId': b['sourceModuleId'], 'sourceOrder': b['order']}
                                 for s in sections for b in s['blocks'] if b['kind'] == 'image']
            groups = []
            for section in sections:
                brand = record.get('brand', '')
                if not brand or not section['title'].startswith(brand + ' '):
                    continue
                model = section['title'][len(brand):].strip()
                # A heading must explicitly name a vehicle already evidenced in
                # the vehicle catalogue. Equipment names never become car models.
                if not any(model.casefold() == name.casefold() or model.casefold().startswith(name.casefold() + ' ') or model.casefold().startswith(name.casefold() + '/') for name in known_models.get(brand, ())):
                    continue
                section['vehicleModel'] = model
                photos = [{'src': b['src'], 'alt': b['alt']} for b in section['blocks'] if b['kind'] == 'image']
                symptoms = [b['text'].lstrip('-–• ') for b in section['blocks'] if b['kind'] in {'text', 'heading'} and re.match(r'^[-–•]?\s*(?:fall[oa]|sin |no )', b.get('text', ''), re.I)]
                groups.append({'model': model, 'modelAliases': [model], 'vehicleModel': True,
                               'anchor': section['anchor'], 'blocks': [{'images': photos, 'symptoms': symptoms}]})
            if groups:
                record['modelGroups'] = groups
                record['coveredModels'] = [g['model'] for g in groups]
        if record.get('image', '').startswith('http'):
            local = local_media.get(unquote(urlsplit(record['image']).path))
            if local:
                record['image'] = local
            else:
                record.pop('image', None)
        counts = Counter(b['kind'] for s in sections for b in s['blocks'])
        rows.append({'uid': record['uid'], 'sourceHtmlSha256': document['sourceHtmlSha256'],
                     'sectionCount': len(sections), 'renderableBlocks': dict(counts),
                     'exclusions': exclusions, 'view': 'specialist-pilot' if record.get('contentPilot') or record.get('contentExpansion') != 'source-v1' else 'shared-source-sections'})
    report = {'schemaVersion': 1, 'captureRun': RUN, 'recordCount': len(rows), 'pages': rows,
              'unresolvedLegacyLinks': unresolved_links,
              'totals': {'sharedPages': sum(r['view'] == 'shared-source-sections' for r in rows),
                         'imageOccurrences': sum(r['renderableBlocks'].get('image', 0) for r in rows),
                         'tableOccurrences': sum(r['renderableBlocks'].get('table', 0) for r in rows)},
              'limitations': ['Published source content is not a fresh technical or commercial approval.',
                             'Unresolved historical links require a recorded decision before production.',
                             'References remain within their source section; image proximity never establishes fit.']}
    (root / 'data/source-sections-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report


def render_sections(record):
    import html
    e = lambda value: html.escape(str(value or ''), quote=True)
    sections = record.get('sourceSections', [])
    if not sections:
        return ''
    output = ['<section class="repair-source" data-repair-uid="' + e(record['uid']) + '" data-repair-brand="' + e(record.get('brand')) + '" aria-label="Información de la pieza y sus variantes">']
    vehicle_sections = [s for s in sections if s.get('vehicleModel')]
    index = vehicle_sections if vehicle_sections else [s for s in sections if s['title'] and s['blocks']]
    if len(index) >= 2:
        def index_link(s):
            return '<a href="#' + e(s['anchor']) + '"' + (' data-model-group="' + e(s['vehicleModel']) + '" data-model-anchor="' + e(s['anchor']) + '"' if s.get('vehicleModel') else '') + '>' + e(public_text(s['title'], record['uid'], 'section:' + s['anchor'])) + '</a>'
        groups = REVIEWED_INDEX_GROUPS.get(record['uid'])
        if groups:
            lookup = {s['anchor']: s for s in index}
            expected = [anchor for group in groups for anchor in group['anchors']]
            if set(expected) != set(lookup) or len(expected) != len(lookup):
                raise ValueError('Reviewed public index source changed: ' + record['uid'])
            links = ''.join('<section class="repair-index-group"><h3>' + e(group['label']) + '</h3><div>' + ''.join(index_link(lookup[anchor]) for anchor in group['anchors']) + '</div></section>' for group in groups)
        else:
            links = '<div>' + ''.join(index_link(s) for s in index) + '</div>'
        heading = 'Encuentra tu versión' if vehicle_sections else 'Información de esta pieza'
        guidance = '<p>Compara las imágenes y la denominación de tu versión. Si no sabes cuál es, puedes consultar con una foto. La imagen no confirma la compatibilidad de una pieza.</p>' if vehicle_sections else ''
        output.append('<nav class="repair-section-index" aria-label="Apartados de esta reparación"><p class="eyebrow">Compara tu pieza</p><h2>' + heading + '</h2>' + guidance + links + '</nav>')
    if vehicle_sections:
        output.append('<div id="repair-model-context" class="repair-model-context" role="status" hidden></div>')
    for section in sections:
        if not section['title'] and section['blocks'] and all(
                b['kind'] in {'heading', 'text'} and
                ' '.join(b.get('text', '').split()) == ' '.join(record.get('description', '').split())
                for b in section['blocks']):
            continue  # Intro already presents this paragraph; no empty spacer card.
        model_attrs = (' data-model-group="' + e(section['vehicleModel']) + '" data-model-anchor="' + e(section['anchor']) + '"') if section.get('vehicleModel') else ''
        output.append('<article class="repair-source-section' + (' repair-variant' if section.get('vehicleModel') else '') + '"' + model_attrs + ' id="' + e(section['anchor']) + '">')
        if section['title']:
            output.append('<h2>' + e(public_text(section['title'], record['uid'], 'section:' + section['anchor'])) + '</h2>')
        images = []
        photo_blocks = [b for b in section['blocks'] if b['kind'] == 'image']
        photo_orders = {b['order']: i for i, b in enumerate(photo_blocks, 1)}

        def flush_images():
            if images:
                output.append('<div class="repair-photo-grid">' + ''.join(images) + '</div>')
                images.clear()

        for block in section['blocks']:
            kind, text = block['kind'], block.get('text', '')
            marker = ' data-source-order="' + str(block['order']) + '"'
            if not section['title'] and kind in {'heading', 'text'} and ' '.join(text.split()) == ' '.join(record.get('description', '').split()):
                continue  # Already shown, unchanged, in the page introduction.
            if kind == 'image':
                caption = photo_caption(record, block, section['title'], photo_orders[block['order']], len(photo_blocks))
                images.append('<figure' + marker + '><a href="' + e(block['src']) + '" target="_blank" rel="noopener" aria-label="Ampliar: ' + e(caption) + '"><img src="' + e(block['src']) + '" alt="' + e(block['alt']) + '" width="640" height="480" loading="lazy" decoding="async"><span class="repair-photo-zoom" aria-hidden="true">Ampliar ↗</span></a><figcaption>' + e(caption) + '</figcaption></figure>')
                continue
            if kind == 'link' and not text and block.get('href', '').startswith('/assets/media/'):
                continue
            flush_images()
            if kind in {'heading', 'text'} and text:
                tag = 'h3' if kind == 'heading' and len(text) < 115 and not re.match(r'^[-–•]', text) else 'p'
                output.append('<' + tag + marker + '>' + e(public_text(text, record['uid'], 'block:' + str(block['order']))) + '</' + tag + '>')
            elif kind == 'table':
                rows = block['rows']
                if not any(cell['text'] for row in rows for cell in row):
                    continue
                rendered = []
                for row in rows:
                    cells = []
                    for cell in row:
                        tag = 'th' if cell.get('tag') == 'th' else 'td'
                        spans = ''.join(' ' + k + '="' + str(int(cell[k])) + '"' for k in ('colspan', 'rowspan') if str(cell.get(k, '1')).isdigit() and 1 < int(cell[k]) < 100)
                        cells.append('<' + tag + spans + '>' + e(cell['text']) + '</' + tag + '>')
                    rendered.append('<tr>' + ''.join(cells) + '</tr>')
                table = '<div class="repair-table-scroll" tabindex="0" role="region" aria-label="Datos de ' + e(section['title'] or record['title']) + '"><table' + marker + '><tbody>' + ''.join(rendered) + '</tbody></table></div>'
                output.append('<details class="repair-table-details"><summary>Ver referencias y datos de esta variante</summary>' + table + '</details>' if len(rows) > 8 else table)
            elif kind == 'link' and not block.get('unresolvedLegacyLink') and not block.get('omittedDecorativeLink'):
                url = block['href']
                if url.startswith(('/', 'https://', 'http://', 'mailto:', 'tel:')):
                    label = text or ('Ampliar imagen' if url.startswith('/assets/media/') else 'Ver información relacionada')
                    output.append('<a class="repair-related-link"' + marker + ' href="' + e(url) + '">' + e(label) + ' <span aria-hidden="true">↗</span></a>')
            elif kind == 'link' and block.get('unresolvedLegacyLink') and text:
                query = urlencode({'pieza': record['uid'], 'tipo': 'consulta', 'consulta': text})
                output.append('<a class="repair-related-link"' + marker + ' href="/solicitud.html?' + e(query) + '">Consultar: ' + e(text) + ' →</a>')
            elif kind == 'embed':
                # External videos stay explicit links; no third-party embed is loaded.
                url = block.get('src', '')
                if url.startswith(('https://', 'http://')):
                    output.append('<a class="repair-related-link"' + marker + ' href="' + e(url) + '" target="_blank" rel="noopener">Ver vídeo de este servicio ↗</a>')
        flush_images()
        if section.get('vehicleModel') and any(b['kind'] in {'image', 'table'} for b in section['blocks']):
            model = section['vehicleModel']
            query = urlencode({'pieza': record['uid'], 'marca': record['brand'], 'modelo': model, 'tipo': 'consulta'})
            output.append('<a class="button button-secondary repair-variant-consult" href="/solicitud.html?' + e(query) + '">Consultar mi ' + e(section['title']) + ' →</a>')
        output.append('</article>')
    output.append('<aside class="repair-unlisted"><h2>¿No reconoces tu pieza?</h2><p>Envíanos una foto de su etiqueta y cuéntanos qué falla. Te ayudamos a identificar el servicio.</p><a class="button button-primary" href="/solicitud.html?pieza=' + e(record['uid']) + '&amp;tipo=consulta">Consultar mi pieza →</a></aside></section>')
    return ''.join(output)
