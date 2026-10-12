"""Focused emitted mount failure snapshots and recovery over real ATA PIO."""
import argparse
import json
from pathlib import Path

from generate_memory import PROFILE
from native_program import ROOT, build, compiler, execute, read_build, require
from generate_dos_mounts import encode
from ideplus_media import filesystem_fixture, sdfs_image
from filesystem_audit import Audit
from test_ideplus import ide_emulator
from test_cooperative import data
from test_heap_api import clean_ownership


def run(out, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    atr = sdfs_image(ROOT/'tests/fixtures/filesystem-write/sdfs-256.atr', out/'stage.atr')
    audit = Audit(atr)
    mounts = [dict(alias='IDE', device='ideplus.device', unit=2, profile=0,
                   format=2, sectors=audit.image.count, sector_bytes=512),
              dict(alias='RAM', format=3)]
    profile=out/'profile.json'
    memory=json.loads(PROFILE.read_text()); memory['image_data_bytes']=4096
    profile.write_text(json.dumps(memory))
    p = read_build(out) if reuse else build(compiler(ROOT/'build/actionc', release=True),
        ROOT/'tests/programs/ide_diagnostics_mount.act', out, optimize=True,
        tasks=True, task_capacity=8, console_deferred=True, memory_profile=profile, dos_mounts=mounts)
    for name, error, stage in [('valid', 0, 0), ('count', -4, 7),
            ('protected', 4, 8), ('missing-slot', -1, 4), ('bad-header', 225, 10),
            ('no-controller', -1, 4), ('no-disk', -1, 4)]:
        dest = out/name
        dest.mkdir(exist_ok=True)
        raw, mapping = filesystem_fixture(atr)
        configured = [dict(m) for m in mounts]
        if name == 'count': configured[0]['sectors'] -= 1
        if name == 'protected': configured[0]['access'] = 'readwrite'
        if name == 'missing-slot': configured[0]['unit'] = 1
        if name == 'bad-header': raw[mapping['start']*512+32] = 0
        disk = dest/'ide.img'
        disk.write_bytes(raw)
        with ide_emulator(dest, disk, absent=name == 'no-controller',
                          missing_disk=name == 'no-disk') as b:
            def before(b):
                b.memload(p['build']['task_storage']['BASE']+0x900, encode(configured))
                for field, value, width in [('EXPECTEDERROR', error, 4), ('EXPECTEDSTAGE', stage, 1)]:
                    address = next(d['address'] for d in p['image']['data']
                                   if '_IDEDIAGNOSTICSMOUNT_'+field+'_' in d['name'])
                    b.memload(address, value.to_bytes(width, 'little', signed=value < 0))
            try: runtime, _ = execute(b, p, before_run=before, timeout=90, frame_limit=4500)
            except Exception:
                print(name, 'checks', data(b, p['image'], 'checks', True),
                      'failure', data(b, p['image'], 'failure', False), flush=True)
                raise
            clean_ownership(b, p, out)
            checks = data(b, p['image'], 'checks', True)
        require(disk.read_bytes() == raw, 'Mount diagnostics modified disk')
        (dest/'results.json').write_text(json.dumps(dict(status='pass', tier='development',
            build=p['build'], runtime=runtime, checks=checks), indent=2)+'\n')
        print('IDE mount diagnostics passed', name, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/ide-diagnostics/mount')
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    run(args.output, args.reuse)
