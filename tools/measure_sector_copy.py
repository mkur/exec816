#!/usr/bin/env python3
"""Separate SDFS Consume's byte loop from setup, bookkeeping and interruptions.

Passive PCs come from the pinned compiler's emitted routine, not a rewritten
copy of its source. The single backward branch identifies the loop; fail closed
if the emitted control flow changes. No guest timing instructions are added.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import statistics

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from sio_transaction_trace import BASE_HZ, read_events
from test_cooperative import data
from test_heap_api import clean_ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES = (('full128', 128), ('tail55', 55), ('full256', 256))
ENV = ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS', 'EXEC816_MASK_TRACE')


def markers_for(program):
    image = program['image']
    matches = [r for r in image['routines'] if r['name'].startswith('M_SDFSFILE_CONSUME_')]
    require(len(matches) == 1, 'Missing or ambiguous SDFS Consume')
    routine = matches[0]
    source = ROOT/'build/actionc/tools/disassemble65816.py'
    # Loading as source avoids leaving an untracked __pycache__ in the pinned
    # compiler checkout, which must stay clean for subsequent native builds.
    decoder = {'__name__': 'copy_disassembler'}
    exec(compile(source.read_text(), str(source), 'exec'), decoder)
    segments = []
    for s in image['segments']:
        lo = max(s['address'], routine['address'])
        hi = min(s['address']+len(s['bytes']), routine['address']+routine['size'])
        if lo < hi:
            segments.append(dict(address=lo, bytes=s['bytes'][lo-s['address']:hi-s['address']], executable=True))
    # v4 adds an arithmetic-fault contract; these scalar instruction encodings
    # are identical to v3. Decode a routine-only view, preserving the real image.
    require(image['version'] in (3, 4), 'Unsupported instruction image version')
    listing = decoder['disassemble']({**image, 'version': 3, 'segments': segments})
    instructions = []
    for line in listing.splitlines():
        pc, rest = line.split('  ', 1)
        code, text = rest[:11].strip(), rest[12:]
        instructions.append(dict(pc=int(pc, 16), bytes=bytes.fromhex(code), text=text))
    backward = [i for i in instructions if i['text'].startswith('BRL $') and int(i['text'][5:], 16) < i['pc']]
    require(len(backward) == 1, 'Consume must contain exactly one backward loop branch')
    back = backward[0]
    head = int(back['text'][5:], 16)
    end = back['pc'] + len(back['bytes'])
    require(any(i['text'] == f'BRL ${end:06X}' and head <= i['pc'] < back['pc'] for i in instructions),
            'Missing loop-exit branch')
    require(not any(i['text'].startswith(('JSL', 'JML', 'RTL')) and head <= i['pc'] < end for i in instructions),
            'Unexpected call or escape inside byte loop')
    returns = [i['pc'] for i in instructions if i['text'] == 'RTL']
    require(len(returns) == 2, 'Changed Consume return paths')
    marks = dict(consume=routine['address'], loop=head, bookkeeping=end,
                 native_nmi=program['labels']['native_nmi'], native_irq=program['labels']['native_irq'])
    marks.update({f'return{n}': pc for n, pc in enumerate(returns)})
    loop_code = b''.join(i['bytes'] for i in instructions if head <= i['pc'] < end)
    return marks, listing, dict(routine=routine['name'], address=routine['address'], size=routine['size'],
                               loop_bytes=end-head, loop_sha256=hashlib.sha256(loop_code).hexdigest(), decoder_sha256=sha256(source))


def samples(events, marks):
    """Pair each Consume activation and count every byte-loop header visit.

    Interrupt entry anywhere in the activation disqualifies its isolated timing.
    IRQs/NMIs remain enabled. The fixture has no competing Tasks; HELLO samples
    with preemption remain useful elapsed intervals but are not CPU-cost samples.
    """
    current = None
    result = []
    returns = {value for key, value in marks.items() if key.startswith('return')}
    interrupts = {marks['native_nmi'], marks['native_irq']}
    for tick, event in events:
        if event[0] != 'cpu':
            continue
        pc = int(event[4], 16)
        if pc in interrupts and current is not None:
            current['interrupts'] += 1
        if pc == marks['consume']:
            require(current is None, 'Overlapping Consume activations')
            require(not int(event[11], 16) & 4, 'Consume entered with IRQs masked')
            current = dict(begin=tick, dp=int(event[9], 16), interrupts=0, iterations=0)
        elif current is not None and pc == marks['loop']:
            require(int(event[9], 16) == current['dp'], 'Loop changed Task domain')
            current.setdefault('loop', tick)
            current['iterations'] += 1
        elif current is not None and pc == marks['bookkeeping']:
            require('loop' in current and 'bookkeeping' not in current, 'Unmatched loop exit')
            current['bookkeeping'] = tick
        elif current is not None and pc in returns:
            require('bookkeeping' in current and int(event[9], 16) == current['dp'], 'Unmatched Consume return')
            # The marker precedes RTL; its six CPU cycles complete the routine.
            end = tick + 6/8
            row = dict(begin=current['begin'], end=end, interrupts=current['interrupts'],
                       bytes=current['iterations']-1, dp=current['dp'])
            points = (current['begin'], current['loop'], current['bookkeeping'], end)
            row['microseconds'] = {name:(b-a)/BASE_HZ*1e6 for name,a,b in zip(('setup','loop','bookkeeping'),points,points[1:])}
            row['microseconds']['total'] = (end-current['begin'])/BASE_HZ*1e6
            result.append(row)
            current = None
    require(current is None and result, 'Incomplete or empty Consume trace')
    return result


def summarize(rows):
    clean = [r for r in rows if r['interrupts'] == 0]
    require(clean, 'No uninterrupted samples')
    def stats(values):
        return dict(min_us=min(values), median_us=statistics.median(values), mean_us=statistics.mean(values), max_us=max(values))
    return dict(samples=len(rows), uninterrupted=len(clean), interrupted=len(rows)-len(clean),
                uninterrupted_us={name:stats([r['microseconds'][name] for r in clean]) for name in ('setup','loop','bookkeeping','total')},
                elapsed_us={name:stats([r['microseconds'][name] for r in rows]) for name in ('setup','loop','bookkeeping','total')})


def run_fixture(program, output, observed, marks):
    previous = {key:os.environ.get(key) for key in ENV}
    try:
        for key in ENV:
            os.environ.pop(key, None)
        if observed:
            os.environ['EXEC816_LATENCY_TRACE'] = '1'
            os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in marks.values())
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
            machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            runtime, _ = execute(bridge, program, timeout=180, frame_limit=3000,
                                 before_run=(lambda b:b.profile_start()) if observed else None)
            if observed:
                bridge.profile_stop()
            require(data(bridge, program['image'], 'finished') == [1], 'Incomplete byte checks')
            require(runtime['created'] == 0, 'Unexpected worker in isolated fixture')
            clean_ownership(bridge, program, program['output'])
            return dict(runtime=runtime, checks=data(bridge, program['image'], 'checks', True), machine=machine)
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def hello_samples(events, rows):
    """Select payload consumption by on-wire sector commands, excluding DIR."""
    packets = []
    packet = None
    for tick, event in events:
        if event[0] == 'command' and event[2] == '1':
            packet = dict(start=tick, tx=[])
            packets.append(packet)
        if packet is not None and event[0] == 'ready':
            packet['tx'].append(int(event[2]))
    reads = [p for p in packets if len(p['tx']) == 5 and p['tx'][:2] == [49,82]]
    sector = lambda p:p['tx'][2]+256*p['tx'][3]
    first = next(i for i,p in enumerate(reads) if sector(p) == 70)
    require([sector(p) for p in reads[first:first+19]] == list(range(70,89)), 'Changed HELLO sector layout')
    require(len(reads) > first+19, 'Missing subsequent DIR boundary')
    selected = [r for r in rows if reads[first]['start'] <= r['begin'] < reads[first+19]['start']]
    require([r['bytes'] for r in selected] == [128]*18+[55], 'Changed HELLO consume sequence')
    return selected


def run_hello(bundle, output, prime_worker, analyze_only=False):
    from measure_command_loading import run
    program = read_build(bundle)
    marks, listing, routine = markers_for(program)
    (output/'consume.asm').write_text(listing)
    (output/'markers.json').write_text(json.dumps(marks, indent=2)+'\n')
    previous = {key:os.environ.get(key) for key in ENV}
    try:
        os.environ['EXEC816_LATENCY_TRACE'] = '1'
        os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in marks.values())
        os.environ.pop('EXEC816_MASK_TRACE', None)
        measured = json.loads((output/'results.json').read_text()) if analyze_only else run(bundle, output, prime_worker=prime_worker, cpu_trace=True)
        require(measured['status'] == 'pass' and measured['xex_sha256'] == program['build']['xex_sha256'], 'Changed HELLO replay')
        require(measured['prime_worker']['mode'] == prime_worker, 'Changed prime-worker mode')
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
    events = read_events(output/'emulator.log')
    rows = hello_samples(events, samples(events, marks))
    result = dict(status='pass', prime_worker=prime_worker, xex_sha256=measured['xex_sha256'],
                  routine=routine, cases={str(amount):summarize([r for r in rows if r['bytes']==amount]) for amount in (128,55)},
                  samples=rows, scope='Unchanged diagnostic HELLO image. Loop/setup/bookkeeping include preemption in interrupted samples; only interrupt-free activations supply isolated timings.',
                  inputs={p:sha256(ROOT/p) for p in ('tools/measure_sector_copy.py','tools/measure_command_loading.py')})
    (output/'copy-analysis.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps(result['cases'], indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--mode', choices=('raw','opt'))
    mode.add_argument('--hello-bundle', type=Path)
    parser.add_argument('--prime-worker', choices=('stopped','active'), default='stopped')
    parser.add_argument('--analyze-only', action='store_true', help='Analyze an existing HELLO replay')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=True)
    if args.hello_bundle:
        require(args.from_build is None, 'Use --hello-bundle without --from-build')
        run_hello(args.hello_bundle.resolve(), out, args.prime_worker, args.analyze_only)
        return
    require(not args.analyze_only, '--analyze-only requires --hello-bundle')
    program = read_build(args.from_build) if args.from_build else build(
        compiler(ROOT/'build/actionc'), ROOT/'tests/programs/sector_copy.act', out/'program',
        tasks=True, console=False, optimize=args.mode=='opt', stack_checks=True,
        image_data=[(0xa0000, bytes(0xc00))])
    require(program['build']['optimize'] == (args.mode=='opt'), 'Wrong NIR mode')
    marks, listing, routine = markers_for(program)
    (out/'consume.asm').write_text(listing)
    (out/'markers.json').write_text(json.dumps(marks, indent=2)+'\n')
    result = dict(status='running', mode=args.mode, build=program['build'], pin=PIN, routine=routine,
                  inputs={p:sha256(ROOT/p) for p in ('tools/measure_sector_copy.py','tests/programs/sector_copy.act','lib/spartados/sdfsfile.act')})
    try:
        observed = run_fixture(program, out/'observed', True, marks)
        replay = run_fixture(program, out/'replay', False, marks)
        require(observed == replay, 'Identical-image replay differs')
        rows = samples(read_events(out/'observed/emulator.log'), marks)
        require(len(rows) == 96, 'Expected 32 samples of each size')
        cases = {}
        for index, (name, amount) in enumerate(CASES):
            selection = rows[32*index:32*(index+1)]
            require(all(r['bytes'] == amount for r in selection), 'Wrong byte-loop iteration count')
            cases[name] = dict(bytes=amount, **summarize(selection))
        result.update(status='pass', observed=observed, replay=replay, identical_image_replay=True, cases=cases, samples=rows,
                      scope='Actual SDFS Consume; root only, resident upper-RAM records/buffers, IRQ/NMI enabled, no disk or other workers. Uninterrupted elapsed instruction time includes machine bus timing; not an ideal CPU-cycle model.',
                      bank_zero_delta=dict(fixed=0,per_task=0), production_changed=False)
        print(json.dumps(cases, indent=2), flush=True)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result, indent=2)+'\n')


if __name__ == '__main__':
    main()
