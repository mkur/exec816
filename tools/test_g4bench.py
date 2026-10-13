#!/usr/bin/env python3
"""Loaded G4BENCH pixels, timing, cancellation and lifetime development check."""
import argparse
import json
from pathlib import Path
from build_c_program import build as application
from build_gem_desktop import build_desktop
from gem_applications import symbols
from make_data_disk import make
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import PIN, BRIDGE, ROM
from test_cooperative import data
from stack_budget import bank_zero_delta, stack_usage
from desktop_mouse import schedule
from g4bench_results import read as read_results
from g4bench_oracle import check as check_pixels
from filesystem_audit import Audit
import adapter_state as adapter


def run(out,reuse=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if reuse:p=read_build(out/'program')
    else:
        p=build_desktop(out,source=ROOT/'tests/programs/g4bench_session.act',
            system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2),dict(alias='WORK',unit=56,sectors=720,
                sector_bytes=128,profile=4,format=2,access='readwrite')])
        application(out/'apps/g4clock',[ROOT/'tests/programs/g4bench_pixels.c',
                    ROOT/'ports/gem4xe/apps/g4bench/clock.c',
                    out/'apps/g4bench/source/src/apps/g4bench.c'])
        media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        (media/'C/G4BENCH.APP').write_bytes((out/'apps/g4bench/program.app').read_bytes())
        (media/'C/G4CLOCK.APP').write_bytes((out/'apps/g4clock/program.app').read_bytes())
        make(out/'system.atr',media,binary_names={'C/G4BENCH.APP','C/G4CLOCK.APP'},
             filesystem='sdfs',sector_bytes=256,sectors=2880)
        work=out/'work-files';work.mkdir(exist_ok=True)
        make(out/'work.atr',work,filesystem='sdfs',sector_bytes=128,sectors=720)
    report=dict(status='running',tier='development',qualification=False,
                bank_zero_delta=bank_zero_delta(p['build']['memory']),
                bank_zero_slice_delta=dict(fixed=0,per_public_task=[0]*8,idle=0),cases=[])
    at=lambda name:next(d['address'] for d in p['image']['data']
                       if '_G4BENCHTEST_'+name.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(out/'system.atr'));b.mount(7,str(out/'work.atr'))
            def get(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
            def reach(condition):
                b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    value=original()
                    if int(value['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return value
                b.regs=regs
                try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=300,frame_limit=24000)
                except Exception:
                    report['failure']=dict(adapter=b.memdump(adapter.STATE,64).hex(),
                        checks=get(at('checks')),ready=get(at('ready')),pc=original(),
                        dos=b.memdump(p['build']['memory']['dos_storage']['BASE'],128).hex(),
                        sio=b.memdump(int((p['output']/'sio-storage-action.inc').read_text()
                            .split('CONST SIO_STATE=$',1)[1].splitlines()[0],16),128).hex())
                    raise
                finally:b.regs=original
            def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def key(name):
                b._cmd_ok('KEY '+name+' down');frames(3)
                b._cmd_ok('KEY '+name+' up');frames(20)
            def before(b):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                reach('dw($%x)>0'%at('benchmark'))
                probe=symbols(b,p,out,'g4clock',get(at('benchmark'),4))
                reach('dw($%x)=1'%probe['g4p_ready'])
                schedule(b,p,[320,120],(630,230));frames(100)
                for row in range(5):
                    reach('dw($%x)=%d'%(probe['g4p_stage'],row+1));frames(100)
                    check_pixels(b,out,out/'selected/src/vdi/font8x8.c',row)
                    print('G4BENCH pixels:',row,flush=True);key('RETURN')
                report['pixels']=5
                for cycle in (1,2):
                    reach('dw($%x)=%d'%(at('ready'),cycle))
                    sy=symbols(b,p,out,'g4bench',get(at('benchmark'),4))
                    reach('dw($%x)=1'%sy['g4b_ready']);frames(100)
                    require(get(sy['g4b_done'])==0,'Reload retained results')
                    key('RETURN')
                    if cycle==2:
                        # A title drag changes the timed canvas through normal
                        # input. It must invalidate the run, not improve its score.
                        reach('dw($%x)>0'%sy['g4b_phase'])
                        position=schedule(b,p,[630,230],(200,48));frames(3)
                        b._cmd_ok('MOUSE AT 2000 0 0 1');frames(20)
                        position=schedule(b,p,position,(240,48));frames(3)
                        b._cmd_ok('MOUSE AT 2000 0 0 0');frames(20)
                        reach('dw($%x)=1'%sy['g4b_done']);frames(100)
                        moved=read_results(b,sy);report['invalidated']=moved
                        require(any(r['status']=='invalidated' for r in moved['rows']),
                                'Move did not invalidate the timed run')
                        key('RETURN')
                        reach('dw($%x)>0'%sy['g4b_phase']);key('ESC')
                    reach('dw($%x)=1'%sy['g4b_done']);frames(100)
                    results=read_results(b,sy);report['cases'].append(results)
                    if cycle==1:
                        require(all(r['status'] in ('complete','low resolution') for r in results['rows']),
                                'Incomplete measured workloads: '+str(results))
                        require(results['save']==1,'Benchmark report was not saved')
                        b._cmd_ok('EJECT drive=7')
                        audit=Audit((out/'work.atr').read_bytes());audit.sdfs()
                        text=audit.files['G4BENCH.TXT'].replace(b'\r\n',b'\n').replace(b'\r',b'\n').decode('ascii')
                        require(text.count('  sample ')==15 and 'SKIP window cycles' in text,'Incomplete disk report')
                        for row_result in results['rows']:
                            for sample in row_result['samples']:
                                require(f"ops={sample['operations']} ticks={sample['ticks']} " in text,'Saved samples differ')
                        (out/'G4BENCH.TXT').write_text(text)
                        print('G4BENCH medians:',[r['median_ms_per_operation'] for r in results['rows']],flush=True)
                        key('ESC')
                    else:
                        require(any(r['status']=='cancelled' for r in results['rows']),'Escape did not cancel')
                        require(results['save']==2,'Missing WORK disk should report save failure')
                        b._cmd_ok('KEY ESC down')
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=36000)
            ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[2],'Benchmark lifetimes incomplete')
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                          stack_usage=stack_usage(b,p['build']['memory']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();run(args.output,args.replay)
