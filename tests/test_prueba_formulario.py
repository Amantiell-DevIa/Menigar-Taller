"""The upload package of the test form (12-11-2026): what travels, where it points, and what never travels."""
import re
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import build_prueba_formulario as package  # noqa: E402


class TestFormPackageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory(prefix='menigar-paquete-')
        cls.root = Path(cls.temp.name) / 'paquete'
        cls.manifest = package.build(cls.root)
        cls.public = cls.root / 'httpdocs/pruebas'

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_every_local_address_in_the_pages_exists_in_the_package(self):
        for page in ['solicitud.html', 'resumen.html']:
            html = (self.public / page).read_text()
            for value in re.findall(r'(?:href|src)="(/[^"#?]*)', html) + [u for s in re.findall(r'srcset="([^"]+)"', html) for u in re.findall(r'(/\S+)', s)]:
                self.assertTrue(value.startswith('/pruebas/'), (page, value))
                self.assertTrue((self.root / 'httpdocs' / value.lstrip('/')).is_file(), (page, value))
        css = (self.public / 'style.css').read_text()
        for value in re.findall(r'url\("?(/[^")]+)', css):
            self.assertTrue((self.root / 'httpdocs' / value.lstrip('/')).is_file(), value)

    def test_the_logo_for_sharp_screens_points_to_the_test_folder(self):
        # On 11-11 only src was rewritten; phones and Macs asked WordPress for the 2x logo and got a 404.
        html = (self.public / 'solicitud.html').read_text()
        self.assertIn('srcset="/pruebas/assets/marca/menigar-logo-2x.webp 2x, /pruebas/assets/marca/menigar-logo-3x.webp 3x"', html)

    def test_pages_that_do_not_travel_open_on_the_new_site_preview(self):
        html = (self.public / 'solicitud.html').read_text()
        self.assertIn('href="https://menigar-taller.vercel.app/politica-de-privacidad/"', html)
        self.assertIn('href="https://menigar-taller.vercel.app/servicios/"', html)

    def test_server_rules_close_listing_hide_from_google_and_pass_the_login_to_php(self):
        rules = (self.public / '.htaccess').read_text()
        self.assertIn('Options -Indexes', rules)
        self.assertIn('X-Robots-Tag "noindex, nofollow"', rules)
        self.assertIn('Referrer-Policy "same-origin"', rules)
        self.assertIn('E=HTTP_AUTHORIZATION:%{HTTP:Authorization}', rules)
        self.assertIn('RewriteRule ^(?:api|equipo)(?:/|$) api/index.php', rules)
        self.assertIn('DirectoryIndex solicitud.html', rules)
        self.assertEqual((self.public / 'robots.txt').read_text(), 'User-agent: *\nDisallow: /\n')

    def test_api_entry_reads_code_and_settings_from_outside_the_public_folder(self):
        entry = (self.public / 'api/index.php').read_text()
        self.assertIn('define(\'MENIGAR_APP_ROOT\', "/var/www/vhosts/menigar.com/pruebas.menigar.com");', entry)
        self.assertIn('/private/config-subpath.php', entry)

    def test_no_settings_secret_catalogue_or_public_team_access_travels(self):
        names = set(self.manifest['files'])
        self.assertFalse([n for n in names if Path(n).name.startswith('config')])
        self.assertFalse([n for n in names if n.startswith('httpdocs/pruebas/') and ('/reparacion' in n or n.endswith('index.html'))])
        for name in names:
            if name.endswith(('.webp', '.woff2', '.ico', '.png')):
                continue
            text = (self.root / name).read_text(errors='ignore')
            self.assertNotIn('publicStaffAccess', text, name)
            self.assertNotIn('serveCatalogFallback', text, name)
            if name.startswith('httpdocs/'):
                self.assertNotIn('$2y$', text, name)

    def test_the_package_refuses_a_page_that_points_to_a_missing_file(self):
        rewriter = package.Rewriter('/pruebas', 'https://example.invalid', {'style.css'})
        rewriter.html('<img src="/assets/no-existe.webp">')
        self.assertEqual(rewriter.missing, ['/assets/no-existe.webp'])


if __name__ == '__main__':
    unittest.main()
