#!/usr/bin/env python3
"""GF0: private loaded Counters beside native filesystem/SIO work."""
import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from unittest.mock import patch

import adapter_state as adapter
from build_bitmap_console import drawing, prepare
from bitmap_console_performance import native_markers
from build_c_program import build as application
from c_program import ABI, binding
from filesystem_audit import Audit
from gem_applications import instances
from gem_first_observe import digit_pixels, progress
from console_turn_profile import analyze_events, Timeline
from desktop_mouse import schedule
from generate_aes_server import expected_layout, layout, ABI as AES_ABI
from generate_desktop import layout as desktop_layout, ABI as DESKTOP_ABI
from generate_memory import PROFILE
from make_data_disk import make
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from sio_transaction_trace import read_events
from stack_budget import current_task_memory, stack_usage
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, ROM, PIN
from generate_mouse_acceleration import metadata as mouse_metadata

CASES = ('idle', 'disk', 'blocking', 'update-held', 'cancel')
PAYLOAD = bytes((i ^ (i >> 8) ^ 0x5a) & 255 for i in range(16384))
INPUTS = (
    'tests/programs/gem_first.act', 'tests/programs/gem_first_counter.c',
    'tests/programs/gem_first_provider.c', 'examples/gem-counter/counter.c',
    'examples/gem-counter/counter.h', 'tools/test_gem_first.py',
)


def snapshot_sources(out):
    """Preserve native GUI modules as well as the build's kernel input lists."""
    paths = {ROOT/name for name in INPUTS}
    paths.add(ROOT/'tools/gem_first_observe.py')
    for directory in ('lib', 'platform', 'c/include', 'abi', 'toolchain'):
        paths.update(path for path in (ROOT/directory).rglob('*')
                     if path.is_file() and path.suffix in ('.act', '.inc', '.s', '.h', '.json'))
    hashes = {}
    for path in sorted(paths):
        relative = path.relative_to(ROOT)
        target = out/'source-snapshot'/relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[str(relative)] = sha256(path)
    (out/'source-snapshot.json').write_text(json.dumps(hashes, indent=2)+'\n')
    return hashes


def build_fixture(out):
    out.mkdir(parents=True, exist_ok=True)
    application(out/'apps/counter', [ROOT/'tests/programs/gem_first_counter.c',
                ROOT/'examples/gem-counter/counter.c'], minimum_stack=1312)
    media = out/'media'
    (media/'C').mkdir(parents=True, exist_ok=True)
    shutil.copyfile(out/'apps/counter/program.app', media/'C/COUNTER.APP')
    (media/'LOAD.BIN').write_bytes(PAYLOAD)
    make(out/'seed.atr', media, binary_names={'C/COUNTER.APP', 'LOAD.BIN'},
         sector_bytes=256, sectors=2880, filesystem='sdfs')
    foreign = drawing(out, True, widgets=True, client_sources=[
        ROOT/'c/calypsi/aes.c', ROOT/'c/calypsi/aes-messages.c',
        ROOT/'c/calypsi/aes-events.c', ROOT/'c/calypsi/program.c',
        ROOT/'tests/programs/gem_first_provider.c'],
        client_roots=['GFStart', 'GFAbort', 'GFStop', 'GFChildren', 'GFFailure',
                      'ExecProgramRun', *ABI['imports']],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c', expected_layout())])
    binding(foreign, out)
    (out/'c-image.json').write_text(json.dumps(foreign, indent=2)+'\n')
    return compile_native(out, foreign)


def compile_native(out, foreign):
    """Rebuild only the native fixture when its controller changes."""
    text = (ROOT/'tests/programs/gem_first.act').read_text()
    for name in ('GFStart', 'GFChildren', 'GFStop'):
        text = text.replace('$'+name.upper(), '$'+format(foreign['symbols'][name], 'x'))
    source = out/'gem-first.act'
    source.write_text(text)
    profile = json.loads(PROFILE.read_text())
    profile['image_data_bytes'] = 11264
    memory = out/'fixture-memory.json'
    memory.write_text(json.dumps(profile, indent=2)+'\n')
    launcher = prepare(source, out, foreign, desktop=True, aes=True)
    program = build(compiler(ROOT/'build/actionc', release=True), launcher,
                    out/'program', tasks=True, task_capacity=12, optimize=True,
                    foreign_image=foreign, console_deferred=True,
                    memory_profile=memory, stack_checks=True, system_mount='D1',
                    dos_mounts=[dict(alias='D1', unit=49, sectors=2880,
                                     sector_bytes=256, profile=4, format=2,
                                     access='readwrite')])
    baseline = current_task_memory()
    for key in ('bank_zero_budget', 'task_pools', 'runtime_reservations'):
        require(program['build']['memory'][key] == baseline[key],
                'GF0 changed reserved bank-zero storage: '+key)
    record = dict(inputs={name: sha256(ROOT/name) for name in INPUTS},
                  seed_sha256=sha256(out/'seed.atr'), xex_sha256=sha256(program['xex']),
                  counter_body_sha256=sha256(ROOT/'examples/gem-counter/counter.c'))
    record['source_snapshot'] = snapshot_sources(out)
    (out/'fixture.json').write_text(json.dumps(record, indent=2)+'\n')
    return program, foreign


def fixture(out, reuse=False):
    if not reuse:
        return build_fixture(out)
    record = json.loads((out/'fixture.json').read_text())
    for name, digest in record['inputs'].items():
        if name != 'tools/test_gem_first.py':
            require(sha256(ROOT/name) == digest, 'Changed GF0 input: '+name)
    program = read_build(out/'program')
    require(sha256(program['xex']) == record['xex_sha256'], 'Changed GF0 executable')
    require(sha256(out/'seed.atr') == record['seed_sha256'], 'Changed GF0 seed disk')
    return program, json.loads((out/'c-image.json').read_text())


class PrefixCaptured(Exception):
    """Ends an observation-only emulator instance without claiming cleanup."""


def run_case(out, p, foreign, name, cpu_prefix=False):
    folder = out/(name+'-cpu-prefix' if cpu_prefix else name)
    folder.mkdir(parents=True, exist_ok=True)
    disk = folder/'disk.atr'
    shutil.copyfile(out/'seed.atr', disk)
    report = dict(name=name, status='running', samples=[])
    at = lambda field: next(d['address'] for d in p['image']['data']
                            if '_GEMFIRST_'+field.upper()+'_' in d['name'])
    sy = foreign['symbols']
    memory = p['build']['memory']
    turn = native_markers(p, [('AESSYSTEM_COLLECT', 'turn')])['turn']['entry']
    restore = p['labels']['context_restore']
    hosted = (p['output']/'hosted.bin').read_bytes()
    require(hosted[restore-adapter.RESIDENT_BASE:restore-adapter.RESIDENT_BASE+8]
            == bytes.fromhex('c230ab2b7afa6840'), 'Unknown context restore sequence')
    points = {key: p['labels'][key] for key in ('native_irq', 'native_nmi', 'interrupt_schedule')}
    points.update(turn=turn, selected=restore+4)
    definition = dict(spans={}, points=points, task_dps=[row['dp'] for row in memory['task_pools']])
    traced = cpu_prefix
    environment = {key: value for key, value in os.environ.items()
                   if key not in ('EXEC816_LATENCY_TRACE', 'EXEC816_MASK_TRACE', 'EXEC816_LATENCY_PCS')}
    if traced:
        environment.update(EXEC816_LATENCY_TRACE='1',
            EXEC816_LATENCY_PCS=','.join(format(pc, 'x') for pc in sorted(set(points.values()))))
    (folder/'trace-definition.json').write_text(json.dumps(definition, indent=2)+'\n')
    native_at = lambda module, field: next(d['address'] for d in p['image']['data']
                                           if '_'+module+'_'+field.upper()+'_' in d['name'])
    try:
        with patch.dict(os.environ, environment, clear=True), emulator(BRIDGE, ROM, folder, pin=PIN) as b:
            b.config('diskemu', 'generic56k')
            b.mount(0, str(disk))
            b._cmd_ok('MOUSE ST')
            report['machine'] = verify_machine(b, ROM, PIN)
            number = lambda address, size=2: int.from_bytes(b.memdump(address, size), 'little')

            def reach(condition, limit=18000):
                marker = p['labels']['native_irq']
                b.bp_clear_all()
                b.bp_set(marker, condition=condition)
                b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
                original = b.regs
                def registers():
                    value = original()
                    if int(value['PC'].lstrip('$'), 16) == p['labels']['done']:
                        raise RuntimeError('Guest stopped: '+hex(number(adapter.STATE)))
                    return value
                b.regs = registers
                try:
                    run_to(b, marker, condition=condition, frame_limit=limit, timeout=600)
                finally:
                    b.regs = original
                require(number(adapter.STATE) == 65535, 'Fixture stopped before rendezvous')
                b.bp_clear_all()

            def frames(count):
                reach('@frame>='+str(b.eval_expr('@frame')+count))

            def sample(label):
                clients = sorted(instances(b, p, out), key=lambda item: item['identity'])
                frame_path = folder/('%02d-%s-scanout.bgra' % (len(report['samples']), label))
                frame = b.rawscreen(str(frame_path))
                raw = frame_path.read_bytes()
                entries = []
                for client in clients:
                    base = client['symbols']['GEMCounter']
                    config = number(base, 4)
                    pixels = b''
                    if config:
                        # Counter's fixed NAME frame has 8/11-pixel work insets.
                        x, y = number(config+4), number(config+6)
                        pixels = digit_pixels(raw, frame.stride, frame.width, frame.height,
                                              x+8+64, y+11+8)
                    entries.append(dict(identity=client['identity'], base=client['base'],
                        ready=number(base+12), count=number(base+14, 4),
                        paints=number(base+18, 4), id=number(base+4),
                        window=number(base+8), work=[number(base+38+i*2) for i in range(4)],
                        io_phase=number(client['symbols']['GFIOPhase']),
                        io_loops=number(client['symbols']['GFIOLoops'], 4),
                        io_bytes=number(client['symbols']['GFIOBytes'], 4),
                        io_error=number(client['symbols']['GFIOError'])))
                    entries[-1]['digits_sha256'] = hashlib.sha256(pixels).hexdigest()
                result = dict(label=label, frame=b.eval_expr('@frame'),
                              clock=b.eval_expr('@clk'), clients=entries,
                              live_tasks=number(p['build']['task_storage']['LIVE'], 1),
                              heartbeat=number(at('heartbeat'), 4), phase=number(at('phase')),
                              scanout=frame_path.name, scanout_sha256=sha256(frame_path))
                storage = p['build']['task_storage']
                result['tasks'] = []
                for slot, pool in enumerate(memory['task_pools'][:12]):
                    row = b.memdump(storage['BASE']+slot*storage['SIZE'], storage['SIZE'])
                    state = row[storage['TCB_STATE']]
                    if state:
                        task = int.from_bytes(row[storage['TCB_ITEM']:storage['TCB_ITEM']+3], 'little')
                        app = next((client for client in clients if client['task'] == task), None)
                        entry = int.from_bytes(row[storage['TCB_ENTRY']:storage['TCB_ENTRY']+3], 'little')
                        routine = next((item['name'] for item in p['image']['routines']
                                        if item['address'] == entry), None)
                        result['tasks'].append(dict(slot=slot, dp=pool['dp'], state=state,
                            task=task, entry=routine, app=None if app is None else app['identity'],
                            stack_bytes=pool['stack_bytes']))
                records = layout()
                contexts = b.memdump(sy['contexts'], 4*AES_ABI['constants']['CONTEXTS'])
                result['aes_registrations'] = sum(
                    bool(number(int.from_bytes(contexts[i:i+4], 'little')+records['Request']['fields']['client'], 4))
                    for i in range(0, len(contexts), 4) if any(contexts[i:i+4]))
                desktop = number(native_at('DESKSTATE', 'service'), 3)
                records = desktop_layout()
                result['focus'] = number(desktop+records['Service']['fields']['focus'], 4)
                result['windows'] = []
                for index in range(DESKTOP_ABI['constants']['WINDOWS']):
                    window = desktop+records['Service']['fields']['windows']+index*records['Window']['size']
                    identity = number(window+records['Window']['fields']['id'], 4)
                    if identity:
                        title = b.memdump(window+records['Window']['fields']['title'], 65).split(b'\0')[0]
                        result['windows'].append(dict(id=identity, title=title.decode('ascii')))
                result['wire_phase'] = number(p['labels']['SD_PHASE'], 1)
                result['wire_posts'] = number(p['labels']['SD_POSTS'])
                report['samples'].append(result)
                return result

            def pointer(label):
                x_at = native_at('DESKINPUT', 'cursorX')
                y_at = native_at('DESKINPUT', 'cursorY')
                current = [number(x_at), number(y_at)]
                target = [current[0]+8, current[1]+8]
                # Read the active native preference through the existing helper.
                observed = {**p, 'build': {**p['build'], 'desktop_mouse': mouse_metadata(None)}}
                start = b.eval_expr('@clk')
                x, y = schedule(b, observed, current, target)
                reach('(dw($%x)=%d)&(dw($%x)=%d)' % (x_at, x, y_at, y))
                captured = b.eval_expr('@clk')
                reach('(db($%x)=0)' % native_at('DESKINPUT', 'dirty'))
                presented = b.eval_expr('@clk')
                frames(1)
                report.setdefault('pointer', []).append(dict(label=label, target=[x, y],
                    start=start, captured=captured, presented=presented,
                    capture_ms=((captured-start)&0xffffffff)/1773447.5*1000,
                    presentation_ms=((presented-start)&0xffffffff)/1773447.5*1000,
                    scanout_observed=b.eval_expr('@clk')))

            def before(bridge):
                b.poke16(at('variant'), CASES.index(name))
                if traced:
                    b.profile_start()
                reach('dw($%x)=1' % at('ready'))
                clients = instances(b, p, out)
                require(len(clients) == 2, 'Two private application images were not retained')
                clients.sort(key=lambda c: c['identity'])
                report['identities'] = [c['identity'] for c in clients]
                ready = [c['symbols']['GEMCounter']+12 for c in clients]
                if name not in ('idle', 'disk'):
                    ready[1] = clients[1]['symbols']['GFIOReady']
                reach('&'.join('(dw($%x)=1)' % address for address in ready))
                initial = sample('ready')
                b.poke16(at('command'), 1)
                if name == 'disk':
                    active = '(db($%x)>0)&(db($%x)<13)' % (p['labels']['SD_PHASE'], p['labels']['SD_PHASE'])
                    reach('(dw($%x)=2)&(%s)' % (at('phase'), active))
                    pointer('disk')
                    for _ in range(4):
                        reach('((dw($%x)=2)|(dw($%x)=3))&(%s)' % (at('phase'), at('phase'), active))
                        frames(100)
                        sample('disk')
                    if cpu_prefix:
                        final = report['samples'][-1]
                        report['window'] = [initial['clock'], final['clock']]
                        # A later context boundary must bracket the final sample.
                        frames(2)
                        report['stacks'] = stack_usage(b, memory)
                        report['scope'] = 'Timing prefix only; no completion, persistence or cleanup claim'
                        b.profile_stop()
                        raise PrefixCaptured
                    reach('dw($%x)=4' % at('phase'))
                elif name not in ('idle', 'disk'):
                    io = clients[1]['symbols']
                    reach('dw($%x)=1' % io['GFIOPhase'])
                    if name == 'cancel':
                        reach('(dw($%x)=1)&(db($%x)>0)&(db($%x)<13)' %
                              (io['GFIOPhase'], p['labels']['SD_PHASE'], p['labels']['SD_PHASE']))
                    blocked = sample('blocked')
                    if name == 'cancel':
                        b.poke16(at('command'), 2)
                    else:
                        frames(75)
                        during = sample('during-read')
                        require(during['clients'][1]['io_phase'] == 1,
                                'Read did not span one observed second')
                        require(during['clients'][1]['io_loops'] == blocked['clients'][1]['io_loops'],
                                'Synchronous read did not block its own event loop')
                        require(during['heartbeat'] > blocked['heartbeat'], 'Heartbeat stopped during Read')
                        if name == 'update-held':
                            require(during['clients'][0]['paints'] == blocked['clients'][0]['paints'],
                                    'Peer painted through held UPDATE')
                        else:
                            progress(blocked, during, 1)
                    reach('dw($%x)=%d' % (io['GFIOPhase'], 3 if name == 'cancel' else 2))
                else:
                    pointer('idle')
                    frames(200)
                frames(100)
                final = sample('complete')
                report['progress'] = progress(initial, final, 2 if name in ('idle', 'disk') else 1)
                if name in ('idle', 'disk'):
                    inactive = next(row['id'] for row in final['windows'] if row['title'] == 'Counter A')
                    require(final['focus'] != inactive, 'Inactive-window control gained focus')
                report['window'] = [initial['clock'], final['clock']]
                report['stacks'] = stack_usage(b, memory)
                b.screenshot(str(folder/'scene.png'))
                if traced:
                    b.profile_stop()
                b.poke16(at('command'), 9)

            try:
                report['runtime'], _ = execute(b, p, before_run=before,
                                               frame_limit=18000, timeout=600)
            except PrefixCaptured:
                require(cpu_prefix, 'Unexpected early capture exit')
            else:
                ownership(b, p, p['output'])
                require(number(sy['GFFailure']) == 0, 'Application failed: '+str(number(sy['GFFailure'])))
                report['checks'] = number(at('checks'))
        if traced:
            events = read_events(folder/'emulator.log', kinds={'cpu'})
            interrupt_entries = {points['native_irq'], points['native_nmi']}
            while events and int(events[-1][1][4], 16) in interrupt_entries:
                events.pop()
            profile = analyze_events(events, definition, include_segments=True)
            start, end = report['window']
            align = lambda tick: tick+round((events[0][0]-tick)/(1 << 32))*(1 << 32)
            start, end = align(start), align(end)
            report['cpu'] = {str(slot): Timeline(profile['segments'], pool['dp']).measure(start, end)
                             for slot, pool in enumerate(memory['task_pools'])}
            report['system_worker_dp'] = profile['worker_dp']
        if name == 'disk':
            samples = [s for s in report['samples'] if s['label'] == 'disk']
            require(all(s['phase'] in (2, 3) for s in samples), 'Disk cohort finished before observations')
            report['disk_progress'] = progress(samples[0], samples[-1])
        if not cpu_prefix:
            audit = Audit(disk.read_bytes())
            report['filesystem'] = audit.sdfs()
            require(audit.files['LOAD.BIN'] == PAYLOAD, 'Read-only input changed')
            if name == 'disk':
                require(audit.files['RESULT.BIN'] == PAYLOAD, 'Persisted output differs')
        report.update(status='captured' if cpu_prefix else 'pass', media_sha256=sha256(disk))
        report['observer_inputs'] = {str(path.relative_to(ROOT)): sha256(path) for path in (
            Path(__file__), ROOT/'tools/gem_first_observe.py', ROOT/'tools/console_turn_profile.py',
            ROOT/'tools/gem_applications.py', ROOT/'tools/sio_transaction_trace.py')}
        return report
    except Exception as error:
        report.update(status='fail', error=str(error))
        raise
    finally:
        (folder/'results.json').write_text(json.dumps(report, indent=2)+'\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--reuse', action='store_true')
    parser.add_argument('--build-only', action='store_true')
    parser.add_argument('--trace-prefix', action='store_true', help='Disk CPU observation only; no completion/cleanup claim')
    parser.add_argument('--case', choices=CASES, action='append')
    args = parser.parse_args()
    require(not args.trace_prefix or args.case == ['disk'], 'Trace prefix requires --case disk')
    out = args.output.resolve()
    p, foreign = fixture(out, args.reuse)
    if not args.build_only:
        results = []
        for name in args.case or CASES:
            print('GF0:', name, flush=True)
            results.append(run_case(out, p, foreign, name, args.trace_prefix))
        record = dict(status='captured' if args.trace_prefix else 'pass', tier='development', qualification=False,
                      cases=results, xex_sha256=sha256(p['xex']),
                      bank_zero_delta=dict(fixed=0, root=0, kernel=0,
                                           per_public_task=[0]*12, idle=0))
        (out/('trace-results.json' if args.trace_prefix else 'results.json')).write_text(json.dumps(record, indent=2)+'\n')


if __name__ == '__main__':
    main()
