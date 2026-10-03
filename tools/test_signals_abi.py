#!/usr/bin/env python3
"""Execute signal Task layout and native/COP call probes in raw and optimized code."""
from library_paths import module_args
import argparse
import json
from pathlib import Path
import re

from native_program import ROOT, build, command, compiler, execute, platform_files, require, sha256, verify_machine
from generate_tasks import ABI, SIGNALS, SELECTORS, check_routine, declarations, generate, public_api, storage
from generate_memory import layout
from os_boundary import emulator
from test_banked import PIN, changed_image
from test_cooperative import data
from banked_test_memory import read as far_read


def imports(toolchain, output):
    source = output/'imports.act'
    source.write_text('MODULE SIGNALIMPORTS\nUSE EXECLISTS\n'+public_api()+'''
Task prepared
Task POINTER result
BYTE old
LONGCARD mask
PROC POINTER missing()
'''+declarations()+'''
PROC Entry()
RETURN
PROC Main()
  Forbid()
  result=AddTask(@prepared,@Entry,missing)
  result=FindTask(BYTE POINTER(0))
  old=SetTaskPri(result,$80)
  old=AllocSignal($ff)
  FreeSignal(old)
  mask=SetSignal(LONGCARD($ffffffff),LONGCARD($80000000))
  Signal(result,mask)
  mask=Wait(mask)
  RemTask(result)
  Permit()
RETURN
ENDMODULE
''')
    interfaces = json.loads(command([toolchain['binary'],*module_args(),'--emit-interfaces',source]))
    require({i['name'].split('.')[1] for i in interfaces} == set(ABI['imports']), 'Missing imports')
    for interface in interfaces:
        check_routine(interface,interface['name'].split('.')[1])
    return interfaces


def gateway(output, locations=None):
    (output/'probe.cfg').write_text('MEMORY { RAM: start=$060000, size=$1000, file=%O; } SEGMENTS { CODE: load=RAM, type=ro; }\n')
    locations = locations or dict(FREED=0,TARGET=0,MASKS=0)
    command(['ca65','-I',output,*[v for k,a in locations.items() for v in ('-D',f'{k}={a}')],
             '-o',output/'probe.o', ROOT/'probes/signals-abi/gateway.s'])
    command(['ld65','-C',output/'probe.cfg','-o',output/'probe.bin','-Ln',output/'probe.lbl',output/'probe.o'])
    return {label.lstrip('.'):int(addr,16) for _,addr,label in
            (line.split() for line in (output/'probe.lbl').read_text().splitlines())}


def case(bridge, toolchain, output, optimize, cop):
    generate(output,layout())
    labels = gateway(output)
    source = output/'signals_abi.act'
    text = (ROOT/'tests/programs/signals_abi.act').read_text()
    if cop:
        text = text.replace('  Calls()','  oldCop=copVector\n  copVector=$'+f'{labels["probe_cop"]:x}'+'\n  Calls()\n  copVector=oldCop')
    source.write_text(text)
    program = build(toolchain,source,output,optimize=optimize,banked=True)
    base,size = 0x04ffe0,96
    program['image']['segments'].append({'address':base,'bytes':[0xa5]*size,'writable':True,'executable':False})
    routines = {}
    for name in SIGNALS:
        matches = [r for r in program['image']['routines'] if re.fullmatch('M_SIGNALABI_'+name.upper()+'_[0-9A-F]+',r['name'])]
        require(len(matches) == 1, 'Missing emitted routine '+name)
        routines[name] = matches[0]
        check_routine(matches[0],name)
    if cop:
        locations = {}
        for name in ('FREED','TARGET','MASKS'):
            locations[name] = next(d['address'] for d in program['image']['data']
                                   if re.fullmatch('M_SIGNALABI_'+name+'_[0-9A-F]+',d['name']))
        require(gateway(output,locations) == labels, 'Probe addresses moved')
        program['image']['segments'].append({'address':0x60000,'bytes':list((output/'probe.bin').read_bytes()),
                                             'writable':False,'executable':True})
        # Redirect ordinary emitted entries before their prologue. This executes
        # the exact native outgoing call areas through generated production stubs.
        for name,routine in routines.items():
            address = routine['address']
            target = labels['tasks_'+SELECTORS[name].lower()]
            segment = next(s for s in program['image']['segments']
                           if s['address'] <= address < s['address']+len(s['bytes']))
            offset = address-segment['address']
            segment['bytes'][offset:offset+4] = [0x5c,*target.to_bytes(3,'little')]
    changed_image(program)
    result,_ = execute(bridge,program,frame_limit=1200,timeout=60)
    raw = bytes(data(bridge,program['image'],'facts'))
    facts = [int.from_bytes(raw[i:i+3],'little') for i in range(0,len(raw),3)]
    expected = [62,*[f[2] for f in ABI['task']['fields']],64,32,3,13,12,6]
    require(facts == expected, f'Emitted layout differs: {facts} != {expected}')
    raw = bytes(data(bridge,program['image'],'masks'))
    masks = [int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
    require(masks == [0xffffffff,0x80000001,0xab1234cd,0,0xff46ca8a,0xffffffff,0x80123456,0x04ffef],f'Truncated/changed masks: {masks}')
    require(data(bridge,program['image'],'numbers') == [255,0], 'BYTE return changed')
    require(data(bridge,program['image'],'freed') == [0xa9], 'BYTE argument changed')
    observed = far_read(bridge,base,size,output)
    want = bytearray([0xa5]*size)
    start = 0x04ffef-base
    for offset,value,width in [(16,0xffffffff,4),(20,0x80000001,4),(24,0xab1234cd,4),(28,0,4),(58,0x3f0040,3)]:
        want[start+offset:start+offset+width] = value.to_bytes(width,'little')
    require(observed == want,'Task fields or padding/guards changed')
    return dict(build=program['build'],runtime=result,facts=facts,masks=masks,routines=routines,
                guarded_task_bytes=observed.hex(),cop=cop)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/abi')
    args = parser.parse_args()
    output = args.output.resolve(); output.mkdir(parents=True,exist_ok=True)
    toolchain = compiler(args.compiler_dir)
    platform_files(args.bridge_dir,args.rom)
    report = dict(schema_version=1,status='running',scope='Signal ABI only; no signal policy',
                  platform=PIN,interfaces=imports(toolchain,output),storage=storage(layout()),cases=[],
                  inputs={name:sha256(ROOT/name) for name in ('abi/tasks.json','lib/exec/exec-task-types.inc',
                          'tools/generate_tasks.py','tools/test_signals_abi.py','tests/programs/signals_abi.act','probes/signals-abi/gateway.s')})
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['emulator_config'] = verify_machine(bridge,args.rom,PIN)
            for optimize in (False,True):
                for cop in (False,True):
                    name = ('opt' if optimize else 'raw')+('-cop' if cop else '-native')
                    print('Running '+name+'...',flush=True)
                    report['cases'].append(dict(name=name,status='pass',**case(bridge,toolchain,output/name,optimize,cop)))
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error)); raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed raw/optimized native and generated COP ABI probes')


if __name__ == '__main__': main()
