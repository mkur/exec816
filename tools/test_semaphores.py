#!/usr/bin/env python3
"""Small emitted-code semaphore cases and passive complete-pair accounting."""
import argparse
import json
import os
import statistics
from pathlib import Path

from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_heap_api import clean_ownership
from stack_budget import stack_usage
from bitmap_console_performance import native_markers
from console_turn_profile import analyze_events, Timeline
from g4bench_trace import calls
from sio_transaction_trace import read_events

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES = {'baseline': 0, 'native': 1, 'abi': 2, 'empty-release': 3,
         'extra-release': 4, 'owner-removal': 5, 'depth-overflow': 6, 'owned-overflow': 7,
         'wrong-owner': 8, 'far-object': 9, 'far-task': 10, 'blocking': 11, 'waiter-removal': 12, 'granted-removal': 13, 'native-bench': 14, 'coexist': 15}
FAULTS = set(range(3, 9)) | {12,13}


def inputs():
    paths = [ROOT/'tests/programs/semaphores.act',
             ROOT/'tools/native_program.py', ROOT/'tools/generate_tasks.py', ROOT/'tools/generate_semaphores.py',
             ROOT/'toolchain/actionc.json']
    paths += list((ROOT/'lib').rglob('*.act')) + list((ROOT/'lib').rglob('*.inc'))
    paths += list((ROOT/'abi').glob('*.json')) + list((ROOT/'platform/altirraos').glob('*.s'))
    paths += list((ROOT/'platform/altirraos').glob('*.inc'))
    return {str(p.relative_to(ROOT)): sha256(p) for p in sorted(set(paths))}


def definition(program):
    names = ('LibraryPair', 'LibraryObtain', 'LibraryRelease', 'FreePairs',
             'RecursivePairs', 'CounterTurn', 'NativePair','NativeFreePairs','NativeRecursivePairs')
    native = native_markers(program, [('SEMAPHORES_'+name.upper(), name) for name in names])
    require(set(native) == set(names), 'Missing semaphore observation boundary')
    restore = program['labels']['context_restore']
    points = {name: program['labels'][name] for name in
              ('native_irq', 'native_nmi', 'interrupt_schedule')}
    points.update(selected=restore+4, turn=native['CounterTurn']['entry'])
    timeline = dict(points=points, spans={},
                    task_dps=[p['dp'] for p in program['build']['memory']['task_pools']])
    pcs = set(points.values()) | {span['entry'] for span in native.values()}
    pcs.update(pc for span in native.values() for pc in span['returns'])
    import generate_semaphores as sem
    public = {name: dict(entry=program['labels'][label], returns=[program['labels'][label+'_end']-1])
              for name, label in sem.LABELS.items() if name in sem.ABI['imports']}
    for span in public.values():
        pcs.add(span['entry'])
        pcs.update(span['returns'])
    for name in ('fast_entry', 'fast_complete', 'fast_general', 'sem_policy'):
        pcs.add(program['labels'][name])
    for name in ('native_timer_work','exec_reply_msg_native'):
        pcs.add(program['labels'][name])
    return dict(native=native, public=public, labels={name: program['labels'][name] for name in
                ('fast_entry', 'fast_complete', 'fast_general', 'sem_policy')}, timeline=timeline, pcs=sorted(pcs))


def analyze(path, definition, native_case=False):
    events = read_events(path, kinds={'cpu'})
    irqs = {definition['timeline']['points'][n] for n in ('native_irq', 'native_nmi')}
    while events and int(events[-1][1][4], 16) in irqs:
        events.pop()
    timeline_definition=definition['timeline']
    if native_case:
        timeline_definition=dict(timeline_definition,points=dict(timeline_definition['points'],turn=definition['native']['NativePair']['entry']))
    profile = analyze_events(events, timeline_definition, include_segments=True)
    native = definition['native']
    root_dps = {int(e[9], 16) for _, e in events if int(e[4], 16) == native['NativePair' if native_case else 'LibraryPair']['entry']}
    require(len(root_dps) == 1, 'No unique semaphore benchmark Task')
    root = root_dps.pop()
    timeline = Timeline(profile['segments'], root)
    spans, unfinished = calls(events, {v['entry']: n for n, v in native.items()}, set(), root,
                              {pc for v in native.values() for pc in v['returns']})
    require(not unfinished, 'Unfinished semaphore spans: '+str(unfinished))
    result = {}
    for name in (('NativeFreePairs','NativeRecursivePairs') if native_case else ('FreePairs','RecursivePairs')):
        windows = [s for s in spans if s['kind'] == name]
        require(len(windows) == 1, 'Missing measured batch '+name)
        a, b = windows[0]['start'], windows[0]['end']
        pairs = [dict(s, **timeline.measure(s['start'], s['end'])) for s in spans
                 if s['kind'] == ('NativePair' if native_case else 'LibraryPair') and a <= s['start'] < s['end'] <= b]
        require(len(pairs) == 32, 'Wrong pair count: '+str((name, len(pairs))))
        result[name] = dict(samples=pairs, **{
            key: dict(min=min(p[key] for p in pairs), median=statistics.median(p[key] for p in pairs),
                      max=max(p[key] for p in pairs))
            for key in ('elapsed_ms', 'charged_cpu_ms', 'off_cpu_ms', 'interrupt_ms')})
    return dict(root_dp=root, counter_dp=profile['worker_dp'], batches=result,
                scope='Complete composition pair; Task CPU includes gateway/bus stalls; IRQ and off-Task time separate.')


def public_calls(path, definition, program):
    """Count only the operation's requests; late-work Poll is a separate event."""
    import generate_semaphores as sem
    events = read_events(path, kinds={'cpu'})
    entries = {v['entry']: n for n, v in definition['public'].items()}
    exits = {pc for v in definition['public'].values() for pc in v['returns']}
    result = []
    for pool in program['build']['memory']['task_pools']:
        spans, unfinished = calls(events, entries, set(), pool['dp'], exits)
        require(not unfinished, 'Unfinished public semaphore operation')
        lo, hi = pool['stack_base'], pool['stack_base']+pool['stack_bytes']
        for span in spans:
            selected = [(t,e) for t,e in events if span['start']<=t<=span['end']]
            posts = [e for t,e in selected if int(e[4],16)==definition['labels']['fast_entry']
                     and lo<=int(e[6],16)<hi and int(e[7],16) in sem.ABI['services'].values()]
            expected = int(span['kind']!='InitSemaphore')
            require(len(posts)==expected, 'Wrong public semaphore request count: '+str((span, len(posts))))
            result.append(dict(span, task_dp=pool['dp'], requests=len(posts),
                policy_continuations=sum(int(e[4],16)==definition['labels']['sem_policy'] and
                                         lo<=int(e[9],16)<hi for _,e in selected),
                native_completions=sum(int(e[4],16)==definition['labels']['fast_complete'] and
                                       lo<=int(e[9],16)<hi for _,e in selected),
                post_operation_polls=sum(int(e[4],16)==definition['labels']['fast_general'] and
                                         lo<=int(e[9],16)<hi for _,e in selected)))
    return result


def run(out, mode, from_build=None, suite='baseline', diagnostic=False, checkpoint=0, irq=False):
    out.mkdir(parents=True, exist_ok=True)
    frozen_inputs = inputs()
    if from_build:
        require(json.loads((from_build/'inputs.json').read_text()) == frozen_inputs, 'Changed semaphore build inputs')
        program = read_build(from_build/'program')
    else:
        source = out/'semaphores.act'
        source.write_text((ROOT/'tests/programs/semaphores.act').read_text().replace(
            'INCLUDE "semaphore-action.inc"', 'INCLUDE "'+str(out/'program/semaphore-action.inc')+'"'))
        program = build(compiler(ROOT/'build/actionc', release=True), source,
                        out/'program', tasks=True, optimize=mode == 'opt', probe_nmi=200 if diagnostic else 0,
                        image_data=[(0x04fff0, bytes([0xa5])*32), (0x06ffe0, bytes([0xa5])*96)])
        (out/'inputs.json').write_text(json.dumps(frozen_inputs, indent=2)+'\n')
    require(program['build']['probe_nmi']==(200 if diagnostic else 0),'Wrong diagnostic image')
    require(program['build']['optimize'] == (mode == 'opt'), 'Wrong semaphore build mode')
    d = definition(program)
    (out/'definition.json').write_text(json.dumps(d, indent=2)+'\n')
    report = dict(status='running', tier='development', mode=mode, suite=suite, pin=PIN, build=program['build'],
                  runner_sha256=sha256(Path(__file__)))
    previous = {k: os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE', 'EXEC816_LATENCY_PCS')}
    os.environ['EXEC816_LATENCY_TRACE'] = '1'
    os.environ['EXEC816_LATENCY_PCS'] = ','.join(f'{pc:x}' for pc in d['pcs'])
    try:
        case = CASES[suite]
        with emulator(ROOT/'build/shell-paced-bridge', ROOT/'build/firmware/altirraos-816.rom', out, pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            def before(b):
                at = next(d['address'] for d in program['image']['data'] if '_VARIANT_' in d['name'])
                b.poke(at, case)
                if diagnostic:
                    import adapter_state as adapter
                    from os_boundary import run_to
                    b.bp_set(program['labels']['task_start'])
                    run_to(b,program['labels']['task_start'],frame_limit=300,timeout=30)
                    b.bp_clear_all()
                    b.memload(adapter.PROBE0,checkpoint.to_bytes(2,'little')+bytes(6))
                b.profile_start()
            runtime, _ = execute(bridge, program, timeout=120, frame_limit=1200,
                                 expected_status=4 if case in FAULTS else 0, before_run=before,timer_irq=irq)
            report['runtime'] = runtime
            if diagnostic and checkpoint:
                import adapter_state as adapter
                require(bridge.peek16(adapter.PROBE0)==256,'Checkpoint not reached')
                require(runtime['native_nmi_count']>bridge.peek16(adapter.PROBE0+2),'Missing checkpoint NMI')
                report['checkpoint']=checkpoint
            if irq:
                require(runtime['native_irq_count']>0,'Missing concurrent IRQ')
            report['checks'] = data(bridge, program['image'], 'checks', True)[0]
            expected = {0: 14, 1: 12, 2: 13, 9: 13, 10: 9, 11: 48, 12: 23, 13: 25, 14: 3, 15: 18}.get(case, 0)
            require(report['checks'] == expected, 'Semaphore fixture assertions: '+str(report['checks']))
            report['counter'] = data(bridge, program['image'], 'counter', True)[0]
            report['stack_usage'] = stack_usage(bridge, program['build']['memory'])
            if case in FAULTS:
                require(data(bridge, program['image'], 'reached') == [0], 'Expected semaphore fault returned')
                words = data(bridge, program['image'], 'device', True)
                if case >= 11:
                    require(words[2] == 1, 'Ownership lost before removal fault')
                    records = runtime['task_records'][:4]
                    states = [r[8] for r in records]
                    counts = [int.from_bytes(bytes(r[50:52]),'little') for r in records]
                    waits = [int.from_bytes(bytes(r[52:55]),'little') for r in records]
                    require(states.count(6)==(3 if case==12 else 2), 'Wrong semaphore wait state')
                    require(counts==([1,0,0,0] if case==12 else [0,1,0,0]),
                            'Removal protection did not transfer with ownership')
                    require(sum(bool(w) for w in waits)==(3 if case==12 else 2),
                            'Wait association lost')
                    report['fault_snapshot'] = dict(words=words,states=states,owned=counts,waits=waits)
                else:
                    require(words[2] == (0xffff if case == 6 else 1 if case in (5, 7, 8) else 0),
                            'Fault partially changed depth: '+str(words))
                    require(words[3:] == [0, 0, 0], 'Fault changed waiter links')
                    owned = bridge.peek16(program['build']['task_storage']['BASE']+
                                          program['build']['task_storage']['TCB_SEMAPHOREOWNED'])
                    require(owned == (0xffff if case == 7 else 1 if case in (5, 6) else 0),
                            'Fault changed owned count: '+str(owned))
                    report['fault_snapshot'] = dict(words=words, owned=owned)
            else:
                clean_ownership(bridge, program, program['output'])
            if case in (9, 10):
                from banked_test_memory import read
                base, size, begin, end = ((0x04fff0, 32, 10, 22) if case == 9 else (0x06ffe0, 96, 16, 78))
                raw = read(bridge, base, size, out)
                require(raw[:begin] == bytes([0xa5])*begin and raw[end:] == bytes([0xa5])*(size-end),
                        'Cross-bank record guards changed')
        if case in (0,14):
            report['timing'] = analyze(out/'emulator.log', d,case==14)
            if case==14:
                report['public_calls']=public_calls(out/'emulator.log',d,program)
                require(all(c['policy_continuations']==0 for c in report['public_calls']),
                        'Uncontended benchmark entered policy')
        elif case not in FAULTS:
            report['public_calls'] = public_calls(out/'emulator.log', d, program)
            if diagnostic and checkpoint in (40,46,47,48):
                require(sum(c['post_operation_polls'] for c in report['public_calls'])>0,
                        'Mutation checkpoint did not take post-operation Poll')
            if case==15:
                from sio_transaction_trace import BASE_HZ
                events=read_events(out/'emulator.log',kinds={'cpu'})
                replies=sum(int(e[4],16)==program['labels']['exec_reply_msg_native'] for _,e in events)
                require(replies==1,'Expected one native timer reply')
                blocked=next(c for c in report['public_calls'] if c['kind']=='ObtainSemaphore' and c['policy_continuations'])
                release=next(c for c in report['public_calls'] if c['kind']=='ReleaseSemaphore' and c['policy_continuations'])
                report['coexistence']=dict(native_timer_replies=replies,
                    blocked_obtain_ms=(blocked['end']-blocked['start'])/BASE_HZ*1000,
                    queued_release_to_obtain_return_ms=(blocked['end']-release['start'])/BASE_HZ*1000)
        report['status'] = 'pass'
        print('Passed', mode, suite+';', report['checks'], 'checks', flush=True)
        if 'timing' in report:
            print(json.dumps({n: v['charged_cpu_ms'] for n, v in report['timing']['batches'].items()}, indent=2))
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode', choices=('raw', 'opt'), default='opt')
    parser.add_argument('--suite', choices=tuple(CASES), default='baseline')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--diagnostic',action='store_true')
    parser.add_argument('--checkpoint',type=int,default=0)
    parser.add_argument('--irq',action='store_true')
    args = parser.parse_args()
    run(args.output.resolve(), args.mode, args.from_build.resolve() if args.from_build else None, args.suite,args.diagnostic,args.checkpoint,args.irq)
