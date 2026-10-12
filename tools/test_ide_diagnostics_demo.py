"""Diagnostic builtin and redirection on an exact standard or VBXE OF816 demo."""
import argparse
import json
from pathlib import Path

from native_program import require, sha256
from test_demo import run


def check(bundle):
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    expected = [b'IDE CTRL      =DETECTED (PBI ID 0)', b'IDE SECTORS   =8192',
                b'IDE CAPACITY  =4 MiB (512B)', b'APT STATUS    =VALID',
                b'APT UNIT      =1 RO 512B', b'APT UNIT      =2 RW 512B']
    for partition in manifest['ide_mapping']['partitions']:
        expected.append(f"  LBA {partition['start']} SECTORS {partition['sectors']}".encode())

    def validate(command, screen):
        if command in ('MOUNT DIAGNOSTICS', 'CAT RAM:IDE.TXT'):
            for row in expected:
                require(row in screen, f'{command}: missing {row!r}')

    result = run(bundle, boot_smoke=True, profile_commands=False,
        measurement_commands=['CLS', 'MOUNT', 'MOUNT DIAGNOSTICS',
            'MOUNT DIAGNOSTICS >RAM:IDE.TXT', 'CLS', 'CAT RAM:IDE.TXT'],
        measurement_validate=validate)
    result.update(tier='development', runner_sha256=sha256(Path(__file__)))
    (bundle/'ide-diagnostics-results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Packaged IDE diagnostics passed', bundle, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    args = parser.parse_args()
    check(args.bundle.resolve())
