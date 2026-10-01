#!/usr/bin/env python3
"""Bounded depth, checked overflow and physical I/O on two larger Task stacks."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from make_data_disk import make
from generate_dos_mounts import validate_mounts
from filesystem_formats import SDFS
from native_program import ROOT, build, compiler, execute, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from native_abi import FIELDS
from stack_budget import bank_zero_delta, stack_usage
from test_cooperative import data

PIN = json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES = {'depth':0, 'overflow':1, 'coexistence':2, 'process':3, 'compiler':4, 'assembly':5}


def observe(bridge, program, progress, slots=(6,7), code_bank=None, pc_range=None):
    """Read the full saved frame at the unchanged bank-zero NMI rendezvous."""
    marker = program['labels']['native_nmi']
    prologue = bytes.fromhex('c23048da5a0b8bd83baa2900ffc90001f004a9ef011bda')
    require(bridge.memdump(marker,len(prologue)) == prologue, 'NMI observer needs updating')
    marker += len(prologue)
    observations = []
    for index,slot in enumerate(slots):
        condition = f'(db(${adapter.CURRENT:04x})={slot})&(dw(${progress[index]:x})>0)'
        if pc_range is not None:
            low, high = pc_range
            require(low >> 16 == (high-1) >> 16, 'Observer PC range crosses a bank')
            condition += (f'&(db(dw($1ee)+13)={low >> 16})'
                          f'&(dw(dw($1ee)+11)>={low & 65535})'
                          f'&(dw(dw($1ee)+11)<{((high-1) & 65535)+1})')
        bridge.bp_clear_all()
        bridge.bp_set(marker,condition=condition)
        run_to(bridge,marker,frame_limit=3000,timeout=90,condition=condition)
        bridge.bp_clear_all()
        stack = bridge.peek16(0x1ee)
        pool = program['build']['memory']['task_pools'][slot]
        require(pool['stack_base']+256 <= stack < pool['stack_base']+pool['stack_bytes']-13,
                'NMI frame outside the selected stack')
        frame = bridge.memdump(stack+1,13)
        require(int.from_bytes(frame[1:3],'little') == pool['dp'], 'NMI saved the wrong DP')
        pc = int.from_bytes(frame[10:13],'little')
        if code_bank is not None:
            require(pc >> 16 == code_bank, 'NMI did not interrupt C code')
        if pc_range is not None:
            require(low <= pc < high, 'NMI did not interrupt the selected routine')
        observations.append(dict(slot=slot,saved_s=stack,saved_d=pool['dp'],pc=pc,
                                 depth=pool['stack_base']+pool['stack_bytes']-stack-1,
                                 frame=frame.hex()))
    return observations


def run(output, mode, case, nmi=0, from_build=None):
    output.mkdir(parents=True,exist_ok=True)
    injected = case in ('compiler','assembly')
    fault = injected or case == 'overflow'
    source = ROOT/'tests/programs'/('large_stack_checks.act' if injected else 'large_stacks.act')
    mounts=[]
    media=None
    if case == 'coexistence':
        media_source=output/'media';media_source.mkdir(exist_ok=True)
        (media_source/'DATA.BIN').write_bytes(bytes(i ^ 0x5a for i in range(128)))
        media=output/'system.atr'
        make(media,media_source,binary_names={'DATA.BIN'})
        mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=SDFS)]
    mounts=validate_mounts(mounts)
    program=read_build(from_build) if from_build else build(
        compiler(ROOT/'build/actionc'),source,output/'program',
        optimize=mode=='opt',tasks=True,task_capacity=8,console=case=='coexistence',
        dos_mounts=mounts,probe_nmi=nmi)
    require(program['build']['optimize'] == (mode=='opt') and
            program['build']['probe_nmi'] == nmi and
            program['build']['dos_mounts'] == mounts, 'Reused fixture differs')
    require(program['build']['source_sha256'] == sha256(source),'Fixture source changed')
    for group in ('platform_inputs','task_inputs','console_inputs'):
        for name,digest in program['build'].get(group,{}).items():
            require(sha256(ROOT/name)==digest,'Build input changed: '+name)
    program={**program,'output':output}
    report=dict(status='running',tier='development',mode=mode,case=case,nmi_checkpoint=nmi,
                build=program['build'],bank_zero_delta=bank_zero_delta(program['build']['memory']))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',output,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,ROOT/'build/firmware/altirraos-816.rom',PIN)
            if media:
                report['media_sha256']=sha256(media)
                bridge.config('diskemu','generic56k');bridge.mount(0,str(media))
            at=lambda name:next(d['address'] for d in program['image']['data'] if '_'+name.upper()+'_' in d['name'])
            sentinel=bytes((i*37+11)&255 for i in range(4096))
            def before(b):
                b.poke(at('variant'),CASES[case])
                b.memload(0x8000,sentinel)
                if injected:
                    address = program['labels']['console_write' if case == 'assembly' else 'general_task_start']
                    condition = f'db(${adapter.CURRENT:04x})=6'
                    b.bp_set(address,condition=condition)
                    run_to(b,address,condition=condition)
                    b.bp_clear_all()
                    pool=program['build']['memory']['task_pools'][6]
                    floor_at=pool['dp']+FIELDS['stack_floor']['offset']
                    floor=b.peek16(floor_at)
                    ceiling=pool['stack_base']+pool['stack_bytes']
                    report['injection']=dict(slot=6,original_floor=floor,injected_floor=ceiling,
                                             entry_s_low=int(b.regs()['S'].lstrip('$'),16))
                    b.poke16(floor_at,ceiling)
                    stop=program['labels']['stack_overflow']
                    b.bp_set(stop)
                    run_to(b,stop)
                    b.poke16(floor_at,floor)
                    b.bp_clear_all()
                elif not fault:
                    report['preemption']=observe(b,program,[at('progress'),at('progress')+2])
            try:
                runtime,_=execute(bridge,program,before_run=before,frame_limit=6000,timeout=180,
                                  expected_status=1 if fault else 0)
            except Exception:
                print('large stack state',data(bridge,program['image'],'checks',True),
                      bridge.memdump(adapter.STATE,64).hex(),flush=True)
                raise
            report['runtime']=runtime
            report['stack_usage']=stack_usage(bridge,program['build']['memory'])
            require(bridge.memdump(0x8000,4096)==sentinel,'VBXE aperture changed')
            if fault:
                require(runtime['fault_required']>0,'Missing checked reservation failure')
                pool=program['build']['memory']['task_pools'][6]
                limit=pool['stack_bytes'] if injected else 512
                require(pool['stack_base']+256 <= runtime['fault_s'] < pool['stack_base']+limit,
                        'Fault outside larger worker')
                if case == 'assembly':
                    require(runtime['fault_s'] & 255 == report['injection']['entry_s_low'],
                            'Checked failure changed entry S')
            else:
                require(data(bridge,program['image'],'finished')==[2],'Missing completed worker')
                for slot in ('6','7'):
                    require(768 < report['stack_usage'][slot]['peak'] < 2304,'Depth did not exercise larger stack')
                require(runtime['native_nmi_count']>0,'Missing VBI')
            if media:
                require(runtime['native_irq_count']>0 and sha256(media)==report['media_sha256'],
                        'Missing physical IRQ or changed read-only media')
            report['checks']=data(bridge,program['image'],'checks',True)
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('raw','opt'),required=True)
    p.add_argument('--case',choices=CASES,default='depth')
    p.add_argument('--nmi',type=int,choices=(0,9,10,11,12,15,16,17),default=0)
    p.add_argument('--from-build',type=Path)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    run(args.output.resolve(),args.mode,args.case,args.nmi,args.from_build)
    print('Larger stacks passed:',args.mode,args.case,args.nmi)
