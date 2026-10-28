"""The services page (26 Oct 2026) opens with the specialties and the featured services instead of the
whole catalogue page by page, and loads the catalogue only when someone searches or chooses."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_servicios


class ServicesPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / 'servicios.html').read_text()

    def test_generated_blocks_match_the_catalogue(self):
        for name, html in build_servicios.build().items():
            with self.subTest(block=name):
                self.assertIn(f'<!-- generado:{name} -->{html}<!-- /generado:{name} -->', self.page,
                              'Ejecuta python3 scripts/build_servicios.py')

    def test_the_catalogue_is_not_loaded_on_arrival(self):
        self.assertNotIn('<script src="/data/catalogo-v2.js"', self.page)
        self.assertIn('data-catalog-src="/data/catalogo-v2.js"', self.page)
        app = (ROOT / 'app.js').read_text()
        self.assertIn('dataset?.catalogSrc', app)
        self.assertIn('const useCatalogue = () =>', app)

    def test_controller_elements_and_homepage_entries_exist(self):
        for element_id in ['catalog-filter-form', 'catalog-query', 'catalog-brand', 'catalog-model', 'catalog-component',
                           'catalog-results', 'catalog-related-brand', 'results-count', 'results-pagination', 'active-filters',
                           'results-title', 'results-guidance', 'catalog-filter-panel', 'catalog-selection', 'catalog-selection-text',
                           'resultados', 'catalog-showcase', 'family-brands', 'catalogo']:
            with self.subTest(element=element_id):
                self.assertEqual(len(re.findall(rf'\bid="{element_id}"', self.page)), 1)
        self.assertRegex(self.page, r'<input type="search" name="q" id="catalog-query" form="catalog-filter-form"')
        self.assertRegex(self.page, r'<button class="button button-primary" type="submit" form="catalog-filter-form">')

    def test_specialties_and_featured_services_are_real(self):
        tiles = re.findall(r'<a class="s-family" href="/servicios\.html\?pieza=(\w+)#resultados" data-catalog-link>', self.page)
        self.assertEqual(tiles, ['cuadro', 'abs', 'multimedia', 'display', 'cambio', 'palanca'])
        featured = re.findall(r'<a class="s-featured-card" href="([^"]+)">', self.page)
        self.assertEqual(len(featured), 6)
        for path in featured:
            with self.subTest(path=path):
                self.assertTrue((ROOT / path.strip('/') / 'index.html').is_file())
        for src in re.findall(r'<img class="s-fit-\w+" src="([^"]+)"', self.page):
            with self.subTest(src=src):
                self.assertTrue((ROOT / src.lstrip('/')).is_file())
                self.assertNotRegex(src, r'no-disponible|garantia|slide', 'Sin carteles ni fotos con texto incrustado.')

    def test_stylesheet_is_published(self):
        self.assertIn('<link rel="stylesheet" href="/servicios.css">', self.page)
        self.assertNotRegex(self.page, r'\sstyle="', 'La CSP no admite estilos en línea.')
        for name in ['servidor.py', 'backend/dev-router.php', 'backend/review-router.php',
                     'scripts/build_vercel_static.cjs', 'scripts/build_review_package.py']:
            with self.subTest(file=name):
                self.assertIn("'servicios.css'", (ROOT / name).read_text())


if __name__ == '__main__':
    unittest.main()
