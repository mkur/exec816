#!/usr/bin/env python3
"""Focused CreateTask admission and retirement checks through native code."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, command, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_signals_irq import PIN

CASES = {'return': 0, 'self-removal': 1, 'boundaries': 2, 'capacity': 3,
         'reservations': 4, 'held-removal': 5, 'producer-removal': 6,
         'memory-list-removal': 7, 'dos-removal': 8, 'concurrent': 9,
         'retired-result': 10, 'packet-extent': 11, 'packet-tag': 12, 'packet-width': 13}
FAULTS = {5, 6, 7, 8, 11, 12, 13}


def packet_probe(program, variant, out):
    from generate_tasks import ABI
    # Replace only the fixture's Main entry, preserving all production code.
    tag = ABI['constants']['PROFILE_TAG'] + (1 if variant == 12 else 0)
    width = "sep #$20\n.a8" if variant == 13 else ""
    source = out/'packet.s'
    source.write_text(f'.setcpu "65816"\n.segment "CODE"\n.a16\n.i16\n'
                      f'ldx #0\nldy #${tag:x}\n{width}\n'
                      f'lda #{ABI["services"]["CREATE_TASK"]}\ncop $50\nrtl\n')
    config = out/'packet.cfg'
    config.write_text('MEMORY { RAM: start=$1000, size=$100, file=%O; } '
                      'SEGMENTS { CODE: load=RAM,type=ro; }\n')
    command(['ca65', '-o', out/'packet.o', source])
    command(['ld65', '-C', config, '-o', out/'packet.bin', out/'packet.o'])
    return (out/'packet.bin').read_bytes()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--capacity', type=int, choices=(4, 8), default=4)
    parser.add_argument('--worker-stack', type=int)
    parser.add_argument('--suite', default=','.join(CASES))
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    program = read_build(args.from_build) if args.from_build else build(
        compiler(ROOT/'build/actionc'), ROOT/'tests/programs/create_task.act', out/'program',
        optimize=args.mode == 'opt', tasks=True, task_capacity=args.capacity,
        worker_stack=args.worker_stack)
    require(program['build']['optimize'] == (args.mode == 'opt'), 'Wrong compiler mode')
    report = dict(status='running', tier='development', build=program['build'], cases=[],
                  pin=PIN, bank_zero_delta=dict(fixed=0, per_task=0))
    try:
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            for number, name in enumerate(args.suite.split(',')):
                variant = CASES[name]
                caseout = out/name
                caseout.mkdir(exist_ok=True)
                if number:
                    bridge.state_load(slot='loaded')

                def before(b):
                    if not number:
                        b.state_save(slot='loaded')
                    symbol = next(d for d in program['image']['data'] if '_VARIANT_' in d['name'])
                    b.poke(symbol['address'], variant)
                    if variant >= 11:
                        from banked_test_memory import write
                        write(b, program['image']['entry'], packet_probe(program, variant, caseout), caseout)

                try:
                    runtime, _ = execute(bridge, {**program, 'output': caseout}, before_run=before,
                                         preloaded=bool(number), frame_limit=3000, timeout=120,
                                         expected_status=4 if variant in FAULTS else 0)
                except Exception:
                    print('checks:', data(bridge, program['image'], 'checks', True), flush=True)
                    raise
                if variant in (0, 1):
                    require(data(bridge, program['image'], 'finished') == [4], 'Workers did not finish')
                expected_created = {0: 4, 1: 4, 2: 2, 3: args.capacity, 4: 4,
                                    5: 1, 6: 1, 7: 1, 8: 1, 9: 4, 10: 1, 11: 0, 12: 0, 13: 0}[variant]
                require(runtime['created'] == expected_created, 'Failed admission changed capacity')
                # Scan untouched fill, including the interrupt reserve, after shutdown.
                stacks = [('kernel', 0x4a00, 1536)] + [
                    (str(slot), pool['stack_base'], pool.get('stack_bytes', 1536))
                    for slot, pool in enumerate(program['build']['memory']['task_pools'])]
                runtime['stack_high_water'] = {}
                for label, base, size in stacks:
                    contents = bridge.memdump(base, size)
                    first = next((i for i, byte in enumerate(contents) if byte != 0xa5), size)
                    runtime['stack_high_water'][label] = size-first
                if variant in (0, 1, 9):
                    require(runtime['native_nmi_count'] > 0, 'No native VBI observed')
                report['cases'].append(dict(name=name, status='pass', runtime=runtime,
                                           checks=data(bridge, program['image'], 'checks', True)))
                print('Passed', args.mode, name, flush=True)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')


if __name__ == '__main__':
    main()
