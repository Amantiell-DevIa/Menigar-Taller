#!/usr/bin/env python3
"""Write the old addresses that change: data/redirects.json and the redirects of vercel.json.

data/redirects.json lists every address of www.menigar.com whose page no longer answers there, with
the reason: the 301s to enable on menigar.com at the migration, disabled until then. vercel.json
applies the same 301s on the preview and keeps the prototype's former addresses (/reparaciones/...,
/como-funciona.html...) working, so links already shared still open their page.
Run from any directory: python3 scripts/build_redirects.py (scripts/build_catalog.py also runs it).
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from site_paths import (GENERAL_PAGES, OLDER_PROTOTYPE_PAGES, WORDPRESS_DROPPED, WORDPRESS_OTHER,
                        WORDPRESS_PAGES, prototype_path)

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
ORIGIN = 'https://www.menigar.com'
# A Vercel deployment accepts 2,048 routes, these redirects included; the headers and the
# trailing-slash rule take a few more.
VERCEL_REDIRECT_LIMIT = 2000


def wordpress_redirects(catalogue, excluded, aliases):
    """The WordPress addresses that change, from the pages left out of the catalogue and the aliases."""
    by_uid = {row['uid']: row for row in catalogue}
    by_path = {row['localPath']: row for row in catalogue}
    served = set(by_path) | {page['path'] for page in GENERAL_PAGES} | {'/', '/sitemap.xml'}
    kept = {page['wordpress'] for page in GENERAL_PAGES if page['wordpress']} | {'/'}
    merged_into = {entry['uid']: by_uid[entry['mergedInto']] for entry in excluded if entry.get('mergedInto')}
    entries = []

    def add(url, to, kind, reason, **extra):
        target = by_path.get(urlsplit(to).path)
        entries.append({'from': url, 'fromPath': urlsplit(url).path, 'to': to, 'status': 301, 'kind': kind, 'reason': reason,
                        **({'uid': target['uid']} if target else {}), **extra, 'enabled': False, 'reviewRequired': True})

    used = set()
    for entry in excluded:
        path = urlsplit(entry['url']).path
        if entry.get('mergedInto'):
            add(entry['url'], merged_into[entry['uid']]['localPath'], 'merged-copy',
                'Copia de otra página: se une a su ficha más completa.', mergedFrom=entry['uid'])
        elif path in WORDPRESS_PAGES:
            add(entry['url'], *WORDPRESS_PAGES[path])
            used.add(path)
        elif path not in kept and path not in WORDPRESS_DROPPED:
            raise ValueError('WordPress page without a decision: ' + entry['url'])
    if used != set(WORDPRESS_PAGES):
        raise ValueError('Decision for a page WordPress does not have: ' + ', '.join(sorted(set(WORDPRESS_PAGES) - used)))
    for path, (to, kind, reason) in WORDPRESS_OTHER.items():
        add(ORIGIN + path, to, kind, reason)
    # Old addresses that WordPress itself sends to a page today, found in the links of its own content.
    for alias in aliases:
        target = by_uid.get(alias.get('resolvedUid')) or merged_into.get(alias.get('resolvedUid'))
        if alias.get('resolution') == 'restored-wordpress-page-id' and target:
            add(alias['originalUrl'], target['localPath'], 'wordpress-redirect',
                'Dirección antigua que WordPress ya redirige a esta página; se mantiene la 301.')
    entries.sort(key=lambda entry: entry['fromPath'])
    sources = [entry['fromPath'] for entry in entries]
    if len(sources) != len(set(sources)):
        raise ValueError('An old address has two destinations')
    for entry in entries:
        if entry['fromPath'] in served:
            raise ValueError('A redirect would hide a page: ' + entry['fromPath'])
        if urlsplit(entry['to']).path not in served:
            raise ValueError('A redirect leads to an address without a page: ' + entry['to'])
    return entries


def vercel_redirects(catalogue, excluded, redirects):
    """The 301s of the preview: the WordPress ones, then the prototype's former addresses."""
    by_uid = {row['uid']: row for row in catalogue}
    pairs = [(entry['fromPath'], entry['to']) for entry in redirects]
    pairs += [(page['prototype'], page['path']) for page in GENERAL_PAGES] + list(OLDER_PROTOTYPE_PAGES.items())
    pairs += [(entry['formerLocalPath'], by_uid[entry['mergedInto']]['localPath']) for entry in excluded if entry.get('mergedInto')]
    pairs += sorted((prototype_path(row), row['localPath']) for row in catalogue)
    items = [{'source': source, 'destination': destination, 'statusCode': 301} for source, destination in pairs]
    sources = [item['source'] for item in items]
    if len(sources) != len(set(sources)):
        raise ValueError('vercel.json: an address has two destinations')
    # Literal paths only: Vercel reads :, *, ( and similar characters in a source as a pattern.
    if not all(re.fullmatch(r'/[a-z0-9_./-]*', source) for source in sources):
        raise ValueError('vercel.json: a source is not a plain path')
    if len(items) > VERCEL_REDIRECT_LIMIT:
        raise ValueError(f'vercel.json: {len(items)} redirects, more than Vercel accepts')
    return items


def write_vercel(items):
    path = ROOT / 'vercel.json'
    # Only the redirects are generated; the rest of the file is written by hand.
    block = '"redirects": [\n' + ',\n'.join('    { ' + json.dumps(item, ensure_ascii=False)[1:-1] + ' }' for item in items) + '\n  ]'
    text, count = re.subn(r'"redirects": \[.*?\n  \]', lambda _: block, path.read_text(encoding='utf-8'), flags=re.S)
    if count != 1:
        raise ValueError('vercel.json: redirects block not found')
    # Like WordPress, an address without its final slash leads to the one with it (Vercel answers 308).
    if json.loads(text).get('trailingSlash') is not True:
        raise ValueError('vercel.json must keep "trailingSlash": true')
    path.write_text(text, encoding='utf-8')


def write_redirects(catalogue, excluded):
    aliases = json.loads((DATA / 'legacy-link-resolution.json').read_text(encoding='utf-8'))['links']
    redirects = wordpress_redirects(catalogue, excluded, aliases)
    (DATA / 'redirects.json').write_text(json.dumps(redirects, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    items = vercel_redirects(catalogue, excluded, redirects)
    write_vercel(items)
    return redirects, items


if __name__ == '__main__':
    catalogue = json.loads((DATA / 'catalogo-v2.json').read_text(encoding='utf-8'))
    excluded = json.loads((DATA / 'catalogo-report.json').read_text(encoding='utf-8'))['excluded']
    redirects, items = write_redirects(catalogue, excluded)
    print(f'data/redirects.json: {len(redirects)} direcciones de WordPress que cambian · vercel.json: {len(items)} redirecciones')
