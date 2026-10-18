"""Source-conservation checks for the BMW page rather than inferred fit tests."""
import hashlib
import json
import sys
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from bmw_source import extract_bmw


class Page(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.images, self.links, self.ids, self.text, self.modules = [], [], [], [], []
        self.feed(source)

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if attrs.get('id'):
            self.ids.append(attrs['id'])
        if attrs.get('data-source-module'):
            self.modules.append(attrs['data-source-module'])
        if tag == 'img':
            self.images.append(attrs)
        if tag == 'a':
            self.links.append(attrs)

    def handle_data(self, text):
        self.text.append(text)


class BMWContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        cls.record = next(row for row in cls.catalogue if row['uid'] == 'main-2321')
        cls.source = extract_bmw(ROOT)
        cls.document = json.loads((ROOT / 'data/wordpress_exports/2026-10-13-publico/prepared/documents/main/pages-2321.json').read_text())
        cls.manifest = json.loads((ROOT / 'data/bmw-media-manifest.json').read_text())
        cls.page_html = (ROOT / cls.record['localPath'].lstrip('/') / 'index.html').read_text()
        cls.page = Page(cls.page_html)

    def test_expansion_affects_only_the_selected_bmw_record(self):
        self.assertEqual({row['uid'] for row in self.catalogue if row.get('contentExpansion') == 'bmw-v1'}, {'main-2321'})
        self.assertEqual(self.record['componentKey'], 'display')
        self.assertEqual(self.record['sourceCapture']['run'], '2026-10-13-publico')
        self.assertEqual(self.record['sourceHtmlSha256'], self.document['sourceHtmlSha256'])

    def test_every_source_module_image_occurrence_and_model_service_paragraph_is_preserved(self):
        source_images = [block for block in self.document['blocks'] if block['kind'] == 'image']
        self.assertEqual(len(source_images), 42)
        self.assertEqual(Counter(block['src'] for block in source_images), Counter(image['originalSrc'] for image in self.record['gallery']))
        groups = self.record['modelGroups']
        blocks = [block for group in groups for block in group['blocks']]
        self.assertEqual(len(groups), 21)
        self.assertEqual(len(blocks), 22)
        self.assertEqual(len(self.record['contentBlocks']), 25)
        self.assertEqual(Counter(self.page.modules), Counter(block['sourceModuleId'] for block in blocks))
        text = ' '.join(self.page.text)
        for block in blocks:
            self.assertTrue(all(paragraph in text for paragraph in block['paragraphs']))

    def test_two_x5_x6_screens_do_not_lose_their_separate_context(self):
        group = next(group for group in self.record['modelGroups'] if group['model'] == 'X5 E70 y X6 E71')
        self.assertEqual([block['serviceLabel'] for block in group['blocks']], ['Pantalla del cuadro', 'Pantalla central'])
        self.assertEqual([len(block['images']) for block in group['blocks']], [2, 2])
        self.assertEqual([block['sourceModuleId'] for block in group['blocks']], ['dslc-module-9upl5at8cso', 'dslc-module-g76f0m2prlo'])
        self.assertNotEqual(group['blocks'][0]['images'], group['blocks'][1]['images'])

    def test_vehicle_selector_context_excludes_non_vehicle_service_names(self):
        self.assertEqual(len(self.record['coveredModels']), 19)
        self.assertNotIn('BMW Live Cockpit', self.record['coveredModels'])
        self.assertNotIn('BMW pantalla reposacabezas', self.record['coveredModels'])
        self.assertEqual({group['model'] for group in self.record['modelGroups'] if not group['vehicleModel']}, {'BMW Live Cockpit', 'BMW pantalla reposacabezas'})
        group = next(group for group in self.record['modelGroups'] if group['model'] == 'Serie 1 E81/E87 y X1 E84')
        self.assertEqual(group['modelAliases'], ['Serie 1 E81/E87', 'X1 E84'])
        self.assertNotIn('Serie 1 E88', group['modelAliases'])

    def test_local_images_are_complete_and_match_the_download_manifest(self):
        self.assertFalse(self.manifest['failures'])
        self.assertEqual(len(self.manifest['files']), 32)
        for entry in self.manifest['files']:
            path = ROOT / entry['localPath'].lstrip('/')
            self.assertTrue(path.is_file())
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
        self.assertEqual(len(self.page.images), 42)
        self.assertTrue(all(image['src'].startswith('/assets/bmw/') and image['alt'] for image in self.page.images))

    def test_photo_links_have_distinct_source_based_accessible_names(self):
        groups = [group for group in self.record['modelGroups'] if group['vehicleModel']]
        groups += [group for group in self.record['modelGroups'] if not group['vehicleModel']]
        expected = []
        for group in groups:
            for block in group['blocks']:
                images = block['images']
                for ordinal, image in enumerate(images, 1):
                    label = f"{image['alt']} · {block['serviceLabel']}"
                    if len(images) > 1:
                        label += f' · foto {ordinal} de {len(images)}'
                    expected.append((image['src'], label))

        photos = [image for image in self.page.images if image['src'].startswith('/assets/bmw/')]
        photo_links = [link for link in self.page.links if link.get('href', '').startswith('/assets/bmw/')]
        self.assertEqual([(image['src'], image['alt']) for image in photos], expected)
        self.assertEqual([(link['href'], link['aria-label']) for link in photo_links],
                         [(source, f'Ampliar: {label}') for source, label in expected])
        self.assertEqual(len({link['aria-label'] for link in photo_links}), len(photo_links))

    def test_model_anchors_and_requests_retain_the_selected_context(self):
        self.assertEqual(len(self.page.ids), len(set(self.page.ids)))
        requests = [parse_qs(urlsplit(link.get('href', '')).query) for link in self.page.links if link.get('href', '').startswith('/solicitud.html?')]
        for group in self.record['modelGroups']:
            self.assertIn(group['anchor'], self.page.ids)
            if group['vehicleModel']:
                for alias in group.get('modelAliases') or [group['model']]:
                    self.assertTrue(any(query.get('pieza') == ['main-2321'] and query.get('marca') == ['BMW'] and query.get('modelo') == [alias] for query in requests), alias)
                if len(group.get('modelAliases', [])) > 1:
                    self.assertFalse(any(query.get('modelo') == [group['model']] for query in requests), 'A person selects one vehicle, not the combined source heading')
        self.assertTrue(any(query.get('pieza') == ['main-2321'] and query.get('marca') == ['BMW'] and not query.get('modelo') for query in requests))

    def test_model_index_is_at_the_start_and_links_only_to_vehicle_sections(self):
        self.assertLess(self.page_html.index('id="bmw-index-title"'), self.page_html.index('id="bmw-fallos"'))
        self.assertLess(self.page_html.index('class="bmw-model-index"'), self.page_html.index('class="bmw-fault-overview"'))
        self.assertIn('Ver lista de modelos', self.page_html)
        nav_start = self.page_html.index('<nav class="bmw-model-jumps"')
        nav_body = self.page_html[self.page_html.index('>', nav_start) + 1:self.page_html.index('</nav>', nav_start)]
        index_links = Page(nav_body).links
        vehicle_groups = [group for group in self.record['modelGroups'] if group['vehicleModel']]
        self.assertEqual([link['href'] for link in index_links], ['#' + group['anchor'] for group in vehicle_groups])
        self.assertEqual(len(index_links), 19)
        self.assertEqual(set(link['href'][1:] for link in index_links) & {group['anchor'] for group in self.record['modelGroups'] if not group['vehicleModel']}, set())

    def test_references_prices_and_compatibility_are_not_invented(self):
        self.assertEqual(self.record['references'], [])
        self.assertEqual(self.record['dtcCodes'], [])
        self.assertFalse(self.record['timing'])
        self.assertFalse(self.record['warranty'])
        self.assertNotIn('price', self.record)
        report = json.loads((ROOT / 'data/bmw-content-report.json').read_text())
        self.assertFalse(any(report['constraints'].values()))
        self.assertTrue(all(image['wordpressMediaId'] for image in self.record['gallery']))


if __name__ == '__main__':
    unittest.main()
