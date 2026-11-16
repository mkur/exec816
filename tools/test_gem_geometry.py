#!/usr/bin/env python3
"""Focused shared GEM layout/bridge probe; no desktop or application catalog."""
import argparse
import json
from pathlib import Path

from calypsi_build import emit
from generate_gem_objects import ABI, layout
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def native_case(out, case):
    out.mkdir(parents=True, exist_ok=True)
    program = build(compiler(ROOT/'build/actionc', release=True),
                    ROOT/('tests/programs/gem_window_'+case+'.act'), out/'program',
                    tasks=True, task_capacity=8, optimize=True)
    with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROM, PIN)
        runtime, _ = execute(bridge, program, timeout=120, frame_limit=2000)
        ownership(bridge, program, program['output'])
        names = ('checks','oneCost','twoCost','heldCount') if case=='storage' else ('checks',)
        facts = {n: data(bridge, program['image'], n, True) for n in names}
    result = dict(status='pass', tier='development', qualification=False,
                  facts=facts, machine=machine, runtime=runtime,
                  build=program['build'])
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Window '+case+' passed:', facts, flush=True)
    return result


def run(out, optimize):
    out.mkdir(parents=True, exist_ok=True)
    expressions, values = [], []
    for name, record in ABI['records'].items():
        expressions.append('sizeof('+record['c_type']+')')
        values.append(layout()[name]['size'])
        for field, kind, cfield, *counts in record['fields']:
            expressions.append('offsetof('+record['c_type']+', '+cfield+')')
            values.append(layout()[name]['fields'][field])
    c = out/'probe.c'
    c.write_text('''#include <stddef.h>
#include <gem/geometry.h>
UWORD GeometryObserved;
const UWORD GeometryLayout[] = { %s };
LONG GeometryProbe(ULONG address) {
    GEMFRAMEDRAW *request=(GEMFRAMEDRAW *)address;
    OBJECT *tree=(OBJECT *)request->tree;
    if (request->start!=GEM_O_VSCROLL || request->depth!=8 ||
        request->clip.g_x!=-17 || request->clip.g_h!=211 ||
        tree[GEM_O_VSLIDE].ob_next!=GEM_O_VSCROLL ||
        tree[GEM_O_VSLIDE].ob_spec!=0x12345678UL) return 0;
    tree[GEM_O_HSLIDE].ob_width=93;
    GeometryObserved=0x5937;
    request->status=GeometryObserved;
    return request->status;
}
int main(void) { return 0; }
''' % ', '.join(expressions))
    foreign = emit(out/'c', [c], [ROOT/'c/calypsi/image-info.s'], (), optimize,
                   roots=['GeometryProbe', 'GeometryLayout'])
    sy = foreign['symbols']
    statements = []
    for name, record in ABI['records'].items():
        statements.append(f'  Require(SIZEOF(GEMOBJECTS.{name})={layout()[name]["size"]})')
    statements += [f'  Require(words({i})={v})' for i, v in enumerate(values)]
    source = out/'probe.act'
    source.write_text('''MODULE GEMGEOMETRYTEST
USE EXEC
USE HEAPCORE
USE CALYPSICALL
USE GEMOBJECTS

CARD checks

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fa00+checks)
  FI
  checks==+1

RETURN

PROC Main()

  LET words=CARD POINTER($%x)
%s
  LET frame=GEMOBJECTS.Frame POINTER(EXEC.AllocMem(
      GEMOBJECTS.FRAME_SIZE,EXEC.MEMF_PUBLIC+EXEC.MEMF_CLEAR))
  LET request=GEMOBJECTS.DrawRequest POINTER(EXEC.AllocMem(
      GEMOBJECTS.DRAWREQUEST_SIZE,EXEC.MEMF_PUBLIC+EXEC.MEMF_CLEAR))
  Require(frame<>NULL AND request<>NULL)
  frame.tree(GEMOBJECTS.O_VSLIDE).next=GEMOBJECTS.O_VSCROLL
  frame.tree(GEMOBJECTS.O_VSLIDE).spec=$12345678
  request.tree=LONGCARD(ADDRESS(@frame.tree(0)))
  request.start=GEMOBJECTS.O_VSCROLL
  request.depth=8
  request.clip.x=-17
  request.clip.height=211
  Require(CALYPSICALL.Invoke(ADDRESS($%x),LONGCARD(ADDRESS(request)))=$5937)
  Require(request.status=$5937)
  Require(frame.tree(GEMOBJECTS.O_HSLIDE).width=93)
  EXEC.FreeMem(BYTE POINTER(request),GEMOBJECTS.DRAWREQUEST_SIZE)
  EXEC.FreeMem(BYTE POINTER(frame),GEMOBJECTS.FRAME_SIZE)

RETURN
ENDMODULE
''' % (sy['GeometryLayout'], '\n'.join(statements), sy['GeometryProbe']))
    program = build(compiler(ROOT/'build/actionc', release=True), source,
                    out/'program', tasks=True, task_capacity=8,
                    optimize=optimize, foreign_image=foreign)
    with emulator(BRIDGE, ROM, out, pin=PIN) as bridge:
        machine = verify_machine(bridge, ROM, PIN)
        runtime, _ = execute(bridge, program, timeout=120, frame_limit=600)
        ownership(bridge, program, program['output'])
    result = dict(status='pass', tier='development', qualification=False,
                  optimize=optimize, layout=layout(), runtime=runtime,
                  machine=machine, build=program['build'])
    (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('GEM geometry ABI passed:', 'opt' if optimize else 'raw', flush=True)
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--case', choices=('abi','storage','layout'), default='abi')
    args = parser.parse_args()
    if args.case!='abi':
        native_case(args.output.resolve(), args.case)
    else:
        for optimize in (False, True):
            run(args.output.resolve()/('opt' if optimize else 'raw'), optimize)
