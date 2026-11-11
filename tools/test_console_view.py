#!/usr/bin/env python3
"""Small emitted console-view ABI, generation and retained-owner checks."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from generate_console_view import files, layout
from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import BRIDGE, ROM, PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(out, mode):
    out.mkdir(parents=True, exist_ok=True)
    for path, content in files().items():
        require(path.read_text() == content, 'Stale console view ABI')
    checks = ['sizeof(struct ExecConsoleViewSnapshot)==88',
              'sizeof(struct ExecConsoleViewInput)==72']
    checks += [f'offsetof(struct ExecConsoleView{name},{field})=={offset}'
               for name, record in layout().items()
               for field, offset in record['fields'].items()]
    c = out/'probe.c'
    c.write_text('''#include <stddef.h>
#include <exec816/console-view-types.h>
ULONG ViewPacket;
extern void ViewRegisterUse(void);
LONG EXEC_CALL ViewProbe(ULONG unused) {
    struct ExecConsoleViewSnapshot *p=(void *)ViewPacket;
    UWORD i;
    ViewRegisterUse();
    if (p->unit!=23 || p->count!=64 || p->width!=16) return 2;
    for (i=0;i<64;++i) if (p->cells[i]!=(UBYTE)i) return 3;
    p->first=64;p->cells[63]=201;
    return 0;
}
int main(void) { return 0; }
''')
    assembly = out/'registers.s'
    assembly.write_text("""              .rtmodel version,"1"
              .rtmodel codeModel,"large"
              .rtmodel dataModel,"huge"
              .rtmodel core,"65816"
              .extern _Dp,_Vfp
              .section farcode,text
              .public ViewRegisterUse
ViewRegisterUse:
              lda dp:_Dp
              lda dp:_Vfp
              rtl
""")
    layout_source = out/'layout.c'
    layout_source.write_text('#include <stddef.h>\n#include <exec816/console-view-types.h>\n'
        '__attribute__((section("exec_layout"))) const UWORD ViewLayout[]={\n'+
        ',\n'.join(expression.split('==')[0] for expression in checks)+'};\n')
    expected = [(expression.split('==')[0], int(expression.split('==')[1]))
                for expression in checks]
    foreign = emit(out/'c', [c], [assembly, ROOT/'c/calypsi/image-info.s'], (),
                   mode=='opt', roots=['ViewPacket','ViewProbe'], probes=[(layout_source, expected)])
    source = out/'view.act'
    source.write_text((ROOT/'tests/programs/console_view.act').read_text()
                      .replace('$VIEWPACKET', f"${foreign['symbols']['ViewPacket']:x}")
                      .replace('$VIEWPROBE', f"${foreign['symbols']['ViewProbe']:x}"))
    p = build(compiler(ROOT/'build/actionc', release=True), source, out/'program',
              tasks=True, task_capacity=8, optimize=mode=='opt', foreign_image=foreign)
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        machine = verify_machine(b, ROM, PIN)
        try:
            runtime, _ = execute(b, p, frame_limit=1200, timeout=120)
        except Exception:
            print('checks', data(b, p['image'], 'checks', True),
                  'C result', data(b, p['image'], 'probeResult', False),
                  'before', data(b, p['image'], 'beforeMemory', False),
                  'after', data(b, p['image'], 'afterMemory', False), flush=True)
            raise
        ownership(b, p, p['output'])
        count = data(b, p['image'], 'checks', True)[0]
        require(count >= 100, 'Incomplete console view cases: '+str(count))
    report = dict(status='pass', tier='development', qualification=False,
                  mode=mode, checks=count, machine=machine, runtime=runtime,
                  build=p['build'])
    (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Console view checks passed:', count, flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode)
