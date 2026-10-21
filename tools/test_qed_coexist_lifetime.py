#!/usr/bin/env python3
"""Targeted repeated QED lifetimes and allocation refusal beside an ordinary peer."""
import argparse
import json
import struct
from pathlib import Path

from native_program import ROOT, require, sha256
from qed_coexist_observe import heap_checkpoint
from qed_saving_observe import SavingEditor
from test_qed_documents import fixtures
from test_qed_selection import run

LARGE = b'\n'.join([b'head\tneedle'+b'x'*500] +
                    [b'row %03d\t' % i+b'y'*500 for i in range(127)])


def interact(b, p, app, record, owner):
    e = SavingEditor(b, p, app, record, owner); cycle = e.native('cycle')
    if cycle == 0:
        b._cmd_ok('MOUSE ST'); b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d' % (e.at('phase'), cycle+1)); e.frames(40)

    def memory(name):
        result = heap_checkpoint(e.reach, lambda at, n: b.memdump(at, n), p['build']['memory'])
        e.scene.setdefault('heap', []).append(dict(name=name, **result))
        return result

    if cycle == 0:
        lines = LARGE.split(b'\n')
        e.launched('coexist-large', lines, len(LARGE), path=b'D1:LONG.TXT')
        b.memload(e.at('control'), struct.pack('<H', 1)); e.reach('dw($%x)=100' % e.at('phase'))
        e.click(100, 44); e.move(630, 20)
        peer = e.peer(); paints = e.get(peer['QedPeerPaints'])
        e.put('QedEditFailLine', 1); e.key('A', dialog=True); e.alert(1)
        e.selection('coexist-line-refusal', lines, None, 0, 0)
        require(e.get(e.sy['QedEditFailureHits']) == 1, 'Line-allocation refusal not reached')
        require(not e.text()['dirty'], 'Allocation refusal dirtied the document')
        e.select('coexist-copy', lines, e.cell(0, 0), e.cell(4, 0), (0, 0, 0, 4), (4, 0))
        e.key('C', ctrl=True); e.clipboard([b'head'])
        e.key('X'); edited = [b'x'+lines[0][4:], *lines[1:]]
        e.selection('coexist-large-undo', edited, None, 1, 0)
        memory('document-clipboard-undo')
        e.key('N', ctrl=True); e.decision(3)
        e.selection('coexist-new-cancel', edited, None, 1, 0)
        e.key('N', ctrl=True); e.decision(2); e.loaded('coexist-empty', [b''])
        e.clipboard([b'head'])
        e.put('QedFormFailAllocation', 1); e.key('F', ctrl=True); e.alert(1); e.command_idle()
        require(e.get(e.sy['QedFormAllocationFailures']) == 1, 'Form-allocation refusal not reached')
        e.selection('coexist-form-refusal', [b''], None, 0, 0)
        require(not e.text()['dirty'], 'Failed Find dirtied the document')
        baseline = None
        for index in range(12):
            e.key('A'); e.key('RETURN'); e.key('V', ctrl=True)
            e.selection('reuse-edit-'+str(index), [b'a', b'head'], None, 4, 1)
            e.key('Z', ctrl=True); e.key('Z', ctrl=True)
            e.key('N', ctrl=True); e.decision(2); e.loaded('reuse-new-'+str(index), [b''])
            e.clipboard([b'head'])
            current = memory('reuse-'+str(index))
            if baseline is None:
                baseline = current
            else:
                require(current == baseline, 'Repeated editing accumulated heap fragmentation')
        require(e.get(peer['QedPeerPaints']) > paints, 'Peer stopped during allocation/reuse checks')
        e.scene['coexist_lifetime'] = dict(document_bytes=len(LARGE), repeated_edits=12,
            line_refusals=1, form_refusals=1, peer_paints=e.get(peer['QedPeerPaints'])-paints,
            exact_heap_restoration=True)
        b.memload(e.at('control'), struct.pack('<H', 100)); e.reach('dw($%x)=101' % e.at('phase'))
        b.memload(e.at('control'), struct.pack('<H', 101)); e.click(100, 44)
        return e.retire_key('Q', ctrl=True)
    if cycle == 1:
        e.form_open(); e.alert(1); e.loaded('coexist-missing', [b''])
    elif cycle == 2:
        e.launched('coexist-deep', [b'deep'], 4, path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT')
    else:
        e.launched('coexist-stop', [b'one', b'last'], 9, ending=0, path=b'D1:CRLF.TXT')
        e.key('A'); e.open_find()
        b.memload(e.at('control'), struct.pack('<H', 4)); e.reach('dw($%x)=104' % e.at('phase'))
        e.alert(3); e.command_idle(); e.selection('coexist-stop-cancel', [b'aone', b'last'], None, 1, 0)
        b.memload(e.at('control'), struct.pack('<H', 104)); return e.alert(2, retiring=True)
    b.memload(e.at('control'), struct.pack('<H', cycle+1))
    return e.retire_key('Q', ctrl=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--native-from', type=Path, default=ROOT/'build/qed-cursor/editor')
    args = parser.parse_args(); files = fixtures(); files['LONG.TXT'] = LARGE
    result = run(args.output, native_from=args.native_from,
        fixture_source=ROOT/'tests/programs/qed_cleanup_stop.act', media_files=files,
        saving=True, caret=True, writable=True, interaction=interact)
    result['observer_inputs'] = {str(p.relative_to(ROOT)): sha256(p) for p in
        [Path(__file__), ROOT/'tools/qed_coexist_observe.py']}
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('QED coexistence lifetime passed', result['completed'])
