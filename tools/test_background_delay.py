#!/usr/bin/env python3
"""Background cancellation, foreground routing and exact timer wait cleanup."""
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


def run(out, compiler_dir, raw=False):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'tests/programs/background_delay.act'
    local = out/source.name
    if raw:
        local.write_text('MODULE BACKGROUNDDELAY\nUSE PROCESS\nUSE PROCESSSTATE\nUSE DOSCLIENT\nUSE PROGRAMAPI\nUSE HEAPCORE\nBYTE finished\nPROC Main()\n  IF SIZEOF(PROCESSSTATE.Entry)<>128 OR SIZEOF(DOSCLIENT.ClientContext)<>98 THEN\n    HEAPCORE.Abort($ea80)\n  FI\n  IF PROCESS.StartBackgroundLoaded(NULL,NULL,0)<>0 OR PROCESS.RequestBreak(0)<>0 OR PROGRAMAPI.Delay(0)=0 THEN\n    HEAPCORE.Abort($ea81)\n  FI\n  IF DOSCLIENT.ReleaseContext()=0 THEN\n    HEAPCORE.Abort($ea82)\n  FI\n  finished=1\nRETURN\nENDMODULE\n')
    else:
        local.write_bytes(source.read_bytes())
    (out/'bgfault.act').write_bytes((ROOT/'tests/programs/bgfault.act').read_bytes())
    import generate_tasks
    original = generate_tasks.policy_modules
    def modules(*args, **kwargs):
        directory = original(*args, **kwargs)
        for name in ('dosbreak', 'dosdelay'):
            text = read_source(ROOT/'lib/dos'/f'{name}.act')
            text = text.replace('USE EXEC\n', 'USE EXEC\nUSE BGFAULT\n', 1)
            if name == 'dosbreak':
                needle = '  scope=DOSBREAKTYPES.Scope POINTER(EXEC.AllocMem(DOSBREAKTYPES.SCOPE_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))'
                assert needle in text
                text = text.replace(needle, '  IF BGFAULT.failure=1 THEN\n    scope=NULL\n  ELSE\n'+needle+'\n  FI')
            else:
                needle = '    client.timer=EXEC.CreateIORequest(client.port,SIZEOF(TIMER.TimerClockRequest))'
                text = text.replace(needle, '    IF BGFAULT.failure=2 THEN\n      client.timer=NULL\n    ELSE\n'+needle+'\n    FI')
                needle = '    error=EXEC.OpenDevice(BYTE POINTER(c"timer.device"),TIMER.UNIT_VBLANK,\n        client.timer,0)'
                text = text.replace(needle, '    IF BGFAULT.failure=3 THEN\n      error=EXEC.IOERR_OPENFAIL\n    ELSE\n'+needle+'\n    FI')
            (directory/f'{name}.act').write_text(text)
        return directory
    generate_tasks.policy_modules = modules
    p = build(compiler(compiler_dir), local, out, optimize=not raw,
              tasks=True, task_capacity=8, console=True)
    pin = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    bridge, rom = ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom'
    with emulator(bridge, rom, out, pin=pin) as b:
        for key, value in pin['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(b, rom, pin)
        at = lambda name: next(d['address'] for d in p['image']['data']
                               if '_BACKGROUNDDELAY_'+name.upper()+'_' in d['name'])
        def reach(condition):
            b.bp_clear_all()
            b.bp_set(p['labels']['native_nmi'], condition=condition)
            b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
            run_to(b, p['labels']['native_nmi'], 6000, 30, condition)
            require(b.peek16(adapter.STATE) == 65535, 'Background fixture stopped early')
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
            key('BREAK')
            reach(f'db(${at("phase"):x})=2')
            key('A')
            b._cmd_ok('KEY RETURN down')
            b.bp_clear_all()
        try:
            runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        except Exception:
            if not raw:
                print('Background checks:', data(b, p['image'], 'checks', True), flush=True)
            print('Adapter:', b.memdump(adapter.STATE,64).hex(), flush=True)
            raise
        b._cmd_ok('KEY ALL up')
        require(data(b, p['image'], 'finished') == [1], 'Background fixture incomplete')
        ownership(b, p, p['output'])
    return dict(status='pass', tier='development', raw=raw, runtime=runtime,
                build=p['build'], machine=machine, bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    parser.add_argument('--raw', action='store_true')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    result = run(args.output.resolve(), args.compiler_dir, args.raw)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Background cancellation and timer checks passed:', args.raw, flush=True)
