#!/usr/bin/env python3
"""Emitted write cancellation, uncertain completion, shutdown and writer lifetime."""
import argparse
import json
import shutil
import time
from pathlib import Path

from library_paths import library_file, read_source
from native_program import ROOT, build, compiler, require, verify_machine, sha256, read_build
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute, ownership
from test_cooperative import data
from filesystem_audit import Audit, word
from generate_dos_mounts import encode

CASES = {'before': 1, 'wire': 2, 'final': 3, 'create': 4, 'close-break': 5,
         'write-error': 6, 'close-error': 7, 'stop': 8, 'detached': 9,
         'parent-first': 10, 'child-first': 11, 'cleanup-error': 12,
         'earlier-error': 13, 'create-error': 14, 'delete-error': 15,
         'rename-error': 16, 'truncate-error': 17, 'mkdir-error': 18,
         'delete-break': 19, 'rename-break': 20, 'truncate-break': 21, 'mkdir-break': 22}


def instrument(output):
    for name in ('filesystem_write_lifetime.act', 'fswriteprobe.act'):
        (output/name).write_text(read_source(ROOT/'tests/programs'/name))
    edits = {
        'fswriteio.act': [
            ('  IF BLOCKIO.BeginStore(', '  FSWRITEPROBE.Before(service)\n'
             '  IF Checkpoint(service)=0 THEN RETURN(0) FI\n  IF BLOCKIO.BeginStore('),
            ('  error=BLOCKIO.FinishStore(', '  error=FSWRITEPROBE.Completion(service,error)\n'
             '  error=BLOCKIO.FinishStore(')],
        'blockwire.act': [
            ('  EXEC.SendIO(EXEC.IORequest POINTER(request))',
             '  EXEC.SendIO(EXEC.IORequest POINTER(request))\n'
             '  IF cancellable=0 THEN FSWRITEPROBE.OnWire(EXEC.IORequest POINTER(request)) FI')],
    }
    for name, replacements in edits.items():
        source = read_source(library_file(name))
        source = source.replace('USE EXEC\n', 'USE EXEC\nUSE FSWRITEPROBE\n', 1)
        for old, new in replacements:
            require(source.count(old) == 1, 'Stale write hook: ' + name + ' ' + old)
            source = source.replace(old, new)
        if name == 'fswriteio.act':
            marker = '\nRETURN(1)\n\nPUBLIC PROC Zero('
            require(source.count(marker) == 1, 'Stale post-write hook')
            source = source.replace(marker, '\n  FSWRITEPROBE.After(service)\n' + marker)
        (output/name).write_text(source)
    return {name: sha256(output/name) for name in (*edits, 'fswriteprobe.act')}


def outcome(media, filesystem, baseline, fault, expected, target='WRITE.BIN'):
    audit = Audit(media.read_bytes())
    issue = None
    try:
        report = getattr(audit, filesystem)()
    except ValueError as error:
        require(fault, 'Allocation audit: ' + str(error))
        issue, report = str(error), None
    if not fault:
        additions=expected if isinstance(expected,dict) else {target:expected}
        require(audit.files == {**baseline.files, **additions},
                'Unexpected committed contents')
    else:
        # Independently compare every pre-existing payload/map allocation.
        # Shared directory/bitmap sectors legitimately change in this test.
        for sector, owner in baseline.owners.items():
            if owner == target or owner.startswith(target + ' '):
                continue
            if any(owner == path or owner.startswith(path + ' ')
                   for path in baseline.files):
                require(audit.image.sector(sector) == baseline.image.sector(sector),
                        'Unrelated file allocation changed: ' + owner)
    return dict(allocation=report, external_finding=issue,
                classification='consistent' if issue is None else 'requires-external-check',
                sha256=sha256(media))


def run(output, mode, filesystem, size, names, ordinal, from_build=None, path=None,
        amount=300, accurate=False, prime_tail=False, confirmed_bytes=0, profile=4):
    require(1<=amount<=8192,'Amount must be 1..8192')
    observers = instrument(output)
    baseline = Audit((ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr').read_bytes())
    getattr(baseline, filesystem)()
    mounts = [dict(alias='D1', unit=49, sectors=baseline.image.count,
                   sector_bytes=size, format=1 if filesystem == 'mydos' else 2,
                   access='readwrite',profile=profile)]
    program = read_build(from_build) if from_build else build(compiler(ROOT/'build/actionc'), output/'filesystem_write_lifetime.act', output,
                    optimize=mode == 'opt', tasks=True, task_capacity=8, console=True,
                    dos_mounts=mounts, image_data=[(0x30ffd0,bytes([0xa5])*(8192+64))])
    if from_build:
        record = program['build']
        require(sha256(output/'filesystem_write_lifetime.act') == record['source_sha256'], 'Changed test source')
        require(record['optimize'] == (mode == 'opt'), 'Changed emission mode')
        for group in ('platform_inputs', 'task_inputs', 'console_inputs', 'banked_inputs'):
            for input_name, digest in record.get(group, {}).items():
                require(sha256(ROOT/input_name) == digest, 'Changed input: ' + input_name)
        for input_name, digest in observers.items():
            require(sha256(from_build/input_name) == digest, 'Changed observer: ' + input_name)
    cases = []
    with emulator(ROOT/'build/altirra-sio-multi', ROOT/'build/firmware/altirraos-816.rom', output, pin=PIN) as bridge:
        configuration = {**PIN['configuration'],
                         'diskemu': {1:'fastest', 2:'810', 4:'generic56k'}[profile],
                         'accuratedisk': accurate}
        for key, value in configuration.items():
            bridge.config(key, str(value).lower() if isinstance(value, bool) else value)
        machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
        ordinals = ordinal if isinstance(ordinal, list) else [ordinal]
        for index, (name, ordinal) in enumerate((name, n) for name in names for n in ordinals):
            print('Write lifetime', name, ordinal, flush=True)
            case_out = output/(name if len(ordinals) == 1 else f'{name}-{ordinal}')
            case_out.mkdir(exist_ok=True)
            media = case_out/'volume.atr'
            shutil.copyfile(ROOT/f'tests/fixtures/filesystem-write/{filesystem}-{size}.atr', media)
            if index:
                bridge.state_load(slot='loaded')

            def before(bridge):
                if not index:
                    bridge.state_save(slot='loaded')
                bridge.mount(0, str(media))
                bridge.memload(program['build']['task_storage']['BASE'] + 0x900, encode(mounts))
                if path:
                    encoded=path.encode('ascii')+b'\0'
                    symbol=next(d for d in program['image']['data'] if '_FSWRITELIFETIME_PATH_' in d['name'])
                    require(len(encoded)<=symbol['size'], 'Injected path too long')
                    bridge.memload(symbol['address'],encoded)
                for key, value in (('scenario', CASES[name]), ('nth', ordinal), ('amount',amount)):
                    address = next(d['address'] for d in program['image']['data']
                                   if '_FSWRITELIFETIME_' + key.upper() + '_' in d['name'])
                    bridge.memload(address, value.to_bytes(2, 'little'))
                address=next(d['address'] for d in program['image']['data']
                             if '_FSWRITELIFETIME_PRIMETAIL_' in d['name'])
                bridge.poke(address,int(prime_tail))
                address=next(d['address'] for d in program['image']['data']
                             if '_FSWRITELIFETIME_CONFIRMEDBYTES_' in d['name'])
                bridge.memload(address,confirmed_bytes.to_bytes(2,'little'))

            try:
                runtime, _ = execute(bridge, {**program, 'output': case_out}, before_run=before,
                                     timeout=900, frame_limit=50000, preloaded=bool(index))
            except Exception:
                inspection = {**program['image'], 'data': [d for d in program['image']['data']
                                                          if '_FSWRITELIFETIME_' in d['name']]}
                print({key: data(bridge, inspection, key, True)
                       for key in ('checks', 'scenario', 'phase', 'result', 'error')}, flush=True)
                raise
            ownership(bridge, program, program['output'])
            probe_image = {**program['image'], 'data': [d for d in program['image']['data']
                                                     if '_FSWRITEPROBE_' in d['name']]}
            probe = {key: data(bridge, probe_image, key) for key in ('fired', 'count', 'wirePhase')}
            if name=='wire':
                start=int.from_bytes(bytes(data(bridge,probe_image,'deliveredFrame')),'little')
                view={**program['image'],'data':[d for d in program['image']['data'] if '_FSWRITELIFETIME_' in d['name']]}
                end=int.from_bytes(bytes(data(bridge,view,'collectedFrame')),'little')
                probe['break_pal_frames']=(end-start)&65535
            if name == 'wire':
                require(1 <= probe['wirePhase'][0] < 13, 'Missing actual wire injection')
            time.sleep(3)
            bridge.regs()
            bridge._cmd_ok('EJECT drive=0')
            view={**program['image'],'data':[d for d in program['image']['data'] if '_FSWRITELIFETIME_' in d['name']]}
            group_limit=int.from_bytes(bytes(data(bridge,view,'groupLimit')),'little')
            payload = bytes((i & 255) ^ 0x69 for i in range(amount))
            expected = {'before': b'', 'wire': payload[:size-3 if filesystem=='mydos' else size*group_limit],
                        'final': payload[:17], 'create': b'', 'close-break': b'',
                        'stop': payload, 'detached': payload[:17],
                        'parent-first': payload[:17]*2, 'child-first': payload[:17]*2,
                        'delete-break':{}, 'rename-break':{'TARGET':payload},
                        'truncate-break':b'', 'mkdir-break':{}}.get(name)
            if name=='before':
                expected=payload[:confirmed_bytes]
            if name=='wire' and filesystem=='mydos' and prime_tail:
                expected=payload[:size-3]+payload[:(size-3)*group_limit]
            target = path.partition(':')[2] if path else 'WRITE.BIN'
            report = outcome(media, filesystem, baseline, expected is None, expected, target)
            if name=='mkdir-break':
                require(report['allocation']['directories']==baseline.directories+1,
                        'Committed directory was not published')
            cases.append(dict(name=name, ordinal=ordinal, runtime=runtime, probe=probe,
                              group_limit=group_limit,
                              media=report, status='pass'))
            (output/'progress.json').write_text(json.dumps(cases, indent=2) + '\n')
    return dict(status='pass', build=program['build'], cases=cases, observers=observers,
                configuration=configuration, machine=machine, path_override=path,
                confirmed_bytes=confirmed_bytes,
                scope='Development only: task-side injection at physical write boundaries; '
                      'lost completion is injected after the real transport reply, not a device fault.',
                bank_zero_delta=dict(fixed=0, per_task=0))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case', choices=('raw', 'opt'), required=True)
    parser.add_argument('--filesystem', choices=('mydos', 'sdfs'), required=True)
    parser.add_argument('--size', type=int, choices=(128, 256), default=128)
    parser.add_argument('--suite', default=','.join(CASES))
    parser.add_argument('--ordinal', type=int, default=1)
    parser.add_argument('--ordinals', help='Comma-separated physical write boundaries for one fault operation')
    parser.add_argument('--from-build', type=Path)
    parser.add_argument('--amount',type=int,default=300)
    parser.add_argument('--confirmed-bytes',type=int,default=0,
                        help='Expected earlier complete prefix on a later-group failure')
    parser.add_argument('--accurate-media',action='store_true')
    parser.add_argument('--profile',type=int,choices=(1,2,4),default=4)
    parser.add_argument('--prime-tail',action='store_true',help='Start wire cancellation on newly allocated MyDOS sectors')
    parser.add_argument('--path', help='Existing short fixture path for split-record fault checks')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    result = dict(status='running')
    try:
        result = run(output, args.case, args.filesystem, args.size, args.suite.split(','),
                     [int(n) for n in args.ordinals.split(',')] if args.ordinals else args.ordinal,
                     args.from_build.resolve() if args.from_build else None,
                     args.path, args.amount, args.accurate_media, args.prime_tail,
                     args.confirmed_bytes, args.profile)
    except Exception as error:
        result.update(status='fail', error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('Write lifetime passed', args.case, args.filesystem)
