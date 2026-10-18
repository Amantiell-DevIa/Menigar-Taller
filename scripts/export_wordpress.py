#!/usr/bin/env python3
"""Archive public WordPress REST responses without changing WordPress or old captures.

No authentication, private collections, media-binary downloads or catalogue writes.
An export is complete only when pagination counts, IDs, hashes and final totals agree.
WordPress REST pagination is not a transactional snapshot; this is explicitly recorded.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
SITES = {
    'main': 'https://www.menigar.com/wp-json/wp/v2/',
    'abs': 'https://www.menigar.com/reparacion-abs/wp-json/wp/v2/',
}
COLLECTIONS = ('pages', 'posts', 'media')


def now():
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + '.part')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def public_get(url):
    """Bounded retries; only the two explicitly allowed public API roots."""
    if not any(url.startswith(root) for root in SITES.values()):
        raise ValueError('URL outside the public API allowlist')
    for attempt in range(3):
        try:
            req = Request(url, headers={'User-Agent': 'MENIGAR-public-content-archive/1.0',
                                        'Accept': 'application/json'})
            with urlopen(req, timeout=45) as response:
                final_url = response.geturl()
                if not any(final_url.startswith(root) for root in SITES.values()):
                    raise ValueError('Unexpected redirect outside the API allowlist')
                body = response.read(64 * 1024 * 1024 + 1)
                if len(body) > 64 * 1024 * 1024:
                    raise ValueError('Response exceeds 64 MiB')
                return body, {
                    'url': url, 'finalUrl': final_url, 'status': response.status,
                    'fetchedAt': now(), 'sha256': digest(body), 'bytes': len(body),
                    'total': response.headers.get('X-WP-Total'),
                    'totalPages': response.headers.get('X-WP-TotalPages'),
                    'etag': response.headers.get('ETag'),
                    'lastModified': response.headers.get('Last-Modified'),
                }
        except HTTPError as error:
            if error.code not in (429, 500, 502, 503, 504) or attempt == 2:
                raise
        except (URLError, TimeoutError):
            if attempt == 2:
                raise
        time.sleep(2 ** attempt)
    raise RuntimeError('Request failed')


def pagination(meta, per_page):
    try:
        total, pages = int(meta['total']), int(meta['totalPages'])
    except (TypeError, ValueError, KeyError):
        raise ValueError('Missing or invalid WordPress pagination headers')
    if total < 0 or pages != (total + per_page - 1) // per_page:
        raise ValueError('Inconsistent WordPress pagination headers')
    return total, pages


def stable_boundary_record(record):
    # Observed WPForms output includes request-dependent action URLs and token times.
    # Preserve the full response on disk, but omit whole generated form blocks when
    # comparing boundary records. Page metadata and all non-form HTML must still agree.
    result = dict(record)
    if isinstance(record.get('content'), dict):
        result['content'] = dict(record['content'])
        result['content']['rendered'] = re.sub(r'<form\b[^>]*>.*?</form\s*>',
                                              '[generated form omitted for stability comparison]',
                                              record['content'].get('rendered', ''), flags=re.I | re.S)
        # Contact Form 7 increments this wrapper counter across a paginated request.
        # Only the documented wrapper ID changes; ordinary text/numeric IDs stay intact.
        result['content']['rendered'] = re.sub(r'(\bid=["\']wpcf7-f\d+-o)\d+(["\'])',
                                              r'\g<1>COUNTER\2', result['content']['rendered'])
    return result


def archive_response(directory, filename, url, fetch, resume=False):
    path, metadata = directory / filename, directory / (filename + '.meta.json')
    if path.exists() or metadata.exists():
        if not resume or not path.is_file() or not metadata.is_file():
            raise ValueError('Existing archive requires a verified --resume: ' + str(path))
        meta = json.loads(metadata.read_text(encoding='utf-8'))
        body = path.read_bytes()
        if meta.get('url') != url or meta.get('sha256') != digest(body):
            raise ValueError('Cached response URL or integrity mismatch: ' + str(path))
    else:
        body, meta = fetch(url)
        # Decode before persisting, so an HTML error cannot become a JSON snapshot.
        json.loads(body)
        directory.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(path.suffix + '.part')
        temporary.write_bytes(body)
        temporary.replace(path)
        write_json(metadata, meta)
    return json.loads(body), meta


def export_collection(site, collection, output, per_page=50, resume=False, fetch=public_get):
    if site not in SITES or collection not in COLLECTIONS or not 1 <= per_page <= 100:
        raise ValueError('Unsupported public collection or page size')
    root = SITES[site] + collection
    query = {'per_page': per_page, 'orderby': 'id', 'order': 'asc', 'context': 'view'}
    directory = output / site / collection
    first_url = root + '?' + urlencode(dict(query, page=1))
    first, first_meta = archive_response(directory, 'page-0001.json', first_url, fetch, resume)
    total, pages = pagination(first_meta, per_page)
    records, responses = [], []
    for page in range(1, max(1, pages) + 1):
        if page == 1:
            rows, meta = first, first_meta
        else:
            url = root + '?' + urlencode(dict(query, page=page))
            rows, meta = archive_response(directory, 'page-%04d.json' % page, url, fetch, resume)
        if not isinstance(rows, list) or pagination(meta, per_page) != (total, pages):
            raise ValueError('Collection changed or invalid page during export')
        expected = min(per_page, total - (page - 1) * per_page)
        if len(rows) != expected:
            raise ValueError('Missing records in page %s/%s' % (page, pages))
        ids = [row.get('id') for row in rows if isinstance(row, dict)]
        if len(ids) != len(rows) or any(type(value) is not int for value in ids):
            raise ValueError('Invalid record ID')
        records.extend(rows)
        responses.append(dict(meta, path=str((directory / ('page-%04d.json' % page)).relative_to(output)),
                              count=len(rows)))
        print('%s/%s: %s/%s (%s registros)' % (site, collection, page, max(1, pages), len(records)), flush=True)
    ids = [row['id'] for row in records]
    if len(records) != total or len(set(ids)) != total or ids != sorted(ids):
        raise ValueError('Duplicate, missing or unordered IDs: %s/%s' % (site, collection))
    # Recheck both ends and the totals, without overwriting the captured first page.
    validations = []
    for order in ('asc', 'desc'):
        url = root + '?' + urlencode({'per_page': 1, 'orderby': 'id', 'order': order, 'context': 'view'})
        body, meta = fetch(url)
        rows = json.loads(body)
        # Keep the verification payload as well as its hash and collection headers.
        validation_path = directory / ('validation-' + order + '.json')
        # Revalidations may be rerun after an interrupted export. Their dated hashes
        # remain in the manifest for this completed run; original capture pages stay immutable.
        validation_path.write_bytes(body)
        write_json(directory / ('validation-' + order + '.meta.json'), meta)
        meta = dict(meta, path=str(validation_path.relative_to(output)))
        if pagination(meta, 1)[0] != total or not isinstance(rows, list):
            raise ValueError('Collection totals changed by the end of export')
        expected_id = (ids[0] if order == 'asc' else ids[-1]) if ids else None
        if (rows[0]['id'] if rows else None) != expected_id:
            raise ValueError('Collection boundary changed by the end of export')
        # Stable boundary content is additional evidence, not a database lock.
        if rows and stable_boundary_record(rows[0]) != stable_boundary_record(records[0] if order == 'asc' else records[-1]):
            raise ValueError('Boundary record content changed during export')
        validations.append(meta)
    result = {'site': site, 'collection': collection, 'complete': True, 'total': total,
              'totalPages': pages, 'perPage': per_page, 'responses': responses,
              'validationRequests': validations, 'checks': {
                  'headerCountsAgree': True, 'uniqueOrderedIds': True,
                  'recordCountMatchesTotal': True, 'finalTotalsAndBoundariesAgree': True,
                  'boundaryEqualityOmitsGeneratedFormBlocks': True,
                  'boundaryEqualityNormalizesContactForm7WrapperCounters': True, 'transactionalSnapshot': False}}
    write_json(directory / 'collection.json', result)
    return result


def export_site(site, output, per_page, resume):
    directory = output / site
    types, meta = archive_response(directory, 'types.json', SITES[site] + 'types', public_get, resume)
    if not isinstance(types, dict):
        raise ValueError('Invalid WordPress type discovery response')
    collections = [export_collection(site, collection, output, per_page, resume) for collection in COLLECTIONS]
    return {'site': site, 'apiRoot': SITES[site], 'typeDiscovery': dict(meta, path=site + '/types.json'),
            'discoveredTypes': {key: {'restBase': row.get('rest_base'), 'namespace': row.get('rest_namespace')}
                                for key, row in types.items()},
            'collections': collections, 'scope': 'Public pages, posts and attachment metadata only'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', default=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ'))
    parser.add_argument('--per-page', type=int, default=50)
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args()
    if not args.run or any(char not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-' for char in args.run):
        parser.error('Run ID must contain only letters, digits, underscores and hyphens')
    output = ROOT / 'data' / 'wordpress_exports' / args.run
    if output.exists() and not args.resume:
        parser.error('Run directory exists; choose a new ID or use --resume')
    if args.resume and (output / 'manifest.json').exists():
        parser.error('Completed export is immutable; use a new run ID')
    output.mkdir(parents=True, exist_ok=True)
    started = now()
    run_file = output / 'run.json'
    if args.resume and run_file.exists():
        previous = json.loads(run_file.read_text(encoding='utf-8'))
        if previous.get('perPage') != args.per_page or previous.get('sites') != SITES:
            parser.error('Resume must use the original page size and source roots')
        started = previous['startedAt']
    else:
        write_json(run_file, {'startedAt': started, 'perPage': args.per_page,
                              'sites': SITES, 'authenticated': False})
    try:
        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(lambda site: export_site(site, output, args.per_page, args.resume), SITES))
        manifest = {'schemaVersion': 1, 'runId': args.run, 'startedAt': started,
                    'finishedAt': now(), 'complete': True, 'authenticated': False, 'sites': results,
                    'limitations': [
                        'Complete means all public records in the selected REST collections, verified against their pagination headers.',
                        'This is not a full WordPress backup or a transactional database snapshot.',
                        'Boundary equality excludes generated form blocks with request-dependent action URLs and token times, and normalizes Contact Form 7 wrapper counters; complete original responses remain archived.',
                        'Private content, revisions, unexposed plugin fields, users, comments, form submissions, menus and theme settings are outside this export.',
                        'Media metadata and file URLs are archived; binary files are not downloaded.',
                        'Public content is evidence of what the source says, not technical or commercial approval.',
                    ]}
        write_json(output / 'manifest.json', manifest)
        if (output / 'failure.json').exists():
            # Keep the failure as history; do not leave a misleading active failure.
            (output / 'failure.json').replace(output / 'previous-failure.json')
        print(json.dumps({'run': str(output), 'complete': True,
                          'counts': {site['site']: {c['collection']: c['total'] for c in site['collections']} for site in results}}, ensure_ascii=False), flush=True)
    except Exception as error:
        write_json(output / 'failure.json', {'at': now(), 'error': str(error), 'complete': False})
        raise


if __name__ == '__main__':
    main()
