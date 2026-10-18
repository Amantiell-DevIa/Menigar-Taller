"""Meaningful regressions for the recovered catalogue and its browser projection."""
import hashlib
import json
import re
import unittest
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
OMITTED_BROWSER_FIELDS = {'sourceText', 'dtcDetails', 'instructionGroups', 'sourceSections', 'sourceCapture', 'sourceHtmlSha256', 'contentBlocks'}


class CatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((DATA / 'catalogo-v2.json').read_text(encoding='utf-8'))
        cls.by_uid = {row['uid']: row for row in cls.rows}
        cls.report = json.loads((DATA / 'catalogo-report.json').read_text(encoding='utf-8'))
        browser = (DATA / 'catalogo-v2.js').read_text(encoding='utf-8')
        cls.browser_rows = json.loads(browser.split('window.MENIGAR_CATALOG = ', 1)[1].rsplit(';', 1)[0])
        family_source = browser.split('window.MENIGAR_FAMILIES = ', 1)[1].split(';\nwindow.MENIGAR_CATALOG', 1)[0]
        cls.families = json.loads(family_source)
        cls.snapshots = {}
        for source, dirname in [('main', 'cache'), ('abs', 'cache_abs')]:
            cls.snapshots[source] = {page['id']: page for path in (DATA / dirname).glob('*.json') for page in json.loads(path.read_text(encoding='utf-8'))}

    def test_identity_is_scoped_to_its_source_wordpress(self):
        self.assertEqual(len(self.rows), len(self.by_uid))
        self.assertEqual(len(self.rows), len({row['localPath'] for row in self.rows}))
        for row in self.rows:
            with self.subTest(uid=row['uid']):
                self.assertEqual(row['uid'], f"{row['source']}-{row['sourceId']}")
                source_page = self.snapshots[row['source']][row['sourceId']]
                self.assertEqual(row['url'], source_page['link'])
                self.assertEqual(row['localPath'], f"/reparaciones/{row['uid']}-{row['slug']}/")

    def test_honda_selection_cannot_resolve_to_the_other_wordpress_mini(self):
        honda, mini = self.by_uid['abs-3198'], self.by_uid['main-3198']
        self.assertEqual(honda['sourceId'], mini['sourceId'])
        self.assertEqual((honda['brand'], honda['model'], honda['componentKey']), ('Honda', 'Civic', 'abs'))
        self.assertEqual((mini['brand'], mini['componentKey']), ('Mini', 'display'))
        self.assertIn('2016-2022', honda['variant'])
        self.assertNotEqual(honda['localPath'], mini['localPath'])

    def test_reference_fragments_are_not_fault_codes(self):
        picanto = next(row for row in self.rows if row['source'] == 'main' and row['slug'] == 'picanto')
        self.assertIn('94003-07010', picanto['references'])
        self.assertIn('9400307010', picanto['references'])
        self.assertTrue(all('07010' not in row['dtcCodes'] for row in self.rows))
        self.assertNotIn('0003', self.by_uid['main-635']['dtcCodes'])
        self.assertNotIn('0517', self.by_uid['main-3230']['dtcCodes'])
        self.assertNotIn('0104', self.by_uid['main-5937']['dtcCodes'])

    def test_references_and_fault_codes_preserve_strings_and_leading_zeroes(self):
        honda = self.by_uid['abs-3198']
        self.assertIn('06.2109-6664.3', honda['references'])
        self.assertIn('06210262244', honda['references'])
        self.assertIn('01130', self.by_uid['abs-2444']['dtcCodes'])
        for row in self.rows:
            self.assertTrue(all(isinstance(value, str) for value in row['references'] + row['dtcCodes']))

    def test_browser_projection_keeps_every_reference_and_navigation_field(self):
        self.assertEqual(len(self.rows), len(self.browser_rows))
        for full, browser in zip(self.rows, self.browser_rows):
            with self.subTest(uid=full['uid']):
                for key in ('uid', 'source', 'localPath', 'brand', 'model', 'componentKey', 'title', 'references', 'dtcCodes', 'symptoms'):
                    self.assertEqual(browser[key], full[key])
                self.assertEqual([g['model'] for g in browser.get('modelGroups', [])], [g['model'] for g in full.get('modelGroups', [])])
                self.assertLessEqual(len(browser.get('gallery', [])), 1)
                if full.get('gallery'):
                    self.assertEqual(browser['gallery'][0]['src'], full['gallery'][0]['src'])
                self.assertFalse(OMITTED_BROWSER_FIELDS & browser.keys())

    def test_mk61_shipping_context_preserves_all_six_applicable_tables(self):
        instructions = self.by_uid['abs-2444']
        self.assertTrue(instructions['isInstruction'])
        self.assertEqual(len(instructions['instructionGroups']), 6)
        vag = instructions['instructionGroups'][0]
        self.assertIn('Grupo Vag', vag['label'])
        self.assertEqual(vag['rows'][0], ['01130', 'SI SÓLO', 'NO'])
        self.assertIn(['01276', 'SI', 'SI'], vag['rows'])
        self.assertTrue(any(instructions['uid'] in row['relatedInstructions'] for row in self.rows))
        for row in self.rows:
            for uid in row['relatedInstructions']:
                self.assertTrue(self.by_uid[uid]['isInstruction'])

    def test_service_families_do_not_conflate_distinct_modules(self):
        keys = {family['key'] for family in self.families}
        self.assertTrue({'bluetooth', 'inmo', 'ecu', 'clima', 'palanca', 'cambio'} <= keys)
        self.assertEqual(next(row for row in self.rows if row['slug'] == 'reparacion-modulo-bluetooth-blueme-fiat')['componentKey'], 'bluetooth')
        self.assertEqual(next(row for row in self.rows if row['slug'] == 'reparacion-inmovilizadores-transponder')['componentKey'], 'inmo')
        self.assertTrue(all(row['componentKey'] in keys for row in self.rows))

    def test_recovered_text_excludes_menu_and_customer_form_chrome(self):
        for row in self.rows:
            with self.subTest(uid=row['uid']):
                self.assertNotIn('Marcas ABS\nAlfa Romeo', row['sourceText'])
                self.assertNotIn('Nombre (requerido)', row['sourceText'])
                self.assertNotIn('Copyright © 2017', row['sourceText'])
                self.assertNotRegex(row['sourceText'], r'<(?:style|script)\b')

    def test_imports_do_not_create_unapproved_price_defaults(self):
        self.assertTrue(all('price' not in row and 'estimatedPrice' not in row for row in self.rows))
        self.assertTrue(all(row['reviewStatus'] == 'source-imported' for row in self.rows))

    def test_redirects_remain_disabled_and_target_matching_records(self):
        redirects = json.loads((DATA / 'redirects.json').read_text(encoding='utf-8'))
        self.assertEqual(len(redirects), len(self.rows))
        for entry in redirects:
            row = self.by_uid[entry['uid']]
            self.assertFalse(entry['enabled'])
            self.assertTrue(entry['reviewRequired'])
            self.assertEqual(entry['from'], row['url'])
            self.assertEqual(entry['fromPath'], urlparse(row['url']).path)
            self.assertEqual(entry['to'], row['localPath'])

    def test_original_source_snapshots_are_unchanged(self):
        self.assertEqual(len(self.report['snapshotSha256']), 26)
        for relative_path, expected_digest in self.report['snapshotSha256'].items():
            self.assertEqual(hashlib.sha256((ROOT / relative_path).read_bytes()).hexdigest(), expected_digest, relative_path)
        self.assertEqual(self.report['sourcePageCounts'], {source: len(pages) for source, pages in self.snapshots.items()})


if __name__ == '__main__':
    unittest.main()
