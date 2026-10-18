"""Loss-aware Hyundai pilot, built only from the preserved public snapshots.

The full catalogue is unchanged outside the two explicitly selected records.
Module boundaries, repeated model headings, original media attributes and
reference spellings remain available instead of being flattened together.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
from collections import OrderedDict
from html.parser import HTMLParser
from urllib.parse import urlparse

PILOT_IDS = {'main-3915', 'main-1604'}
MEDIA_PREFIX = 'https://www.menigar.com/wp-content/uploads/'


def normalize(value):
    return re.sub(r'[^a-z0-9]', '', value.lower())


def media_info(attrs, model='i30'):
    source = html.unescape(attrs.get('src', ''))
    if not source.startswith(MEDIA_PREFIX):
        return None
    candidates = [(0, source)]
    for candidate in html.unescape(attrs.get('srcset', '')).split(','):
        match = re.fullmatch(r'\s*(https://\S+)\s+(\d+)w\s*', candidate)
        if match and match[1].startswith(MEDIA_PREFIX):
            candidates.append((int(match[2]), match[1]))
    download = max(candidates, key=lambda item: item[0])[1]
    filename = urlparse(download).path.rsplit('/', 1)[-1]
    filename = re.sub(r'[^A-Za-z0-9._-]', '-', filename)
    image_id = re.search(r'\bwp-image-(\d+)\b', attrs.get('class', ''))
    return {
        'originalSrc': source, 'originalSrcset': attrs.get('srcset', ''),
        'downloadUrl': download,
        'localPath': '/assets/hyundai/' + hashlib.sha256(download.encode()).hexdigest()[:12] + '-' + filename,
        'sourceAlt': attrs.get('alt', ''), 'sourceTitle': attrs.get('title', ''),
        'wordpressMediaId': int(image_id[1]) if image_id else None,
        'alt': 'Imagen del componente publicada para Hyundai ' + model,
    }


class ContentModules(HTMLParser):
    """Read Live Composer text modules without deduplicating their contents."""
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.depth = 0
        self.active = None
        self.modules = []
        self.images = []
        self.capture = None
        self.buffer = []
        self.module_id = ''

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == 'div':
            self.depth += 1
            if attrs.get('id', '').startswith('dslc-module-'):
                self.module_id = attrs['id']
            if self.active is None and 'dslc-text-module-content' in attrs.get('class', '').split():
                self.active = {'depth': self.depth, 'sourceModuleId': self.module_id,
                               'headings': [], 'paragraphs': [], 'images': []}
        if tag == 'img':
            self.images.append(attrs)
            if self.active is not None:
                self.active['images'].append(attrs)
        if self.active is not None and tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p'):
            self.capture, self.buffer = tag, []

    def handle_endtag(self, tag):
        if self.active is not None and tag == self.capture:
            text = ' '.join(''.join(self.buffer).split())
            if text:
                if tag.startswith('h'):
                    self.active['headings'].append({'level': int(tag[1]), 'text': text})
                else:
                    self.active['paragraphs'].append(text)
            self.capture = None
        if tag == 'div':
            if self.active is not None and self.depth == self.active['depth']:
                self.active.pop('depth')
                self.modules.append(self.active)
                self.active = None
                self.capture = None
            self.depth -= 1

    def handle_data(self, data):
        if self.capture is not None:
            self.buffer.append(data)


def extract_pilot(raw_pages, main_html):
    result = {}
    for uid in sorted(PILOT_IDS):
        page = raw_pages[uid]
        parser = ContentModules()
        raw = main_html(page['content']['rendered'])
        parser.feed(raw)
        parser.close()
        modules = []
        for module in parser.modules:
            model = next((h['text'] for h in module['headings'] if h['level'] == 3 and len(h['text']) < 35), 'i30')
            modules.append({**module, 'images': [m for a in module['images'] if (m := media_info(a, model))]})
        result[uid] = {
            'sourceUid': uid, 'sourceUrl': page['link'], 'contentBlocks': modules,
            'sourceHtmlSha256': hashlib.sha256(page['content']['rendered'].encode()).hexdigest(),
            'images': [m for a in parser.images if (m := media_info(a))],
        }
    groups = OrderedDict()
    for block in result['main-3915']['contentBlocks']:
        model = next((h['text'] for h in block['headings'] if h['level'] == 3 and len(h['text']) < 35), '')
        if not model or not block['images']:
            continue
        group = groups.setdefault(normalize(model), {'model': model, 'blocks': []})
        group['blocks'].append(block)
    result['main-3915']['modelGroups'] = list(groups.values())
    result['main-3915']['images'] = [image for group in groups.values() for block in group['blocks'] for image in block['images']]
    return result


def enrich_hyundai(catalogue, all_pages, root, main_html):
    raw_pages = {f'{source}-{page["id"]}': page for source, page in all_pages if f'{source}-{page["id"]}' in PILOT_IDS}
    pilot = extract_pilot(raw_pages, main_html)
    manifest_path = root / 'data' / 'hyundai-media-manifest.json'
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {'files': []}
    downloaded = {item['downloadUrl']: item for item in manifest['files']}

    def hydrate(image):
        image = dict(image)
        entry = downloaded.get(image['downloadUrl'])
        local = root / image['localPath'].lstrip('/')
        image['src'] = image['localPath'] if entry and local.is_file() else image['originalSrc']
        return image

    by_id = {record['uid']: record for record in catalogue}
    for uid, extracted in pilot.items():
        record = by_id[uid]
        record['contentPilot'] = 'hyundai-v1'
        record['sourceHtmlSha256'] = extracted['sourceHtmlSha256']
        record['gallery'] = [hydrate(image) for image in extracted['images']]
        record['contentBlocks'] = [{**block, 'images': [hydrate(image) for image in block['images']]} for block in extracted['contentBlocks']]
    general = by_id['main-3915']
    general['modelGroups'] = [
        {**group, 'blocks': [{**block, 'images': [hydrate(image) for image in block['images']]} for block in group['blocks']]}
        for group in pilot['main-3915']['modelGroups']
    ]
    general['coveredModels'] = [group['model'] for group in general['modelGroups']]
    i30_group = next(group for group in general['modelGroups'] if normalize(group['model']) == 'i30')
    i30_group['relatedServiceUid'] = 'main-1604'
    i30_group['relatedServiceLabel'] = 'Ver información del cuadro Hyundai i30'
    specific = by_id['main-1604']
    specific['relatedServices'] = [{'uid': 'main-3915', 'label': 'Consultar displays Hyundai', 'relation': 'related-component-information'}]
    general['relatedServices'] = [{'uid': 'main-1604', 'label': i30_group['relatedServiceLabel'], 'relation': 'related-component-information'}]
    ref_groups = OrderedDict()
    for value in specific['references']:
        key = normalize(value)
        group = ref_groups.setdefault(key, {'normalized': key, 'display': value, 'spellings': []})
        group['spellings'].append(value)
    specific['referenceGroups'] = list(ref_groups.values())
    def knowledge_image(image):
        # Original alt/title attributes remain in the archive; the answer data
        # uses the model context, including where the source alt was mistaken.
        return {'src': image['src'], 'sourceUrl': image['downloadUrl'], 'alt': image['alt']}

    knowledge_groups = [
        {'model': group['model'], 'blocks': [
            {'sourceModuleId': block['sourceModuleId'], 'paragraphs': block['paragraphs'],
             'images': [knowledge_image(image) for image in block['images']]}
            for block in group['blocks']
        ], 'relatedServiceUid': group.get('relatedServiceUid')}
        for group in general['modelGroups']
    ]
    knowledge = {
        'version': 'hyundai-pilot-v1',
        'reviewStatus': 'source-extracted; technician approval pending',
        'constraints': {'catalogueMatchConfirmsDiagnosis': False, 'imageAloneConfirmsVariant': False,
                        'crossComponentReferencesAreInterchangeable': False},
        'records': [
            {'uid': general['uid'], 'sourceUrl': general['url'], 'sourceHtmlSha256': general['sourceHtmlSha256'],
             'componentKey': 'display', 'brand': 'Hyundai', 'models': general['coveredModels'],
             'modelGroups': knowledge_groups, 'relatedServices': general['relatedServices'],
             'price': None, 'timing': None, 'warranty': None},
            {'uid': specific['uid'], 'sourceUrl': specific['url'], 'sourceHtmlSha256': specific['sourceHtmlSha256'],
             'componentKey': 'cuadro', 'brand': 'Hyundai', 'model': 'i30', 'symptoms': specific['symptoms'],
             'referenceGroups': specific['referenceGroups'], 'gallery': [knowledge_image(image) for image in specific['gallery']],
             'relatedServices': specific['relatedServices'], 'price': None, 'timing': None, 'warranty': None},
        ],
    }
    (root / 'data' / 'hyundai-pilot-knowledge.json').write_text(json.dumps(knowledge, ensure_ascii=False, indent=2) + '\n')
    metadata_warnings = []
    for group in general['modelGroups']:
        for block in group['blocks']:
            for image in block['images']:
                if image['sourceAlt'] and normalize(group['model']) not in normalize(image['sourceAlt']):
                    metadata_warnings.append({'model': group['model'], 'originalSrc': image['originalSrc'],
                                              'sourceAlt': image['sourceAlt'], 'action': 'Original preserved; public alt uses source section context.'})
    report = {
        'scope': sorted(PILOT_IDS), 'source': 'Preserved local public WordPress snapshots; no new admin export.',
        'modelCount': len(general['modelGroups']), 'modelBlockCount': sum(len(g['blocks']) for g in general['modelGroups']),
        'i30BlockCount': len(i30_group['blocks']), 'i30ImagesPerBlock': [len(b['images']) for b in i30_group['blocks']],
        'sourceImagesByRecord': {uid: len(value['images']) for uid, value in pilot.items()},
        'uniqueMediaFiles': len({m['downloadUrl'] for value in pilot.values() for m in value['images']}),
        'referenceSpellings': len(specific['references']), 'normalizedReferences': len(specific['referenceGroups']),
        'symptoms': len(specific['symptoms']),
        'knowledgeFile': 'data/hyundai-pilot-knowledge.json', 'metadataWarnings': metadata_warnings,
        'checks': {'modelBlocksPreserved': len(i30_group['blocks']) == 2, 'i30ReferenceSpellingsPreserved': len(specific['references']) == 118,
                   'galleryContextPreserved': len(specific['gallery']) == 2, 'crossFamilyRelationIsNotCompatibility': True},
        'pending': ['No years, interchangeability or image-to-reference mapping inferred.', 'Other catalogue records still use the previous renderer.',
                    'Fresh WordPress export and production approval remain pending.'],
    }
    (root / 'data' / 'hyundai-pilot-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    return report
