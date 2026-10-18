"""The home finder index stays small and follows the complete catalogue."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from build_catalog import FAMILIES
from build_home_index import project_records, write_home_index


class HomeIndexTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogue = json.loads((ROOT / 'data/catalogo-v2.json').read_text(encoding='utf-8'))
        cls.content = (ROOT / 'data/home-index.js').read_text(encoding='utf-8')

    def test_index_is_generated_from_current_catalogue_and_families(self):
        with tempfile.TemporaryDirectory() as directory:
            destination = Path(directory) / 'home-index.js'
            write_home_index(self.catalogue, FAMILIES, destination)
            self.assertEqual(self.content, destination.read_text(encoding='utf-8'))
        rows = json.loads(self.content.split('window.MENIGAR_CATALOG = ', 1)[1].rsplit(';', 1)[0])
        families = json.loads(self.content.split('window.MENIGAR_FAMILIES = ', 1)[1].split(';\nwindow.MENIGAR_CATALOG', 1)[0])
        self.assertEqual(rows, project_records(self.catalogue))
        self.assertEqual(families, FAMILIES)

    def test_index_excludes_result_details_and_is_much_smaller(self):
        full_size = (ROOT / 'data/catalogo-v2.js').stat().st_size
        index_size = len(self.content.encode('utf-8'))
        self.assertLess(index_size, full_size / 10)
        rows = project_records(self.catalogue)
        self.assertTrue(all({'uid', 'brand', 'model', 'componentKey'} <= row.keys() for row in rows))
        self.assertTrue(all(not {'description', 'references', 'symptoms', 'gallery', 'sourceText', 'localPath'} & row.keys() for row in rows))


if __name__ == '__main__':
    unittest.main()
