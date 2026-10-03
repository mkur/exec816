#!/usr/bin/env python3
"""M1: existing emitted SIO transfers with a fixed diagnostic sampler."""
import argparse
import json
import os
import re
from pathlib import Path

from native_program import ROOT, build, compiler, execute, require, verify_machine, sha256, read_build
from os_boundary import emulator
from sio_transactions import disk_image
from sio_adapter_trace import analyze
from sio_transaction_trace import read_events, BASE_HZ, stats
from stack_budget import stack_usage
from test_cooperative import data
from test_mouse_observe import PIN, BRIDGE, ROM
from mouse_timer_trace import accounting


def fixture(out, capture=False):
    # Reuse the existing exact-byte, deadline and guard assertions. Only add
    # ownership order/capture checks around those real transfers.
    for name in ('timerprobe.act', 'producerprobe.act', 'sioprobe.act'):
        (out/name).write_text((ROOT/'tests/programs'/name).read_text())
    if capture:
        (out/'timerprobe.act').write_text((ROOT/'tests/programs/timer_input_probe.act').read_text())
    text = (ROOT/'tests/programs/sio_adapter.act').read_text()
    text = text.replace('INCLUDE "tasks_exec_helpers.inc"',
                        f'INCLUDE "{ROOT}/tests/programs/tasks_exec_helpers.inc"')
    text = text.replace('USE EXEC\n', 'USE EXEC\nUSE TIMERPROBE\n')
    text = text.replace('  added=EXEC.AddTask',
        '  background.tc_SPUpper=ADDRESS(TASKSTACKS.UPPER1)\n'
        '  background.tc_SPReg=ADDRESS(TASKSTACKS.UPPER1-2)\n'
        '  added=EXEC.AddTask')
    text = text.replace('  bit=EXEC.AllocSignal(31)',
                        '  Require(added<>NULL)\n  bit=EXEC.AllocSignal(31)')
    text = text.replace('BYTE variant', '''BYTE variant,mouseOrder
BYTE POINTER timerUsers,timerAlarm
CARD POINTER timerSamples
CARD sampleBefore
BYTE savedMask
VOLATILE BYTE pokmsk=$10''')
    text = text.replace('  IF variant=5 THEN', '''  IF mouseOrder=3 THEN
    Require(sharedAlarm=1)
    TIMERPROBE.Stop()
    Require(sharedUsers=1 AND sharedAlarm=1)
  ELSEIF mouseOrder=4 THEN
    Require(sharedAlarm=1)
    Require(TIMERPROBE.Start()=1)
    Require(sharedUsers=3 AND sharedAlarm=1)
  FI

  IF variant=5 THEN''')
    text = text.replace('''  Setup()
  Transfers()
  SIOADAPTER.Shutdown()''', '''  savedMask=pokmsk
  pokmsk=savedMask OR 1
  Require(TIMERPROBE.Start()=0 AND sharedUsers=0)
  pokmsk=savedMask
  IF mouseOrder=0 OR mouseOrder=5 THEN
    Require(TIMERPROBE.Start()=1)
  FI

  Setup()
  IF mouseOrder<>0 AND mouseOrder<>4 AND mouseOrder<>5 THEN
    Require(TIMERPROBE.Start()=1)
  FI

  IF mouseOrder<>4 THEN
    sampleBefore=sharedSamples
    EXECTASKS.Sleep(3)
    Require(sharedSamples<>sampleBefore AND sharedUsers=3)
  FI

  Transfers()
  IF mouseOrder=1 OR mouseOrder=3 OR mouseOrder=5 THEN
    TIMERPROBE.Stop()
    Require(sharedUsers=1)
    SIOADAPTER.Shutdown()
  ELSE
    SIOADAPTER.Shutdown()
    Require(sharedUsers=2)
    sampleBefore=sharedSamples
    EXECTASKS.Sleep(3)
    Require(sharedSamples<>sampleBefore)
    TIMERPROBE.Stop()
  FI

  Require(sharedUsers=0 AND sharedAlarm=0)''')
    # The second transfer tests reacquisition after an in-flight stop too.
    text = text.replace('  okay=SIOADAPTER.Start()', '''  IF mouseOrder=3 THEN
    Require(TIMERPROBE.Start()=1 OR sharedUsers=3)
  ELSEIF mouseOrder=4 AND sharedUsers=3 THEN
    TIMERPROBE.Stop()
  FI

  okay=SIOADAPTER.Start()''')
    for name, pointer in [('sharedUsers','timerUsers'), ('sharedAlarm','timerAlarm'), ('sharedSamples','timerSamples')]:
        text = re.sub(r'\b'+name+r'\b', pointer+'^', text)
    text = text.replace('PROC Main()\n', 'PROC Main()\n\n'
        '  timerUsers=BYTE POINTER($3f0f30)\n'
        '  timerAlarm=BYTE POINTER($3f0f32)\n'
        '  timerSamples=CARD POINTER($3f0f3a)\n')
    path = out/'shared_timer.act'
    path.write_text(text)
    return path


def run(out, mode, order, emulation=False, unobserved=False, capture=False):
    out.mkdir(parents=True, exist_ok=True)
    pin = json.loads(json.dumps(PIN))
    pin['startup_configuration']['diskemu'] = 'fastest'
    report = dict(status='running', slice='M3' if capture else 'M1', tier='development', mode=mode,
                  order=order, emulation=emulation, observer=not unobserved, pin=pin, capture=capture)
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'],
                'Unpinned timer observer')
        p = build(compiler(ROOT/'build/actionc'), fixture(out,capture), out/'program',
                  optimize=mode == 'opt', tasks=True, task_capacity=8, io_test_device=True, irq_probe=11,
                  image_data=[(a, bytes([0xa5])*256) for a in (0x8ffa0, 0xcffa0)])
        capture_boundaries = [r['address'] for r in p['image']['routines']
                              if r['name'].startswith(('M_TIMERPROBE_START_', 'M_TIMERPROBE_STOP_'))]
        capture_pcs = ','+','.join(f'{v:x}' for v in capture_boundaries) if capture else ''
        baseline = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget', 'task_pools', 'runtime_reservations', 'phase_reservations'):
            require(p['build']['memory'][key] == baseline[key], 'Bank-zero change: '+key)
        disk_image(out/'disk.atr')
        os.environ.update(EXEC816_LATENCY_TRACE='1', EXEC816_MASK_TRACE='1',
            EXEC816_LATENCY_PCS=','.join(f'{v:x}' for k, v in p['labels'].items()
                if k.startswith(('sio_', 'timer_', 'native_', 'signal_route', 'dispatch_', 'context_restore')))+capture_pcs)
        if unobserved:
            for name in ('EXEC816_LATENCY_TRACE', 'EXEC816_MASK_TRACE', 'EXEC816_LATENCY_PCS'):
                os.environ.pop(name, None)
        with emulator(BRIDGE, ROM, out, pin=pin) as b:
            b.config('diskemu', 'fastest')
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, pin)
            at = lambda n: next(d['address'] for d in p['image']['data'] if '_'+n.upper()+'_' in d['name'])
            saved = {}
            def before(bridge):
                if not unobserved:
                    b.profile_start()
                for address, length in ((0x20a, 10), (0x10, 1), (0x232, 1)):
                    saved[address] = b.memdump(address, length)
                b.mount(0, str(out/'disk.atr'))
                b.memload(at('mouseOrder'), bytes([order]))
                b.memload(at('variant'), bytes([5 if emulation else 0]))
                if capture:
                    for i,(dx,dy) in enumerate([(128,0),(-128,0),(0,128),(0,-128)]):
                        b._cmd_ok(f'MOUSE AT {50000+i*200000} {dx} {dy} -1')
                    b._cmd_ok('MOUSE AT 750000 0 0 1')
                    b._cmd_ok('MOUSE AT 800000 0 0 0')
            try:
                runtime, _ = execute(b, p, before_run=before, timeout=120, frame_limit=6000)
            except Exception:
                report['failure'] = dict(checks=data(b, p['image'], 'checks', True),
                    descriptor=b.memdump(0x3f0800, 128).hex(),
                    timer=b.memdump(0x3f0f30, 32).hex(),
                    progress=data(b, p['image'], 'progress', True))
                raise
            if not unobserved:
                b.profile_stop()
            for address, value in saved.items():
                require(b.memdump(address, len(value)) == value, 'Timer hardware restoration '+hex(address))
            if capture:
                report['captured'] = dict(samples=data(b,p['image'],'samples',True)[0],
                                          losses=data(b,p['image'],'losses',True)[0])
                require(report['captured']['samples']>0 and report['captured']['losses']==0,
                        'Addressed capture did not survive SIO: '+str(report['captured']))
            report.update(runtime=runtime, checks=data(b, p['image'], 'checks', True),
                          results=data(b, p['image'], 'results', True),
                          stack_usage=stack_usage(b, p['build']['memory']))
        if unobserved:
            report.update(status='pass', build=p['build'], xex_sha256=sha256(p['xex']),
                          bank_zero_delta=dict(fixed=0, per_task=[0]*8, private_idle=0))
            return report
        timing = analyze(out/'emulator.log', p['labels'])
        require(timing['verdict'] == 'pass', 'Serial timing regression: '+str(timing))
        events = read_events(out/'emulator.log')
        sharedSamples = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) == p['labels']['timer_sample']]
        boundaries = [t for t, e in events if e[0] == 'cpu' and int(e[4], 16) in
                      (capture_boundaries if capture else (p['labels']['timer_probe_start'], p['labels']['timer_probe_stop']))]
        gaps = [b-a for a, b in zip(sharedSamples, sharedSamples[1:]) if not any(a < t <= b for t in boundaries)]
        require(len(gaps) > 100, 'Sampler not exercised')
        require(max(gaps)/BASE_HZ < .001, 'Sample gap exceeds 1 ms: '+str(stats(gaps)))
        report.update(status='pass', timing=timing, sample_gaps=stats(gaps), sample_count=len(sharedSamples),
                      timer_accounting=accounting(out/'emulator.log', p['labels']),
                      build=p['build'], xex_sha256=sha256(p['xex']),
                      bank_zero_delta=dict(fixed=0, per_task=[0]*8, private_idle=0))
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    print('Shared timer passed:', mode, order, emulation, flush=True)
    return report


def recovery_run(out, mode, capture=False, replay=False):
    """Keep the sampler alive through real cancellation and offline recovery."""
    import test_sio_recovery
    out.mkdir(parents=True, exist_ok=True)
    for name in ('timerprobe.act', 'producerprobe.act', 'sioprobe.act'):
        (out/name).write_text((ROOT/'tests/programs'/name).read_text())
    if capture:
        (out/'timerprobe.act').write_text((ROOT/'tests/programs/timer_input_probe.act').read_text())
    source = ROOT/'tests/programs/sio_recovery.act'
    text = re.sub(r'INCLUDE "([^"]+)"',
                  lambda m: 'INCLUDE "'+str((source.parent/m[1]).resolve())+'"', source.read_text())
    text = text.replace('USE EXEC\n', 'USE EXEC\nUSE TIMERPROBE\n')
    text = text.replace('CARD checks,sectorSize', 'CARD checks,sectorSize,sampleBefore\nCARD POINTER timerSamples')
    text = text.replace('  Rollback()',
        '  timerSamples=CARD POINTER($3f0f3a)\n'
        '  Require(TIMERPROBE.Start()=1)\n  Rollback()')
    text = text.replace('  cleanupReached=1', '  TIMERPROBE.Stop()\n  cleanupReached=1')
    text = text.replace('  Cleanup()',
        '  sampleBefore=timerSamples^\n  EXECTASKS.Sleep(3)\n'
        '  Require(timerSamples^<>sampleBefore)\n  Cleanup()')
    path = out/'timer_recovery.act'
    path.write_text(text)
    report = dict(status='running', slice='M5' if capture else 'M1', tier='development', mode=mode,capture=capture,
                      stimulus='Idle physical port during fault recovery; motion uses the pinned main mouse bridge.')
    try:
        p = read_build(out) if replay else build(compiler(ROOT/'build/actionc'), path, out, optimize=mode == 'opt',
                  tasks=True, task_capacity=8, io_test_device=True, irq_probe=11)
        for name in ('functional','timed','active-256'):(out/name).mkdir(exist_ok=True)
        report['result'] = test_sio_recovery.run(None, out/'functional', mode == 'opt',
                ['queued','active','terminal','checksum','nak'], False, prepared=p)
        report['timed'] = test_sio_recovery.run(None, out/'timed', mode == 'opt',
                ['wrap','absent'], True, prepared=p)
        # A 256-byte read keeps the active payload window open long enough
        # for a Task-driven abort under capture/trace load. Terminal-won
        # cancellation is covered separately; retain the existing time bound.
        report['timed_active_256'] = test_sio_recovery.run(None, out/'active-256', mode == 'opt',
                ['active'], True, sector_size=256, prepared=p)
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode', choices=('raw', 'opt'), required=True)
    p.add_argument('--order', type=int, choices=range(6), default=0)
    p.add_argument('--emulation', action='store_true')
    p.add_argument('--unobserved', action='store_true')
    p.add_argument('--capture', action='store_true')
    p.add_argument('--recovery', action='store_true')
    p.add_argument('--replay',action='store_true',help='Reuse a built recovery fixture')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    if args.recovery:
        recovery_run(args.output.resolve(), args.mode,args.capture,args.replay)
    else:
        run(args.output.resolve(), args.mode, args.order, args.emulation, args.unobserved, args.capture)
