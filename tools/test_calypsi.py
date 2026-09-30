#!/usr/bin/env python3
"""Run the Calypsi message example through native Tasks, console and cleanup."""
import argparse
import json
from pathlib import Path

from build_calypsi import build_example
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_console_display import glyph
from test_dos_stack import execute
from test_heap_api import clean_ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
LINES = ('C sends: 10,20', 'C reply: 60,70', 'C message returned; resources released.')
PROMPT = 'Press RETURN to exit.'


def run(output, mode, from_build=None, context=False):
    output.mkdir(parents=True, exist_ok=True)
    if from_build:
        program = read_build(from_build/'program')
        foreign = json.loads((from_build/'c-image.json').read_text())
        require(program['build']['foreign_image'] == foreign['provenance'], 'C image provenance differs')
        for name, digest in foreign['provenance']['source_inputs'].items():
            require(sha256(ROOT/name) == digest, 'C source changed: ' + name)
    else:
        program, foreign = build_example(output, optimize=mode == 'opt', context=context)
    require(program['build']['optimize'] == (mode == 'opt'), 'Wrong compiler mode')
    require(foreign['provenance'].get('context_probe', False) == context, 'Wrong C fixture')
    bridge_dir = ROOT/'build/shell-paced-bridge'
    rom = ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(bridge_dir/'AltirraBridgeServer') == PIN['emulator']['sha256'], 'Wrong emulator')
    require(sha256(rom) == PIN['rom']['sha256'], 'Wrong ROM')
    report = dict(status='running', tier='development', mode=mode, build=program['build'], pin=PIN,
                  bank_zero_delta=dict(fixed=0, per_task=0))
    try:
        with emulator(bridge_dir, rom, output, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, rom, PIN)
            saved = {}

            def before_run(b):
                saved.update(address=b.peek16(88), cursor=b.peek(752), mask=b.peek(16))
                saved['screen'] = b.memdump(saved['address'], 960)
                b._cmd_ok('KEY ALL up')
                if context:
                    report['c_preemption'] = seed_and_observe(b, program, foreign)
                prompt_address = saved['address']+len(LINES)*40
                condition = '&'.join(f'db(${prompt_address+i:x})={glyph(ord(c))}' for i, c in enumerate(PROMPT))
                cursor_address = saved['address']+(len(LINES)+1)*40
                condition += f'&(db(${cursor_address:x})=128)'
                marker = program['labels']['native_nmi']
                b.bp_set(marker, condition=condition)
                run_to(b, marker, frame_limit=3000, timeout=90, condition=condition)
                screen = b.memdump(saved['address'], 960)
                expected = bytearray(960)
                for row, line in enumerate((*LINES, PROMPT)):
                    expected[row*40:row*40+len(line)] = bytes(map(glyph, line.encode('ascii')))
                expected[(len(LINES)+1)*40] = 128
                (output/'output.screen.bin').write_bytes(screen)
                require(screen == expected, 'C example console output differs')
                for symbol, value in (('received_x', 60), ('received_y', 70), ('same_message', 1)):
                    require(b.eval_expr(f'dw(${foreign["symbols"][symbol]:x})') == value, 'Wrong C result: ' + symbol)
                if context:
                    check_context(b, program, foreign)
                report['output'] = list(LINES)
                require(b._cmd_ok('KEY RETURN down')['raw_scan'], 'Physical Return required')
                capture = program['build']['memory']['console_storage']['CAPTURE']
                previous = b.eval_expr(f'dw(${capture+10:x})')
                b.bp_clear_all()
                condition = f'dw(${capture+10:x})>{previous}'
                b.bp_set(marker, condition=condition)
                run_to(b, marker, frame_limit=120, timeout=15, condition=condition)
                b._cmd_ok('KEY RETURN up')
                b.bp_clear_all()

            runtime, _ = execute(bridge, program, before_run=before_run, frame_limit=3000, timeout=90)
            report['runtime'] = runtime
            require(runtime['created'] == 2, 'Wrong C/console Task count')
            require(runtime['os_calls'] == 0, 'C example used ROM output adapter')
            require(runtime['root_task'][16:20] == [255, 255, 0, 0], 'Root leaked a signal')
            require(bridge.memdump(saved['address'], 960) == saved['screen'] and
                    bridge.peek(16) == saved['mask'] and bridge.peek(752) == saved['cursor'],
                    'OS display/input restoration failed')
            clean_ownership(bridge, program, program['output'])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


def pattern(slot):
    return bytes((slot*71 + index*37 + 19) & 255 for index in range(128))


def seed_and_observe(bridge, program, foreign):
    pools = program['build']['memory']['task_pools']
    for slot in (0, 2):
        entry = program['labels']['task_start' if slot == 0 else 'general_task_start']
        condition = f'db($2023)={slot}'
        bridge.bp_set(entry, condition=condition)
        run_to(bridge, entry, frame_limit=3000, timeout=90, condition=condition)
        bridge.bp_clear_all()
        dp = pools[slot]['dp']
        bridge.memload(dp+8, pattern(slot)[8:16])  # callee-preserved registers
        bridge.memload(dp+20, pattern(slot)[20:])  # unused caller workspace
    bridge.memload(0x2600, pattern(4))
    marker = program['labels']['native_nmi']
    # REGS/@s expose only S8. Observe the unmodified NMI prologue just after
    # it pushes the full native saved S onto the OS stack. Validate its bytes
    # rather than silently depending on an instruction offset after edits.
    prologue = bytes.fromhex('c23048da5a0b8bd83baa2900ffc90001f004a9ef011bda')
    require(bridge.memdump(marker, len(prologue)) == prologue, 'NMI observer needs updating')
    marker += len(prologue)
    observations = []
    for slot in (2, 0):
        progress = foreign['symbols']['progress'] + (2 if slot == 2 else 0)
        condition = f'(db($2023)={slot})&(dw(${progress:x})>0)&(dw(${progress:x})<30000)'
        bridge.bp_set(marker, condition=condition)
        run_to(bridge, marker, frame_limit=3000, timeout=90, condition=condition)
        bridge.bp_clear_all()
        stack = bridge.peek16(0x1ee)
        pool = pools[slot]
        require(pool['stack_base'] <= stack < pool['stack_base']+1536-13,
                'NMI did not enter from the C Task stack')
        frame = bridge.memdump(stack+10, 4)  # nine saved register bytes
        require(frame[3] == 12, 'VBI did not interrupt the C code bank')
        observations.append(dict(slot=slot, pc=int.from_bytes(frame[1:4], 'little'),
                                 progress=bridge.eval_expr(f'dw(${progress:x})')))
    return observations


def check_context(bridge, program, foreign):
    require(bridge.eval_expr(f'dw(${foreign["symbols"]["failures"]:x})') == 0, 'C API probe failed')
    for who, slot in enumerate((0, 2)):
        a, b = 0x12345678+who, 0x87654321-who
        for index in range(30000):
            a = ((a << 1) ^ (a >> 31) ^ b) & 0xffffffff
            b = (b + (a ^ index)) & 0xffffffff
        address = foreign['symbols']['checksum'] + who*4
        actual = bridge.eval_expr(f'dw(${address:x})') | bridge.eval_expr(f'dw(${address+2:x})') << 16
        require(actual == a ^ b, f'Interrupted C computation corrupted in slot {slot}')
        dp = program['build']['memory']['task_pools'][slot]['dp']
        if slot == 0:  # main returns; the worker deliberately removes itself.
            require(bridge.memdump(dp+8, 8) == pattern(slot)[8:16], 'C callee-saved registers changed')
        require(bridge.memdump(dp+20, 108) == pattern(slot)[20:], 'Unused C workspace changed')
    require(bridge.memdump(0x2600, 128) == pattern(4), 'Kernel lower DP workspace changed')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--context', action='store_true', help='Run C preemption and API boundary probe')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.from_build.resolve() if args.from_build else None, args.context)
    print('Calypsi C example passed:', args.mode)
