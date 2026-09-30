#!/usr/bin/env python3
"""Focused SYS routing and lifetime checks through the emitted DOS implementation."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, compiler, require, sha256, verify_machine
from os_boundary import emulator, run_to
from banked_test_memory import write
from test_sio_device import PIN
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(t, out, mode, selected=True, drives=False):
    out=out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    names=b'D1:TOOLS\0'.ljust(64,b'\0')+b'D1:TOOLS/SUB/DATA.BIN\0'
    mounts=[dict(alias='D4',unit=51,sectors=720,sector_bytes=128,profile=1),
            dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)]
    p=build(t,ROOT/'tests/programs/dos_system.act',out,optimize=mode=='opt',tasks=True,
            task_capacity=8,console=False,dos_mounts=mounts,system_mount='D1' if selected else None,
            image_data=[(0xd1000,names),(0xd1100,bytes([int(selected),0,0])),(0xd3000,bytes(256)),(0xd3200,bytes(260)),(0xd4000,bytes(800))])
    media=ROOT/'tests/fixtures/mydos/mydos450-128.atr'
    digest=sha256(media)
    rom=ROOT/'build/firmware/altirraos-816.rom'
    cases=[('default',{},1 if selected else 0,0,False)]
    if not selected:
        cases += [('no-selection-drive',{6:2},0,1,False)]
    if drives:
        cases += [('D2',{6:2},2,0,False)]
        if mode=='opt':
            cases += [('zero',{6:0},1,1,False),('range',{6:9},1,1,False),
                      ('malformed',{0:0,6:2},1,1,False),
                      ('unit-conflict',{6:3},3,0,True),('alias-conflict',{6:4},4,0,True)]
    observations=[]
    for name,patch,drive,status,conflict in cases:
        print('SYS native',mode,name,flush=True)
        with emulator(ROOT/'build/altirra-sio-multi',rom,out,pin=PIN) as b:
            machine=verify_machine(b,rom,PIN)
            b.config('diskemu','fastest')
            for unit in {max(0,drive-1),2}:b.mount(unit,str(media))
            b.boot(str(p['xex']))
            run_to(b,p['labels']['loader_start'],frame_limit=1800,timeout=180)
            address=p['build']['memory']['boot_config']['address']
            require(b.memdump(address+6,1)[0]==int(selected),'Wrong loader system-drive default')
            for offset,value in patch.items():b.poke(address+offset,value)
            effective=drive or 1
            names=f'D{effective}:TOOLS\0'.encode().ljust(64,b'\0')+f'D{effective}:TOOLS/SUB/DATA.BIN\0'.encode()
            write(b,0xd1000,names,out)
            write(b,0xd1100,bytes([drive,status,int(conflict)]),out)
            b.bp_clear_all()
            b.bp_set(p['labels']['start'])
            run_to(b,p['labels']['start'])
            try:runtime,_=execute(b,p,preloaded=True,timeout=240,frame_limit=12000)
            except Exception:
                print('SYS checks',data(b,p['image'],'checks',True),flush=True)
                raise
            ownership(b,p,out)
            require(data(b,p['image'],'finished')==[1],'Incomplete SYS fixture')
            require(sha256(media)==digest,'Read-only media modified')
            checks=data(b,p['image'],'checks',True)
        observations.append(dict(case=name,requested_drive=drive,status=status,conflict=conflict,
                                 checks=checks,runtime=runtime))
    result=dict(status='pass',mode=mode,selected=selected,checks=checks,build=p['build'],
                cases=observations,machine=machine,media_sha256=digest,bank_zero_delta=dict(fixed=0,per_task=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--drives',action='store_true')
    parser.add_argument('--no-selection',action='store_true')
    parser.add_argument('--output',type=Path,default=ROOT/'build/dos-system')
    args=parser.parse_args()
    result=run(compiler(ROOT/'build/actionc'),args.output/(args.case+('-none' if args.no_selection else '')),args.case,not args.no_selection,args.drives)
    print('SYS checks passed:',result['checks'])
