"""Public clarity changes retain the archived technical associations."""
import hashlib
from html import escape
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import tempfile
import unicodedata
import unittest
from urllib.parse import parse_qs, urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_pages import repair_page, header, footer
from public_copy import public_text, photo_caption, reset_copy_report, write_copy_report


class Elements(HTMLParser):
    def __init__(self, source):
        super().__init__()
        self.tags = []
        self.feed(source)
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class PublicDecisionContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        cls.lookup = {r['uid']: r for r in cls.rows}

    def test_mazda_titles_context_and_photo_captions_do_not_change_source(self):
        record = self.lookup['main-2942']
        before = json.dumps(record, ensure_ascii=False, sort_keys=True)
        rendered = repair_page(record, self.lookup)
        self.assertIn('<h1>Reparación de la pantalla del cuadro de instrumentos Mazda</h1>', rendered)
        self.assertIn('Pantallas Mazda por modelo', rendered)
        self.assertNotIn('garantiar', rendered)
        self.assertNotRegex(rendered, re.compile(r'al mejor precio|máxima garantía|en el menor tiempo', re.I))
        self.assertEqual(before, json.dumps(record, ensure_ascii=False, sort_keys=True))
        self.assertEqual(record['title'], 'Reparación Display Mazda')
        parsed = Elements(rendered)
        variants = [attrs for tag, attrs in parsed.tags if tag == 'article' and 'repair-variant' in attrs.get('class', '').split()]
        self.assertEqual([(v['data-model-group'], v['data-model-anchor']) for v in variants],
                         [('3 BK', 'detalle-6'), ('3 BM', 'detalle-17'), ('5', 'detalle-28'), ('6', 'detalle-39')])
        self.assertEqual(len([1 for tag, attrs in parsed.tags if tag == 'figcaption']), 8)
        self.assertIn('Detalle de la pantalla de velocidad · Mazda 3 BM', rendered)
        self.assertIn('Cuadro completo · Mazda 5', rendered)
        self.assertIn('data-repair-uid="main-2942"', rendered)
        self.assertIn('id="repair-model-context"', rendered)

    def test_unknown_images_get_only_a_factual_source_group_caption(self):
        caption = photo_caption({'uid': 'test', 'title': 'Servicio de prueba'},
                                {'src': '/assets/media/unknown.jpg'}, 'Modelo ABC', 2, 3)
        self.assertEqual(caption, 'Foto 2 de 3 · Modelo ABC')
        self.assertNotIn('Cuadro completo', caption)
        self.assertNotIn('Detalle de la pantalla', caption)
        # The reviewed caption is scoped to its exact record and full media path.
        caption = photo_caption({'uid': 'other', 'title': 'Otro servicio'},
                                {'src': '/assets/media/09/0978ba55626204a5-mazda-3.webp'}, 'Otro', 1, 1)
        self.assertEqual(caption, 'Foto 1 de 1 · Otro')

    def test_search_titles_match_detail_without_overwriting_source_titles(self):
        source = (ROOT / 'data/catalogo-v2.js').read_text()
        browser = json.loads(source.split('window.MENIGAR_CATALOG = ', 1)[1].rsplit(';', 1)[0])
        self.assertEqual(len(browser), len(self.rows))
        for item in browser:
            archived = self.lookup[item['uid']]
            self.assertEqual(item['title'], archived['title'])
            expected = public_text(archived['title'], archived['uid'], 'title')
            self.assertEqual(item.get('publicTitle', item['title']), expected)

    def test_public_titles_tell_every_ficha_apart(self):
        by_title = {}
        for row in self.rows:
            title = public_text(row['title'], row['uid'], 'title')
            key = re.sub(r'[^a-z0-9]+', ' ', unicodedata.normalize('NFKD', title).encode('ascii', 'ignore').decode().lower()).strip()
            by_title.setdefault(key, set()).add(row['uid'])
        self.assertEqual([uids for uids in by_title.values() if len(uids) > 1], [])
        self.assertEqual(self.lookup['main-8026']['title'], 'Reparación cuadro de instrumentos Audi 100')
        self.assertIn('<h1>Reparación cuadro de instrumentos Audi V8</h1>', repair_page(self.lookup['main-8026'], self.lookup))

    def test_copies_merge_into_their_most_complete_ficha(self):
        # The same old page published two or three times becomes one ficha (26 Oct 2026):
        # its old addresses redirect there, and links to a copy open that ficha.
        merged = {'main-8607': 'main-8394', 'main-8241': 'main-8236', 'abs-2475': 'abs-1936',
                  'main-13359': 'main-8674', 'main-14038': 'main-8674', 'main-9052': 'main-14508'}
        report = json.loads((ROOT / 'data/catalogo-report.json').read_text())
        copies = {entry['uid']: entry for entry in report['excluded'] if entry.get('mergedInto')}
        self.assertEqual({uid: entry['mergedInto'] for uid, entry in copies.items()}, merged)
        redirects = {entry['from']: entry for entry in json.loads((ROOT / 'data/redirects.json').read_text())}
        vercel = {entry['source']: entry['destination'] for entry in json.loads((ROOT / 'vercel.json').read_text())['redirects']}
        for uid, kept in merged.items():
            with self.subTest(uid=uid):
                self.assertNotIn(uid, self.lookup)
                target = self.lookup[kept]['localPath']
                self.assertEqual((redirects[copies[uid]['url']]['to'], redirects[copies[uid]['url']]['mergedFrom']), (target, uid))
                former = copies[uid]['formerLocalPath']
                self.assertFalse((ROOT / former.strip('/')).exists())
                self.assertEqual((vercel[former], vercel[former.rstrip('/')]), (target, target))
        links = [block for section in self.lookup['main-8674']['sourceSections'] for block in section['blocks']
                 if block.get('originalHref', '').endswith('/seat-full-link/')]
        self.assertEqual([(block['href'], block['relatedServiceUid']) for block in links], [(self.lookup['main-14508']['localPath'], 'main-14508')])
        # Every generated ficha folder belongs to a ficha in the catalogue.
        folders = {path.name for path in (ROOT / 'reparaciones').iterdir() if path.is_dir()}
        self.assertEqual(folders, {row['localPath'].strip('/').split('/')[-1] for row in self.rows})

    def test_bmw_and_hyundai_keep_the_same_variant_context_contract(self):
        for uid in ('main-2321', 'main-3915'):
            row = self.lookup[uid]
            parsed = Elements(repair_page(row, self.lookup))
            variants = [attrs for tag, attrs in parsed.tags if tag == 'article' and 'repair-variant' in attrs.get('class', '').split()]
            expected = [g for g in row['modelGroups'] if g.get('vehicleModel', True)]
            self.assertEqual(len(variants), len(expected), uid)
            self.assertTrue(all(v.get('data-model-group') and v.get('data-model-anchor') for v in variants))
            ids = [attrs['id'] for _, attrs in parsed.tags if attrs.get('id')]
            self.assertEqual(len(ids), len(set(ids)))

    def test_generated_actions_have_the_consequence_they_name(self):
        links = [a for tag, a in Elements(header() + footer()).tags if tag == 'a']
        request_queries = [parse_qs(urlsplit(a.get('href', '')).query) for a in links if a.get('href', '').startswith('/solicitud.html')]
        self.assertIn({'tipo': ['consulta']}, request_queries)
        self.assertIn({'intencion': ['envio']}, request_queries)
        self.assertTrue(any(a.get('href') == '/ayuda.html#reparacion-en-curso' for a in links))
        for uid in ('main-2942', 'main-514', 'main-1604', 'main-3915', 'main-2321'):
            document = repair_page(self.lookup[uid], self.lookup)
            self.assertIn('noindex, nofollow', document)
            self.assertNotIn('Solicitar reparación', document)
            self.assertIn('presupuesto final', document)

    def test_table_cells_and_media_membership_stay_with_their_variant(self):
        for uid in ('main-2942', 'main-514', 'main-13614'):
            record = self.lookup[uid]
            document = repair_page(record, self.lookup)
            for section in record['sourceSections']:
                if not any(block['kind'] in {'image', 'table'} for block in section['blocks']):
                    continue
                article = re.search(r'<article[^>]+id="' + section['anchor'] + r'">(.*?)</article>', document, re.S)[1]
                parsed = Elements(article)
                self.assertEqual([a['src'] for tag, a in parsed.tags if tag == 'img'],
                                 [b['src'] for b in section['blocks'] if b['kind'] == 'image'])
                for block in section['blocks']:
                    if block['kind'] == 'table':
                        for row in block['rows']:
                            for cell in row:
                                self.assertIn(escape(cell['text'], quote=True), article)

    def test_recopy_report_is_reversible_and_does_not_edit_the_catalogue(self):
        path = ROOT / 'data/catalogo-v2.json'
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        reset_copy_report()
        for row in self.rows:
            rendered = repair_page(row, self.lookup)
            self.assertNotRegex(rendered, re.compile(r'al mejor (?:precio|coste)|máxima garantía|en el menor tiempo|garantiar|tiempo r[eé]cord', re.I), row['uid'])
        with tempfile.TemporaryDirectory() as folder:
            (Path(folder) / 'data').mkdir()
            report = write_copy_report(folder)
        self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)
        self.assertFalse(any(report['constraints'].values()))
        self.assertGreater(len(report['replacements']), 100)
        self.assertTrue(all(r['sourceText'] != r['publicText'] for r in report['replacements']))
        self.assertTrue(all(hashlib.sha256(r['sourceText'].encode()).hexdigest() == r['sourceTextSha256'] for r in report['replacements']))
        self.assertEqual(len(report['reviewedPhotoCaptions']), 8)
        # Technical codes and identifiers are unaffected by the commercial rules.
        text = 'BMW E60/E61 · 94003-2L410 · P0500 · ABS 5.7'
        self.assertEqual(public_text(text, 'test', 'technical'), text)


if __name__ == '__main__':
    unittest.main()
