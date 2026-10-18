#!/usr/bin/env python3
"""Prepare exact legacy media routes from the verified local manifests, offline."""
import json
from pathlib import Path
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[1]


def routes():
    media = json.loads((ROOT / 'data/media-local-manifest.json').read_text())
    documents = json.loads((ROOT / 'data/documentos-local-manifest.json').read_text())
    result = {}
    entries = list(media['urlIndex'].items()) + [(d['sourcePath'], d['localPath']) for d in documents]
    for source, target in entries:
        source = unquote(urlsplit(source).path)
        if not source.startswith(('/wp-content/uploads/', '/reparacion-abs/wp-content/uploads/', '/docs/')):
            raise ValueError('Unexpected source: ' + source)
        if not target.startswith(('/assets/media/', '/assets/documentos/')) or '..' in target or '?' in target or '#' in target:
            raise ValueError('Unexpected target: ' + target)
        if not (ROOT / target.lstrip('/')).is_file():
            raise FileNotFoundError(target)
        if source in result and result[source] != target:
            raise ValueError('Conflicting source: ' + source)
        result[source] = target
    return dict(sorted(result.items()))


if __name__ == '__main__':
    result = routes()
    (ROOT / 'data/legacy-media-routes.json').write_text(json.dumps(result, ensure_ascii=False, separators=(',', ':')) + '\n')
    print(json.dumps({'exactLegacyMediaRoutes': len(result), 'activation': 'proposed, not deployed'}))
