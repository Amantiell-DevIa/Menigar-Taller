"""Cómo funciona, Sobre nosotros and Ayuda share paginas.css and the language of the services page: a title band
with the main actions, short blocks in cards and a closing block to talk to the laboratory. On 28 Oct 2026
«Cómo enviar» became Cómo funciona and «El laboratorio» became Sobre nosotros, which received the homepage's
why repair, videos, reviews and contact sections."""
from pathlib import Path
import json
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
PAGES = ['como-funciona.html', 'sobre-nosotros.html', 'ayuda.html']


def local_files(html):
    """Every local file an <img> or a link points to, including each srcset candidate."""
    paths = re.findall(r'\ssrc="(/[^"]+)"', html)
    for srcset in re.findall(r'\ssrcset="([^"]+)"', html):
        paths += [candidate.split()[0] for candidate in srcset.split(',')]
    paths += re.findall(r'href="(/assets/[^"#?]+)"', html)
    return paths


class InformationPagesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.pages = {name: (ROOT / name).read_text() for name in PAGES}

    def test_shared_stylesheet_band_and_no_inline_styles(self):
        for name, html in self.pages.items():
            with self.subTest(page=name):
                self.assertIn('<link rel="stylesheet" href="/paginas.css">', html)
                self.assertNotRegex(html, r'\sstyle="', 'La CSP no admite estilos en línea.')
                self.assertEqual(len(re.findall(r'<h1[\s>]', html)), 1)
                self.assertRegex(html, r'<section class="page-intro page-heading pg-intro"')
                self.assertRegex(html, r'class="pg-actions"')
        for name in ['servidor.py', 'backend/dev-router.php', 'backend/review-router.php',
                     'scripts/build_vercel_static.cjs', 'scripts/build_review_package.py']:
            with self.subTest(file=name):
                text = (ROOT / name).read_text()
                for page in ['paginas.css', 'como-funciona.html', 'sobre-nosotros.html']:
                    self.assertIn(f"'{page}'", text)
                self.assertNotRegex(text, r"'(envios|taller)\.html'")

    def test_former_addresses_redirect_and_no_page_links_to_them(self):
        redirects = {item['source']: item['destination'] for item in json.loads((ROOT / 'vercel.json').read_text())['redirects']}
        self.assertEqual(redirects['/envios.html'], '/como-funciona.html')
        self.assertEqual(redirects['/taller.html'], '/sobre-nosotros.html')
        self.assertFalse((ROOT / 'envios.html').exists() or (ROOT / 'taller.html').exists())
        for name in ['index.html', 'servicios.html', 'solicitud.html', 'garantia.html', 'sitemap.xml', *PAGES]:
            with self.subTest(page=name):
                self.assertNotRegex((ROOT / name).read_text(), r'/(envios|taller)\.html')

    def test_every_image_and_document_exists(self):
        for name, html in self.pages.items():
            for path in local_files(html):
                with self.subTest(page=name, path=path):
                    self.assertTrue((ROOT / path.lstrip('/')).is_file())

    def test_how_it_works_opens_with_three_steps_and_keeps_the_shipping_guide(self):
        html = self.pages['como-funciona.html']
        self.assertIn('<a href="/como-funciona.html" aria-current="page">Cómo funciona</a>', html)
        journey = re.search(r'<ol class="pg-steps pg-steps--3">(.*?)</ol>', html, re.S)
        self.assertEqual(re.findall(r'<h3>([^<]+)</h3>', journey.group(1)), ['Cuéntanos qué falla', 'Te orientamos', 'Envía tu pieza'])
        steps = re.search(r'<ol class="pg-steps">(.*?)</ol>', html, re.S)
        titles = re.findall(r'<h3>([^<]+)</h3>', steps.group(1))
        self.assertEqual(len(titles), 4)
        for title in titles:
            with self.subTest(title=title):
                self.assertNotRegex(title, r'^\s*(\d|Paso)', 'El número lo pone la lista, no el título.')
        self.assertRegex(html, r'<section class="pg-section" id="preparar"')
        self.assertNotIn('https://www.menigar.com/docs/', html, 'Los PDF se sirven desde /assets/documentos/.')
        for document in ['direccion_envio.pdf', 'peticion_reparacion-2026a.pdf', 'como_embalar.pdf']:
            with self.subTest(document=document):
                self.assertRegex(html, rf'href="/assets/documentos/[0-9a-f]+-{re.escape(document)}"')
        self.assertIn('Durante esta revisión de la nueva web, la solicitud digital solo sirve para pruebas', html)
        self.assertIn('No confundas el número del transportista', html)
        self.assertIn('El presupuesto final se confirma al revisar la unidad.', html)

    def test_about_page_calls_menigar_a_laboratory_and_holds_the_moved_sections(self):
        html = self.pages['sobre-nosotros.html']
        self.assertIn('<a href="/sobre-nosotros.html" aria-current="page">Sobre nosotros</a>', html)
        h1 = re.search(r'<h1[^>]*>(.*?)</h1>', html, re.S).group(1)
        self.assertIn('Laboratorio', h1)
        self.assertNotRegex(h1, r'\b[Tt]aller\b')
        chips = re.findall(r'<a href="/servicios\.html\?pieza=(\w+)#resultados">', html)
        self.assertEqual(chips, ['cuadro', 'abs', 'multimedia', 'display', 'cambio', 'palanca'])
        gallery = re.search(r'<ul class="pg-gallery">(.*?)</ul>', html, re.S).group(1)
        self.assertEqual(len(re.findall(r'<figcaption><strong>', gallery)), 3)
        self.assertRegex(html, r'<img src="/assets/paginas/hero-lab-\d+\.webp"[^>]*fetchpriority="high"')
        for section in ['por-que-reparar', 'videos', 'opiniones', 'donde-estamos']:
            with self.subTest(section=section):
                self.assertEqual(len(re.findall(rf'<section class="p-section [^"]+" id="{section}"', html)), 1)
        self.assertIn('<a href="/garantia.html">Ver la garantía</a>', html)
        self.assertIn('href="#donde-estamos">Cómo llegar', html)
        self.assertIn('href="/solicitud.html?cliente=empresa&amp;tipo=consulta"', html, 'El bloque para talleres vive aquí.')

    def test_videos_and_map_load_only_on_request(self):
        html = self.pages['sobre-nosotros.html']
        self.assertNotRegex(html, r'(?i)<iframe', 'Nada de marcos de terceros al abrir la página.')
        videos = re.findall(r'data-embed="youtube" data-embed-src="([^"]+)".*?href="https://www\.youtube\.com/watch\?v=([^"]+)"', html, re.S)
        self.assertEqual(len(videos), 3)
        for video_id, link in videos:
            with self.subTest(video=video_id):
                self.assertRegex(video_id, r'^[\w-]{11}$')
                self.assertEqual(link, video_id, 'El enlace sin JavaScript abre el mismo vídeo.')
        self.assertRegex(html, r'data-embed="map" data-embed-src="https://www\.google\.com/maps/embed\?pb=[\w!%.-]+"')
        self.assertRegex(html, r'class="p-score-label"><span class="p-g p-g--lg" aria-hidden="true">')
        css = (ROOT / 'paginas.css').read_text()
        for selector in ['.p-video-frame', '.p-score-num', '.p-map-card', '.p-readouts']:
            with self.subTest(selector=selector):
                self.assertIn(selector, css)

    def test_help_page_keeps_every_question_and_anchor(self):
        html = self.pages['ayuda.html']
        for anchor in ['reparacion-en-curso', 'reparacion-en-curso-pregunta', 'contacto']:
            with self.subTest(anchor=anchor):
                self.assertEqual(len(re.findall(rf'\bid="{anchor}"', html)), 1)
        self.assertEqual(len(re.findall(r'<details class="faq-item"', html)), 10)
        for href in re.findall(r'<a class="pg-tile" href="([^"]+)"', html):
            with self.subTest(tile=href):
                if href.startswith('#'):
                    self.assertIn(f'id="{href[1:]}"', html)
                else:
                    self.assertTrue((ROOT / href.split('?')[0].lstrip('/')).is_file())
        for contact in ['mailto:informacion@menigar.com', 'mailto:admon@menigar.com', 'tel:+34916622781', 'tel:+34916610397']:
            with self.subTest(contact=contact):
                self.assertIn(f'href="{contact}', html)


if __name__ == '__main__':
    unittest.main()
