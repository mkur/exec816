#!/usr/bin/env python3
"""INFO on an exact OF816 demo bundle: SIO standard or native IDE/VBXE."""
import argparse
import json
from pathlib import Path

from filesystem_audit import Audit
from native_program import require, sha256
from test_demo import run


def check(bundle):
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    expected = {}
    for filename, alias, label, readonly in (
            ('system.atr', 'SYSTEM' if manifest.get('ide_only') else 'D1', 'SYS', True),
            ('work.atr', 'WORK', 'WORK', False)):
        audit = Audit((bundle/filename).read_bytes())
        counts = audit.sdfs()
        require(bytes(audit.image.sector(1)[22:30]) == label.ljust(8).encode(), 'Demo volume label')
        total, free, size = counts['sectors'], counts['free'], audit.image.size
        expected[alias] = [f'{alias}: ({label})'.encode(),
            (f'  Size {total*size//1024}K Used {(total-free)*size//1024}K '
             f'Free {free*size//1024}K {"RO" if readonly else "RW"}').encode(),
            (f'  SpartaDOS {size}B '+('ideplus.device/'+str(1 if readonly else 2)
                if manifest.get('ide_only') else 'sio.device/D'+str(1 if readonly else 8))).encode()]
    expected['RAM'] = [b'RAM:', b'  Size dynamic Used 0K Free - RW', b'  RAM, volatile']
    primary = 'SYSTEM' if manifest.get('ide_only') else 'D1'
    def validate(command, screen):
        rows = (sum(expected.values(), []) if command in ('INFO', 'CAT RAM:INFO.TXT') else
                expected[primary] if command in ('INFO SYS:', 'INFO C:') else
                expected['WORK'] if command == 'INFO WORK:' else
                expected['RAM'] if command == 'INFO RAM:' else [])
        for row in rows:
            require(row in screen, f'{command}: missing {row!r}')
    result = run(bundle, boot_smoke=True, profile_commands=False,
        measurement_commands=['CLS', 'INFO SYS:', 'INFO WORK:', 'INFO C:',
                              'INFO RAM:', 'INFO', 'INFO >RAM:INFO.TXT', 'CAT RAM:INFO.TXT'],
        measurement_validate=validate)
    result.update(tier='development', runner_sha256=sha256(Path(__file__)),
                  bank_zero_delta=dict(fixed=0, per_task=0, idle=0))
    (bundle/'info-results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Packaged INFO passed', bundle, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    check(parser.parse_args().bundle.resolve())
