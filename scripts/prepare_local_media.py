#!/usr/bin/env python3
"""Build a portable media library from the verified external backup, offline.

This never downloads from WordPress. Original binaries remain in the backup;
the generated manifest preserves every occurrence and all observed relations.
Requires Pillow only when rebuilding the optimized library.
"""
from __future__ import annotations
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import shutil
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
PREPARED = ROOT / 'data/wordpress_exports/2026-10-13-publico/prepared'
BACKUP = Path('/Users/kaykostar/Documents/MENIGAR/respaldo-web-2026-10-14')
DESTINATION = ROOT / 'assets/media'
MANIFEST = ROOT / 'data/media-local-manifest.json'
# Replaced by the new site's own interface. All omissions remain inventoried.
DECORATIVE_NAMES = {'ventajas-150x150.png', 'icons.jpg', 'circuito_animado-277x130.gif',
                    'senal_peligro-150x150.png'}


def key(url):
    parsed = urlsplit(url)
    if parsed.hostname not in {'menigar.com', 'www.menigar.com'}:
        return None
    return unquote(parsed.path)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def decorative(url):
    parsed = urlsplit(url)
    if parsed.hostname == 'lh3.googleusercontent.com' or (parsed.hostname == 's.w.org' and '/emoji/' in parsed.path):
        return True
    name = unquote(urlsplit(url).path.rsplit('/', 1)[-1]).lower()
    return name in DECORATIVE_NAMES or bool(re.search(r'^(?:logo[_-]|banner[_-]|google[_-]|estrellas[_-]|trabaja_con)', name))


def build():
    from PIL import Image, ImageOps
    source_files = {}
    with (BACKUP / 'control/archivos-copiados.jsonl').open() as stream:
        for line in stream:
            row = json.loads(line)
            if row['status'] == 'copied':
                source_files['/' + row['path'].removeprefix('httpdocs/')] = row
    metadata = {}
    for source in ('main', 'abs'):
        for item in json.loads((PREPARED / ('media-' + source + '.json')).read_text()):
            urls = [item.get('source_url', '')] + [s.get('source_url', '') for s in item.get('media_details', {}).get('sizes', {}).values()]
            for url in urls:
                if key(url):
                    metadata[(source, key(url))] = item
    files, by_content, url_index, occurrences, missing, omitted = [], {}, {}, [], [], []
    resolved = {}

    def resolve(source, url):
        path = key(url)
        cache_key = (source, path)
        if cache_key in resolved:
            return resolved[cache_key]
        item = metadata.get(cache_key, {})
        candidates = [item.get('source_url', ''), url]
        candidates += [s.get('source_url', '') for s in sorted(item.get('media_details', {}).get('sizes', {}).values(), key=lambda s: -s.get('width', 0))]
        selected = next(((candidate, source_files[key(candidate)]) for candidate in candidates if key(candidate) in source_files), None)
        if selected is None:
            resolved[cache_key] = None
            return None
        chosen_url, backup_row = selected
        original = BACKUP / backup_row['local_path']
        digest = sha(original)
        if digest != backup_row['sha256']:
            raise ValueError('Source binary differs from the verified backup: ' + backup_row['path'])
        if digest not in by_content:
            stem = re.sub(r'[^a-z0-9]+', '-', unquote(urlsplit(chosen_url).path.rsplit('/', 1)[-1]).rsplit('.', 1)[0].lower()).strip('-')[:65] or 'imagen'
            folder = DESTINATION / digest[:2]
            folder.mkdir(parents=True, exist_ok=True)
            entry = {'sourceSha256': digest, 'backupPath': backup_row['path'],
                     'sourceBytes': original.stat().st_size, 'chosenSourceUrl': chosen_url,
                     'wordpressMediaId': item.get('id'), 'sourceInstallation': source}
            suffix = original.suffix.lower()
            if suffix == '.svg':
                text = original.read_text()
                if re.search(r'<script|onload=|<foreignObject|(?:href|url)\s*[=(]\s*[\"\']?https?:', text, re.I):
                    raise ValueError('SVG needs manual review')
                target = folder / (digest[:16] + '-' + stem + '.svg')
                shutil.copyfile(original, target)
                entry['format'] = 'SVG'
            else:
                with Image.open(original) as im:
                    image = ImageOps.exif_transpose(im)
                    entry['sourceWidth'], entry['sourceHeight'] = image.size
                    if getattr(im, 'is_animated', False):
                        target = folder / (digest[:16] + '-' + stem + suffix)
                        shutil.copyfile(original, target)
                        entry['format'] = im.format
                    else:
                        image.thumbnail((1600, 1600), Image.Resampling.LANCZOS)
                        if image.mode not in ('RGB', 'RGBA'):
                            image = image.convert('RGBA' if 'transparency' in image.info else 'RGB')
                        target = folder / (digest[:16] + '-' + stem + '.webp')
                        if not target.exists():
                            image.save(target, 'WEBP', quality=90, method=5, lossless=suffix in {'.png', '.gif'})
                        entry.update({'format': 'WEBP', 'width': image.width, 'height': image.height})
            entry.update({'localPath': '/' + str(target.relative_to(ROOT)), 'bytes': target.stat().st_size, 'sha256': sha(target)})
            files.append(entry)
            by_content[digest] = entry
        entry = by_content[digest]
        resolved[cache_key] = entry
        # Preserve observed URL plus aliases only from the matching installation.
        aliases = [url, chosen_url, item.get('source_url', '')]
        aliases += [s.get('source_url', '') for s in item.get('media_details', {}).get('sizes', {}).values()]
        for alias in aliases:
            if key(alias):
                old = url_index.setdefault(key(alias), entry['localPath'])
                if old != entry['localPath']:
                    raise ValueError('An old URL resolved to two different binaries')
        return entry

    for index, document_path in enumerate(sorted((PREPARED / 'documents').glob('*/*.json'))):
        document = json.loads(document_path.read_text())
        for block in document['blocks']:
            if block['kind'] != 'image':
                continue
            context = {'sourceUid': document['uid'], 'sourceUrl': document['url'],
                       'sourceModuleId': block['sourceModuleId'], 'sourceOrder': block['order'],
                       'precedingHeadings': block['precedingHeadings'], 'originalSrc': block['src'],
                       'sourceAlt': block.get('attributes', {}).get('alt', ''),
                       'matchedMediaIds': block.get('matchedMediaIdsByUrl', [])}
            if decorative(block['src']):
                omitted.append({**context, 'reason': 'Legacy decoration, review avatar or emoji; excluded from the service photo library'})
                continue
            try:
                entry = resolve(document['source'], block['src'])
            except (ValueError, OSError) as error:
                entry = None
                context['errorType'] = type(error).__name__
            if entry:
                occurrences.append({**context, 'localPath': entry['localPath'], 'sourceSha256': entry['sourceSha256']})
            else:
                missing.append(context)
        if index and index % 300 == 0:
            print('Documentos revisados:', index, 'archivos propios:', len(files), flush=True)
    report = {'schemaVersion': 1, 'source': 'verified-external-backup', 'networkUsed': False,
              'optimization': {'maxDimensions': [1600, 1600], 'jpegWebpQuality': 90, 'pngConversion': 'lossless', 'originalsPreservedInBackup': True},
              'files': files, 'urlIndex': url_index, 'occurrences': occurrences,
              'omitted': omitted, 'missing': missing,
              'totals': {'files': len(files), 'imageOccurrences': len(occurrences), 'omittedOccurrences': len(omitted),
                         'missingOccurrences': len(missing), 'sourceBytes': sum(f['sourceBytes'] for f in files),
                         'outputBytes': sum(f['bytes'] for f in files)},
              'bySource': dict(Counter(row['sourceUid'].split('-')[0] for row in occurrences))}
    MANIFEST.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(json.dumps(report['totals'], ensure_ascii=False, indent=2))


if __name__ == '__main__':
    build()
