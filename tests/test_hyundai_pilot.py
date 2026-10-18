"""Content-conservation regressions for the Hyundai pilot and public views."""
import hashlib
import json
import unittest
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit, parse_qs

ROOT = Path(__file__).resolve().parents[1]


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.images, self.links, self.ids, self.text = [], [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if tag == 'img':
            self.images.append(attrs)
        if tag == 'a':
            self.links.append(attrs)

    def handle_data(self, text):
        self.text.append(text)


class HyundaiPilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        cls.by_id = {row['uid']: row for row in cls.records}
        cls.general, cls.i30 = cls.by_id['main-3915'], cls.by_id['main-1604']
        cls.group = next(group for group in cls.general['modelGroups'] if group['model'] == 'i30')
        cls.manifest = json.loads((ROOT / 'data/hyundai-media-manifest.json').read_text())
        cls.pages = {uid: Page((ROOT / cls.by_id[uid]['localPath'].lstrip('/') / 'index.html').read_text()) for uid in ('main-3915', 'main-1604')}

    def test_only_two_records_use_the_pilot_and_keep_distinct_service_scopes(self):
        self.assertEqual({row['uid'] for row in self.records if row.get('contentPilot')}, {'main-1604', 'main-3915'})
        self.assertEqual(self.general['componentKey'], 'display')
        self.assertEqual(self.i30['componentKey'], 'cuadro')
        self.assertEqual(self.general['relatedServices'][0]['relation'], 'related-component-information')
        self.assertEqual(len(self.general['modelGroups']), 11)

    def test_repeated_i30_headings_preserve_two_distinct_source_image_pairs(self):
        blocks = self.group['blocks']
        self.assertEqual(len(blocks), 2)
        self.assertEqual([block['sourceModuleId'] for block in blocks], ['dslc-module-rp0jevjdak', 'dslc-module-r29np8c4ovo'])
        self.assertEqual([len(block['images']) for block in blocks], [2, 2])
        self.assertIn('hyundai-i30_1.jpg', blocks[0]['images'][0]['downloadUrl'])
        self.assertIn('display_hyundai_i30.jpg', blocks[0]['images'][1]['downloadUrl'])
        self.assertIn('hyundai-i30.jpg', blocks[1]['images'][0]['downloadUrl'])
        self.assertIn('display_hyundai_i30_2.jpg', blocks[1]['images'][1]['downloadUrl'])
        self.assertTrue(set(x['downloadUrl'] for x in blocks[0]['images']).isdisjoint(x['downloadUrl'] for x in blocks[1]['images']))

    def test_all_pilot_photographs_are_local_and_integrity_checked(self):
        self.assertFalse(self.manifest['failures'])
        self.assertEqual(len(self.manifest['files']), 23)
        for entry in self.manifest['files']:
            path = ROOT / entry['localPath'].lstrip('/')
            self.assertTrue(path.is_file(), entry['localPath'])
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
        for uid, count in [('main-3915', 23), ('main-1604', 2)]:
            self.assertEqual(len(self.pages[uid].images), count)
            self.assertTrue(all(image['src'].startswith('/assets/hyundai/') and image['alt'] for image in self.pages[uid].images))

    def test_i30_reference_aliases_are_preserved_without_counting_extra_parts(self):
        groups = self.i30['referenceGroups']
        self.assertEqual(len(groups), 59)
        self.assertEqual(sum(len(group['spellings']) for group in groups), 118)
        self.assertEqual([value for group in groups for value in group['spellings'] if value == '94003-2L410'], ['94003-2L410'])
        match = next(group for group in groups if group['display'] == '94003-2L410')
        self.assertIn('940032L410', match['spellings'])
        self.assertEqual(set(self.i30['references']), {value for group in groups for value in group['spellings']})
        page = ' '.join(self.pages['main-1604'].text)
        self.assertIn('Referencias del cuadro (59)', page)
        self.assertTrue(all(value in page for value in self.i30['references']))

    def test_i30_faults_and_relationship_are_available_in_the_public_html(self):
        specific = ' '.join(self.pages['main-1604'].text)
        self.assertEqual(len(self.i30['symptoms']), 3)
        self.assertTrue(all(value in specific for value in self.i30['symptoms']))
        self.assertTrue(any(link.get('href') == self.i30['localPath'] for link in self.pages['main-3915'].links))
        self.assertTrue(any(link.get('href') == self.general['localPath'] + '#modelo-i30' for link in self.pages['main-1604'].links))
        self.assertIn('modelo-i30', self.pages['main-3915'].ids)
        self.assertIn('no identifican por sí solas el display de recambio', ' '.join(self.pages['main-3915'].text))

    def test_model_requests_keep_the_display_family_and_vehicle_context(self):
        requests = [parse_qs(urlsplit(link.get('href', '')).query) for link in self.pages['main-3915'].links if link.get('href', '').startswith('/solicitud.html?')]
        for group in self.general['modelGroups']:
            self.assertTrue(any(query.get('pieza') == ['main-3915'] and query.get('marca') == ['Hyundai'] and query.get('modelo') == [group['model']] for query in requests))

    def test_pilot_pages_keep_unique_ids_and_every_media_url_comes_from_the_source(self):
        raw = {page['id']: page for file in (ROOT / 'data/cache').glob('*.json') for page in json.loads(file.read_text())}
        for uid in ('main-3915', 'main-1604'):
            record = self.by_id[uid]
            self.assertEqual(len(self.pages[uid].ids), len(set(self.pages[uid].ids)))
            source = raw[record['sourceId']]['content']['rendered']
            self.assertEqual(hashlib.sha256(source.encode()).hexdigest(), record['sourceHtmlSha256'])
            self.assertTrue(all(image['originalSrc'] in source and image['downloadUrl'] in source for image in record['gallery']))
            self.assertNotIn('generation', record)

    def test_future_answer_data_separates_source_facts_from_unconfirmed_commercial_claims(self):
        knowledge = json.loads((ROOT / 'data/hyundai-pilot-knowledge.json').read_text())
        self.assertFalse(any(knowledge['constraints'].values()))
        self.assertEqual({row['uid'] for row in knowledge['records']}, {'main-1604', 'main-3915'})
        self.assertEqual({row['componentKey'] for row in knowledge['records']}, {'cuadro', 'display'})
        self.assertNotIn('"sourceAlt"', json.dumps(knowledge))
        getz = next(group for group in self.general['modelGroups'] if group['model'] == 'Getz')
        image = getz['blocks'][0]['images'][0]
        self.assertIn('i30', image['sourceAlt'])
        self.assertIn('Getz', image['alt'])
        self.assertNotIn('i30', image['alt'])
        for row in knowledge['records']:
            self.assertNotIn('sourceText', row)
            self.assertIsNone(row['price'])
            self.assertIsNone(row['timing'])
            self.assertIsNone(row['warranty'])


if __name__ == '__main__':
    unittest.main()
