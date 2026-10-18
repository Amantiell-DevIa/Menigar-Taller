#!/usr/bin/env python3
"""Verify a completed public archive and prepare offline, traceable source documents.

Does not overwrite the live prototype catalogue or publish the captured copy.
Images, headings, table rows and module boundaries stay together as evidence;
their proximity never proves compatibility, a variant or a repair diagnosis.
"""
from __future__ import annotations

import argparse
import html
import json
import re
from collections import Counter, defaultdict
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urljoin, urlsplit, urlunsplit

from build_catalog import main_html, flat, taxonomy
from export_wordpress import ROOT, digest, now, write_json

VOID = {'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta', 'param', 'source', 'track', 'wbr'}
TEXT_TAGS = {'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'li', 'figcaption', 'blockquote'}
EDITOR_CONTAINERS = {'dslca-module-manage', 'dslca-module-options-front', 'dslca-module-code'}
CHANGE_SIGNALS = ('bodyTextChanged', 'bodyImagesChanged', 'bodyImageMetadataChanged',
                  'bodyTablesChanged', 'bodyHeadingsChanged', 'bodyLinksChanged', 'bodyEmbedsChanged')


class PublicBodyFilter(HTMLParser):
    """Remove observed Live Composer editor overlays, preserving editable copy.

    A blanket dslca-* filter would wrongly remove dslca-editable-content.
    Raw source responses remain untouched; this is only a derived-content filter.
    """
    def __init__(self):
        super().__init__(convert_charrefs=False)
        self.stack, self.output, self.removed = [], [], 0

    def handle_starttag(self, tag, attrs):
        classes = set(dict(attrs).get('class', '').split())
        inherited = self.stack[-1][1] if self.stack else False
        own_skip = bool(classes & EDITOR_CONTAINERS)
        skip = inherited or own_skip
        if own_skip and not inherited:
            self.removed += 1
        if not skip:
            self.output.append(self.get_starttag_text())
        if tag not in VOID:
            self.stack.append((tag, skip))

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i][0] == tag), None)
        if index is not None:
            skip = self.stack[index][1]
            self.stack = self.stack[:index]
            if not skip:
                self.output.append('</' + tag + '>')
        elif not self.stack or not self.stack[-1][1]:
            self.output.append('</' + tag + '>')

    def handle_data(self, data):
        if not self.stack or not self.stack[-1][1]:
            self.output.append(data)

    def handle_entityref(self, name):
        self.handle_data('&' + name + ';')

    def handle_charref(self, name):
        self.handle_data('&#' + name + ';')


def public_body(raw):
    parser = PublicBodyFilter()
    parser.feed(main_html(raw))
    return ''.join(parser.output), parser.removed


def url_key(value):
    parsed = urlsplit(html.unescape(value))
    if parsed.scheme not in ('https', 'http') or not parsed.netloc:
        return ''
    return urlunsplit(('https', parsed.netloc.lower(), parsed.path, '', ''))


class SourceBlocks(HTMLParser):
    """Ordered semantic inventory, never injected as HTML into the public website."""
    def __init__(self, base_url):
        super().__init__(convert_charrefs=True)
        self.base_url, self.stack, self.blocks, self.headings = base_url, [], [], []
        self.sequence = 0

    def context(self):
        module = next((frame['attrs'].get('id') for frame in reversed(self.stack)
                       if frame['attrs'].get('id', '').startswith('dslc-module-')), None)
        return {'sourceModuleId': module, 'precedingHeadings': list(self.headings)}

    def block(self, kind, **values):
        block = {'order': self.sequence, 'kind': kind, **self.context(), **values}
        self.sequence += 1
        self.blocks.append(block)
        return block

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        frame = {'tag': tag, 'attrs': attrs}
        if tag in TEXT_TAGS:
            frame['text'] = []
            frame['block'] = self.block('heading' if tag.startswith('h') and len(tag) == 2 else 'text', tag=tag)
        if tag == 'table':
            frame['block'] = self.block('table', rows=[])
        if tag == 'tr':
            frame['row'] = []
        if tag in ('td', 'th'):
            frame['cell'] = []
        if tag == 'a' and attrs.get('href'):
            frame['linkText'] = []
            frame['linkBlock'] = self.block('link', href=urljoin(self.base_url, attrs['href']), sourceHref=attrs['href'])
        if tag == 'img':
            value = attrs.get('src') or attrs.get('data-src', '')
            image = self.block('image', src=urljoin(self.base_url, value) if value else '', attributes=attrs)
            match = re.search(r'(?:^|\s)wp-image-(\d+)(?:\s|$)', attrs.get('class', ''))
            image['wordpressMediaIdHint'] = int(match[1]) if match else None
            image['urls'] = list(dict.fromkeys(
                urljoin(self.base_url, url) for url in
                [value, attrs.get('data-src', '')] + [part.strip().split()[0] for part in attrs.get('srcset', '').split(',') if part.strip()]
                if url and not url.startswith('data:')))
        if tag in ('iframe', 'video', 'audio', 'source') and attrs.get('src'):
            self.block('embed', tag=tag, src=urljoin(self.base_url, attrs['src']), attributes=attrs)
        if tag == 'br':
            self.handle_data(' ')
        if tag not in VOID:
            self.stack.append(frame)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def finish_frame(self, frame):
        tag = frame['tag']
        if 'text' in frame:
            text = ' '.join(''.join(frame['text']).split())
            frame['block']['text'] = text
            if tag in {'h1', 'h2', 'h3', 'h4', 'h5', 'h6'} and text:
                level = int(tag[1])
                self.headings = [heading for heading in self.headings if heading['level'] < level]
                self.headings.append({'level': level, 'text': text})
        if 'linkText' in frame:
            frame['linkBlock']['text'] = ' '.join(''.join(frame['linkText']).split())
        if 'cell' in frame:
            row = next((entry for entry in reversed(self.stack) if 'row' in entry), None)
            if row is not None:
                row['row'].append({'tag': tag, 'text': ' '.join(''.join(frame['cell']).split()),
                                   'colspan': frame['attrs'].get('colspan', '1'),
                                   'rowspan': frame['attrs'].get('rowspan', '1')})
        if 'row' in frame:
            table = next((entry for entry in reversed(self.stack) if entry['tag'] == 'table'), None)
            if table is not None:
                table['block']['rows'].append(frame['row'])

    def handle_endtag(self, tag):
        index = next((i for i in range(len(self.stack) - 1, -1, -1) if self.stack[i]['tag'] == tag), None)
        if index is not None:
            while len(self.stack) > index:
                self.finish_frame(self.stack.pop())

    def handle_data(self, data):
        for frame in self.stack:
            for key in ('text', 'cell', 'linkText'):
                if key in frame:
                    frame[key].append(data)

    def finish(self):
        while self.stack:
            self.finish_frame(self.stack.pop())
        return [block for block in self.blocks if block['kind'] not in ('text', 'heading') or block.get('text')]


def structure(page):
    raw, removed = public_body(page.get('content', {}).get('rendered', ''))
    reader = SourceBlocks(page.get('link', ''))
    reader.feed(raw)
    blocks = reader.finish()
    return {'bodyHtmlSha256': digest(raw.encode()), 'bodyText': flat(raw), 'blocks': blocks,
            'filteredEditorContainers': removed}


def load_archive(run):
    manifest = json.loads((run / 'manifest.json').read_text(encoding='utf-8'))
    if not manifest.get('complete'):
        raise ValueError('Incomplete archive')
    collections, captures = {}, {}
    def verified_payload(metadata):
        path = (run / metadata['path']).resolve()
        if run.resolve() not in path.parents or digest(path.read_bytes()) != metadata['sha256']:
            raise ValueError('Archive integrity or path mismatch: ' + str(path))
        return json.loads(path.read_bytes())
    for site in manifest['sites']:
        if site.get('typeDiscovery'):
            verified_payload(dict(site['typeDiscovery'], path=site['typeDiscovery'].get('path', site['site'] + '/types.json')))
        for collection in site['collections']:
            if collection.get('complete') is False:
                raise ValueError('Incomplete collection')
            for validation in collection.get('validationRequests', []):
                verified_payload(validation)
            key = (site['site'], collection['collection'])
            rows = []
            for response in collection['responses']:
                data = verified_payload(response)
                if len(data) != response['count']:
                    raise ValueError('Response count mismatch')
                rows.extend(data)
                for row in data:
                    captures[(site['site'], collection['collection'], row['id'])] = {
                        'responsePath': response['path'], 'responseSha256': response['sha256'],
                        'capturedAt': response['fetchedAt']}
            ids = [row['id'] for row in rows]
            if len(rows) != collection['total'] or len(set(ids)) != len(rows):
                raise ValueError('Collection integrity mismatch')
            collections[key] = rows
    return manifest, collections, captures


def media_index(rows):
    by_url = defaultdict(list)
    for media in rows:
        urls = [media.get('source_url', '')]
        urls.extend(size.get('source_url', '') for size in media.get('media_details', {}).get('sizes', {}).values())
        for url in set(urls):
            if url_key(url):
                by_url[url_key(url)].append(media['id'])
    return by_url


def compare_page(old, page):
    if old is None:
        return {'state': 'added', 'changes': []}
    old_html, new_html = old.get('content', {}).get('rendered', ''), page.get('content', {}).get('rendered', '')
    changes = [field for field in ('slug', 'link', 'parent', 'title') if old.get(field) != page.get(field)]
    if old_html != new_html:
        changes.append('renderedHtml')
    old_body, _ = public_body(old_html)
    new_body, _ = public_body(new_html)
    body_text_changed = flat(old_body) != flat(new_body)
    # Compare images and tables even when the visible text is identical.
    a, b = structure(old), structure(page)
    images = lambda record: [url_key(block['src']) for block in record['blocks'] if block['kind'] == 'image']
    image_meta = lambda record: [{key: block['attributes'].get(key, '') for key in ('alt', 'title', 'srcset')}
                                  for block in record['blocks'] if block['kind'] == 'image']
    tables = lambda record: [block['rows'] for block in record['blocks'] if block['kind'] == 'table']
    headings = lambda record: [(block['tag'], block['text']) for block in record['blocks'] if block['kind'] == 'heading']
    links = lambda record: [(block['href'], block.get('text', '')) for block in record['blocks'] if block['kind'] == 'link']
    embeds = lambda record: [(block['tag'], block['src']) for block in record['blocks'] if block['kind'] == 'embed']
    return {'state': 'changed' if changes else 'unchanged', 'changes': changes,
            'bodyTextChanged': body_text_changed, 'bodyImagesChanged': images(a) != images(b),
            'bodyImageMetadataChanged': image_meta(a) != image_meta(b),
            'bodyTablesChanged': tables(a) != tables(b), 'bodyHeadingsChanged': headings(a) != headings(b),
            'bodyLinksChanged': links(a) != links(b), 'bodyEmbedsChanged': embeds(a) != embeds(b),
            'legacyHtmlSha256': digest(old_html.encode()), 'currentHtmlSha256': digest(new_html.encode())}


def audit(run):
    manifest, collections, captures = load_archive(run)
    output = run / 'prepared'
    output.mkdir(exist_ok=True)
    current_catalog = {row['uid']: row for row in json.loads((ROOT / 'data/catalogo-v2.json').read_text())}
    old = {}
    legacy_hashes = {}
    baseline_hashes = json.loads((ROOT / 'data/catalogo-report.json').read_text())['snapshotSha256']
    for site, folder in [('main', 'cache'), ('abs', 'cache_abs')]:
        for path in sorted((ROOT / 'data' / folder).glob('*.json')):
            relative = str(path.relative_to(ROOT))
            legacy_hashes[relative] = digest(path.read_bytes())
            if baseline_hashes.get(relative) != legacy_hashes[relative]:
                raise ValueError('Legacy snapshot differs from the existing catalogue baseline: ' + relative)
            old.update({(site, row['id']): row for row in json.loads(path.read_text())})
    index, comparisons, issues, binaries = [], [], [], {}
    site_stats = {}
    for site in ('main', 'abs'):
        media_rows = collections[(site, 'media')]
        media_lookup = media_index(media_rows)
        used_media = set()
        for collection in ('pages', 'posts'):
            for page in collections[(site, collection)]:
                uid = site + '-' + str(page['id'])
                source = structure(page)
                row = current_catalog.get(uid) if collection == 'pages' else None
                comparison = compare_page(old.get((site, page['id'])), page) if collection == 'pages' else {'state': 'not-in-legacy-pages'}
                comparisons.append({'uid': uid, 'collection': collection, 'url': page.get('link'), **comparison})
                counts = Counter(block['kind'] for block in source['blocks'])
                unmatched = []
                for block in source['blocks']:
                    if block['kind'] == 'image':
                        ids = sorted({mid for url in block['urls'] for mid in media_lookup.get(url_key(url), [])})
                        block['matchedMediaIdsByUrl'] = ids
                        used_media.update(ids)
                        if not ids:
                            unmatched.append(block['src'])
                        for url in block['urls']:
                            key = url_key(url)
                            if not key:
                                continue
                            entry = binaries.setdefault(key, {'url': key, 'kind': 'image', 'usedBy': []})
                            if uid not in entry['usedBy']:
                                entry['usedBy'].append(uid)
                    elif block['kind'] == 'link':
                        url = block['href']
                        if re.search(r'\.(?:pdf|docx?|xlsx?|zip)(?:$|[?#])', url, re.I):
                            key = url_key(url)
                            if key:
                                entry = binaries.setdefault(key, {'url': key, 'kind': 'document', 'usedBy': []})
                                if uid not in entry['usedBy']:
                                    entry['usedBy'].append(uid)
                title = flat(page.get('title', {}).get('rendered', ''))
                family = taxonomy(site, page.get('link', ''), title)[0] if collection == 'pages' else None
                flags = []
                if row:
                    if counts['image'] and not row.get('contentPilot'):
                        flags.append('source-images-not-in-public-detail-template')
                    if counts['table'] and not row.get('contentPilot') and not row.get('isInstruction'):
                        flags.append('source-table-layout-needs-review')
                    if counts['image'] > 1 and not row.get('contentPilot'):
                        flags.append('catalogue-has-only-first-image-field')
                if unmatched:
                    flags.append('some-image-urls-not-matched-to-current-site-media-api')
                if any(comparison.get(field) for field in CHANGE_SIGNALS):
                    flags.append('fresh-source-content-needs-comparison')
                record = {
                    'uid': uid, 'source': site, 'sourceId': page['id'], 'collection': collection,
                    'url': page.get('link'), 'title': title, 'slug': page.get('slug'),
                    'parentId': page.get('parent'), 'modified': page.get('modified'),
                    'modifiedGmt': page.get('modified_gmt'), 'featuredMediaId': page.get('featured_media'),
                    'seo': page.get('yoast_head_json', {}), 'excerpt': page.get('excerpt'),
                    'sourceHtmlSha256': digest(page.get('content', {}).get('rendered', '').encode()),
                    'capture': captures[(site, collection, page['id'])],
                    'componentKeyCandidate': family, 'currentCatalogUid': row['uid'] if row else None,
                    'reviewStatus': 'unreviewed-public-source',
                    'contextRule': 'Module IDs and preceding headings identify source position; they do not establish fit or interchangeability.',
                    **source,
                }
                relative = Path('documents') / site / (collection + '-' + str(page['id']) + '.json')
                write_json(output / relative, record)
                entry = {'uid': uid, 'collection': collection, 'source': site, 'sourceId': page['id'],
                         'url': page.get('link'), 'title': title, 'modifiedGmt': page.get('modified_gmt'),
                         'document': str(relative), 'sourceHtmlSha256': record['sourceHtmlSha256'],
                         'componentKeyCandidate': family, 'inCurrentCatalog': bool(row),
                         'currentLocalPath': row.get('localPath') if row else None,
                         'currentIsAggregator': row.get('isAggregator') if row else None,
                         'filteredEditorContainers': source['filteredEditorContainers'],
                         'counts': dict(counts), 'flags': flags}
                index.append(entry)
                if flags:
                    issues.append(entry)
        site_stats[site] = {'pages': len(collections[(site, 'pages')]), 'posts': len(collections[(site, 'posts')]),
                            'media': len(media_rows), 'mimeTypes': dict(Counter(r.get('mime_type', '') for r in media_rows)),
                            'mediaIdsMatchedInPageImages': len(used_media),
                            'mediaIdsNotMatchedInPageImages': len(media_rows) - len(used_media)}
        # This media inventory retains original alt/caption/parent without propagating it as approved copy.
        write_json(output / ('media-' + site + '.json'), media_rows)
    fresh_ids = {(site, row['id']) for site in ('main', 'abs') for row in collections[(site, 'pages')]}
    missing = [{'uid': site + '-' + str(identifier), 'url': page.get('link')}
               for (site, identifier), page in old.items() if (site, identifier) not in fresh_ids]
    for path, sha in legacy_hashes.items():
        if digest((ROOT / path).read_bytes()) != sha:
            raise ValueError('Legacy snapshot changed during analysis')
    report = {'schemaVersion': 1, 'runId': manifest['runId'], 'preparedAt': now(),
              'archiveVerified': True, 'sourceSites': site_stats,
              'legacySnapshotSha256': legacy_hashes, 'legacySnapshotsUnchanged': True,
              'pageComparisonCounts': dict(Counter(r['state'] for r in comparisons)),
              'changeSignals': {field: sum(bool(row.get(field)) for row in comparisons) for field in CHANGE_SIGNALS},
              'missingFromPublicPages': missing, 'documents': len(index),
              'documentsWithImages': sum(bool(r['counts'].get('image')) for r in index),
              'documentsWithTables': sum(bool(r['counts'].get('table')) for r in index),
              'documentsWithFilteredEditorControls': sum(bool(r['filteredEditorContainers']) for r in index),
              'cataloguePageFlags': dict(Counter(flag for r in index if r['inCurrentCatalog'] for flag in r['flags'])),
              'distinctImageUrls': sum(r['kind'] == 'image' for r in binaries.values()),
              'distinctDocumentUrls': sum(r['kind'] == 'document' for r in binaries.values()),
              'appliedToPublicCatalogue': False,
              'answerAutomationConnected': False,
              'limitations': manifest['limitations'] + [
                  'Content signals are automatic comparisons, not proof of an editorial change or error.',
                  'Table cells remain in order with colspan/rowspan; references are not matched to photos by proximity.',
                  'Image inventory includes source banners and decorative images requiring selection.',
                  'Semantic blocks exclude navigation, forms, scripts, styles and the Live Composer footer; the full rendered response remains in the archive.',
                  'Observed Live Composer editor overlays are removed by exact container class; dslca-editable-content is retained.',
                  'CSS background images and unrendered shortcode/plugin data are not interpreted as semantic image blocks.',
                  'URLs outside the media API are inventoried but neither fetched nor declared missing files.',
                  'Unmatched media may be unused, decorative or referenced elsewhere; it is not declared orphaned.',
                  'Prepared documents retain unapproved source statements; they are not ready-to-send customer answers.',
              ]}
    write_json(output / 'index.json', index)
    write_json(output / 'comparison.json', comparisons)
    write_json(output / 'review-queue.json', issues)
    write_json(output / 'binary-url-inventory.json', sorted(binaries.values(), key=lambda row: row['url']))
    write_json(output / 'report.json', report)
    print(json.dumps({key: report[key] for key in ('runId', 'sourceSites', 'pageComparisonCounts', 'changeSignals', 'documents',
                                                   'documentsWithImages', 'documentsWithTables', 'cataloguePageFlags',
                                                   'distinctImageUrls', 'distinctDocumentUrls')}, ensure_ascii=False, indent=2))
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True, help='Completed run ID under data/wordpress_exports')
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run):
        parser.error('Invalid run ID')
    audit(ROOT / 'data/wordpress_exports' / args.run)
