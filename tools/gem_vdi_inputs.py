#!/usr/bin/env python3
"""Fetch or verify the selected, immutable GEM4XE inputs for the hosted port."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import urllib.request

from os_boundary import ROOT, require, sha256

MANIFEST = ROOT/'ports/gem4xe/inputs.json'


def source_inputs(directory, fetch=False):
    manifest = json.loads(MANIFEST.read_text())
    directory = Path(directory).resolve()
    records = {}
    for name, record in manifest['files'].items():
        path = directory/name
        require(path.resolve().is_relative_to(directory), 'Source path escapes checkout')
        if not path.exists() and fetch:
            url = ('https://raw.githubusercontent.com/slaapliedje/gem4xe/'
                   + manifest['revision'] + '/' + name)
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = response.read()
            require(hashlib.sha256(payload).hexdigest() == record['sha256'],
                    'Downloaded GEM source differs: '+name)
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(payload)
        require(path.is_file(), 'Missing GEM input (use --fetch): '+str(path))
        require(sha256(path) == record['sha256'], 'Changed GEM input: '+name)
        records[name] = record
    return records


def local_inputs():
    manifest = json.loads(MANIFEST.read_text())
    for key in ('actionc_pin', 'platform_pin'):
        require(sha256(ROOT/manifest[key]) == manifest[key+'_sha256'], 'Changed '+key)
    calypsi = manifest['calypsi']
    paths = {}
    for name, record in calypsi['tools'].items():
        path = shutil.which(name)
        require(path is not None, 'Missing Calypsi tool: '+name)
        path = Path(path).resolve()
        require(sha256(path) == record['sha256'], 'Changed Calypsi tool: '+name)
        paths[name] = str(path)
    runtime = Path(paths['cc65816']).parent.parent/'lib'/calypsi['runtime']['name']
    require(sha256(runtime) == calypsi['runtime']['sha256'], 'Changed Calypsi runtime')
    return dict(calypsi_paths=paths, runtime_path=str(runtime), manifest_sha256=sha256(MANIFEST))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, default=ROOT/'build/gem-vdi/upstream')
    parser.add_argument('--fetch', action='store_true', help='Download missing pinned files only')
    args = parser.parse_args()
    sources = source_inputs(args.source, args.fetch)
    local_inputs()
    print(f'GEM inputs verified: {len(sources)} source/notice files and local toolchain pins')


if __name__ == '__main__':
    main()
