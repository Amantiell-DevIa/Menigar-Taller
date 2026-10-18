"""Conserve the public BMW display page, using the dated WordPress archive.

This is a deliberately scoped expansion: one catalogue record. A module is
source context, not evidence that its images or vehicles are interchangeable.
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import OrderedDict
from pathlib import Path
from urllib.parse import urlparse

UID = 'main-2321'
RUN = '2026-10-13-publico'
MEDIA_PREFIX = 'https://www.menigar.com/wp-content/uploads/'
NON_VEHICLE_HEADINGS = {'BMW Live Cockpit', 'BMW pantalla reposacabezas'}


def slug(value):
    return re.sub(r'[^a-z0-9]+', '-', value.lower()).strip('-')


def load_source(root):
    archive = root / 'data' / 'wordpress_exports' / RUN
    path = archive / 'prepared' / 'documents' / 'main' / 'pages-2321.json'
    document = json.loads(path.read_text())
    raw_path = archive / document['capture']['responsePath']
    if hashlib.sha256(raw_path.read_bytes()).hexdigest() != document['capture']['responseSha256']:
        raise ValueError('BMW public response fingerprint does not match the archive')
    raw = next(page for page in json.loads(raw_path.read_text()) if page['id'] == 2321)
    if hashlib.sha256(raw['content']['rendered'].encode()).hexdigest() != document['sourceHtmlSha256']:
        raise ValueError('BMW content fingerprint does not match the prepared document')
    media = json.loads((archive / 'prepared' / 'media-main.json').read_text())
    return document, {item['id']: item for item in media}


def image_from_block(block, model, media):
    original = block['src']
    if not original.startswith(MEDIA_PREFIX):
        raise ValueError('Unexpected BMW image host or uploads path')
    candidates = [(0, original)]
    matched_id = None
    for media_id in block.get('matchedMediaIdsByUrl', []):
        item = media.get(media_id, {})
        sizes = item.get('media_details', {}).get('sizes', {})
        urls = [item.get('source_url')] + [size.get('source_url') for size in sizes.values()]
        # IDs alone are insufficient: the observed original URL must also match.
        if original not in urls:
            continue
        matched_id = media_id
        for size in sizes.values():
            url = size.get('source_url', '')
            if url.startswith(MEDIA_PREFIX):
                candidates.append((size.get('width', 0), url))
        url = item.get('source_url', '')
        if url.startswith(MEDIA_PREFIX):
            candidates.append((item.get('media_details', {}).get('width', 0), url))
    download = max(candidates, key=lambda pair: pair[0])[1]
    filename = re.sub(r'[^A-Za-z0-9._-]', '-', urlparse(download).path.rsplit('/', 1)[-1])
    attrs = block.get('attributes', {})
    return {
        'originalSrc': original, 'originalSrcset': attrs.get('srcset', ''),
        'downloadUrl': download,
        'localPath': '/assets/bmw/' + hashlib.sha256(download.encode()).hexdigest()[:12] + '-' + filename,
        'sourceAlt': attrs.get('alt', ''), 'sourceTitle': attrs.get('title', ''),
        'wordpressMediaId': matched_id,
        'mediaAssociation': 'matching-captured-media-id-and-observed-url' if matched_id else 'original-image-url-only',
        'sourceModuleId': block['sourceModuleId'], 'sourceOrder': block['order'],
        'alt': 'Imagen publicada por Menigar en ' + model,
    }


def extract_bmw(root):
    document, media = load_source(root)
    modules = OrderedDict()
    for block in document['blocks']:
        modules.setdefault(block['sourceModuleId'], []).append(block)
    blocks, groups = [], OrderedDict()
    for module_id, items in modules.items():
        headings = [{'level': int(item['tag'][1]), 'text': item['text']}
                    for item in items if item['kind'] == 'heading']
        model = next((heading['text'] for heading in headings
                      if heading['level'] == 3 and len(heading['text']) < 80), '')
        paragraphs = [item['text'] for item in items if item['kind'] == 'text']
        images = [image_from_block(item, model, media) for item in items if item['kind'] == 'image']
        links = [{'url': item['href'], 'text': item['text'], 'sourceOrder': item['order']}
                 for item in items if item['kind'] == 'link']
        block = {'sourceModuleId': module_id, 'headings': headings,
                 'paragraphs': paragraphs, 'images': images, 'links': links}
        if model and images:
            # Both X5/X6 modules keep their own descriptions and photos.
            description = ' '.join(paragraphs).lower()
            block['serviceLabel'] = ('Pantalla central' if 'pantalla central' in description else
                                     'Arañazos en pantalla' if 'arañazos' in description else
                                     'Cuadro digital' if 'cuadro de instrumentos digital' in description else
                                     'Pantalla del cuadro')
            group = groups.setdefault(model, {
                'model': model, 'modelAliases': model.split(' y '),
                'vehicleModel': model not in NON_VEHICLE_HEADINGS,
                'anchor': 'modelo-' + slug(model), 'blocks': [],
            })
            group['blocks'].append(block)
        blocks.append(block)
    return {'sourceUid': UID, 'sourceUrl': document['url'], 'sourceHtmlSha256': document['sourceHtmlSha256'],
            'sourceModified': document['modified'], 'capture': document['capture'],
            'contentBlocks': blocks, 'modelGroups': list(groups.values()),
            'gallery': [image for group in groups.values() for block in group['blocks'] for image in block['images']]}


def enrich_bmw(catalogue, root):
    extracted = extract_bmw(root)
    record = next(item for item in catalogue if item['uid'] == UID)
    manifest_path = root / 'data' / 'bmw-media-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': []}
    downloads = {item['downloadUrl']: item for item in manifest['files']}

    def hydrate(image):
        image = dict(image)
        local = root / image['localPath'].lstrip('/')
        image['src'] = image['localPath'] if image['downloadUrl'] in downloads and local.is_file() else image['originalSrc']
        return image

    for block in extracted['contentBlocks']:
        block['images'] = [hydrate(image) for image in block['images']]
    # Groups share the original block objects, avoiding a flattened copy.
    extracted['gallery'] = [image for group in extracted['modelGroups'] for block in group['blocks'] for image in block['images']]
    record.update({key: extracted[key] for key in ('sourceHtmlSha256', 'sourceModified', 'contentBlocks', 'modelGroups', 'gallery')})
    record['contentExpansion'] = 'bmw-v1'
    record['sourceCapture'] = {'run': RUN, **extracted['capture']}
    record['coveredModels'] = [group['model'] for group in record['modelGroups'] if group['vehicleModel']]
    record['title'] = 'Reparación de pantallas y displays BMW'
    record['description'] = '¿La pantalla de tu BMW pierde píxeles, no se ilumina o deja de funcionar? Busca tu modelo y compara las imágenes para encontrar tu pieza.'
    record['symptoms'] = ['Fallos en algún píxel o píxeles del display o pantalla', 'Fallos de iluminación', 'Fallos en el cuentakilómetros', 'Fallo total del display']
    record['symptomContext'] = 'General faults listed in the source introduction; not attributed to every model or screen.'
    record['image'] = record['gallery'][0]['src']
    lookup = {item['url'].rstrip('/'): item for item in catalogue}
    for block in record['contentBlocks']:
        for link in block['links']:
            target = lookup.get(link['url'].rstrip('/'))
            if target:
                link['localPath'], link['relatedServiceUid'] = target['localPath'], target['uid']
    report = {
        'scope': [UID], 'captureRun': RUN, 'sourceHtmlSha256': extracted['sourceHtmlSha256'],
        'sourceModuleCount': len(record['contentBlocks']),
        'serviceBlockCount': sum(len(group['blocks']) for group in record['modelGroups']),
        'groupCount': len(record['modelGroups']), 'vehicleGroupCount': len(record['coveredModels']),
        'imageOccurrences': len(record['gallery']), 'uniqueImageFiles': len({image['downloadUrl'] for image in record['gallery']}),
        'references': len(record['references']), 'dtcCodes': len(record['dtcCodes']),
        'constraints': {'imageToReferenceInferred': False, 'fitConfirmedByImage': False, 'priceInferred': False, 'timingInferred': False},
        'notes': ['Two X5 E70/X6 E71 modules remain separate: cluster screen and central screen.',
                  'Live Cockpit and headrest displays are service groups, not vehicle models.',
                  'Original X5 G05/X6 F16 wording is conserved; it is not a new compatibility validation.'],
    }
    (root / 'data' / 'bmw-content-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report
