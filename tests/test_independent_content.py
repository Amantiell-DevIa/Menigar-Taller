"""Migration regressions: real source relationships and actual generated pages."""
from collections import Counter
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import parse_qs, urlsplit, unquote

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from source_sections import scoped_blocks


class MainAssets(HTMLParser):
    def __init__(self):
        super().__init__()
        self.main = False
        self.images, self.links = [], []
    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.main = True
        attrs = dict(attrs)
        if self.main and tag == 'img':
            self.images.append(attrs.get('src', ''))
        if self.main and tag == 'a':
            self.links.append(attrs.get('href', ''))
    def handle_endtag(self, tag):
        if tag == 'main':
            self.main = False


class IndependentContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        cls.by_uid = {row['uid']: row for row in cls.rows}
        cls.media = json.loads((ROOT / 'data/media-local-manifest.json').read_text())
        cls.prepared = ROOT / 'data/wordpress_exports/2026-10-13-publico/prepared/documents'

    def test_all_1642_pages_have_source_sections_or_their_reviewed_pilot(self):
        # 1,648 captured pages minus six copies merged into their most complete ficha (26 Oct 2026).
        self.assertEqual(len(self.rows), 1642)
        shared = [r for r in self.rows if r.get('contentExpansion') == 'source-v1']
        self.assertEqual(len(shared), 1639)
        for row in self.rows:
            with self.subTest(uid=row['uid']):
                self.assertTrue(row.get('sourceSections') or row.get('contentPilot') or row.get('contentExpansion') == 'bmw-v1')
                self.assertTrue((ROOT / row['localPath'].lstrip('/') / 'index.html').exists())

    def test_every_selected_media_file_exists_and_matches_its_manifest(self):
        self.assertEqual(self.media['totals']['files'], len(self.media['files']))
        self.assertGreater(len(self.media['files']), 3800)
        for entry in self.media['files']:
            path = ROOT / entry['localPath'].lstrip('/')
            with self.subTest(path=entry['localPath']):
                self.assertEqual(path.stat().st_size, entry['bytes'])
                self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), entry['sha256'])
        self.assertFalse(self.media['networkUsed'])
        self.assertEqual({r['originalSrc'] for r in self.media['missing']},
                         {'https://www.menigar.com/servicios/122', 'https://www.menigar.com/servicios/132'})

    def test_no_generated_repair_image_fetches_wordpress(self):
        count = 0
        for row in self.rows:
            parser = MainAssets()
            parser.feed((ROOT / row['localPath'].lstrip('/') / 'index.html').read_text())
            for image in parser.images:
                with self.subTest(uid=row['uid'], image=image):
                    self.assertTrue(image.startswith('/assets/'))
                    self.assertTrue((ROOT / image.lstrip('/')).is_file())
                count += 1
        self.assertGreater(count, 8000)

    def test_mazda_keeps_four_models_and_each_correct_pair_of_photos(self):
        row = self.by_uid['main-2942']
        source = json.loads((self.prepared / 'main/pages-2942.json').read_text())
        expected_models = ['Mazda 3 BK', 'Mazda 3 BM', 'Mazda 5', 'Mazda 6']
        sections = {s['title']: s for s in row['sourceSections']}
        html = (ROOT / row['localPath'].lstrip('/') / 'index.html').read_text()
        for label in expected_models:
            section = sections[label]
            source_images = [b['src'] for b in source['blocks'] if b['kind'] == 'image' and b['precedingHeadings'][-1]['text'] == label]
            expected_images = [self.media['urlIndex'][unquote(urlsplit(url).path)] for url in source_images]
            actual = [b['src'] for b in section['blocks'] if b['kind'] == 'image']
            self.assertEqual(actual, expected_images)
            self.assertEqual(len(actual), 2)
            article = re.search(r'<article[^>]+id="' + section['anchor'] + r'">(.*?)</article>', html, re.S)[1]
            parser = MainAssets(); parser.main = True; parser.feed(article)
            self.assertEqual(parser.images, actual)
            query = next(parse_qs(urlsplit(link).query) for link in parser.links if link.startswith('/solicitud.html'))
            self.assertEqual(query['modelo'], [label.removeprefix('Mazda ')])
            self.assertEqual(query['pieza'], ['main-2942'])

    def test_bmw_serie_5_keeps_six_generations_with_their_own_tables_and_faults(self):
        row = self.by_uid['main-514']
        sections = [s for s in row['sourceSections'] if s.get('vehicleModel')]
        self.assertEqual([s['title'] for s in sections], ['BMW Serie 5 E28', 'BMW Serie 5 E34', 'BMW Serie 5 E39', 'BMW Serie 5 E60/E61', 'BMW Serie 5 F10', 'BMW Serie 5 G30'])
        source = json.loads((self.prepared / 'main/pages-514.json').read_text())
        for section in sections:
            actual = [b for b in section['blocks'] if b['kind'] == 'table']
            expected = [b for b in source['blocks'] if b['kind'] == 'table' and b['precedingHeadings'][-1]['text'] == section['title']]
            self.assertEqual([b['rows'] for b in actual], [b['rows'] for b in expected])
            self.assertTrue(any(b['kind'] == 'heading' and b.get('text', '').startswith('Problemas comunes') for b in section['blocks']))

    def test_composition_media_keeps_nine_reference_tables_in_their_equipment_groups(self):
        row = self.by_uid['main-13614']
        source = json.loads((self.prepared / 'main/pages-13614.json').read_text())
        expected = {b['order']: b['rows'] for b in source['blocks'] if b['kind'] == 'table'}
        actual = {b['order']: b['rows'] for s in row['sourceSections'] for b in s['blocks'] if b['kind'] == 'table'}
        self.assertEqual(len(actual), 9)
        self.assertEqual(actual, expected)
        groups = [s for s in row['sourceSections'] if any(b['kind'] == 'table' for b in s['blocks'])]
        self.assertEqual(len(groups), 9)
        # Repeated codes stay in every source group rather than a global set.
        source_counts = Counter(c['text'] for rows in expected.values() for cells in rows for c in cells if len(re.findall(r'\d', c['text'])) >= 5)
        actual_counts = Counter(c['text'] for rows in actual.values() for cells in rows for c in cells if len(re.findall(r'\d', c['text'])) >= 5)
        self.assertEqual(source_counts, actual_counts)
        self.assertTrue(any(count > 1 for count in source_counts.values()))

    def test_audi_indexes_have_all_24_and_40_resolved_repair_destinations(self):
        for uid, count in [('main-231', 24), ('abs-205', 40)]:
            links = [b for s in self.by_uid[uid]['sourceSections'] for b in s['blocks'] if b.get('relatedServiceUid')]
            self.assertEqual(len(links), count)
            for link in links:
                self.assertEqual(link['href'], self.by_uid[link['relatedServiceUid']]['localPath'])
                self.assertTrue((ROOT / link['href'].lstrip('/') / 'index.html').is_file())

    def test_table_headings_keep_table_context_and_cannot_create_vehicle_sections(self):
        page = {'link': 'https://www.menigar.com/test/', 'content': {'rendered': '<h3>Modelo A</h3><table><tr><td><h4>12345678</h4></td></tr></table><h3>Modelo B</h3>'}}
        blocks = scoped_blocks(page)
        self.assertTrue(next(b for b in blocks if b.get('text') == '12345678')['insideTable'])
        self.assertFalse(next(b for b in blocks if b.get('text') == 'Modelo B')['insideTable'])

    def test_public_pdfs_are_local_and_match_their_archived_originals(self):
        rows = json.loads((ROOT / 'data/documentos-local-manifest.json').read_text())
        self.assertEqual(len(rows), 3)
        for row in rows:
            path = ROOT / row['localPath'].lstrip('/')
            self.assertTrue(path.read_bytes().startswith(b'%PDF'))
            self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), row['sha256'])
        envios = (ROOT / 'envios.html').read_text()
        self.assertNotIn('https://www.menigar.com/docs/', envios)


if __name__ == '__main__':
    unittest.main()
