#!/usr/bin/env python3
"""Qualify Task and signal policy through emitted machine code."""
import adapter_state as adapter
import argparse
import json
from pathlib import Path
from native_program import ROOT, build, command, compiler, execute, platform_files, require, sha256, verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import data
from test_tasks_exec import check as check_tasks


def check_masks(bridge,program,result):
    image=program['image']
    checks=data(bridge,image,'checks',True)
    expected=[__import__('generate_tasks').ABI['version'],1,1,1,31,255,255,255,255,255,255,31,1,1,31,1,1,1,31,1,1,1,1,1]
    require(checks==expected,'Signal allocation/ownership: '+str(checks))
    raw=bytes(data(bridge,image,'values'))
    values=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
    require(values==[0,0xab1234cd,0x8012ffcd,0x0012ffcd,0x80000000,0], 'Signal masks: '+str(values))
    numbers=data(bridge,image,'allocated')
    require(sorted(numbers)==list(range(16,32)), 'Signal namespace allocation/exhaustion')
    require(result['created']==2,'Missing isolation/reuse')
    return dict(checks=checks,values=values,allocated=numbers)


def masked_probe(program, wait_test=0):
    output=program['output'];image=program['image']
    names={k:program['labels'][v] for k,v in [('ALLOC','tasks_alloc_signal'),('FREE','tasks_free_signal'),('SET','tasks_set_signal'),('WAIT_CALL','tasks_wait')]}
    names['WAIT_TEST']=wait_test
    names.update({name:next(d['address'] for d in image['data'] if '_'+name+'_' in d['name']) for name in ('CHECKS','VALUES')})
    probe_base=sorted(program['build']['memory']['usable_banks'])[-2]<<16
    (output/'masked.cfg').write_text(f'MEMORY {{ RAM: start=${probe_base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',output,*[v for k,a in names.items() for v in ('-D',f'{k}={a}')],
             '-o',output/'masked.o',ROOT/'tests/programs/signals_masked.s'])
    command(['ld65','-C',output/'masked.cfg','-o',output/'masked.bin',output/'masked.o'])
    image['segments'].append(dict(address=probe_base,bytes=list((output/'masked.bin').read_bytes()),writable=False,executable=True))
    segment=next(s for s in image['segments'] if s['address']==image['entry'])
    segment['bytes'][:4]=[0x5c,*probe_base.to_bytes(3,'little')]
    from test_banked import changed_image
    changed_image(program)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--compiler-dir',type=Path,required=True)
    parser.add_argument('--bridge-dir',type=Path,required=True)
    parser.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    parser.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/policy')
    parser.add_argument('--mode',choices=('raw','opt'))
    parser.add_argument('--case',action='append')
    args=parser.parse_args()
    output=args.output.resolve();output.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir);platform_files(args.bridge_dir,args.rom)
    cases=[]
    for mode in ('raw','opt'):
        if args.mode and args.mode!=mode:continue
        for fixture in ('core','admission','root','sleep','reuse','far','masks','masked','wait','lifecycle','irq_targets','shutdown'):
            cases.append((fixture+'-'+mode,fixture,mode,0,0x100,None))
        for checkpoint in range(1,7):
            cases.append((f'signal-nmi-{checkpoint}-{mode}','masks' if checkpoint==6 else 'wait',mode,-checkpoint,0x100,None))
        if mode=='opt':
            for point in range(4,8):
                cases.append((f'irq-context-{point}-{mode}','irq',mode,100+point,0x100,3))
        for point in (2,3):
            cases.append((f'burst-{point}-{mode}','burst',mode,100+point,0x100,None))
        cases.append(('atomic-'+mode,'atomic',mode,109,0x100,None))
        for variant in range(3):
            cases.append((f'irq-{variant}-{mode}','irq',mode,0,0x100,variant))
        for variant in range(3):
            cases.append((f'queue-{variant}-{mode}','queue',mode,0,0x100,variant))
        cases.append(('queue-nmi-'+mode,'queue',mode,99,0x100,2))
        for variant in range(11):
            cases.append((f'free-fault-{variant}-{mode}','faults',mode,0,0x100,variant))
        for variant in (1,2):
            cases.append((f'masked-wait-{variant}-{mode}','masked_wait',mode,0,0x100,variant))
        for point in (9,10,11,12,13,14,15,16,17,18):
            cases.append((f'nmi-{point}-{mode}','core',mode,point,0x100,None))
        for flags in (0xc9,0xd9,0xe9,0xf9,0xcd):
            cases.append((f'registers-{flags:02x}-{mode}','core',mode,0,flags,None))
    if args.case:
        cases=[c for c in cases if c[0] in args.case]
        require({c[0] for c in cases}==set(args.case),'Unknown case')
    report=dict(schema_version=1,status='running',platform=PIN,cases=[],
                inputs={str(p.relative_to(ROOT)):sha256(p) for folder in ('tools','lib','abi','platform/altirraos','tests/programs','toolchain')
                        for p in sorted((ROOT/folder).glob('**/*' if folder=='lib' else '*')) if p.is_file()})
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),output,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,args.rom,PIN)
            for name,fixture,mode,point,flags,variant in cases:
                print('Running '+name+'...',flush=True)
                stem='signals_masked' if fixture=='masked_wait' else ('signals_'+fixture) if fixture in ('masks','faults','masked','wait','lifecycle','queue','irq','irq_targets','burst','shutdown','atomic') else 'tasks_exec'+('' if fixture=='core' else '_'+fixture)
                extra_data=[(0x04ffe0,bytes([0xa5])*96),(0x05fff0,bytes([0xa5])*32)] if fixture=='far' else ()
                if fixture=='queue': extra_data=[(a,bytes(96)) for a in (0x08ffe0,0x09ffe0,0x0affe0)]
                if fixture=='atomic': extra_data=[(0x04ffd0,bytes([0xa5])*128)]
                program=build(toolchain,ROOT/'tests/programs'/(stem+'.act'),output/name,
                              tasks=True,optimize=mode=='opt',probe_nmi=0 if point>=99 else max(point,0),probe_flags=flags,image_data=extra_data,policy_probe=max(-point,0),irq_probe=point-100 if point>100 else int(point==99),manual_wake=fixture in ('queue','irq_targets'))
                if fixture in ('masked','masked_wait'): masked_probe(program,variant or 0)
                before=None
                if fixture in ('faults','queue','irq'):
                    at=next(d['address'] for d in program['image']['data'] if '_VARIANT_' in d['name'])
                    before=lambda b:b.poke(at,variant)
                try:
                    expected_status=4 if variant is not None and fixture not in ('queue','irq') else 0
                    result,_=execute(bridge,program,expected_status=expected_status,
                                     before_run=before,timer_irq=fixture=='far',frame_limit=12000 if fixture=='reuse' else 2400,
                                     timeout=1200 if fixture=='reuse' else 240)
                    if fixture=='atomic':
                        checks=data(bridge,program['image'],'checks',True)
                        raw=bytes(data(bridge,program['image'],'values'))
                        values=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                        require(checks==[31,1,1,1] and values==[0,0x80010001,0x40010000,2,0x80000001,2],
                                'Atomic far masks/claim repost: '+str((checks,values)))
                        require(bridge.peek16(adapter.PROBE0)==127 and result['native_irq_count']>=2,
                                'Claimed wake repost/checkpoints missing')
                        require(bridge.peek16(adapter.PROBE1)==1,'Rejected IRQ COP corrupted kernel scratch/guard')
                        from banked_test_memory import read as far_read
                        record=far_read(bridge,0x04ffd0,128,program['output'])
                        require(record[:23]==bytes([0xa5])*23 and record[85:]==bytes([0xa5])*43,
                                'Cross-bank Task guards changed')
                        observed=dict(checks=checks,values=values,claimed_repost=127,rejected_irq_cop=1)
                    elif fixture=='shutdown':
                        observed=dict(shutdown='completed with VBI disabled')
                    elif fixture=='burst':
                        checks=data(bridge,program['image'],'checks',True)
                        require(checks==[1]*4+[0]*4,'Full queue drain: '+str(checks))
                        raw=bytes(data(bridge,program['image'],'values'))
                        require([int.from_bytes(raw[i:i+4],'little') for i in range(0,16,4)]==[1]*4,'Burst Wait results')
                        from banked_test_memory import read
                        flags=list(read(bridge,program['build']['task_storage']['SERIAL_STATE']+5,4,program['output']))
                        require(flags==[1]*4,'Queue did not reach all public contexts: '+str(flags))
                        require(result['idle_runs']>=2,'Burst did not wake idle')
                        if point==103:
                            require(bridge.peek16(adapter.PROBE0)==2 and result['native_irq_count']>=2,'Masked IRQ or protected window failed')
                            require(int.from_bytes(bytes(result['root_task'][24:28]),'little')==2,'Window post lost or incorrectly consumed')
                        observed=dict(checks=checks,queued=flags,masked_pending=bridge.peek16(adapter.PROBE0))
                    elif fixture=='irq':
                        checks=data(bridge,program['image'],'checks',True)
                        require(checks==[1]*5+[0]*3,'IRQ safe delivery: '+str(checks))
                        require(result['native_irq_count']>0,'No hardware serial IRQ')
                        observed=dict(checks=checks)
                        if point>=104:
                            import struct
                            raw=bridge.memdump(adapter.PROBE0,18);f=0xc9+(point-104)*16
                            expected=struct.pack('<BHHHHB',0x12,adapter.TASK0_DP,0x78 if f&16 else 0x5678,0x34 if f&16 else 0x1234,0xabcd,f)
                            require(raw[:10]==expected and raw[10:12]==raw[12:14] and raw[14]==program['labels']['signal_context']>>16 and raw[16:18]==b'\xef\xbe','Serial IRQ native context: '+raw.hex())
                            observed['context']=raw.hex()
                    elif fixture=='irq_targets':
                        checks=data(bridge,program['image'],'checks',True)
                        require(checks==[1]*26+[0]*6,'IRQ target states/lifecycle: '+str(checks))
                        observed=dict(checks=checks)
                    elif fixture=='queue':
                        checks=data(bridge,program['image'],'checks',True)
                        count=18 if variant==0 else 15
                        require(checks[:count]==[1]*count and checks[count:]==[0]*(32-count),'IRQ queue: '+str(checks))
                        if point==99: require(bridge.peek16(adapter.PROBE1)>0,'IRQ NMI checkpoints did not execute')
                        observed=dict(checks=checks,order=data(bridge,program['image'],'order'))
                    elif fixture in ('wait','lifecycle'):
                        checks=data(bridge,program['image'],'checks',True)
                        raw=bytes(data(bridge,program['image'],'values'))
                        values=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                        if fixture=='wait':
                            require(checks==[1,0,1,0,0,0,1,0,1,1,255,1,1,1], 'Signal Wait/Forbid: '+str(checks))
                            require(values==[0x80000001,2,2,0,1,0xc0000000,0,0],'Signal Wait result: '+str(values))
                        else:
                            require(checks[:6]==[1]*6 and 6<=checks[6]<128 and checks[7:14]==[1]*7 and checks[14:]==[0,0], 'Wait lifecycle: '+str(checks))
                            require(values==[0x80000000,1,2], 'Lifecycle masks: '+str(values))
                            require(result['idle_runs']>0,'All-waiting idle path missing')
                        observed=dict(checks=checks,values=values)
                    elif fixture=='masks': observed=check_masks(bridge,program,result)
                    elif fixture=='masked_wait':
                        root=result['root_task']
                        expected_pending=0x80000001 if variant==1 else 0
                        require(int.from_bytes(bytes(root[24:28]),'little')==expected_pending and root[20:24]==[0]*4,'Masked Wait changed signal state')
                        checks=data(bridge,program['image'],'checks',True)
                        require(checks[5]==0,'Masked Wait returned')
                        observed=dict(checks=checks,pending=expected_pending)
                    elif fixture=='masked':
                        checks=data(bridge,program['image'],'checks',True)
                        require(checks[0]==31 and all(v & 4 for v in checks[1:5]),'Caller I not preserved: '+str(checks))
                        raw=bytes(data(bridge,program['image'],'values'))
                        values=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                        require(values==[0,0x80000001],'Masked calls changed pending bits')
                        observed=dict(checks=checks,values=values)
                    elif fixture=='faults':
                        observed=dict(reached=data(bridge,program['image'],'reached'))
                        require(observed['reached']==[0],'Invalid signal operation returned')
                        require(result['root_task'][16:32]==[255,255]+[0]*14,'Rejected operation changed masks')
                    else: observed=check_tasks(bridge,program,fixture,result)
                    if point<0: require(result['signal_nmi_checkpoints']>0,'Signal checkpoint did not execute')
                    if fixture=='far': require(result['native_irq_count']>0,'No concurrent timer IRQ')
                except Exception:
                    (program['output']/'failure.json').write_text(json.dumps(dict(regs=bridge.regs(),state=bridge.memdump(adapter.STATE,64).hex()),indent=2)+'\n')
                    raise
                report['cases'].append(dict(name=name,status='pass',build=program['build'],runtime=result,observed=observed))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed '+str(len(report['cases']))+' signal profile cases')


if __name__=='__main__':main()
