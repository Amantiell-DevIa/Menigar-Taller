"""Only explicitly allowed public document URLs may be fetched."""
import importlib.util
import sys
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
SPEC = importlib.util.spec_from_file_location('linked_pdfs', SCRIPTS / 'archive_linked_pdfs.py')
pdfs = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(pdfs)


class LinkedPDFScopeTests(unittest.TestCase):
    def test_current_public_form_and_scoped_uploads_are_allowed(self):
        self.assertTrue(pdfs.allowed('https://www.menigar.com/docs/peticion_reparacion%202026a.pdf'))
        self.assertTrue(pdfs.allowed('https://www.menigar.com/reparacion-abs/wp-content/uploads/example.pdf'))

    def test_external_hosts_other_file_types_and_encoded_traversal_are_rejected(self):
        for url in ['https://example.com/docs/a.pdf', 'http://www.menigar.com/docs/a.pdf',
                    'https://www.menigar.com/docs/a.exe', 'https://www.menigar.com/wp-admin/a.pdf',
                    'https://www.menigar.com/docs/%2e%2e/wp-admin/a.pdf']:
            with self.subTest(url=url):
                self.assertFalse(pdfs.allowed(url))


if __name__ == '__main__':
    unittest.main()
