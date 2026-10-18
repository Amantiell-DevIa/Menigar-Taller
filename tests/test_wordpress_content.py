"""Source preparation preserves context and rejects corrupted archive payloads."""
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('wordpress_content', SCRIPTS / 'audit_wordpress_export.py')
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def page(content, **fields):
    return {'id': 5, 'link': 'https://www.menigar.com/service/', 'slug': 'service',
            'title': {'rendered': 'Service'}, 'parent': 0, 'content': {'rendered': content}, **fields}


class WordPressSourceTests(unittest.TestCase):
    def test_repeated_model_headings_keep_distinct_modules_and_image_pairs(self):
        raw = '<div id="dslc-main">'
        for number in (1, 2):
            raw += ('<div id="dslc-module-%s"><h3>i30</h3><p>Display</p>'
                    '<img src="/wp-content/uploads/a%s.jpg" class="wp-image-9" alt="source">'
                    '<img src="/wp-content/uploads/b%s.jpg"></div>') % (number, number, number)
        raw += '</div><div id="dslc-footer"><img src="/footer.jpg"></div>'
        blocks = audit.structure(page(raw))['blocks']
        images = [row for row in blocks if row['kind'] == 'image']
        self.assertEqual(len(images), 4)
        self.assertEqual([row['sourceModuleId'] for row in images], ['dslc-module-1'] * 2 + ['dslc-module-2'] * 2)
        self.assertTrue(all(row['precedingHeadings'][-1]['text'] == 'i30' for row in images))
        self.assertEqual(images[0]['wordpressMediaIdHint'], 9)
        self.assertEqual(images[0]['attributes']['alt'], 'source')
        self.assertEqual(len({row['src'] for row in images}), 4)

    def test_table_cell_order_leading_zeroes_and_spans_survive(self):
        raw = '<h2>Referencias</h2><table><tr><th colspan="2">Unidad</th></tr><tr><td>01.0200-0010.3</td><td>001003</td></tr><tr><td rowspan="2">A</td><td>B<br>C</td></tr></table>'
        block = next(row for row in audit.structure(page(raw))['blocks'] if row['kind'] == 'table')
        self.assertEqual(block['rows'][0][0]['colspan'], '2')
        self.assertEqual([cell['text'] for cell in block['rows'][1]], ['01.0200-0010.3', '001003'])
        self.assertEqual(block['rows'][2][0]['rowspan'], '2')
        self.assertEqual(block['rows'][2][1]['text'], 'B C')

    def test_editor_controls_are_excluded_but_editable_service_content_survives(self):
        raw = '<div id="dslc-module-abc"><div class="dslca-module-manage"><p>Anchura del elemento</p><img src="/wp-content/plugins/editor/first-column.webp"></div><div class="dslca-module-options-front"><p>Private editor option</p></div><div class="dslca-editable-content"><h2>Servicio &amp; reparación</h2><p>Referencia 00103</p><img src="/wp-content/uploads/real.jpg"></div></div>'
        result = audit.structure(page(raw))
        self.assertEqual(result['filteredEditorContainers'], 2)
        self.assertNotIn('Anchura', result['bodyText'])
        self.assertNotIn('editor option', result['bodyText'])
        self.assertIn('Servicio & reparación', result['bodyText'])
        self.assertIn('00103', result['bodyText'])
        images = [row for row in result['blocks'] if row['kind'] == 'image']
        self.assertEqual(len(images), 1)
        self.assertEqual(images[0]['sourceModuleId'], 'dslc-module-abc')
        self.assertTrue(images[0]['src'].endswith('/real.jpg'))

    def test_pdf_links_image_variants_and_embeds_remain_separate(self):
        raw = '<a href="/docs/test.pdf">Enviar pieza</a><img src="/a-300.jpg" srcset="/a-300.jpg 300w, /a.jpg 1000w"><iframe src="https://www.youtube.com/embed/test"></iframe>'
        blocks = audit.structure(page(raw))['blocks']
        self.assertEqual([row['kind'] for row in blocks], ['link', 'image', 'embed'])
        self.assertEqual(blocks[0]['href'], 'https://www.menigar.com/docs/test.pdf')
        self.assertEqual(blocks[0]['text'], 'Enviar pieza')
        self.assertEqual(blocks[1]['urls'], ['https://www.menigar.com/a-300.jpg', 'https://www.menigar.com/a.jpg'])

    def test_markup_changes_are_not_automatically_called_text_changes(self):
        result = audit.compare_page(page('<p>Original <b>text</b></p>'), page('<p class="new">Original <strong>text</strong></p>'))
        self.assertEqual(result['state'], 'changed')
        self.assertFalse(result['bodyTextChanged'])
        self.assertFalse(result['bodyImagesChanged'])
        changed = audit.compare_page(page('<img src="/a.jpg">'), page('<img src="/b.jpg">'))
        self.assertTrue(changed['bodyImagesChanged'])
        self.assertFalse(changed['bodyTextChanged'])

    def test_alt_text_download_links_and_embeds_are_not_lost_when_body_text_is_equal(self):
        a = page('<a href="/old.pdf">PDF</a><img src="/same.jpg" alt="Old"><iframe src="https://example.com/old"></iframe>')
        b = page('<a href="/new.pdf">PDF</a><img src="/same.jpg" alt="New"><iframe src="https://example.com/new"></iframe>')
        change = audit.compare_page(a, b)
        self.assertFalse(change['bodyTextChanged'])
        self.assertFalse(change['bodyImagesChanged'])
        self.assertTrue(change['bodyImageMetadataChanged'])
        self.assertTrue(change['bodyLinksChanged'])
        self.assertTrue(change['bodyEmbedsChanged'])

    def test_media_matching_uses_urls_not_reused_numeric_ids_between_sites(self):
        main = audit.media_index([{'id': 9, 'source_url': 'https://www.menigar.com/wp-content/uploads/a.jpg',
                                  'media_details': {'sizes': {'small': {'source_url': 'https://www.menigar.com/wp-content/uploads/a-300.jpg'}}}}])
        abs_ = audit.media_index([{'id': 9, 'source_url': 'https://www.menigar.com/reparacion-abs/wp-content/uploads/b.jpg'}])
        self.assertEqual(main[audit.url_key('http://www.menigar.com/wp-content/uploads/a-300.jpg?cache=1')], [9])
        self.assertEqual(abs_.get(audit.url_key('https://www.menigar.com/wp-content/uploads/a.jpg'), []), [])

    def test_full_raw_capture_hash_is_checked_before_loading_prepared_data(self):
        with tempfile.TemporaryDirectory() as temp:
            run = Path(temp)
            body = json.dumps([page('<p>Text</p>')]).encode()
            (run / 'capture.json').write_bytes(body)
            manifest = {'complete': True, 'sites': [{'site': 'main', 'collections': [{'collection': 'pages', 'total': 1,
                        'responses': [{'path': 'capture.json', 'sha256': audit.digest(body), 'count': 1, 'fetchedAt': 'test'}]}]}]}
            (run / 'manifest.json').write_text(json.dumps(manifest))
            _, rows, captures = audit.load_archive(run)
            self.assertEqual(rows[('main', 'pages')][0]['id'], 5)
            self.assertIn(('main', 'pages', 5), captures)
            (run / 'capture.json').write_bytes(b'[]')
            with self.assertRaisesRegex(ValueError, 'integrity'):
                audit.load_archive(run)


if __name__ == '__main__':
    unittest.main()
