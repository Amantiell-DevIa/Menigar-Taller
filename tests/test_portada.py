"""The homepage after the owner's mockup (28 Oct 2026): one search, the six specialties and three steps. Every way
out of the page starts a repair; the videos, the reviews and the rest moved to Sobre nosotros."""
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_servicios


class HomepageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.page = (ROOT / 'index.html').read_text()
        cls.main = re.search(r'<main id="contenido">(.*?)</main>', cls.page, re.S).group(1)

    def test_specialty_cards_match_the_catalogue(self):
        for name, html in build_servicios.build_home().items():
            self.assertIn(f'<!-- generado:{name} -->{html}<!-- /generado:{name} -->', self.page, 'Ejecuta python3 scripts/build_servicios.py')
        cards = re.findall(r'<a class="h-cat" href="/servicios\.html\?pieza=(\w+)#resultados">', self.main)
        self.assertEqual(cards, ['cuadro', 'abs', 'multimedia', 'display', 'cambio', 'palanca'])

    def test_one_search_and_the_step_by_step_link(self):
        forms = re.findall(r'<form class="h-search" action="/servicios\.html" method="get" role="search">(.*?)</form>', self.main, re.S)
        self.assertEqual(len(forms), 1)
        self.assertRegex(forms[0], r'<input id="h-query" type="search" name="q"[^>]*required')
        self.assertEqual(len(re.findall(r'<form\b', self.main)), 1)
        # The line of example searches under the field was removed at the user's request (28 Oct 2026).
        self.assertNotIn('h-examples', self.page)
        self.assertNotRegex(self.main, r'href="/servicios\.html\?q=')
        self.assertIn('href="/servicios.html#catalogo"', self.main, 'La segunda manera, paso a paso, sigue a mano.')

    def test_no_way_out_except_starting_a_repair(self):
        links = re.findall(r'href="([^"]+)"', self.main)
        for href in links:
            with self.subTest(href=href):
                self.assertRegex(href, r'^/(servicios|solicitud)\.html', 'Desde la portada solo se busca la pieza o se consulta.')
        for gone in ['id="videos"', 'id="opiniones"', 'id="por-que-reparar"', 'data-embed', 'id="contacto"', 'id="talleres"']:
            with self.subTest(section=gone):
                self.assertNotIn(gone, self.page)

    def test_three_steps_and_three_real_pieces(self):
        steps = re.findall(r'<li class="h-step">.*?<h3>([^<]+)</h3>', self.main, re.S)
        self.assertEqual(steps, ['Cuéntanos qué falla', 'Te orientamos', 'Envía tu pieza'])
        pieces = re.findall(r'<figure class="h-piece h-piece--(\w+)"><img [^>]*alt="([^"]+)"', self.main)
        self.assertEqual([name for name, _ in pieces], ['cuadro', 'pantalla', 'abs'])
        for src in re.findall(r'(?:src|href)="(/assets/[^"]+)"', self.page) + [c.split()[0] for s in re.findall(r'(?:srcset|imagesrcset)="([^"]+)"', self.page) for c in s.split(',')]:
            with self.subTest(src=src):
                self.assertTrue((ROOT / src.lstrip('/')).is_file())

    def test_palette_and_contrast_choices_are_kept(self):
        css = (ROOT / 'assets/css/portada.css').read_text()
        for token in ['--h-sky:#edf7fe', '--h-ink:#041637', '--h-blue:#0077fe', '--h-action:#0066db']:
            with self.subTest(token=token):
                self.assertIn(token, css)
        self.assertRegex(css, r'\.h-search-btn\{[^}]*background:var\(--h-action\)', 'El blanco sobre #0077fe no llega a AA: el botón usa #0066db.')
        self.assertNotRegex(self.page, r'\sstyle="', 'La CSP no admite estilos en línea.')
        self.assertIn('<link rel="stylesheet" href="/assets/css/portada-v5.css">', (ROOT / 'opciones-hero.html').read_text())


    def test_whole_site_uses_the_light_palette(self):
        """28 Oct 2026, the user's choice: the homepage palette for every page (sky, navy, one blue)."""
        style = (ROOT / 'style.css').read_text()
        for token in ['--p-ivory:#edf7fe', '--p-ink:#041637', '--p-night-1:#061a3d', '--p-accent:#0077fe', '--action:#0066db']:
            with self.subTest(token=token):
                self.assertIn(token, style)
        self.assertRegex(style, r'\.page-intro\{[^}]*background:var\(--p-band\)', 'Las bandas de título son claras.')
        self.assertIn('.repair-detail-page .page-heading { background: var(--p-band);', (ROOT / 'reparaciones.css').read_text())
        laguna = ['#006b7d', '#005566', '#00414e', '#005f70', '#0e93a8', '#fff0b8', '#ffd54a', 'rgba(14,147,168', 'rgba(255,213,74']
        for name in ['style.css', 'servicios.css', 'garantia.css', 'paginas.css', 'reparaciones.css', 'solicitud.css', 'bmw.css', 'hyundai.css', 'assets/css/portada.css']:
            text = (ROOT / name).read_text()
            for colour in laguna:
                with self.subTest(file=name, colour=colour):
                    self.assertNotIn(colour, text)


if __name__ == '__main__':
    unittest.main()
