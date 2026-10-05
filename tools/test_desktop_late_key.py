#!/usr/bin/env python3
"""A/B the observed late-key ROM chain on one frozen pre-fix raw image."""
import argparse
import json
from pathlib import Path
from native_program import require, read_build, sha256
from test_desktop_apps import run as applications


def run(out, program):
    out.mkdir(parents=True, exist_ok=True)
    p = read_build(program)
    require(not p['build']['optimize'], 'The frozen reproducer is raw')
    record = dict(tier='development', qualification=False, build=p['build'], cases=[])
    for corrected in (False, True):
        observed = {}
        def prepare(b, native):
            start = native['labels']['signal_route']
            raw = b.memdump(start, 192)
            pattern = bytes.fromhex('49ff2f10000029fe')
            require(raw.count(pattern) == 1, 'Not the frozen pre-fix classifier')
            address = start+raw.index(pattern)+len(pattern)-1
            # This fixture always retains the keyboard lease while sampling.
            # Both runs perform the same one-byte bootstrap write. The final
            # production code additionally checks keyboard lease activation.
            b.memload(address, bytes([0x3e if corrected else 0xfe]))
            observed.update(address=address, before=0xfe, after=0x3e if corrected else 0xfe)
        try:
            result = applications(out/('corrected' if corrected else 'original'), 'raw', program, (1,), prepare)
            require(corrected, 'The frozen failing control no longer reproduces')
            record['cases'].append(dict(corrected=True, mutation=observed, result=result))
        except RuntimeError as error:
            require(not corrected and 'Native termination: 0xfae6 stage=3' in str(error), str(error))
            failure = json.loads((out/'original/results.json').read_text())
            record['cases'].append(dict(corrected=False, expected_failure=str(error), mutation=observed,
                                        artifact_sha256=sha256(out/'original/results.json'), result=failure))
    record['status'] = 'pass'
    (out/'results.json').write_text(json.dumps(record, indent=2)+'\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.output.resolve(), args.program.resolve())
