#!/usr/bin/env python3
"""OF system-drive words, conflict rejection and D2-only native handoff."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, read_build, require, verify_machine
from build_of816 import build
from os_boundary import emulator, run_to
from test_of816 import PIN, enter_forth, press, check_boot_guards, screen_text
from test_dos_stack import execute, ownership
from test_cooperative import data
from banked_test_memory import write


def run(output, native, selected=True):
    output=output.resolve()
    record=build(output,native,ROOT/'build/of816-upstream')
    program=read_build(native.resolve())
    labels=record['labels']
    rom=ROOT/'build/firmware/altirraos-816.rom'
    cases=[]
    with emulator(ROOT/'build/shell-paced-bridge',rom,output,pin=PIN) as b:
        machine=verify_machine(b,rom,PIN)
        b.config('diskemu','fastest')
        media=ROOT/'tests/fixtures/mydos/mydos450-128.atr'
        # This fixture selects slot 1; the other descriptor uses unit 51/name D4.
        for unit in ((1,2) if selected else (0,2)):b.mount(unit,str(media))
        b.boot(str(output/'Exec-of816.xex'))
        b.bp_set(labels['of_start'])
        run_to(b,labels['of_start'],3000,90)
        b.bp_clear_all()
        saved=dict(vectors=b.memdump(0x256,9),iocb=b.memdump(0x340,32))
        enter_forth(b,labels)
        for character in 'decimal\n':press(b,labels,character)
        address=record['boot_config']['address']+6
        current=1 if selected else 0
        for requested in (2,0,9,65536,-1,3,4,8,2):
            accepted=selected and requested in (2,8)
            if accepted:current=requested
            for character in f'{requested} SYSTEM-DRIVE!\n':press(b,labels,character)
            require(b.memdump(address,1)[0]==current,f'Wrong setter result for {requested}')
            require(b.memdump(address+1,1)==bytes(1),'Drive setter overwrote reserved byte')
            cases.append(dict(requested=requested,accepted=accepted,retained=current))
        for character in 'SYSTEM-DRIVE@ .\n':press(b,labels,character)
        require(f'{current} ' in screen_text(b.memdump(b.peek16(88),960)), 'Drive getter differs')
        for character in 'exec816':press(b,labels,character)
        press(b,labels,'\n',labels['of_handoff'])
        check_boot_guards(b,record['layout'])
        b.bp_clear_all()
        b.bp_set(program['labels']['loader_start'])
        run_to(b,program['labels']['loader_start'],3000,60)
        drive=2 if selected else 0
        physical=drive or 1
        names=f'D{physical}:TOOLS\0'.encode().ljust(64,b'\0')+f'D{physical}:TOOLS/SUB/DATA.BIN\0'.encode()
        write(b,0xd1000,names,output)
        write(b,0xd1100,bytes([drive,0,0]),output)
        b.bp_clear_all()
        b.bp_set(program['labels']['start'])
        run_to(b,program['labels']['start'],3000,60)
        require(b.memdump(0x256,9)==saved['vectors'] and b.memdump(0x340,32)==saved['iocb'],
                'OF handoff did not restore OS vectors/IOCBs')
        runtime,_=execute(b,program,preloaded=True,frame_limit=12000,timeout=240)
        ownership(b,program,program['output'])
        require(data(b,program['image'],'finished')==[1],'Incomplete SYS native fixture')
        checks=data(b,program['image'],'checks',True)
    report=dict(status='pass',selected=selected,boot=record,machine=machine,cases=cases,
                runtime=runtime,checks=checks,bank_zero_delta=dict(fixed=0,per_task=0))
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--native',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--no-selection',action='store_true')
    args=parser.parse_args()
    run(args.output,args.native,not args.no_selection)
    print('OF system drive passed')
