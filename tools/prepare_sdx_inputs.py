#!/usr/bin/env python3
"""Recover the pinned MD5 and ARC originals without modifying distributions."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, require, sha256
from sdx_patch import manifests, select
from test_sdx_md5 import inputs


def prepare(out, nomarch):
    md5, arc = out/'md5', out/'arc'
    records = inputs(md5, nomarch)
    arc.mkdir(parents=True, exist_ok=True)
    audit = json.loads((ROOT/'docs/plans/spartados-personality-inputs.json').read_text())
    app = next(a for a in audit['applications'] if a['id'] == 'arc')
    cartridge = (md5/'SDX450_maxflash1.car').read_bytes()
    catalog = manifests(ROOT/'compat/sdx')
    for module in app['modules']:
        # Frozen CAR file offsets exclude each bank's boot/vector trailer.
        # This is extraction of one SHA-pinned distribution, not a CAR: driver.
        raw = b''.join(cartridge[offset:offset+length]
                       for offset, length in module['cartridge_ranges'])
        require(len(raw) == module['bytes'], 'Truncated cartridge module')
        _, selected = select(raw, catalog)
        require(selected['file'] == module['file'], 'Wrong cartridge module')
        path = arc/module['file']
        if path.exists():
            require(path.read_bytes() == raw, 'Existing input differs: '+str(path))
        else:
            path.write_bytes(raw)
        records[path.name] = dict(bytes=len(raw), sha256=sha256(path), crc32=selected['crc32'])
    (out/'inputs.json').write_text(json.dumps(records, indent=2)+'\n')
    return records


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/sdx-inputs')
    parser.add_argument('--nomarch', type=Path, default=ROOT/'build/research/s2-vbxe/nomarch-1.4/nomarch')
    args = parser.parse_args()
    prepare(args.output.resolve(), args.nomarch.resolve())
    print('Pinned SDX inputs ready:', args.output, flush=True)
