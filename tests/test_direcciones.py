"""URL parity (2 Nov 2026): the new website answers at the addresses of www.menigar.com.

A ficha answers at the address of its WordPress page and a general page at the address of the page it
replaces. data/redirects.json holds only the old addresses that change, each with its reason, and
vercel.json applies those 301s on the preview while keeping the prototype's former addresses working.
"""
from html import unescape
import json
from pathlib import Path
import re
import sys
import unittest
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from site_paths import FICHA_PATH, GENERAL_PAGES, OLDER_PROTOTYPE_PAGES, WORDPRESS_DROPPED, prototype_path

# The names the prototype used before its pages took their WordPress addresses.
FORMER = re.compile(r'/(?:reparaciones/|(?:index|servicios|como-funciona|garantia|sobre-nosotros|ayuda|privacidad|cookies|condiciones|envios|taller)\.html)')


def served(address):
    """The file that answers an address of the new website, or None."""
    path = urlsplit(address).path
    target = ROOT / path.lstrip('/')
    if path.endswith('/'):
        target = target / 'index.html'
    return target if target.is_file() else None


class UrlParityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rows = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        cls.report = json.loads((ROOT / 'data/catalogo-report.json').read_text())
        cls.redirects = json.loads((ROOT / 'data/redirects.json').read_text())
        cls.vercel = json.loads((ROOT / 'vercel.json').read_text())
        cls.pages = {row['localPath'] for row in cls.rows} | {page['path'] for page in GENERAL_PAGES} | {'/'}

    def test_every_wordpress_page_keeps_its_address_or_has_a_decision(self):
        by_path = {entry['fromPath']: entry for entry in self.redirects}
        wordpress = [row['url'] for row in self.rows] + [entry['url'] for entry in self.report['excluded']]
        # All the pages of both WordPress installations: 831 of the main site and 840 of the ABS one.
        self.assertEqual(len(wordpress), sum(self.report['sourcePageCounts'].values()))
        outcome = {'kept': 0, 'redirected': 0, 'dropped': 0}
        for url in wordpress:
            path = urlsplit(url).path
            with self.subTest(url=url):
                if path in self.pages:
                    self.assertIsNotNone(served(path))
                    outcome['kept'] += 1
                elif path in by_path:
                    self.assertIsNotNone(served(by_path[path]['to']))
                    outcome['redirected'] += 1
                else:
                    self.assertIn(path, WORDPRESS_DROPPED)
                    outcome['dropped'] += 1
        # The fichas, the home and seven general pages keep their address; the six merged copies and
        # fourteen pages without an equivalent redirect; only the WordPress error page disappears.
        self.assertEqual(outcome, {'kept': len(self.rows) + 8, 'redirected': 20, 'dropped': 1})

    def test_each_redirect_leads_to_a_page_in_one_step(self):
        sources = {entry['fromPath'] for entry in self.redirects}
        self.assertEqual(len(sources), len(self.redirects))
        for entry in self.redirects:
            with self.subTest(source=entry['fromPath']):
                self.assertIsNone(served(entry['fromPath']), 'A redirect never hides a page.')
                self.assertIsNotNone(served(entry['to']))
                self.assertNotIn(urlsplit(entry['to']).path, sources, 'No chain of redirects.')
                self.assertTrue(entry['reason'])

    def test_the_preview_applies_the_same_redirects_and_keeps_the_prototype_links(self):
        self.assertIs(self.vercel['trailingSlash'], True, 'Like WordPress, /envios leads to /envios/.')
        items = {item['source']: item for item in self.vercel['redirects']}
        self.assertEqual(len(items), len(self.vercel['redirects']))
        self.assertTrue(all(item['statusCode'] == 301 and 'permanent' not in item for item in items.values()))
        for entry in self.redirects:
            self.assertEqual(items[entry['fromPath']]['destination'], entry['to'])
        prototype = {prototype_path(row): row['localPath'] for row in self.rows}
        prototype.update({page['prototype']: page['path'] for page in GENERAL_PAGES})
        prototype.update(OLDER_PROTOTYPE_PAGES)
        prototype.update({entry['formerLocalPath']: next(row['localPath'] for row in self.rows if row['uid'] == entry['mergedInto'])
                          for entry in self.report['excluded'] if entry.get('mergedInto')})
        for source, destination in prototype.items():
            with self.subTest(source=source):
                self.assertEqual(items[source]['destination'], destination)
                self.assertIsNone(served(source), 'Only the redirect remains of a prototype address.')
        self.assertEqual(len(items), len(self.redirects) + len(prototype))
        self.assertLessEqual(len(items), 2000, 'A Vercel deployment accepts 2,048 routes.')
        self.assertTrue(all(served(item['destination']) for item in items.values()))

    def test_internal_links_use_the_new_addresses_and_reach_a_page(self):
        documents = [ROOT / name for name in ['index.html', 'solicitud.html', 'opciones-hero.html', 'laboratorio.html']]
        documents += [served(path) for path in sorted(self.pages - {'/'})]
        ids = {}
        problems = []
        for document in documents:
            for href in re.findall(r'\b(?:href|action)="(/[^"/][^"]*|/)"', document.read_text()):
                href = unescape(href)
                parts = urlsplit(href)
                if FORMER.match(parts.path):
                    problems.append((document.relative_to(ROOT).as_posix(), href, 'prototype name'))
                elif not served(parts.path):
                    problems.append((document.relative_to(ROOT).as_posix(), href, 'no page'))
                elif parts.fragment and parts.path in {page['path'] for page in GENERAL_PAGES} | {'/'} and document.name != 'opciones-hero.html':
                    # A link to a section of a general page needs that section. The hero designs of
                    # opciones-hero.html point at old homepage sections; laboratorio.js re-points them.
                    if parts.path not in ids:
                        ids[parts.path] = set(re.findall(r'\bid="([^"]+)"', served(parts.path).read_text()))
                    if parts.fragment not in ids[parts.path]:
                        problems.append((document.relative_to(ROOT).as_posix(), href, 'no section'))
        self.assertEqual(problems, [])

    def test_fichas_link_to_the_pages_above_them_like_wordpress(self):
        """WordPress linked every page to its parent; the breadcrumb keeps those links to the brand and family pages."""
        addresses = {row['localPath'] for row in self.rows}
        linked = 0
        for row in self.rows:
            parts = row['localPath'].strip('/').split('/')
            above = [path for path in ('/' + '/'.join(parts[:depth]) + '/' for depth in range(1, len(parts))) if path in addresses]
            crumb = re.search(r'<nav class="breadcrumb"[^>]*>(.*?)</nav>', served(row['localPath']).read_text(), re.S).group(1)
            with self.subTest(path=row['localPath']):
                self.assertEqual(re.findall(r'href="([^"]+)"', crumb), ['/', '/servicios/', *above])
            linked += bool(above)
        # 1,549 of the 1,642 fichas have a WordPress page above them.
        self.assertEqual(linked, 1549)

    def test_sitemap_and_canonicals_use_the_wordpress_addresses(self):
        locs = re.findall(r'<loc>([^<]+)</loc>', (ROOT / 'sitemap.xml').read_text())
        self.assertEqual(len(locs), len(set(locs)))
        self.assertTrue(all(loc.startswith('https://www.menigar.com/') for loc in locs))
        self.assertEqual({urlsplit(loc).path for loc in locs}, self.pages)
        for path in sorted(self.pages):
            with self.subTest(path=path):
                self.assertIn(f'<link rel="canonical" href="https://www.menigar.com{path}">', served(path).read_text())

    def test_every_server_and_build_serves_the_same_addresses(self):
        self.assertTrue(all(FICHA_PATH.fullmatch(row['localPath']) for row in self.rows))
        shape = FICHA_PATH.pattern.lstrip('/')
        for name in ['servidor.py', 'backend/dev-router.php', 'backend/review-router.php',
                     'scripts/build_vercel_static.cjs', 'scripts/build_review_package.py']:
            source = (ROOT / name).read_text()
            with self.subTest(file=name):
                for page in GENERAL_PAGES:
                    self.assertIn("'" + page['path'][1:] + "'", source)
                self.assertNotIn('reparaciones/', source.replace('reparaciones.css', ''))
                if name != 'scripts/build_review_package.py':
                    # The review package copies the fichas the catalogue lists; the others check their shape.
                    self.assertTrue(shape in source or shape.replace('/', '\\/') in source)


if __name__ == '__main__':
    unittest.main()
