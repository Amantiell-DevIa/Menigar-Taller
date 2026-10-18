"""Export must reject incomplete/live-changing pagination and corrupted resumes."""
import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from unittest.mock import patch

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts/export_wordpress.py'
SPEC = importlib.util.spec_from_file_location('wordpress_export', SCRIPT)
export = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(export)


def fake_api(records, change=None):
    calls = []
    def fetch(url):
        calls.append(url)
        query = parse_qs(urlsplit(url).query)
        size, page = int(query['per_page'][0]), int(query.get('page', ['1'])[0])
        rows = sorted(records, key=lambda row: row['id'], reverse=query['order'][0] == 'desc')
        data = rows[(page - 1) * size:page * size]
        total = len(records)
        if change:
            data, total = change(query, data, total)
        body = json.dumps(data).encode()
        return body, {'url': url, 'status': 200, 'total': str(total),
                      'totalPages': str((total + size - 1) // size),
                      'sha256': hashlib.sha256(body).hexdigest(), 'fetchedAt': 'test'}
    fetch.calls = calls
    return fetch


class WordPressExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.output = Path(self.temp.name)
        self.records = [{'id': value, 'content': {'rendered': '<p>%s</p>' % value}} for value in (2, 8, 19)]

    def run_export(self, fetch, **kwargs):
        with patch('builtins.print'):
            return export.export_collection('main', 'pages', self.output, per_page=2, fetch=fetch, **kwargs)

    def test_complete_export_preserves_full_payload_and_checks_both_boundaries(self):
        fetch = fake_api(self.records)
        manifest = self.run_export(fetch)
        self.assertEqual(manifest['total'], 3)
        self.assertTrue(manifest['complete'])
        self.assertFalse(manifest['checks']['transactionalSnapshot'])
        self.assertEqual(len(fetch.calls), 4)
        captured = json.loads((self.output / 'main/pages/page-0001.json').read_text())
        self.assertEqual(captured, self.records[:2])
        self.assertEqual(len(manifest['validationRequests']), 2)

    def test_duplicate_ids_cannot_pass_even_when_record_count_agrees(self):
        fetch = fake_api([{'id': 2}, {'id': 2}, {'id': 19}])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            self.run_export(fetch)
        self.assertFalse((self.output / 'main/pages/collection.json').exists())

    def test_short_page_cannot_be_mistaken_for_finished_collection(self):
        def truncate(query, rows, total):
            return ([], total) if query.get('page') == ['2'] else (rows, total)
        with self.assertRaisesRegex(ValueError, 'Missing records'):
            self.run_export(fake_api(self.records, truncate))

    def test_changed_totals_are_rejected_during_or_after_pagination(self):
        def change(query, rows, total):
            return rows, total + 1 if query['per_page'] == ['1'] else total
        with self.assertRaisesRegex(ValueError, 'totals changed'):
            self.run_export(fake_api(self.records, change))

    def test_equal_counts_with_changed_boundary_content_are_rejected(self):
        def change(query, rows, total):
            if query['per_page'] == ['1'] and rows:
                rows = [dict(rows[0], content={'rendered': 'new text'})]
            return rows, total
        with self.assertRaisesRegex(ValueError, 'content changed'):
            self.run_export(fake_api(self.records, change))

    def test_request_dependent_form_tokens_do_not_hide_real_page_content_changes(self):
        a = {'id': 9, 'modified': 'same', 'content': {'rendered': '<h1>Repair</h1><form action="?page=1" data-token-time="1"><input name="a"></form><p>Original</p>'}}
        b = {'id': 9, 'modified': 'same', 'content': {'rendered': '<h1>Repair</h1><form action="?page=2" data-token-time="2"><input name="a"></form><p>Original</p>'}}
        self.assertEqual(export.stable_boundary_record(a), export.stable_boundary_record(b))
        self.assertIn('data-token-time="1"', a['content']['rendered'])
        b['content']['rendered'] = b['content']['rendered'].replace('Original', 'New information')
        self.assertNotEqual(export.stable_boundary_record(a), export.stable_boundary_record(b))

    def test_contact_form_wrapper_counter_is_the_only_numeric_id_normalized(self):
        a = {'content': {'rendered': '<div class="wpcf7" id="wpcf7-f203-o44"><form></form></div><p id="reference-44">00144</p>'}}
        b = {'content': {'rendered': '<div class="wpcf7" id="wpcf7-f203-o1"><form></form></div><p id="reference-44">00144</p>'}}
        self.assertEqual(export.stable_boundary_record(a), export.stable_boundary_record(b))
        b['content']['rendered'] = b['content']['rendered'].replace('reference-44', 'reference-1')
        self.assertNotEqual(export.stable_boundary_record(a), export.stable_boundary_record(b))

    def test_resume_checks_hash_and_never_silently_overwrites_archive(self):
        self.run_export(fake_api(self.records))
        path = self.output / 'main/pages/page-0001.json'
        original = path.read_bytes()
        with self.assertRaisesRegex(ValueError, 'Existing archive'):
            self.run_export(fake_api(self.records))
        self.assertEqual(path.read_bytes(), original)
        path.write_bytes(b'[]')
        with self.assertRaisesRegex(ValueError, 'integrity mismatch'):
            self.run_export(fake_api(self.records), resume=True)
        self.assertEqual(path.read_bytes(), b'[]')

    def test_zero_record_collection_is_explicitly_archived_and_verified(self):
        manifest = self.run_export(fake_api([]))
        self.assertEqual(manifest['total'], 0)
        self.assertEqual(manifest['totalPages'], 0)
        self.assertEqual(len(manifest['responses']), 1)

    def test_missing_headers_and_private_collections_are_rejected(self):
        with self.assertRaisesRegex(ValueError, 'pagination headers'):
            export.pagination({}, 50)
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            export.export_collection('main', 'users', self.output)
        with self.assertRaisesRegex(ValueError, 'allowlist'):
            export.public_get('https://example.com/wp-json/wp/v2/pages')


if __name__ == '__main__':
    unittest.main()
