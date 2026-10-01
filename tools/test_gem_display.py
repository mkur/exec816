#!/usr/bin/env python3
"""G3 emitted display ownership, VRAM, completion and recovery checks."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
from build_gem_vdi import build_display_probe
from native_program import ROOT,execute,read_build,verify_machine,require,sha256
from os_boundary import emulator,run_to
from stack_budget import stack_usage
from test_heap_api import clean_ownership
from test_cooperative import data
from test_gem_vdi import case_pin
from test_calypsi import pattern
from test_large_stacks import observe

CASES=['pattern','unknown-baseline','absent','unsupported','busy-timeout','vcount-timeout',
       'unquiesced','retained-owner','wrap-timeout','map-nmi']


def run(output,mode,cases=None,replay=False,production=False):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    if production:
        require(cases is None or cases==['pattern'],'Production control runs the real pattern only')
        cases=['pattern']
    report=dict(status='running',tier='development',slice='G3',mode=mode,cases=[],production_control=production)
    try:
        if replay:
            program=read_build(output/'program')
            foreign=json.loads((output/'c-image.json').read_text())
        else:
            program,foreign=build_display_probe(output,optimize=mode=='opt',instrument=not production)
        require(foreign['provenance']['instrumentation']['busy_and_vcount_reads']==(not production),'Replayed instrumentation differs')
        report['build']=program['build']
        report['test_harness_sha256']=sha256(Path(__file__))
        report['media_sha256']=sha256(output/'system.atr')
        report['c_map']=dict(segments=[dict(address=s['address'],bytes=len(s['bytes']),executable=s['executable'])
            for s in foreign['segments']],zero_fill=foreign['zero_fill'],reserved_upper_banks=[12,13],
            reserved_upper_bytes=131072,dp_workspace_bytes=20)
        report['vram']=foreign['provenance']['vram']
        symbols=foreign['symbols']
        memory=program['build']['memory']
        report['bank_zero_delta']=dict(fixed=0,per_task=[0]*8,private_idle=0)
        before=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key]==before[key],'G3 changed '+key)
        for name in cases or CASES:
            variant=CASES.index(name)
            pin=case_pin('absent' if variant==2 else 'unsupported' if variant==3 else 'present')
            folder=output/name
            folder.mkdir(exist_ok=True)
            case=dict(name=name,status='running')
            saved={}
            sentinel=bytes((i*37+11)&255 for i in range(4096))
            with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=pin) as b:
                b.config('diskemu','generic56k')
                b.mount(0,str(output/'system.atr'))
                case['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
                def before_run(b):
                    b.memload(symbols['variant'],variant.to_bytes(2,'little'))
                    b.memload(symbols['tickAddress'],adapter.VBI_COUNT.to_bytes(4,'little'))
                    b.memload(0x8000,sentinel)
                    saved['os']=b.memdump(0x22f,3)
                    saved['screen_at']=b.peek16(0x58)
                    saved['screen']=b.memdump(saved['screen_at'],960)
                    saved['cursor']=b.peek(0x2f0)
                    if variant in (0,9):
                        for slot in (0,6,7):
                            marker=program['labels']['task_start' if slot==0 else 'general_task_start']
                            condition=f'db(${adapter.CURRENT:x})={slot}'
                            b.bp_set(marker,condition=condition)
                            run_to(b,marker,frame_limit=3000,timeout=90,condition=condition)
                            b.bp_clear_all()
                            dp=memory['task_pools'][slot]['dp']
                            b.memload(dp+8,pattern(slot)[8:16])
                            b.memload(dp+20,pattern(slot)[20:])
                        b.memload(adapter.KERNEL_DP,pattern(4))
                    if variant==9:
                        prologue=bytes.fromhex('c23048da5a0b8bd83baa2900ffc90001f004a9ef011bda')
                        marker=program['labels']['native_nmi']
                        require(b.memdump(marker,len(prologue))==prologue,'Changed NMI observer')
                        marker+=len(prologue)
                        observations=[]
                        for point in range(1,5):
                            condition=f'(dw(${symbols['mapPoint']:x})={point})&(db(${adapter.CURRENT:x})=7)'
                            b.bp_clear_all()
                            b.bp_set(marker,condition=condition)
                            run_to(b,marker,frame_limit=3000,timeout=90,condition=condition)
                            stack=b.peek16(0x1ee)
                            frame=b.memdump(stack+1,13)
                            pc=int.from_bytes(frame[10:13],'little')
                            require(pc>>16==12 and int.from_bytes(frame[1:3],'little')==memory['task_pools'][7]['dp'],'Mapping lost owner context')
                            regs=list(b.memdump(0xd65e,2))
                            require(regs==([0,0] if point==1 else [0,0xbf] if point==2 else [0x88,0xbf]),'MEMAC store order changed')
                            observations.append(dict(point=point,pc=pc,saved_s=stack,frame=frame.hex(),memac=regs))
                            b.memload(symbols['mapGate'],point.to_bytes(2,'little'))
                        case['mapping_nmi']=observations
                    if variant in (0,9):
                        case['c_preemption']=observe(b,program,[symbols['progress'],symbols['progress']+2],code_bank=12)
                    b.bp_clear_all()
                try:
                    runtime,_=execute(b,{**program,'output':folder},before_run=before_run,
                        expected_status=0xff93 if variant in (6,7) else 0,
                        frame_limit=16000,timeout=240)
                    case['runtime']=runtime
                    read=lambda key,size=2:int.from_bytes(b.memdump(symbols[key],size),'little')
                    case.update(checks=read('checks'),failures=read('failures'),first_failure=read('first_failure'))
                    require(not case['failures'],f'Target check {case["first_failure"]} failed')
                    if variant not in (6,7):
                        require(read('finished')==1 and data(b,program['image'],'result',True)==[0],'Fixture incomplete')
                        clean_ownership(b,program,program['output'])
                        require(b.memdump(0x8000,4096)==sentinel,'Underlying CPU aperture was changed')
                        require(b.memdump(0x22f,3)==saved['os'],'OS DMA/display list not restored')
                        require(b.memdump(saved['screen_at'],960)==saved['screen'],'OS screen not restored')
                        require(b.peek(0x2f0)==saved['cursor'],'OS cursor not restored')
                        require(b.memdump(0xd65e,2)==bytes(2) if variant!=2 else True,'MEMAC still mapped')
                        if variant==5:
                            case['vcount_reads']=read('vcountReads')
                            require(case['vcount_reads']>1,'VCOUNT wait was not reached')
                        if variant==8:
                            require(read('waitStart')>=0xfffe and read('waitEnd')<32,'Deadline did not cross tick wrap')
                            case['wait_ticks']=[read('waitStart'),read('waitEnd')]
                        if variant in (0,9):
                            require(runtime['native_irq_count']>0,'Physical SIO IRQ did not run')
                            for who,slot in enumerate((6,7)):
                                a,bv=0x12345678+who,0x87654321-who
                                for i in range(30000):
                                    a=((a<<1)^(a>>31)^bv)&0xffffffff
                                    bv=(bv+(a^i))&0xffffffff
                                require(int.from_bytes(b.memdump(symbols['checksum']+who*4,4),'little')==a^bv,'Compute context changed')
                                require(b.memdump(memory['task_pools'][slot]['dp']+20,108)==pattern(slot)[20:],'Unused C DP changed')
                            require(b.memdump(memory['task_pools'][0]['dp']+8,8)==pattern(0)[8:16],'C preserved DP changed')
                            require(b.memdump(adapter.KERNEL_DP,128)==pattern(4),'Kernel lower DP changed')
                            expected=2166136261
                            for row in range(240):
                                for col in range(320):expected=((expected^((col//20)*17))*16777619)&0xffffffff
                            require(read('pixelHash',4)==expected,'VRAM pixel digest mismatch')
                            case['pixel_hash']=expected
                        case['stack_usage']=stack_usage(b,memory)
                        require(all(s['remaining_above_floor']>0 for s in case['stack_usage'].values()),'Stack floor reached')
                    else:
                        case['lease_state']=b.memdump(symbols['display']+17,1)[0]
                        require(case['lease_state']==(4 if variant==6 else 2),f'Lost retained display state: {case["lease_state"]}')
                    case['status']='pass'
                except Exception:
                    print('C checks/failures/first/stage/answer',*[int.from_bytes(b.memdump(symbols[k],2),'little') for k in ('checks','failures','first_failure','stage','answer')],flush=True)
                    print('Native checks',data(b,program['image'],'checks',True),'status',hex(b.peek16(adapter.STATUS)),'lease',b.memdump(symbols['display'],40).hex(),flush=True)
                    raise
            report['cases'].append(case)
        report['status']='pass'
    except Exception as e:
        report.update(status='fail',error=str(e));raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--case',choices=CASES,action='append')
    p.add_argument('--replay',action='store_true')
    p.add_argument('--production-control',action='store_true')
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.output,a.mode,a.case,a.replay,a.production_control)
    print('G3 passed',a.mode,flush=True)
