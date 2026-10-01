#!/usr/bin/env python3
"""G1 development checks: hosted GEM C, recording device and computing peer."""
import argparse
import hashlib
import json
from pathlib import Path

import adapter_state as adapter
from build_gem_vdi import build_probe
from native_program import ROOT, execute, require, sha256, verify_machine
from os_boundary import emulator, run_to
from stack_budget import stack_usage
from test_calypsi import pattern
from test_cooperative import data
from test_heap_api import clean_ownership
from test_large_stacks import observe

PIN = json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text())


def run(output, mode):
    output = Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    report = dict(status='running',tier='development',slice='G1',mode=mode,
                  scope='GEM C entry/layout and recording callbacks; linked VBXE backend is not executed')
    try:
        program,foreign = build_probe(output,optimize=mode=='opt')
        report['build'] = program['build']
        memory = program['build']['memory']
        before = json.loads((ROOT/'docs/development/larger-task-stacks.json').read_text())['bank_zero']['final']['8']
        for key in ('bank_zero_budget','task_pools','runtime_reservations','phase_reservations'):
            require(memory[key] == before[key], 'G1 changed '+key)
        report['bank_zero_delta'] = dict(fixed=0,per_task=[0]*8,private_idle=0)
        report['c_map'] = dict(segments=[dict(address=s['address'],bytes=len(s['bytes']),executable=s['executable'])
                                       for s in foreign['segments']],zero_fill=foreign['zero_fill'],
                               reserved_upper_banks=[12,13],reserved_upper_bytes=131072,
                               dp_workspace_bytes=foreign['provenance']['dp_workspace_bytes'])
        report['vram'] = dict(available_bytes=524288,reserved_bytes=0,active=False)
        rom = ROOT/'build/firmware/altirraos-816.rom'
        bridge_dir = ROOT/'build/shell-paced-bridge'
        require(sha256(rom)==PIN['rom']['sha256'],'Wrong ROM')
        require(sha256(bridge_dir/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Wrong emulator')
        report['pin'] = PIN
        with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
            report['machine'] = verify_machine(bridge,rom,PIN)
            saved = {}
            sentinel = bytes((i*37+11)&255 for i in range(4096))
            symbols = foreign['symbols']

            def before_run(b):
                b.memload(0x8000,sentinel)
                saved['display'] = b.memdump(0x22f,3)
                saved['memac'] = b.memdump(0xd65e,2)
                require(saved['memac']==bytes(2),'VBXE active at boot')
                for slot in (0,6,7):
                    marker = program['labels']['task_start' if slot==0 else 'general_task_start']
                    condition = f'db(${adapter.CURRENT:04x})={slot}'
                    b.bp_set(marker,condition=condition)
                    run_to(b,marker,frame_limit=3000,timeout=90,condition=condition)
                    b.bp_clear_all()
                    dp = memory['task_pools'][slot]['dp']
                    b.memload(dp+8,pattern(slot)[8:16])
                    b.memload(dp+20,pattern(slot)[20:])
                b.memload(adapter.KERNEL_DP,pattern(4))
                target = foreign['provenance']['preemption_routine']
                # The short computing peer can finish before a rare GEM-text VBI.
                report['c_preemption'] = observe(b,program,[symbols['progress']+2],slots=[7],code_bank=12)
                report['c_preemption'] += observe(b,program,[symbols['progress']],slots=[6],code_bank=12,
                                                 pc_range=(target['start'],target['end']))

            runtime,_ = execute(bridge,program,before_run=before_run,frame_limit=3000,timeout=90)
            report['runtime'] = runtime
            read = lambda name,size=2: int.from_bytes(bridge.memdump(symbols[name],size),'little')
            report['results'] = {name:read(name,size) for name,size in
                (('failures',2),('completed',2),('peer_checksum',4),('font_checksum',4))}
            require(data(bridge,program['image'],'result',True)==[0],'C main failed')
            require(read('failures')==0 and read('completed')==2,'GEM C probe failed')
            require(bridge.memdump(symbols['progress'],4)==bytes.fromhex('80003075'),'Workers did not finish')
            a,b = 0x12345678,0x87654321
            for i in range(30000):
                a = ((a << 1) ^ (a >> 31) ^ b) & 0xffffffff
                b = (b+(a ^ i)) & 0xffffffff
            require(read('peer_checksum',4)==a ^ b,'Preempted computation changed')
            font = bridge.memdump(symbols['font8x8'],2048)
            segment = next(s for s in foreign['segments'] if
                           s['address'] <= symbols['font8x8'] < s['address']+len(s['bytes']))
            offset = symbols['font8x8']-segment['address']
            expected_font = bytes(segment['bytes'][offset:offset+2048])
            require(len(expected_font)==2048 and font==expected_font,'Linked font bytes changed')
            report['font_sha256'] = hashlib.sha256(expected_font).hexdigest()
            expected = 0
            for value in font:
                expected = ((expected << 1) ^ (expected >> 31) ^ value) & 0xffffffff
            require(read('font_checksum',4)==expected,'Upper-bank font access changed')
            for slot in (0,6,7):
                dp = memory['task_pools'][slot]['dp']
                require(bridge.memdump(dp+20,108)==pattern(slot)[20:],'Unused C DP changed')
                if slot==0:
                    require(bridge.memdump(dp+8,8)==pattern(slot)[8:16],'C callee-preserved registers changed')
            require(bridge.memdump(adapter.KERNEL_DP,128)==pattern(4),'Kernel lower DP changed')
            require(runtime['created']==2 and runtime['os_calls']==0,'Unexpected worker or ROM call')
            require(runtime['root_task'][16:20]==[255,255,0,0],'Root signal leaked')
            report['stack_usage'] = stack_usage(bridge,memory)
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'Stack floor reached')
            require(bridge.memdump(0x8000,4096)==sentinel,'Aperture RAM changed')
            require(bridge.memdump(0x22f,3)==saved['display'],'OS presentation changed')
            require(bridge.memdump(0xd65e,2)==saved['memac'] and bridge.memdump(0xd653,2)==bytes(2),
                    'VBXE mapping/blitter/IRQ changed')
            clean_ownership(bridge,program,program['output'])
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'G1 {mode}: GEM entry/layout, recording device, peer and cleanup passed')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mode',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path)
    args = parser.parse_args()
    run(args.output or ROOT/'build/gem-vdi'/('g1-'+args.mode),args.mode)
