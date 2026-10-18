#!/usr/bin/env python3
"""Download only media explicitly referenced by the two Hyundai pilot pages.

Public GET requests, maximum three concurrent transfers, no WordPress login,
no page modifications and no full-site crawl. Re-running verifies cached files.
"""
from __future__ import annotations

import hashlib
import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from build_catalog import main_html
from pilot_hyundai import PILOT_IDS, MEDIA_PREFIX, extract_pilot

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / 'data' / 'hyundai-media-manifest.json'
MAX_BYTES = 10 * 1024 * 1024


def sync():
    pages = {}
    for path in (ROOT / 'data' / 'cache').glob('*.json'):
        for page in json.loads(path.read_text()):
            uid = 'main-' + str(page['id'])
            if uid in PILOT_IDS:
                pages[uid] = page
    pilot = extract_pilot(pages, main_html)
    wanted = {}
    for uid, value in pilot.items():
        for image in value['images']:
            entry = wanted.setdefault(image['downloadUrl'], {**image, 'sourceUids': []})
            if uid not in entry['sourceUids']:
                entry['sourceUids'].append(uid)
    old = json.loads(MANIFEST.read_text()) if MANIFEST.exists() else {'files': []}
    old_by_url = {item['downloadUrl']: item for item in old['files']}

    def download(item):
        target = ROOT / item['localPath'].lstrip('/')
        previous = old_by_url.get(item['downloadUrl'])
        if previous and target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == previous['sha256']:
            return {**previous, 'sourceUids': item['sourceUids']}
        fetched_url = item['downloadUrl']
        try:
            request = Request(fetched_url, headers={'User-Agent': 'MENIGAR-Content-Pilot/1.0'})
            try:
                response = urlopen(request, timeout=25)
            except HTTPError as error:
                if error.code != 404 or item['originalSrc'] == fetched_url:
                    raise
                fetched_url = item['originalSrc']
                response = urlopen(Request(fetched_url, headers={'User-Agent': 'MENIGAR-Content-Pilot/1.0'}), timeout=25)
            with response:
                if not response.geturl().startswith(MEDIA_PREFIX):
                    raise ValueError('Unexpected media redirect outside the source uploads directory')
                blob = response.read(MAX_BYTES + 1)
                mime = response.headers.get_content_type()
            if len(blob) > MAX_BYTES:
                raise ValueError('Media exceeds the pilot file limit')
            is_image = blob.startswith(b'\xff\xd8\xff') or blob.startswith(b'\x89PNG\r\n\x1a\n') or (blob[:4] == b'RIFF' and blob[8:12] == b'WEBP')
            if not is_image:
                raise ValueError('The source did not return a supported image')
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = target.with_suffix(target.suffix + '.part')
            temporary.write_bytes(blob)
            temporary.replace(target)
            return {
                'downloadUrl': item['downloadUrl'], 'fetchedUrl': fetched_url, 'originalSrc': item['originalSrc'],
                'originalSrcset': item['originalSrcset'], 'localPath': item['localPath'],
                'sourceUids': item['sourceUids'], 'sha256': hashlib.sha256(blob).hexdigest(),
                'bytes': len(blob), 'mime': mime, 'downloadedAt': datetime.now(timezone.utc).isoformat(),
            }
        except Exception as error:
            return {'downloadUrl': item['downloadUrl'], 'error': str(error)}

    with ThreadPoolExecutor(max_workers=3) as pool:
        results = list(pool.map(download, wanted.values()))
    failures = [item for item in results if 'error' in item]
    files = [item for item in results if 'error' not in item]
    MANIFEST.write_text(json.dumps({'scope': sorted(PILOT_IDS), 'files': files, 'failures': failures}, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps({'referencedFiles': len(wanted), 'availableFiles': len(files), 'bytes': sum(item['bytes'] for item in files), 'failures': failures}, ensure_ascii=False, indent=2))
    if failures:
        raise SystemExit(1)


if __name__ == '__main__':
    sync()
