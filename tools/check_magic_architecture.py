#!/usr/bin/env python3
"""Check the pinned MagiC source model, source locators and documentation links."""
import argparse
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import unquote
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
RECORD = ROOT/'docs/development/magic-architecture.json'


def require(okay, message):
    if not okay:
        raise RuntimeError(message)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def local_links(path):
    text = path.read_text()
    require(len(re.findall(r'^```', text, re.M)) % 2 == 0,
            'Unclosed code fence: '+str(path))
    targets = re.findall(r'(?<!!)\[[^\]]*\]\(([^\s)]+)(?:\s+"[^"]*")?\)', text)
    definitions = dict(re.findall(r'^\[([^\]]+)\]:\s+(\S+)\s*$', text, re.M))
    targets += list(definitions.values())
    # All shortcut reference citations used by this page must be defined.
    if path.name == 'magic.md':
        refs = set(re.findall(r'(?<![\w!])\[([A-Z][A-Z0-9]+)\](?![(:\[])', text))
        require(refs <= definitions.keys(), 'Undefined source references: '+str(refs-definitions.keys()))
    count = 0
    for raw in targets:
        if re.match(r'[a-z]+://|mailto:', raw):
            continue
        target, _, anchor = unquote(raw).partition('#')
        dest = (path.parent/target).resolve() if target else path
        require(dest.exists(), f'Missing link in {path}: {raw}')
        if anchor and dest.suffix == '.md':
            content = dest.read_text()
            slugs = [re.sub(r'[^\w\- ]', '', h.lower()).replace(' ', '-')
                     for h in re.findall(r'^#+\s+(.+)$', content, re.M)]
            require(anchor in slugs or 'id="'+anchor+'"' in content,
                    f'Missing anchor in {path}: {raw}')
        count += 1
    return count, definitions


def check(fetch=False):
    record = json.loads(RECORD.read_text())
    pin = json.loads((ROOT/'toolchain/atari-st-reference.json').read_text())
    require(record['magic_revision'] == pin['magic']['revision'], 'MagiC revision differs from pin')
    require(record['qualification'] is False, 'Static source model must not claim qualification')
    object_source = next(row for row in record['sources'] if row['id'] == 'AESOBJ')
    require(object_source['sha256'] == pin['magic']['object_source']['sha256'],
            'Object source differs from the existing reference pin')
    sources = {}
    for row in record['sources']:
        path = ROOT/row['local_path']
        require('ref='+record['magic_revision'] in row['url'], 'Unpinned source URL')
        if not path.exists():
            require(fetch, 'Missing source; use --fetch: '+str(path))
            with urlopen(row['url'], timeout=60) as response:
                data = response.read()
            require(digest(data) == row['sha256'], 'Downloaded source differs: '+row['path'])
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        data = path.read_bytes()
        require(digest(data) == row['sha256'], 'Changed source: '+row['path'])
        sources[row['id']] = data.decode(row['encoding']).replace('\r\n', '\n').replace('\r', '\n')

    selected = {}
    for row in record['ranges']:
        lines = sources[row['source']].split('\n')
        require(1 <= row['first'] <= row['last'] <= len(lines), 'Invalid range: '+row['id'])
        text = '\n'.join(lines[row['first']-1:row['last']])
        require(digest(text.encode()) == row['normalized_sha256'], 'Changed range: '+row['id'])
        require(row['locator'] in text, 'Missing range locator: '+row['id'])
        selected[row['id']] = text

    for row in record['source_checks']:
        text = selected[row['range']]
        for marker in row.get('contains', []):
            require(marker in text, 'Missing structural marker: '+row['id']+' '+marker)
        for marker in row.get('absent', []):
            require(marker not in text, 'Unexpected structural marker: '+row['id']+' '+marker)
        offset = 0
        for marker in row.get('ordered', []):
            index = text.find(marker, offset)
            require(index >= 0, 'Changed selected call order: '+row['id']+' '+marker)
            offset = index+len(marker)

    for row in record['claims']:
        require(row['ranges'] and set(row['ranges']) <= selected.keys(), 'Untraced model claim: '+row['id'])
        require(row['kind'] in ('source-observation', 'structural-summary'), 'Unknown claim kind')

    pages = [ROOT/name for name in record['documentation_pages']]
    links = 0
    definitions = {}
    for path in pages:
        count, refs = local_links(path)
        links += count
        if path.name == 'magic.md':
            definitions = refs
            require(record['magic_revision'] in path.read_text(), 'Model omits revision')
    for row in record['sources']:
        if row['id'] in definitions:
            require(definitions[row['id']] == row['browse_url'], 'Changed source citation: '+row['id'])
    require(set(definitions) <= {row['id'] for row in record['sources']}, 'Unpinned source citation')

    result = dict(status='pass', tier='documentation', qualification=False,
        sources=len(sources), ranges=len(selected), source_checks=len(record['source_checks']),
        claims=len(record['claims']), pages=len(pages), local_links=links,
        evidence_sha256=digest(RECORD.read_bytes()), checker_sha256=digest(Path(__file__).read_bytes()),
        model_sha256=digest((ROOT/'docs/architecture/magic.md').read_bytes()))
    output = ROOT/'build/magic-architecture/checks.json'
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--fetch', action='store_true', help='Download missing hash-pinned source files')
    check(parser.parse_args().fetch)
