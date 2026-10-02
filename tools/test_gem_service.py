#!/usr/bin/env python3
"""G2: native service transport, lifetime, validation and failure rollback."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_gem_vdi import build_service_probe
from native_program import ROOT, execute, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_calypsi import pattern
from test_cooperative import data
from test_heap_api import clean_ownership
from test_large_stacks import observe

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())
CASES = ['protocol','stop-queued','stop-active','admission','startup-signal',
         'worker-port','worker-scratch','client-port','client-packet','stop-port',
         'stop-packet','held-renderer','held-client','stop-exhausted']


def run(output, mode, cases=None):
    output = Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    report = dict(status='running',tier='development',slice='G2',mode=mode,cases=[],
                  scope='Fixture dispatcher; no GEM drawing or VBXE backend is linked')
    try:
        program,foreign = build_service_probe(output,optimize=mode=='opt')
        report['build'] = program['build']
        memory = program['build']['memory']
        before = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key]==before[key],'G2 changed '+key)
        report['bank_zero_delta'] = dict(fixed=0,per_task=[0]*8,private_idle=0)
        report['c_map'] = dict(segments=[dict(address=s['address'],bytes=len(s['bytes']),executable=s['executable'])
            for s in foreign['segments']],zero_fill=foreign['zero_fill'],reserved_upper_bytes=131072,
            reserved_upper_banks=[12,13],dp_workspace_bytes=20)
        report['pin'] = PIN
        bridge_dir=ROOT/'build/shell-paced-bridge'
        rom=ROOT/'build/firmware/altirraos-816.rom'
        require(sha256(rom)==PIN['rom']['sha256'],'Wrong ROM')
        require(sha256(bridge_dir/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Wrong emulator')
        symbols=foreign['symbols']
        with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
            report['machine']=verify_machine(bridge,rom,PIN)
            for index,name in enumerate(cases or CASES):
                variant=CASES.index(name)
                folder=output/name
                folder.mkdir(exist_ok=True)
                if index:
                    bridge.state_load(slot='loaded')
                case=dict(name=name,status='running')
                saved={}
                sentinel=bytes((i*37+11)&255 for i in range(4096))

                def before_run(b):
                    if not index:
                        b.state_save(slot='loaded')
                    b.memload(symbols['variant'],variant.to_bytes(2,'little'))
                    b.memload(0x8000,sentinel)
                    saved['display']=b.memdump(0x22f,3)
                    saved['memac']=b.memdump(0xd65e,2)
                    if variant==0:
                        for slot in (0,6,7):
                            marker=program['labels']['task_start' if slot==0 else 'general_task_start']
                            condition=f'db(${adapter.CURRENT:04x})={slot}'
                            b.bp_set(marker,condition=condition)
                            run_to(b,marker,frame_limit=3000,timeout=90,condition=condition)
                            b.bp_clear_all()
                            dp=memory['task_pools'][slot]['dp']
                            b.memload(dp+8,pattern(slot)[8:16])
                            b.memload(dp+20,pattern(slot)[20:])
                        b.memload(adapter.KERNEL_DP,pattern(4))
                        case['c_preemption']=observe(b,program,[symbols['progress'],symbols['progress']+2],code_bank=12)

                try:
                    runtime,_=execute(bridge,{**program,'output':folder},before_run=before_run,
                        preloaded=bool(index),expected_status=4 if variant in (11,12) else 0,
                        frame_limit=4000,timeout=120)
                    case['runtime']=runtime
                    read=lambda name,size=2:int.from_bytes(bridge.memdump(symbols[name],size),'little')
                    case['checks']=read('checks')
                    case['failures']=read('failures')
                    case['first_failure']=read('first_failure')
                    require(read('failures')==0,f'Target assertion failed: {case["first_failure"]} ({case["failures"]} failures)')
                    if variant not in (11,12):
                        require(read('finished')==1 and data(bridge,program['image'],'result',True)==[0],'C service fixture failed')
                        require(runtime['root_task'][16:20]==[255,255,0,0],'Root signal leaked')
                        clean_ownership(bridge,program,program['output'])
                    if variant==0:
                        for who in (0,1):
                            a,b=0x12345678+who,0x87654321-who
                            for i in range(30000):
                                a=((a << 1) ^ (a >> 31) ^ b)&0xffffffff
                                b=(b+(a ^ i))&0xffffffff
                            actual=int.from_bytes(bridge.memdump(symbols['checksum']+who*4,4),'little')
                            require(actual==a ^ b,'Interrupted C computation changed')
                        for slot in (0,6,7):
                            dp=memory['task_pools'][slot]['dp']
                            require(bridge.memdump(dp+20,108)==pattern(slot)[20:],'Unused C DP changed')
                        dp=memory['task_pools'][0]['dp']
                        require(bridge.memdump(dp+8,8)==pattern(0)[8:16],'C callee-preserved registers changed')
                        require(bridge.memdump(adapter.KERNEL_DP,128)==pattern(4),'Kernel lower DP changed')
                    if variant==2:
                        require(read('saw_stop')==1,'STOP did not overlap active work')
                    case['stack_usage']=stack_usage(bridge,memory)
                    require(all(s['remaining_above_floor']>0 for s in case['stack_usage'].values()),'Stack floor reached')
                    require(bridge.memdump(0x8000,4096)==sentinel,'Aperture changed')
                    require(bridge.memdump(0x22f,3)==saved['display'],'OS presentation changed')
                    require(saved['memac']==bytes(2) and bridge.memdump(0xd65e,2)==bytes(2) and
                            bridge.memdump(0xd653,2)==bytes(2),'VBXE became active')
                    case['status']='pass'
                    print('Passed G2',mode,name,flush=True)
                except Exception as error:
                    case.update(status='fail',error=str(error),
                        target={key:int.from_bytes(bridge.memdump(symbols[key],2),'little')
                                for key in ('checks','first_failure','failures','finished','active')},
                        adapter=bridge.memdump(adapter.STATE,64).hex())
                    raise
                finally:
                    report['cases'].append(case)
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--cases',help='Comma-separated focused cases')
    args=parser.parse_args()
    run(args.output or ROOT/'build/gem-vdi'/('g2-'+args.mode),args.mode,args.cases.split(',') if args.cases else None)
