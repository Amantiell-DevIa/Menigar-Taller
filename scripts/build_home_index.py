#!/usr/bin/env python3
"""Build the small, source-derived catalogue projection used by the home finder.

The home page needs only brand, model and component choices. The complete
catalogue remains the source for search results on servicios.html.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
CORE_FIELDS = ('uid', 'brand', 'model', 'componentKey')
GROUP_FIELDS = ('model', 'modelAliases', 'vehicleModel')


def project_records(catalogue):
    projected = []
    for record in catalogue:
        row = {key: record.get(key, '') for key in CORE_FIELDS}
        if record.get('coveredModels'):
            row['coveredModels'] = record['coveredModels']
        if record.get('modelGroups'):
            row['modelGroups'] = [
                {key: group[key] for key in GROUP_FIELDS if key in group}
                for group in record['modelGroups']
            ]
        projected.append(row)
    return projected


def write_home_index(catalogue, families, destination=DATA / 'home-index.js'):
    keys = {family['key'] for family in families}
    assert len(catalogue) == len({record['uid'] for record in catalogue})
    assert all(record['componentKey'] in keys for record in catalogue)
    payload = (
        '// Generated offline from data/catalogo-v2.json by scripts/build_home_index.py. Do not edit by hand.\n'
        'window.MENIGAR_FAMILIES = ' + json.dumps(families, ensure_ascii=False, separators=(',', ':')) + ';\n'
        'window.MENIGAR_CATALOG = ' + json.dumps(project_records(catalogue), ensure_ascii=False, separators=(',', ':')) + ';\n'
    )
    destination.write_text(payload, encoding='utf-8')
    return len(payload.encode('utf-8'))


def build():
    # Reuse the same family names and descriptions as the complete catalogue.
    from build_catalog import FAMILIES

    catalogue = json.loads((DATA / 'catalogo-v2.json').read_text(encoding='utf-8'))
    size = write_home_index(catalogue, FAMILIES)
    print(f'Generated {DATA / "home-index.js"}: {len(catalogue)} slim records, {size} bytes')


if __name__ == '__main__':
    build()
