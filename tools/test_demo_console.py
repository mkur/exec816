#!/usr/bin/env python3
"""Text-console keys, shared loaded PRIMES startup, tiles and clean exit."""
import adapter_state as adapter
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_cooperative import data
from test_console_display import glyph
from console_model import read_cells
from test_dos_stack import execute, ownership
from test_shell_core import KEYS
from build_command import compile_command
from make_data_disk import make
from prime_observer import state as prime_state

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out, mode, reuse=False, compiler_dir=ROOT/'build/actionc'):
    out.mkdir(parents=True, exist_ok=True)
    source = ROOT/'tests/programs/demo_console.act'
    t=compiler(compiler_dir)
    media=out/'media/C'
    compile_command(t,ROOT/'examples/commands/primes.act',media/'PRIMES')
    for suffix in ('profile','options'):
        (media/f'PRIMES.{suffix}.json').rename(out/f'PRIMES.{suffix}.json')
    make(out/'system.atr',out/'media',binary_names={'C/PRIMES'},filesystem='sdfs',sector_bytes=256,sectors=2880)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    (out/'memory.json').write_text(json.dumps(profile))
    p = read_build(out) if reuse else build(t, source, out,
        optimize=mode == 'opt', tasks=True, task_capacity=8, console=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)],
        system_mount='D1',memory_profile=out/'memory.json')
    require(p['build']['source_sha256'] == sha256(source), 'Stale fixture')
    require(p['build']['optimize'] == (mode == 'opt'), 'Wrong native mode')
    binary = ROOT/'build/shell-paced-bridge/AltirraBridgeServer'
    rom = ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary) == PIN['emulator']['sha256'] and sha256(rom) == PIN['rom']['sha256'], 'Unpinned machine')
    def at(name):
        return next(d['address'] for d in p['image']['data'] if '_DEMOTEST_'+name.upper()+'_' in d['name'])
    observed = []
    saved = {}
    with emulator(binary.parent, rom, out, pin=PIN) as b:
        for key, value in PIN['configuration'].items():
            b.config(key, str(value).lower() if isinstance(value, bool) else value)
        b.config('diskemu','generic56k')
        b.mount(0,str(out/'system.atr'))
        machine = verify_machine(b, rom, PIN)
        def far(address, length):
            return b''.join((b.eval_expr(f'dw(${address+i:x})') & 65535).to_bytes(2, 'little')
                            for i in range(0, length, 2))[:length]
        def pointer(address):
            return int.from_bytes(far(address, 3), 'little')
        def rendezvous(condition):
            b.bp_clear_all()
            marker = p['labels']['native_nmi']
            b.bp_set(marker, condition=condition)
            b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
            original = b.regs
            def regs():
                state = original()
                if int(state['PC'].lstrip('$'), 16) in (p['labels']['done'], p['labels']['done']+2):
                    require(b.peek16(adapter.STATE) == 0xffff, 'Demo stopped before checkpoint')
                return state
            b.regs = regs
            try:
                run_to(b, marker, 6000, 120, condition)
            finally:
                b.regs = original
        def frames(count=2):
            rendezvous(f'@frame>={b.eval_expr("@frame")+count}')
        capture = p['build']['memory']['console_storage']['CAPTURE']
        def press(character):
            name, shift = KEYS[character]
            if shift:
                b._cmd_ok('KEY SHIFT down')
            previous = b.eval_expr(f'dw(${capture+10:x})')
            require(b._cmd_ok(f'KEY {name} down')['raw_scan'], 'Physical keys required')
            rendezvous(f'dw(${capture+10:x})>{previous}')
            b._cmd_ok(f'KEY {name} up')
            if shift:
                b._cmd_ok('KEY SHIFT up')
            frames(3)
        def screen(label):
            instances = [pointer(at(n)) for n in ('topInstance', 'bottomInstance')]
            views = [pointer(at(n)) for n in ('topView', 'bottomView')]
            condition = '&'.join(f'(dw(${i+14:x})>=dw(${i+16:x}))&(dw(${v+10:x})=dw(${i+54:x})+dw(${i+10:x}))'
                                 for i, v in zip(instances, views))
            rendezvous(condition)
            cells = b''.join(read_cells(far,i) for i in instances)
            physical = b.memdump(saved['address'], 960)
            expected = bytearray(map(glyph, cells))
            cursor = int.from_bytes(far(instances[0]+54, 2), 'little') + int.from_bytes(far(instances[0]+10, 2), 'little')
            expected[cursor] ^= 128
            require(physical == expected, 'Tile redraw/cursor mismatch: '+label)
            require(b'PRIME SEARCH' in cells[720:] and b'Primes' in cells[720:], 'Missing lower region')
            if label == 'echo':
                require(b'TILE' in cells[:720], 'Missing echoed command')
            (out/(label+'.screen.bin')).write_bytes(physical)
            metrics=prime_state(far,p,out,int.from_bytes(far(at('job'),4),'little'))
            observed.append(dict(label=label, primes=metrics['count'], progress=metrics['progress'],
                                 screen_sha256=sha256(out/(label+'.screen.bin'))))
        def before(bridge):
            saved['address'] = b.peek16(88)
            saved['screen'] = b.memdump(saved['address'], 960)
            saved['mask'], saved['cursor'] = b.peek(16), b.peek(752)
            b._cmd_ok('KEY ALL up')
            rendezvous(f'db(${at("stage"):x})=1')
            screen('startup')
            b.poke(at('gate'), 1)
            for character in 'echo TILE\n':
                press(character)
            rendezvous(f'db(${at("stage"):x})=2')
            screen('echo')
            frames(60)
            b.poke(at('gate'), 1)
            b._cmd_ok('KEY BREAK down')
            rendezvous(f'db(${at("stage"):x})=3')
            b._cmd_ok('KEY BREAK up')
            screen('break')
            require(observed[-1]['progress'] > observed[1]['progress'], 'Prime worker stopped on BREAK')
            b.poke(at('gate'), 1)
            for character in 'exit\n':
                press(character)
            rendezvous(f'db(${at("stage"):x})=4')
            b.poke(at('gate'), 1)
            b.bp_clear_all()
        runtime, _ = execute(b, p, before_run=before, timeout=180, frame_limit=9000)
        require(data(b, p['image'], 'stage') == [5], 'Incomplete demo session')
        require(data(b, p['image'], 'exitStatus', True) == [0, 0], 'Demo exit failure')
        require(b.memdump(saved['address'],960) == saved['screen'] and b.peek(16) == saved['mask']
                and b.peek(752) == saved['cursor'], 'OS display/input restoration')
        ownership(b, p, out)
    return dict(status='pass', tier='development', mode=mode, build=p['build'], machine=machine,
                runtime=runtime, observations=observed, pin=PIN, bank_zero_delta=dict(fixed=0, per_task=0),
                source_inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                               (source, ROOT/'examples/demo-session.inc', ROOT/'examples/shell/shell-session.inc',
                                ROOT/'examples/shell/shell-boot.inc', Path(__file__))})


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc')
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    args = parser.parse_args()
    result = run(args.output.resolve(), args.case, args.reuse,args.compiler_dir)
    (args.output/'results.json').write_text(json.dumps(result, indent=2)+'\n')
    print('Demo console checks passed:', args.case)
