#!/usr/bin/env python3
"""Executable DOS stream slice gates, using the pinned compiler and platform."""
import adapter_state as adapter
import argparse
import json
import shutil
from pathlib import Path

from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def fixture(t, out, mode, source, bank=1, large=False):
    out.mkdir(parents=True, exist_ok=True)
    size = 256 if large else 128
    media = out / 'volume.atr'
    shutil.copyfile(ROOT / f'tests/fixtures/mydos/mydos450-{size}.atr', media)
    digest = sha256(media)
    paths = bytearray(128)
    for offset, name in ((0, b'D1:LARGE.BIN\0' if large else b'D1:TOOLS/SUB/DATA.BIN\0'),
                         (32, b'D1:\0')):
        paths[offset:offset + len(name)] = name
    p = build(t, ROOT / 'tests/programs' / source, out, optimize=mode == 'opt',
              tasks=True, task_capacity=8, kernel_bank=bank,
              dos_mounts=[dict(alias='D1', unit=49, sectors=2000 if large else 720,
                               sector_bytes=size, profile=1)], image_data=[(0xd1000, bytes(paths))])
    with emulator(ROOT / 'build/altirra-sio-multi', ROOT / 'build/firmware/altirraos-816.rom', out, pin=PIN) as b:
        machine = verify_machine(b, ROOT / 'build/firmware/altirraos-816.rom', PIN)
        b.config('diskemu', 'fastest'); b.mount(0, str(media))
        try:
            runtime, _ = execute(b, p, timeout=600 if large else 240,
                                 frame_limit=30000 if large else 12000)
        except Exception:
            print('Fixture checks:', data(b, p['image'], 'checks', True), flush=True)
            raise
        ownership(b, p, out)
        require(runtime['kernel_stack_observation']['interrupt_reserve_bytes_touched'] == 0,
                'Kernel interrupt reserve touched')
        observations = dict(checks=int.from_bytes(bytes(data(b, p['image'], 'checks')), 'little'))
        if large:
            observations.update({name: int.from_bytes(bytes(data(b, p['image'], name)), 'little')
                                 for name in ('received', 'verified', 'ioError')})
            require(observations == dict(checks=7, received=70003, verified=70003, ioError=0),
                    'Incomplete single large Read')
        else:
            require(observations['checks'] == 29, 'Incomplete routing fixture')
        require(sha256(media) == digest, 'Read-only media modified')
    return dict(status='pass', build=p['build'], runtime=runtime, machine=machine,
                observations=observations, media_sha256=digest)


def nil(t, out, mode, mounted=False):
    import time
    from os_boundary import run_to
    from test_console_coexistence import PIN as console_pin
    out.mkdir(parents=True, exist_ok=True)
    names=bytearray(1024)
    for offset,value in ((0,b'nIl:'),(16,b'UNKNOWN:'),(32,b'CON:'),(48,b'console:'),
                         (64,b'NIL:suffix'),(80,b'RAW:suffix'),(96,b'NIL'),(112,b':'),
                         (128,b'RAW:'),(144,b'NIL::'),(176,b'D1:TOOLS/SUB/DATA.BIN'),(208,b'D1:')):
        names[offset:offset+len(value)]=value
    names[512:767]=b'X:'+b'a'*253
    names[768:1024]=b'X:'+b'a'*254
    mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)] if mounted else []
    p=build(t,ROOT/'tests/programs/dos_streams_nil.act',out,optimize=mode=='opt',tasks=True,
            task_capacity=8,console=False,dos_mounts=mounts,image_data=[(0xd1000,bytes(names)+bytes(8)),(0xe0000,bytes(16))])
    def at(name):return next(x['address'] for x in p['image']['data'] if '_DOSNILTEST_'+name.upper()+'_' in x['name'])
    media=out/'volume.atr'
    if mounted:shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    evidence={}
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=console_pin) as b:
        for key,value in console_pin['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',console_pin)
        if mounted:b.config('diskemu','fastest');b.mount(0,str(media))
        def before(b):
            b.poke(at('mounted'),int(mounted))
            checkpoint=p['labels']['native_nmi']
            b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original_regs=b.regs
            def regs():
                result=original_regs()
                if int(result['PC'].lstrip('$'),16) in (p['labels']['done'],p['labels']['done']+2):
                    require(b.peek16(adapter.STATE)==0xffff,'Guest stopped before NIL checkpoint')
                return result
            b.regs=regs
            def until(phase):
                condition=f'db(${at("phase"):x})={phase}'
                bp=b.bp_set(checkpoint,condition=condition)
                try:run_to(b,checkpoint,12000,240,condition)
                finally:b.bp_clear(bp)
            until(1)
            evidence['payload_before']=list(b.memdump(at('payload'),8))
            watches=[]
            for i in range(8):watches+=b.watch_set(at('payload')+i,'rw')
            b.poke(at('gate'),1);until(2)
            evidence['payload_after']=list(b.memdump(at('payload'),8))
            require(evidence['payload_before']==evidence['payload_after'],'NIL changed payload')
            # Deliberate read must stop execution with the same watches armed.
            b.poke(at('gate'),2);b.resume();time.sleep(.2)
            pc=b.regs()['PC'];frame=b.eval_expr('@frame');time.sleep(.15)
            require(b.peek(at('phase'))==bytes([2]) and b.regs()['PC']==pc and b.eval_expr('@frame')==frame,
                    'Payload access watch negative control did not stop')
            evidence.update(no_payload_access=True,access_negative_control='stopped',control_pc=pc)
            b.pause();b.bp_clear_all();b.regs=original_regs
        try:runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
        except Exception:
            print('NIL checks',data(b,p['image'],'checks',True), 'status',b.peek16(adapter.STATE),flush=True);raise
        ownership(b,p,out)
        require(runtime['created']==(3 if mounted else 1),'Unexpected stream worker creation')
        require(data(b,p['image'],'phase')==[3],'Missing watch negative-control completion')
        evidence['checks']=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
        require(evidence['checks']==(49 if mounted else 41),'Incomplete NIL assertions: '+str(evidence['checks']))
    return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,observations=evidence,mounted=mounted)


def nil_suite(t,out,mode,only=None):
    from test_dos_abi import run as abi
    cases=[]
    for name,action in (('headless',lambda p:nil(t,p,mode)),('mixed',lambda p:nil(t,p,mode,True)),
                        ('abi',lambda p:abi(t,p,mode=='opt'))):
        if only and only!=name:continue
        print('Running',mode,name,flush=True)
        directory=out/name;directory.mkdir(parents=True,exist_ok=True)
        result=action(directory);result['name']=name
        (directory/'results.json').write_text(json.dumps(result,indent=2)+'\n');cases.append(result)
    require(cases,'Unknown selected case')
    return cases


def defaults(t,out,mode,bank=1):
    out.mkdir(parents=True,exist_ok=True)
    names=bytearray(128)
    for offset,value in ((0,b'NIL:'),(32,b'D1:TOOLS/SUB/DATA.BIN'),(64,b'D1:')):
        names[offset:offset+len(value)]=value
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    p=build(t,ROOT/'tests/programs/dos_streams_defaults.act',out,optimize=mode=='opt',tasks=True,
            task_capacity=8,console=False,kernel_bank=bank,
            dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],image_data=[(0xd1000,bytes(names))])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.config('diskemu','fastest');b.mount(0,str(media))
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Defaults checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
        require(checks==44,'Incomplete defaults checks: '+str(checks))
        require(runtime['created']==5,'Unexpected defaults worker creation')
    return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,observations=dict(checks=checks))


def defaults_suite(t,out,mode,only=None):
    from test_dos_abi import run as abi
    from test_dos_client import run as client
    from test_dos_files import run as files
    cases=[]
    for name,action in (('defaults-bank1',lambda p:defaults(t,p,mode)),
                        ('defaults-bank3',lambda p:defaults(t,p,mode,3)),
                        ('abi',lambda p:abi(t,p,mode=='opt')),
                        ('reuse',lambda p:client(t,p,mode=='opt','reuse')),
                        ('files',lambda p:files(t,p,mode,128,capacity=8,concurrent=True))):
        if only and only!=name:continue
        print('Running',mode,name,flush=True)
        directory=out/name;directory.mkdir(parents=True,exist_ok=True)
        result=action(directory);result['name']=name
        (directory/'results.json').write_text(json.dumps(result,indent=2)+'\n');cases.append(result)
    require(cases,'Unknown selected case')
    return cases


def raw_suite(t,out,mode,only=None):
    from test_dos_streams_raw import run as raw
    from test_dos_abi import run as abi
    from test_console_lifetime import run as console_lifetime
    cases=[]
    for name,action in (('raw-bank1',lambda p:raw(t,p,mode)),
                        ('raw-bank3',lambda p:raw(t,p,mode,3)),
                        ('headless',lambda p:nil(t,p,mode)),
                        ('abi',lambda p:abi(t,p,mode=='opt')),
                        ('large-read',lambda p:fixture(t,p,mode,'dos_large_read.act',large=True)),
                        ('console-removal-guard',lambda p:console_lifetime(t,p,1,mode=='opt'))):
        if only and only!=name:continue
        print('Running',mode,name,flush=True)
        directory=out/name;directory.mkdir(parents=True,exist_ok=True)
        result=action(directory);result['name']=name
        (directory/'results.json').write_text(json.dumps(result,indent=2)+'\n');cases.append(result)
    require(cases,'Unknown selected case')
    return cases


def routing(t, out, mode, only=None):
    from test_dos_abi import run as abi
    from test_dos_client import run as client
    from test_dos_files import run as files
    from test_dos_directories import run as directories
    from test_dos_lifetime import run as lifetime
    cases = []
    for name, action in (
        ('objects-bank1', lambda p: fixture(t, p, mode, 'dos_streams_routing.act')),
        ('objects-bank3', lambda p: fixture(t, p, mode, 'dos_streams_routing.act', bank=3)),
        ('abi', lambda p: abi(t, p, mode == 'opt')),
        ('client', lambda p: client(t, p, mode == 'opt')),
        ('reuse', lambda p: client(t, p, mode == 'opt', 'reuse')),
        ('files', lambda p: files(t, p, mode, 128, capacity=8, concurrent=True)),
        ('directories', lambda p: directories(t, p, mode, 128)),
        ('lifetime', lambda p: lifetime(t, p, mode)),
        ('retry', lambda p: lifetime(t, p, mode, retry=True)),
        ('large-read', lambda p: fixture(t, p, mode, 'dos_large_read.act', large=True)),
    ):
        if only and name != only:
            continue
        print('Running', mode, name, flush=True)
        destination = out / name; destination.mkdir(parents=True, exist_ok=True)
        result = action(destination)
        require(result['status'] == 'pass', 'Failed ' + name)
        result['name'] = name
        (destination / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
        cases.append(result)
    require(cases, 'Unknown selected case')
    return cases


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir', type=Path, default=ROOT / 'build/actionc')
    parser.add_argument('--suite', choices=('routing','nil','defaults','raw'), required=True)
    parser.add_argument('--case', choices=('raw', 'opt'))
    parser.add_argument('--only')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    require(not (out / 'results.json').exists(), 'Choose a fresh output path')
    result = dict(status='running', suite=args.suite, cases=[])
    try:
        t = compiler(args.compiler_dir)
        for mode in ([args.case] if args.case else ['raw', 'opt']):
            result['cases'].append(dict(mode=mode, cases={'routing':routing,'nil':nil_suite,'defaults':defaults_suite,'raw':raw_suite}[args.suite](t, out / mode, mode, args.only)))
        result['status'] = 'pass'
    except Exception as error:
        result.update(status='fail', error=str(error)); raise
    finally:
        (out / 'results.json').write_text(json.dumps(result, indent=2) + '\n')
    print('DOS streams slice passed:', args.suite, flush=True)


if __name__ == '__main__':
    main()
