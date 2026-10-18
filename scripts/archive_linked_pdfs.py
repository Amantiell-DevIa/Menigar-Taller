#!/usr/bin/env python3
"""Archive and extract public PDFs explicitly linked by the prepared source pages.

Requires pypdf. Does not fetch every WordPress attachment or execute PDF actions.
Original binaries and per-page text stay separate from approved website content.
"""
from __future__ import annotations

import argparse
import io
import json
import posixpath
import re
from pathlib import Path
from urllib.parse import unquote, urlsplit
from urllib.request import Request, urlopen

from export_wordpress import ROOT, digest, now, write_json


def allowed(url):
    parsed = urlsplit(url)
    path = posixpath.normpath(unquote(parsed.path))
    return (parsed.scheme == 'https' and parsed.netloc == 'www.menigar.com'
            and any(path.startswith(prefix) for prefix in ('/docs/', '/wp-content/uploads/', '/reparacion-abs/wp-content/uploads/'))
            and path.lower().endswith('.pdf'))


def archive(run):
    from pypdf import PdfReader
    inventory = json.loads((run / 'prepared/binary-url-inventory.json').read_text())
    linked = [row for row in inventory if row['kind'] == 'document' and unquote(urlsplit(row['url']).path).lower().endswith('.pdf')]
    output = run / 'linked-pdfs'
    output.mkdir(exist_ok=True)
    files, failures = [], []
    for entry in linked:
        url = entry['url']
        try:
            if not allowed(url):
                raise ValueError('Outside the public PDF allowlist')
            stem = digest(url.encode())[:12] + '-' + re.sub(r'[^A-Za-z0-9._-]', '-', unquote(urlsplit(url).path.rsplit('/', 1)[-1]))
            path = output / stem
            metadata_path = output / (stem + '.json')
            if path.exists() or metadata_path.exists():
                if not path.is_file() or not metadata_path.is_file():
                    raise ValueError('Incomplete existing PDF capture')
                metadata = json.loads(metadata_path.read_text())
                body = path.read_bytes()
                if metadata.get('sha256') != digest(body) or metadata.get('url') != url:
                    raise ValueError('Existing PDF capture integrity mismatch')
            else:
                with urlopen(Request(url, headers={'User-Agent': 'MENIGAR-public-document-archive/1.0'}), timeout=30) as response:
                    if not allowed(response.geturl()):
                        raise ValueError('Unexpected PDF redirect')
                    body = response.read(20 * 1024 * 1024 + 1)
                    if len(body) > 20 * 1024 * 1024 or b'%PDF-' not in body[:1024]:
                        raise ValueError('Not a PDF or exceeds 20 MiB')
                    metadata = {'url': url, 'finalUrl': response.geturl(), 'fetchedAt': now(),
                                'sha256': digest(body), 'bytes': len(body), 'usedBy': entry['usedBy'],
                                'path': stem, 'lastModified': response.headers.get('Last-Modified')}
                reader = PdfReader(io.BytesIO(body))
                if reader.is_encrypted or len(reader.pages) > 300:
                    raise ValueError('Encrypted PDF or too many pages')
                pages = [{'page': i + 1, 'text': page.extract_text() or ''} for i, page in enumerate(reader.pages)]
                fields = reader.get_fields() or {}
                metadata.update({'pageCount': len(pages), 'textPages': pages,
                                 'fieldNamesAndTypes': [{'name': name, 'type': str(field.get('/FT', ''))} for name, field in fields.items()],
                                 'reviewStatus': 'unreviewed-public-source',
                                 'textExtractionOnly': True, 'ocrApplied': False,
                                 'pagesWithoutExtractableText': [page['page'] for page in pages if not page['text'].strip()]})
                temporary = path.with_suffix('.pdf.part')
                temporary.write_bytes(body)
                temporary.replace(path)
                write_json(metadata_path, metadata)
            files.append({key: metadata[key] for key in ('url', 'path', 'sha256', 'bytes', 'pageCount', 'usedBy', 'pagesWithoutExtractableText')})
            print('PDF: %s (%s páginas)' % (stem, metadata['pageCount']), flush=True)
        except Exception as error:
            failures.append({'url': url, 'error': str(error), 'usedBy': entry['usedBy'],
                             'httpStatus': getattr(error, 'code', None)})
    manifest = {'generatedAt': now(), 'scope': 'PDFs explicitly linked in the prepared page bodies',
                'complete': not failures, 'files': files, 'failures': failures,
                'limitations': ['Not all WordPress media binaries are downloaded.',
                                'Per-page text and field names are extracted, without OCR or technical approval.',
                                'Original documents may contain outdated instructions; they are not published or used as current defaults.']}
    write_json(output / 'manifest.json', manifest)
    if failures:
        raise ValueError('Some linked PDFs could not be archived; see linked-pdfs/manifest.json')
    return manifest


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', required=True)
    args = parser.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9_-]+', args.run):
        parser.error('Invalid run ID')
    archive(ROOT / 'data/wordpress_exports' / args.run)
