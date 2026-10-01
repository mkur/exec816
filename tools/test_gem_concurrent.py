#!/usr/bin/env python3
"""G5 combined VDI / computing Task / physical SDFS development checks."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
from build_gem_vdi import build_concurrent_probe
from gem_render_oracle import Raster, font_bytes
from native_program import ROOT, execute, read_build, verify_machine, require, sha256
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_heap_api import clean_ownership
from test_calypsi import pattern
from test_large_stacks import observe

PIN=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
CASES=['concurrent','stop-queued','stop-active','device-fault','unquiesced',
       'worker-port','worker-scratch','client-port','client-packet','stop-port','stop-packet','admission','startup-signal']


def scene_hash(output):
    raster=Raster(font_bytes(output/'selected/src/vdi/font8x8.c'))
    for i in range(12): raster.apply(8,[64,24+i*16],[32+(i*64+j)%96 for j in range(64)])
    h=2166136261
    for v in raster.packed(): h=((h^v)*16777619)&0xffffffff
    return h


def run(output,mode,cases=None,replay=False,production=False):
    output=Path(output).resolve(); output.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',slice='G5',mode=mode,cases=[],production=production)
    try:
        if replay:
            program=read_build(output/'program')
            foreign=json.loads((output/'c-image.json').read_text())
        else: program,foreign=build_concurrent_probe(output,mode=='opt',not production)
        require(foreign['provenance']['diagnostic']==(not production),'Wrong instrumentation')
        report.update(build=program['build'],pin=PIN,harness_sha256=sha256(Path(__file__)),
            xex_sha256=sha256(program['xex']),xex_bytes=Path(program['xex']).stat().st_size,
            media_sha256=sha256(output/'system.atr'),
            c_map=dict(segments=[dict(address=s['address'],bytes=len(s['bytes']),executable=s['executable'])
                for s in foreign['segments']],zero_fill=foreign['zero_fill'],reserved_upper_bytes=131072),
            bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
        memory=program['build']['memory']; sy=foreign['symbols']
        baseline=json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key]==baseline[key],'Bank-zero change: '+key)
        for name in cases or (['concurrent'] if production else CASES):
            variant=CASES.index(name); folder=output/name; folder.mkdir(exist_ok=True)
            case=dict(name=name,status='running'); report['cases'].append(case)
            with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',folder,pin=PIN) as b:
                b.config('diskemu','generic56k'); b.mount(0,str(output/'system.atr'))
                case['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
                read=lambda k,n=2:int.from_bytes(b.memdump(sy[k],n),'little')
                saved={}
                def reach(label,condition=None):
                    marker=program['labels'][label]; b.bp_clear_all(); b.bp_set(marker,condition=condition)
                    run_to(b,marker,frame_limit=12000,timeout=180,condition=condition)
                    b.bp_clear_all()
                def before(b):
                    b.memload(sy['variant'],variant.to_bytes(2,'little'))
                    b.memload(0x6000,bytes(2))
                    saved['os']=b.memdump(0x22f,3)
                    saved['aperture']=bytes((i*37+11)&255 for i in range(4096))
                    b.memload(0x8000,saved['aperture'])
                    if variant==0 and not production:
                        for slot in (0,6,7):
                            reach('task_start' if slot==0 else 'general_task_start',f'db(${adapter.CURRENT:x})={slot}')
                            dp=memory['task_pools'][slot]['dp']
                            b.memload(dp+8,pattern(slot)[8:16]); b.memload(dp+20,pattern(slot)[20:])
                        b.memload(adapter.KERNEL_DP,pattern(4))
                        # Release the fixture rendezvous at a physical IRQ. A
                        # changed progress counter between active IRQ samples with
                        # an unchanged terminal-post count proves wire overlap.
                        posts=program['labels']['SD_POSTS']
                        phase=program['labels']['SD_PHASE']
                        active=f'(db(${phase:x})>0)&(db(${phase:x})<13)'
                        reach('native_irq',active)
                        sample=lambda: dict(posts=b.peek16(posts),peer=read('progress'),draw=b.peek16(sy['progress']+2))
                        previous=sample(); windows=[previous]; seen=[False,False]
                        b.memload(0x6000,b'\x01\x00')
                        for n in range(100):
                            changed=(f'(dw(${posts:x})!={previous["posts"]})|'
                                f'(dw(${sy["progress"]:x})!={previous["peer"]})|'
                                f'(dw(${sy["progress"]+2:x})!={previous["draw"]})')
                            reach('native_irq',f'({active})&({changed})')
                            current=sample(); windows.append(current)
                            if current['posts']==previous['posts']:
                                seen[0] |= current['peer']>previous['peer']
                                seen[1] |= current['draw']>previous['draw']
                            previous=current
                            if all(seen): break
                        require(all(seen),'No renderer and peer progress during physical SIO')
                        case['physical_overlap']=windows
                        case['c_preemption']=observe(b,program,[sy['progress'],sy['progress']+2],code_bank=12,pc_range=(0xc0000,0xd0000))
                    b.bp_clear_all()
                try:
                    runtime,_=execute(b,{**program,'output':folder},before_run=before,
                        expected_status=0xff93 if variant==4 else 0,frame_limit=24000,timeout=360)
                    case.update(runtime=runtime,checks=read('checks'),failures=read('failures'),first_failure=read('first_failure'))
                    require(not case['failures'],f'Target assertion {case["first_failure"]}')
                    if variant==4:
                        # Hardware cannot prove idle: pending request, port, scratch
                        # and Task leases must remain live at the reset-required park.
                        case['retained_request']=b.memdump(sy['client'],38).hex()
                        require(b.peek16(sy['display']+17)&255==4,'Display lease released while hardware busy')
                        require(all(int.from_bytes(b.memdump(sy['server']+o,n),'little') for o,n in
                            ((8,4),(12,3),(24,3),(36,4),(40,4),(56,4))), 'Live server resources freed')
                        require(int.from_bytes(b.memdump(sy['client']+12,4),'little')==
                            int.from_bytes(b.memdump(sy['client']+8,4),'little')!=0,'Pending packet lost')
                        require(read('finished')==0 and read('inject')==1,'Unquiesced path escaped')
                    else:
                        require(read('finished')==1,'Incomplete target')
                        clean_ownership(b,program,program["output"])
                        require(runtime['native_irq_count']>0,'No physical SIO IRQ')
                        require(b.memdump(0x22f,3)==saved['os'],'OS display was not restored')
                        require(b.memdump(0x8000,4096)==saved['aperture'],'CPU aperture changed')
                        require(b.memdump(0xd65e,2)==bytes(2),'MEMAC left mapped')
                        case.update(frames=(read('endTick')-read('startTick'))&65535,
                            service_round_trips=read('crossings'),completed=read('completed'),
                            stack_usage=stack_usage(b,memory),pixel_hash=read('pixelHash',4))
                        require(all(v['remaining_above_floor']>0 for v in case['stack_usage'].values()),'Stack floor reached')
                        if not production and variant!=3:
                            require(case['pixel_hash']==scene_hash(output),'Scene pixel hash mismatch')
                        a,bv=0x12345678,0x87654321
                        for i in range(30000):
                            a=((a<<1)^(a>>31)^bv)&0xffffffff; bv=(bv+(a^i))&0xffffffff
                        require(read('checksum',4)==a^bv,'Peer register/context corruption')
                        if variant==0 and not production:
                            for slot in (0,6,7):
                                dp=memory['task_pools'][slot]['dp']
                                if slot==0:
                                    require(b.memdump(dp+8,8)==pattern(slot)[8:16],'C return corrupted callee-preserved DP')
                                else:
                                    require(b.memdump(dp+20,108)==pattern(slot)[20:],f'Unused C DP changed: {slot}')
                            require(b.memdump(adapter.KERNEL_DP,128)==pattern(4),'Kernel lower DP changed')
                    case['status']='pass'
                    print(mode,name,'pass',flush=True)
                except Exception:
                    print('target', {k:read(k) for k in ('stage','checks','failures','first_failure','entered','commandCount','completed','finished')},flush=True)
                    raise
        report['status']='pass'
    except Exception as e:
        report.update(status='fail',error=str(e)); raise
    finally: (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',choices=CASES,action='append')
    p.add_argument('--replay',action='store_true')
    p.add_argument('--production',action='store_true')
    a=p.parse_args(); run(a.output,a.mode,a.case,a.replay,a.production)
