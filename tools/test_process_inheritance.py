#!/usr/bin/env python3
"""Focused P2/P3 inheritance, foreground and teardown machine-code checks."""
import adapter_state as adapter
from library_paths import library_file, read_source
import argparse
import json
import re
import shutil
from pathlib import Path

import generate_tasks
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN = json.loads((ROOT/'toolchain/altirra-shell-console.json').read_text())
ORIGINAL_POLICY = generate_tasks.policy_modules
MODULES = ('fsfiles', 'fslocks', 'dosinherit', 'dosclient', 'portcore', 'dosbreak', 'consoleforeground')


def instrument(output, *args, **kwargs):
    directory = Path(ORIGINAL_POLICY(output, *args, **kwargs))
    edits = {
        'dosinherit': [('EXEC.AllocMem(', 'PROCESSPROBE.Allocate(')],
        'fsfiles': [('EXEC.AllocMem(', 'PROCESSPROBE.Allocate(')],
        'fslocks': [('EXEC.AllocMem(', 'PROCESSPROBE.Allocate(')],
        'dosclient': [
            ('  client=ClientContext POINTER(EXEC.AllocMem(CLIENT_SIZE,EXEC.MEMF_UPPER\n      OR EXEC.MEMF_CLEAR))',
             '  IF PROCESSPROBE.failure=1 THEN client=ClientContext POINTER(0)\n'
             '  ELSE client=ClientContext POINTER(EXEC.AllocMem(CLIENT_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR)) FI')],
        'portcore': [
            ('  port=EXEC.MsgPort POINTER(EXEC.AllocMem(EXEC.MSGPORT_SIZE,EXEC.MEMF_PUBLIC\n      OR EXEC.MEMF_CLEAR))',
             '  IF PROCESSPROBE.failure=2 THEN port=EXEC.MsgPort POINTER(0)\n'
             '  ELSE port=EXEC.MsgPort POINTER(EXEC.AllocMem(EXEC.MSGPORT_SIZE,EXEC.MEMF_PUBLIC OR EXEC.MEMF_CLEAR)) FI'),
            ('  LET bit=EXEC.AllocSignal($ff)',
             '  LET bit=IF PROCESSPROBE.failure=3 THEN BYTE($ff) ELSE EXEC.AllocSignal($ff) FI')],
        'dosbreak': [
            ('  signal=EXEC.AllocSignal($ff)',
             '  IF PROCESSPROBE.failure=5 THEN signal=$ff\n  ELSE signal=EXEC.AllocSignal($ff) FI'),
            ('  scope=DOSBREAKTYPES.Scope POINTER(EXEC.AllocMem(DOSBREAKTYPES.SCOPE_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))',
             '  IF PROCESSPROBE.failure=4 THEN scope=DOSBREAKTYPES.Scope POINTER(0)\n'
             '  ELSE scope=DOSBREAKTYPES.Scope POINTER(EXEC.AllocMem(DOSBREAKTYPES.SCOPE_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR)) FI')],
        'consoleforeground': [
            ('  BYTE index,pending\n', '  BYTE index,pending\n'
             '  IF (carry=1 AND PROCESSPROBE.failure=6) OR (carry=0 AND PROCESSPROBE.failure=7) THEN RETURN(0) FI\n'),
            ('  CONSOLECAPTURE.ClearUnit(previous.unit)',
             '  CONSOLECAPTURE.ClearUnit(previous.unit)\n'
             '  PROCESSPROBE.CaptureAfterClear(INPUTNATIVE.Capture POINTER(ADDRESS(CS_CAPTURE)),previous.generation)')],
    }
    for name, replacements in edits.items():
        path = directory/(name+'.act')
        source = path if name == 'consoleforeground' else library_file(path.name)
        text = read_source(source)
        text = text.replace('USE EXEC\n', 'USE EXEC\nUSE INPUTNATIVE\nUSE PROCESSPROBE\n', 1)
        for old, new in replacements:
            require(text.count(old) == (2 if name == 'fsfiles' else 1), 'Stale Process hook: '+name)
            text = text.replace(old, new)
        path.write_text(text)
    return directory


def run(out, mode, bank, variants=(0,1,2,3,4,5)):
    out.mkdir(parents=True, exist_ok=True)
    paths = bytearray(256)
    for offset, value in ((0,b'D1:TOOLS/SUB/DATA.BIN'),(32,b'D1:TOOLS/SUB'),(64,b'DATA.BIN'),
                          (96,b'D1:'),(128,b'NIL:'),(160,b'CON:'),(192,b'RAW:')):
        paths[offset:offset+len(value)] = value
    generate_tasks.policy_modules = instrument
    try:
        program = build(compiler(ROOT/'build/actionc'), ROOT/'tests/programs/process_inheritance.act', out,
                        optimize=mode == 'opt', tasks=True, task_capacity=8, kernel_bank=bank, console=True,
                        dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],
                        image_data=[(0xd1000,bytes(paths)),(0xd2000,bytes(1280))])
    finally:
        generate_tasks.policy_modules = ORIGINAL_POLICY
    return exercise(program, mode, bank, variants)


def exercise(program, mode, bank, variants=(0,1,2,3,4,5)):
    out = program['output']
    media = out/'volume.atr'
    shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr', media)
    digest = sha256(media)
    results = []
    for variant in variants:
        case_out = out/('scenario-'+str(variant))
        case_out.mkdir(exist_ok=True)
        with emulator(ROOT/'build/shell-console-bridge', ROOT/'build/firmware/altirraos-816.rom', case_out, pin=PIN) as bridge:
            machine = verify_machine(bridge, ROOT/'build/firmware/altirraos-816.rom', PIN)
            bridge.config('diskemu','fastest')
            bridge.mount(0,str(media))
            def before(bridge):
                address = next(d['address'] for d in program['image']['data'] if '_PROCESSINHERITANCE_VARIANT_' in d['name'])
                bridge.poke(address,variant)
            expected = 0 if variant == 0 else 4 if variant in (1,2,3) else 0xff94
            try:
                runtime,_ = execute(bridge,program,before_run=before,expected_status=expected,timeout=180,frame_limit=9000)
            except Exception:
                print('Process inheritance state:',{name:int.from_bytes(bytes(data(bridge,program['image'],name)), 'little')
                      for name in ('checks','stage','kind','entered','completed','observedFree')},
                      bridge.memdump(adapter.STATE,64).hex(),flush=True)
                raise
            if variant == 0:
                ownership(bridge,program,out)
                from banked_test_memory import read
                storage = program['build']['memory']['process_storage']
                require(read(bridge,storage['BASE'],storage['TABLE_BYTES'],out) == bytes(8*128),
                        'Process lease or completion remains owned')
                require(data(bridge,program['image'],'layouts',True) == [88,20,112,402,16,20,98,16],
                        'Unexpected private DOS storage layout')
            else:
                retained(bridge,program,variant)
            results.append(dict(variant=variant,runtime=runtime,
                                checks=data(bridge,program['image'],'checks',True)))
            require(sha256(media) == digest,'Read-only media modified')
            print('Process inheritance scenario passed',mode,bank,variant,results[-1]['checks'],flush=True)
    return dict(status='pass',mode=mode,bank=bank,build=program['build'],machine=machine,scenarios=results,
                fixture_overrides={n:sha256(out/'task-kernel'/(n+'.act')) for n in MODULES},
                fixture_sha256=program['build']['source_sha256'],media_sha256=digest,
                runner_sha256=sha256(Path(__file__)),bank_zero_delta=dict(fixed=0,per_task=0))


def retained(bridge, program, variant):
    """A failed retirement must not acknowledge or release the owning lease."""
    from banked_test_memory import read
    contract = json.loads((ROOT/'abi/process.json').read_text())
    fields = {name:offset for name,_,offset in contract['record']}
    storage = program['build']['memory']['process_storage']
    table = read(bridge,storage['BASE'],storage['TABLE_BYTES'],program['output'])
    rows = [table[i*128:(i+1)*128] for i in range(1,8)]
    owned = [row for row in rows if row[fields['state']] != 0]
    require(len(owned) == 1,'Failed retirement lost its Process lease')
    row = owned[0]
    if variant in (4,5):
        require(row[fields['state']] == 3 and row[fields['retireReady']] == 0,
                'Teardown error acknowledged retirement')
        # Task still has its private context and copied arguments.
        require(any(row[fields['arguments']:fields['arguments']+3]), 'Failed cleanup released arguments')
        if variant == 4:
            require(row[fields['foreground']] == 2 and any(row[fields['parentScope']:fields['parentScope']+3]),
                    'Failed foreground restoration released its owner')
        dos_base = int(re.search(r'CONST DS_BASE=\$(\w+)',
                       (program['output']/'dos-storage-action.inc').read_text())[1],16)
        slot = read(bridge,dos_base+16*row[fields['slot']],16,program['output'])
        context = int.from_bytes(slot[:3],'little')
        identity = int.from_bytes(slot[11:14],'little')
        require(context != 0 and identity != 0,'Failed cleanup lost its DOS ownership list')
        client = read(bridge,context,88,program['output'])
        header = read(bridge,identity,20,program['output'])
        require(int.from_bytes(header[3:6],'little') == dos_base+16*row[fields['slot']],
                'Failed cleanup detached its owned handle')
        if variant == 4:
            parent_address = int.from_bytes(row[fields['parentClient']:fields['parentClient']+3],'little')
            parent = read(bridge,parent_address,88,program['output'])
            require(parent[86] == 1 and client[87] == 1 and any(client[83:86]),
                    'Failed restoration released its foreground context')
        else:
            endpoint = int.from_bytes(header[8:11],'little')
            request = read(bridge,endpoint,102,program['output'])
            require(header[6:8] == bytes([1,4]) and int.from_bytes(client[68:70],'little') == 1,
                    'Failed close released its CON handle')
            require(int.from_bytes(request[70:72],'little') == 1 and any(request[16:19]),
                    'Failed close released its device reference')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--bank',type=int,default=1)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--suite',default='0,1,2,3,4,5',help='Comma-separated scenario numbers; 0 is the functional development case')
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True,exist_ok=True)
    result = dict(status='running')
    try:
        variants=tuple(int(value) for value in args.suite.split(','))
        require(bool(variants) and all(0<=value<=5 for value in variants),'Unknown inheritance scenario')
        result = run(out,args.case,args.bank,variants)
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
