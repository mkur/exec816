#!/usr/bin/env python3
"""Small emitted cursor hint regression with deterministic late draw/failure.

Extract the actual Mouse/Cursor/Changed routines unchanged. Only Submit's physical
boundary is supplied by the fixture, allowing a notification to arrive inside
it. Real rendering and scene integration use the loaded MGVIEW scroll check.
"""
import argparse
import json
import re
import shutil
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def run(out):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'lib/console/consolebitmap.act'
    text = source.read_text()
    bodies = []
    for name in ('Mouse', 'Cursor', 'Changed'):
        start = re.search(r'(?m)^PUBLIC BYTE FUNC '+name+r'\(', text)
        require(start is not None, 'Missing cursor routine '+name)
        body = re.split(r'(?m)^(?:PUBLIC |ENDMODULE)', text[start.start()+7:], maxsplit=1)[0]
        bodies.append('PUBLIC '+body)
    module = '''MODULE CURSORHINTBITMAP
USE DISPLAY
INCLUDE "'''+str(ROOT/'lib/console/console-bitmap-types.inc')+'''"
PUBLIC BYTE drawingChanged,lateDraw,returnOkay,observedChanged
PUBLIC CARD lastOperation
Packet request

Packet POINTER FUNC GetPacket()

RETURN(@request)

BYTE FUNC Submit(Packet POINTER output CARD operation)

  observedChanged=drawingChanged
  lastOperation=operation
  IF lateDraw<>0 THEN
    drawingChanged=1
  FI

RETURN(returnOkay)

'''+''.join(bodies)+'ENDMODULE\n'
    (out/'cursorhintbitmap.act').write_text(module)
    shutil.copyfile(ROOT/'tests/programs/cursor_hint.act', out/'cursor_hint.act')
    p = build(compiler(ROOT/'build/actionc', release=True), out/'cursor_hint.act',
              out/'program', tasks=True, optimize=True)
    require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
            'Unpinned observer executable')
    with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROM, PIN)
        runtime, _ = execute(bridge, p, frame_limit=600, timeout=120)
        ownership(bridge, p, p['output'])
        checks = data(bridge, p['image'], 'checks', True)[0]
        require(checks == 48, 'Incomplete hint regression: '+str(checks))
    report = dict(status='pass', tier='development', qualification=False,
                  checks=checks, cases=12, mode='opt', source_sha256=sha256(source),
                  native_sha256=sha256(p['xex']), machine=machine, runtime=runtime,
                  bank_zero_delta=dict(fixed=0, root=0, kernel=0, idle=0, per_public_task=0))
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Cursor hint checks passed:', checks, flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    run(parser.parse_args().output.resolve())
