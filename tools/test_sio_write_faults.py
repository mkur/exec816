#!/usr/bin/env python3
"""Malformed WRITE frame, command NAK, terminal error, protocol error and silence."""
import argparse
import json
import os
import time
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine, sha256
from os_boundary import emulator, run_to
from test_dos_stack import execute
from test_heap_api import clean_ownership
from test_cooperative import data
from sector_images import disk_image
from mydos_fixtures import Image
from banked_test_memory import read
from test_filesystem_write import reuse


def run(output, mode, size, from_build=None):
    program=reuse(from_build) if from_build else build(
        compiler(ROOT/'build/actionc'),ROOT/'tests/programs/sio_write_faults.act',
        output,optimize=mode=='opt',tasks=True)
    require(program['build']['optimize']==(mode=='opt'), 'Wrong replay mode')
    pin=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
    binary=ROOT/'build/altirra-sio-sector-faults'
    require(sha256(binary/'AltirraBridgeServer')==pin['fault_responder']['binary_sha256'], 'Unpinned fault responder')
    selector=output/'fault.txt'
    selector.write_text('none\n')
    os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    os.environ['EXEC816_LATENCY_TRACE']='1'
    cases=[]
    with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',output,pin=pin) as bridge:
        for key,value in {**pin['configuration'],'diskemu':'fastest'}.items():
            bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',pin)
        # This pinned model ACKs the damaged frame but never completes it.
        # Require timeout/offline and unchanged media; do not infer NAK recovery.
        # Absent must run before enabling D8: eject leaves a responding empty drive.
        for index,(name,error,offline) in enumerate((('absent',1,1),('checksum',1,1),
                                                    ('nak',2,0),('device',3,0),('protocol',7,1))):
            print('Physical WRITE fault',name,flush=True)
            case_out=output/name
            case_out.mkdir(exist_ok=True)
            disk_image(case_out/'good.atr',size)
            disk_image(case_out/'target.atr',size)
            expected=Image((case_out/'target.atr').read_bytes())
            if name=='device':
                at=expected.offset(4)
                expected.data[at:at+size]=bytes(i^0x69 for i in range(size))
            selector.write_text((name if name in ('device','protocol') else 'none')+'\n')
            if index:
                bridge.state_load(slot='loaded')

            def before(bridge):
                if not index:
                    bridge.state_save(slot='loaded')
                bridge.mount(0,str(case_out/'good.atr'))
                if name!='absent':
                    bridge.mount(7,str(case_out/'target.atr'))
                for key,value,size_bytes in (('sectorBytes',size,2),('expected',error,1),
                                             ('offline',offline,1),('absent',int(name=='absent'),1),
                                             ('nak',int(name=='nak'),1)):
                    address=next(d['address'] for d in program['image']['data'] if '_SIOWRITEFAULTS_'+key.upper()+'_' in d['name'])
                    bridge.memload(address,value.to_bytes(size_bytes,'little'))
                if name=='checksum':
                    state=program['build']['task_storage']['BASE']+0x800
                    condition=f'(db(${state+1:x})=7)&(dw(${state+20:x})=0)'
                    # This bridge accepts bank-zero breakpoints only. Stop at
                    # IRQ entry after the final payload byte, before checksum TX.
                    bridge.bp_set(program['labels']['native_irq'],condition=condition)
                    run_to(bridge,program['labels']['native_irq'],12000,240,condition)
                    bridge.poke(state+22,bridge.peek(state+22)[0]^1)
                    bridge.bp_clear_all()

            try:
                runtime,_=execute(bridge,{**program,'output':case_out},before_run=before,
                                  preloaded=bool(index),expected_status=0xff93 if offline else 0,
                                  timeout=240,frame_limit=12000)
            except Exception:
                print('checks',data(bridge,program['image'],'checks',True),flush=True)
                state=read(bridge,program['build']['task_storage']['BASE']+0x800,128,case_out)
                print('adapter',state.hex(),flush=True)
                raise
            require(data(bridge,program['image'],'cleanupReached')==[1], 'Write request did not retire')
            state=read(bridge,program['build']['task_storage']['BASE']+0x800,128,case_out)
            require(state[12:15]==state[16:19]==bytes(3), 'Retained caller buffer')
            if not offline:
                clean_ownership(bridge,program,output)
            time.sleep(3)
            bridge.regs()
            bridge._cmd_ok('EJECT drive=7')
            require((case_out/'target.atr').read_bytes()==expected.data, 'Wrong persisted failure outcome')
            if name=='checksum':
                lines=(output/'emulator.log').read_text().splitlines()
                transmitted=[int(line.split()[3]) for line in lines if line.startswith('[SIOPOC] write ')]
                payload=bytes(i^0x69 for i in range(size))
                checksum=sum(payload)
                while checksum>255:
                    checksum=(checksum & 255)+(checksum >> 8)
                require(transmitted[-size-1:]==list(payload)+[checksum^1], 'Wrong damaged wire frame')
            cases.append(dict(status='pass',name=name,error=error,offline=offline,runtime=runtime,
                              media_sha256=sha256(case_out/'target.atr'),hardware=state.hex()))
    return dict(status='pass',build=program['build'],cases=cases,machine=machine,sector_bytes=size,
                pin=pin,runner_sha256=sha256(Path(__file__)),scope='WRITE extension on the pinned sector fault responder; checksum stimulus flips '
                    'the adapter checksum after payload transmission. The model ACKs that malformed frame '
                    'but never completes it; timeout/offline is required. Command NAK uses an invalid sector. '
                    'Device error replaces the real terminal C '
                    'after physical mutation. These are functional tests, not interrupt timing measurements.',
                bank_zero_delta=dict(fixed=0,per_task=0))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--size',type=int,choices=(128,256),default=256)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    output.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:
        result=run(output,args.case,args.size,args.from_build.resolve() if args.from_build else None)
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Physical WRITE failures passed',args.case,args.size)
