"""The warranty page (26 Oct 2026) keeps every condition published at menigar.com/garantias and is
reachable from every header, the footer, the fichas and the old address."""
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))


class WarrantyPageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / 'garantia.html').read_text()

    def test_every_published_condition_is_on_the_page(self):
        text = re.sub(r'\s+', ' ', re.sub(r'<[^>]+>', ' ', self.page))
        for condition in [
            'garantía limitada de dos años desde la fecha de factura',
            'la garantía se limita a 3 meses sobre la parte del material reparado, no sobre la totalidad de la pieza',
            'para que vuelva a funcionar como lo hacía originalmente',
            'defectos de fabricación o de la intervención de nuestra mano de obra',
            'Todos los componentes internos y el trabajo realizado en Menigar',
            'No es transferible',
            'Portes', 'Desmontaje y montaje', 'Diagnosis', 'Codificación y programación', 'Descarga de software', 'Mano de obra',
            'Precintos manipulados o alterados', 'Daños por agua', 'Daños por fuego', 'Daños por una subida de tensión',
            'Daños causados por otra unidad defectuosa del vehículo', 'Daños por arrancar el vehículo con pinzas',
            'Uso incorrecto de la unidad', 'devolver la unidad antigua fuera de los plazos indicados',
            'una unidad de intercambio o la devolución de la totalidad del importe facturado',
            'Sin la factura original de compra de la pieza no se puede efectuar ninguna devolución',
            'Menigar se reserva el derecho a aceptarla o no',
            'se pedirá la factura original de compra de la pieza de recambio',
            'Cada caso se estudia de forma individual',
            'Sin usar', 'En un plazo de 10 días', 'En su embalaje original', 'Con la factura',
            'ready to run', 'Director General del grupo',
            'Pendientes de revisión y aprobación para la nueva web',
        ]:
            with self.subTest(condition=condition):
                self.assertIn(condition, text)

    def test_page_follows_the_site_rules(self):
        self.assertIn('<title>Garantía de reparaciones | Menigar</title>', self.page)
        self.assertIn('<link rel="stylesheet" href="/garantia.css">', self.page)
        self.assertIn('<a href="/garantia.html" aria-current="page">Garantía</a>', self.page)
        self.assertNotRegex(self.page, r'\sstyle="', 'La CSP no admite estilos en línea.')
        self.assertIn('noindex, nofollow', self.page)

    def test_every_header_and_the_fichas_link_to_it(self):
        pages = ['index.html', 'laboratorio.html', 'servicios.html', 'solicitud.html', 'opciones-hero.html', 'envios.html',
                 'taller.html', 'ayuda.html', 'privacidad.html', 'condiciones.html', 'cookies.html', 'garantia.html']
        for name in pages:
            with self.subTest(page=name):
                nav = re.search(r'<ul class="nav-list">(.*?)</ul>', (ROOT / name).read_text(), re.S).group(1)
                labels = re.findall(r'<a href="/([^"]+)"[^>]*>([^<]+)</a>', nav)
                self.assertEqual([href for href, _ in labels], ['servicios.html', 'envios.html', 'garantia.html', 'taller.html', 'ayuda.html'])
        ficha = (ROOT / 'reparaciones/abs-1936-f-650-gs/index.html').read_text()
        self.assertIn('<a href="/garantia.html">Qué cubre la garantía y cómo reclamarla</a>', ficha)
        self.assertIn('<a href="/garantia.html">Garantía de la reparación</a>', ficha)
        self.assertIn('<a href="/garantia.html">', (ROOT / 'condiciones.html').read_text())

    def test_old_address_and_public_file_lists(self):
        catalogue = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        links = [block for row in catalogue for section in row.get('sourceSections') or [] for block in section['blocks']
                 if block.get('originalHref', '').rstrip('/').endswith('/garantias')]
        self.assertTrue(links)
        self.assertTrue(all(block['href'] == '/garantia.html' for block in links))
        for name in ['servidor.py', 'backend/dev-router.php', 'backend/review-router.php',
                     'scripts/build_vercel_static.cjs', 'scripts/build_review_package.py']:
            source = (ROOT / name).read_text()
            with self.subTest(file=name):
                self.assertIn("'garantia.html'", source)
                self.assertIn("'garantia.css'", source)
        self.assertIn('<loc>https://www.menigar.com/garantia.html</loc>', (ROOT / 'sitemap.xml').read_text())


if __name__ == '__main__':
    unittest.main()
