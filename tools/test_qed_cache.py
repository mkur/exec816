#!/usr/bin/env python3
"""Exercise cached scrolling with shorter lines, exposure and editing invalidation."""
import argparse
import json
import struct
from pathlib import Path

from native_program import ROOT, require, sha256
from qed_saving_observe import SavingEditor
from qed_viewport_observe import peer_pixels
from test_qed_cursor import interact as later_life
from test_qed_documents import fixtures
from test_qed_selection import run

LINES = [b'abcdefghij'*4 if row % 2 == 0 else b'abcdefghijab' for row in range(30)]
TEXT = b'\n'.join(LINES)


def interact(b, p, app, record, owner):
    cycle_at = next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_CPROCESSTEST_CYCLE_'))
    if int.from_bytes(b.memdump(cycle_at, 2), 'little'):
        return later_life(b, p, app, record, owner)
    e = SavingEditor(b, p, app, record, owner)
    b._cmd_ok('MOUSE ST'); b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=1' % e.at('phase')); e.frames(40)
    e.launched('cache-launch', LINES, len(TEXT), path=b'D1:LONG.TXT')
    b.memload(e.at('control'), struct.pack('<H', 1)); e.reach('dw($%x)=100' % e.at('phase'))
    e.click(100, 44); e.click(*e.cell(40, 0)); e.stage(0); e.move(630, 20)
    e.selection('cache-desired-column', LINES, None, 40, 0)
    for row in range(1, 27):
        e.key('EQUALS', ctrl=True, settle=3)
        if row >= 22:
            e.selection('cache-shorter-'+str(row), LINES, None, len(LINES[row]), row)
    # A shorter next line moves the caret left. Its former EOF cell must be
    # restored even when it lies beyond every changed character in the row.
    e.peer_command(2); e.frames(40); e.covered = [(0, 60, 224, 172)]
    e.selection('cache-covered', LINES, None, 40, 26); peer_pixels(e, 'cache-peer')
    e.click(100, 44); e.covered = []; e.frames(40); e.move(630, 20)
    e.selection('cache-exposed', LINES, None, 40, 26)
    e.key('Z'); changed = list(LINES); changed[26] += b'z'
    e.selection('cache-edited', changed, None, 41, 26)
    e.key('EQUALS', ctrl=True); e.key('EQUALS', ctrl=True)
    e.selection('cache-after-edit-scroll', changed, None, 40, 28)
    e.key('Z', ctrl=True); e.selection('cache-after-undo', LINES, None, 40, 26)
    e.scene['cache_regressions'] = dict(shorter_line_frames=5, navigation_keys=28,
        old_eof_restored=True, cover_expose=True, edit_and_undo_invalidation=True)
    b.memload(e.at('control'), struct.pack('<H', 100)); e.reach('dw($%x)=101' % e.at('phase'))
    b.memload(e.at('control'), struct.pack('<H', 101)); e.click(100, 44)
    if e.text()['dirty']:
        e.key('Q', ctrl=True); return e.alert(2, retiring=True)
    return e.retire_key('Q', ctrl=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-from', type=Path, default=ROOT/'build/qed-coexist/qc3-cells')
    a = parser.parse_args(); files = fixtures(); files['LONG.TXT'] = TEXT
    result = run(a.output, native_from=a.native_from, reuse_app=True,
        fixture_source=ROOT/'tests/programs/qed_cleanup_stop.act', media_files=files,
        saving=True, caret=True, writable=True, interaction=interact,
        profile_all=False, stack_observation_index=0, stack_observation_count=4)
    result['observer_inputs'] = {str(p.relative_to(ROOT)): sha256(p) for p in
        [Path(__file__), ROOT/'tools/test_qed_cursor.py']}
    (a.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('QED navigation cache passed', result['completed'])
