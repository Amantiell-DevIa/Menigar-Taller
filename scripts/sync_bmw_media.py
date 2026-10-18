#!/usr/bin/env python3
"""Download only the images associated with main-2321 in the public archive."""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from bmw_source import UID, MEDIA_PREFIX, RUN, extract_bmw

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data' / 'bmw-media-manifest.json'
MAX_BYTES = 10 * 1024 * 1024


def sync():
    source = extract_bmw(ROOT)
    wanted = {image['downloadUrl']: image for image in source['gallery']}
    previous = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'files': []}
    old = {item['downloadUrl']: item for item in previous['files']}

    def download(item):
        target = ROOT / item['localPath'].lstrip('/')
        cached = old.get(item['downloadUrl'])
        if cached and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == cached['sha256']:
            return cached
        fetched = item['downloadUrl']
        try:
            def open_url(url):
                return urlopen(Request(url, headers={'User-Agent': 'MENIGAR-Source-Expansion/1.0'}), timeout=25)
            try:
                response = open_url(fetched)
            except HTTPError as error:
                if error.code != 404 or fetched == item['originalSrc']:
                    raise
                fetched = item['originalSrc']
                response = open_url(fetched)
            with response:
                if not response.geturl().startswith(MEDIA_PREFIX):
                    raise ValueError('BMW media redirected outside the original uploads directory')
                blob = response.read(MAX_BYTES + 1)
                mime = response.headers.get_content_type()
            if len(blob) > MAX_BYTES:
                raise ValueError('BMW media exceeds the file limit')
            if not (blob.startswith(b'\xff\xd8\xff') or blob.startswith(b'\x89PNG\r\n\x1a\n') or (blob[:4] == b'RIFF' and blob[8:12] == b'WEBP')):
                raise ValueError('BMW source did not return a supported image')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.part')
            temporary.write_bytes(blob)
            temporary.replace(target)
            return {**item, 'fetchedUrl': fetched, 'sourceUids': [UID], 'sha256': hashlib.sha256(blob).hexdigest(),
                    'bytes': len(blob), 'mime': mime, 'downloadedAt': datetime.now(timezone.utc).isoformat()}
        except Exception as error:
            return {'downloadUrl': item['downloadUrl'], 'error': str(error)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, wanted.values()))
    failures = [item for item in results if 'error' in item]
    files = [item for item in results if 'error' not in item]
    MANIFEST.write_text(json.dumps({'scope': [UID], 'captureRun': RUN, 'sourceHtmlSha256': source['sourceHtmlSha256'],
                                    'files': files, 'failures': failures}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'referencedFiles': len(wanted), 'availableFiles': len(files), 'bytes': sum(item['bytes'] for item in files), 'failures': failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    sync()
