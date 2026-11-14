#!/usr/bin/env python3
"""Disk cursor SDK probe beside two Counters, repeated execution and hidden stop."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT,read_build,require,verify_machine,sha256
from build_gem_desktop import build_desktop
from build_c_program import build as application
from c_program import ABI
from make_data_disk import make
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from stack_budget import stack_usage
from desktop_mouse import schedule
from generate_aes_server import ABI as AES_ABI,layout


def run(out,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    if not replay:
        application(out/'apps/counter',[ROOT/'examples/gem-counter'/name
            for name in ('main.c','counter.c')],minimum_stack=ABI['stack_floor_bytes'])
        application(out/'apps/mouse',[ROOT/'examples/gem-mouse/main.c'],
            minimum_stack=ABI['stack_floor_bytes'])
    apps={name:json.loads((out/'apps'/name/'app.json').read_text()) for name in ('mouse','counter')}
    relative=lambda name,symbol:apps[name]['image']['symbols'][symbol]-(ABI['link_bank']<<16)
    offsets=dict(mouse=relative('mouse','GEMMouse'),counter=relative('counter','GEMCounter'))
    if replay:program=read_build(out/'program')
    else:
        (out/'mouse-app.inc').write_text('CONST MOUSE_MODEL=$%x\nCONST COUNTER_MODEL=$%x\n'
            %(offsets['mouse'],offsets['counter']))
        source=out/'mouse.act'
        source.write_text((ROOT/'tests/programs/c_mouse.act').read_text())
        program=build_desktop(out,source=source,build_applications=False,release_compiler=True,
            program_output=out/'program',system_mount='D1',
            dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)])
    media=out/'media';media.mkdir(exist_ok=True)
    for name in apps:(media/(name.upper()+'.APP')).write_bytes((out/'apps'/name/'program.app').read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
        binary_names={'MOUSE.APP','COUNTER.APP'})
    at=lambda name:next(d['address'] for d in program['image']['data']
        if '_CMOUSETEST_'+name.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,apps=apps,cases=[])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
            bridge.mount(0,str(out/'system.atr'))
            report['machine']=verify_machine(bridge,ROM,PIN)
            number=lambda address,size=2:int.from_bytes(bridge.memdump(address,size),'little')
            def reach(condition):
                marker=program['labels']['native_cop']
                bridge.bp_clear_all();bridge.bp_set(marker,condition=condition)
                faults=[program['labels'][name] for name in ('heap_fault','stack_overflow','arithmetic_fault','done')]
                for address in faults:bridge.bp_set(address)
                original=bridge.regs
                def regs():
                    state=original();pc=int(state['PC'].lstrip('$'),16)
                    require(pc not in faults,'Guest stopped before rendezvous: '+str(state))
                    return state
                bridge.regs=regs
                try:run_to(bridge,marker,condition=condition,timeout=180,frame_limit=18000)
                finally:bridge.regs=original
            def frames(count):reach('@frame>=%d'%(bridge.eval_expr('@frame')+count))
            def before(bridge):
                position=[320,120];bridge._cmd_ok('MOUSE ST')
                for round in range(2):
                    first=round*3+1
                    reach('dw($%x)=%d'%(at('phase'),first))
                    bases=[number(at('bases')+i*4,4) for i in range(2)]
                    models=[base+offsets['counter'] for base in bases]
                    reach('&'.join('dw($%x)=1'%(model+12) for model in models))
                    frames(120)
                    counts=[number(model+14,4) for model in models]
                    require(all(counts),'Counters did not start ticking')
                    probe=number(at('probeBase'),4)+offsets['mouse']
                    bridge.poke16(at('go'),first)
                    reach('dw($%x)=1'%probe)
                    resident=json.loads((out/'c-image.json').read_text())['symbols']
                    request=layout()['Request'];gem_id=number(probe+14)
                    contexts=bridge.memdump(resident['contexts'],AES_ABI['constants']['CONTEXTS']*4)
                    found=[]
                    for offset in range(0,len(contexts),4):
                        context=int.from_bytes(contexts[offset:offset+4],'little')
                        if context and number(context+request['fields']['global']+4)==gem_id:
                            found.append(context)
                    require(len(found)==1,'No private loaded-probe context')
                    sequence=found[0]+request['fields']['sequence']
                    before_rpc=number(sequence,4)
                    position=schedule(bridge,program,position,(548,88))
                    reach('(dw($%x)=1)&(dw($%x)=15)'%(probe,probe+8))
                    after_rpc=number(sequence,4)
                    require(before_rpc==after_rpc,'Warm cursor/scroll added an RPC')
                    reach('dw($%x)=%d'%(at('phase'),first+2))
                    after=[number(model+14,4) for model in models]
                    require(all(b>a for a,b in zip(counts,after)),
                            'Both Counters must advance while the probe runs')
                    require(number(probe+2)==1 and number(probe+6)==0 and number(probe+8,4)==16,
                            'Cursor probe did not complete cleanly')
                    report['cases'].append(dict(round=round,bases=bases,
                        counter_before=counts,counter_after=after,probe_checks=number(probe+4),
                        probe_rounds=number(probe+8,4),measured_warm_rounds=15,
                        warm_rpc_delta=after_rpc-before_rpc))
                    bridge.screenshot(str(out/f'round-{round}.png'))
                    bridge.poke16(at('go'),first+2)
                bridge.bp_clear_all()
            report['runtime'],_=execute(bridge,program,before_run=before,timeout=300,frame_limit=30000)
            ownership(bridge,program,program['output'])
            require(data(bridge,program['image'],'completed',True)==[8],'Incomplete Process lifetimes')
            require(data(bridge,program['image'],'stopHidden',True)==[1],'Hidden stop was not exercised')
            report.update(status='pass',checks=data(bridge,program['image'],'checks',True),
                completed=8,stop_while_hidden=True,build=program['build'],
                stack_usage=stack_usage(bridge,program['build']['memory']),
                app_sha256={name:sha256(out/'apps'/name/'program.app') for name in apps})
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Loaded mouse probe and two Counters passed',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args();run(args.output,args.replay)
