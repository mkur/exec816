#!/usr/bin/env python3
"""Owned lower pane rollback and closing during a live cooked console Read."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from library_paths import read_source
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_cooperative import data
from generate_console import constants


def run(out, compiler_dir, bitmap=False, raw=False, reuse=False):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'tests/programs/console_pane.act'
    local = out/source.name
    if raw:
        text = source.read_text()
        core = text[text.index('PROC Require'):text.index('; Every allocation failure')]
        local.write_text('MODULE PANETEST\nUSE HEAPCORE\nUSE CONSOLECORE\nUSE CONSOLETYPES\nCARD checks\nBYTE finished\nBYTE ARRAY scratch(80),cells(26)\nCONSOLETYPES.Instance model\n'+core+'PROC Main()\n  Core()\n  finished=1\nRETURN\nENDMODULE\n')
    else:
        local.write_bytes(source.read_bytes())
    (out/'panefault.act').write_bytes((ROOT/'tests/programs/panefault.act').read_bytes())
    for name in ('console.act', 'dosraw.act'):
        directory = 'console' if name.startswith('console') else 'dos'
        text = read_source(ROOT/'lib'/directory/name)
        text = text.replace('USE EXEC\n', 'USE EXEC\nUSE PANEFAULT\n', 1)
        (out/name).write_text(text.replace('EXEC.AllocMem(', 'PANEFAULT.AllocMem('))
    # DOSRAW is generated into the Task module path ahead of local modules.
    import generate_tasks
    original = generate_tasks.policy_modules
    def modules(*args, **kwargs):
        directory = original(*args, **kwargs)
        path = directory/'dosraw.act'
        text = path.read_text().replace('USE EXEC\n', 'USE EXEC\nUSE PANEFAULT\n', 1)
        path.write_text(text.replace('EXEC.AllocMem(', 'PANEFAULT.AllocMem('))
        return directory
    generate_tasks.policy_modules = modules
    if bitmap:
        from build_bitmap_console import build_bitmap
        from test_mouse_observe import PIN, BRIDGE, ROM
        p = read_build(out/'program') if reuse else build_bitmap(local, out, True, compiler_dir=compiler_dir)
    else:
        PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
        BRIDGE, ROM = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
        p = read_build(out) if reuse else build(compiler(compiler_dir), local, out, optimize=not raw,
                  tasks=True, task_capacity=8, console=not raw)
    if reuse:
        require(sha256(local) == sha256(source), 'Changed replay fixture')
        for group in ('task_inputs', 'console_inputs', 'banked_inputs'):
            for name, expected in p['build'].get(group, {}).items():
                path = ROOT/name
                if path.is_file():
                    require(sha256(path) == expected, 'Changed replay input: '+name)
    with emulator(BRIDGE, ROM, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, ROM, PIN)
        at = lambda name: next(d['address'] for d in p['image']['data']
                               if '_PANETEST_'+name.upper()+'_' in d['name'])
        instance = p['build']['memory'].get('console_storage', {}).get('INSTANCE', 0)
        c = constants()
        def reach(condition):
            b.bp_clear_all()
            b.bp_set(p['labels']['native_nmi'], condition=condition)
            b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
            run_to(b, p['labels']['native_nmi'], 9000, 30, condition)
            require(b.peek16(adapter.STATE) == 65535, 'Pane fixture stopped early')
        def key(name):
            b._cmd_ok(f'KEY {name} down')
            reach(f'@frame>={b.eval_expr("@frame")+4}')
            b._cmd_ok(f'KEY {name} up')
            reach(f'@frame>={b.eval_expr("@frame")+3}')
        def before(b):
            if raw:
                return
            b._cmd_ok('KEY ALL up')
            reach(f'db(${at("phase"):x})=1')
            reach(f'db(${instance+c["INSTANCE_READREADY"]:x})=2')
            key('A')
            key('B')
            file = int.from_bytes(b.memdump(at('ioConsole'), 3), 'little')
            state = int.from_bytes(b.memdump(file+16, 3), 'little')
            require(b.peek16(state+2) == 2, 'Missing edited draft')
            b.memload(at('closeNow'), b'\1')
            height = 30 if bitmap else 24
            reach(f'dw(${instance+c["INSTANCE_HEIGHT"]:x})={height}')
            require(b.peek16(state+2) == 2, 'Pane close lost cooked draft')
            key('C')
            b._cmd_ok('KEY RETURN down')
            b.bp_clear_all()
        try:
            runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        except Exception:
            print('Pane checks:', data(b, p['image'], 'checks', True), flush=True)
            print('Adapter:', b.memdump(adapter.STATE,64).hex(), flush=True)
            print('DOS slots:', b.memdump(p['build']['memory']['dos_storage']['BASE'],128).hex(), flush=True)
            raise
        b._cmd_ok('KEY ALL up')
        require(data(b, p['image'], 'finished') == [1], 'Pane fixture incomplete')
        ownership(b, p, p['output'])
    return dict(status='pass', tier='development', bitmap=bitmap, raw=raw,
                runtime=runtime, build=p['build'], machine=machine,
                observers={name: sha256(out/name) for name in ('console.act', 'dosraw.act')},
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--bitmap', action='store_true')
    parser.add_argument('--raw', action='store_true')
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.compiler_dir, args.bitmap, args.raw, args.reuse)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Owned console pane checks passed:', args.bitmap, flush=True)
