"""The Content-Security-Policy admits stylesheets and scripts from the site only (2 Nov 2026).

vercel.json, the PHP service and the local server send that rule, so a page that works locally also works on
the preview. Until that day the local server allowed inline styles, and every ficha carried an inline <style>
that Vercel blocked without anyone noticing.
"""
import importlib.util
import json
from pathlib import Path
import re
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from site_paths import GENERAL_PAGES

spec = importlib.util.spec_from_file_location('menigar_server_csp', ROOT / 'servidor.py')
server_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_module)

INLINE_STYLE = re.compile(r'<style[\s>]|\sstyle="')
# A data block such as JSON-LD is never executed, so the CSP lets it through.
INLINE_SCRIPT = re.compile(r'<script(?![^>]*\s(?:src=|type="application/ld\+json"))[^>]*>')


def vercel_csp():
    config = json.loads((ROOT / 'vercel.json').read_text())
    return next(header['value'] for rule in config['headers'] for header in rule['headers']
                if header['key'] == 'Content-Security-Policy')


class ContentSecurityPolicyTests(unittest.TestCase):
    def test_every_server_sends_the_strict_policy(self):
        csp = vercel_csp()
        for directive in ["style-src 'self';", "script-src 'self';"]:
            with self.subTest(directive=directive):
                self.assertIn(directive, csp)
        self.assertNotIn("'unsafe-inline'", csp)
        self.assertEqual(server_module.load_csp(), csp, 'El servidor local manda la misma CSP que Vercel.')
        php = re.search(r'Content-Security-Policy: ([^"]+)"', (ROOT / 'backend/Http.php').read_text()).group(1)
        self.assertIn("style-src 'self';", php)
        self.assertNotIn("'unsafe-inline'", php)

    def test_no_page_carries_inline_styles_or_scripts(self):
        rows = json.loads((ROOT / 'data/catalogo-v2.json').read_text())
        pages = [row['localPath'] for row in rows] + [page['path'] for page in GENERAL_PAGES] + ['/']
        files = [ROOT / path.lstrip('/') / 'index.html' for path in pages]
        files += [ROOT / name for name in sorted(server_module.STATIC_ROOT_FILES) if name.endswith('.html')]
        self.assertGreater(len(files), 1650)
        for file in files:
            html = file.read_text()
            with self.subTest(page=file.relative_to(ROOT).as_posix()):
                self.assertNotRegex(html, INLINE_STYLE)
                self.assertNotRegex(html, INLINE_SCRIPT)


if __name__ == '__main__':
    unittest.main()
