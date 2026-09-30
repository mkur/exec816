#!/usr/bin/env python3
"""Hardcoded buffered SIO feasibility probe; no public device implementation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess

from os_boundary import ROOT, emulator, run_to, require, sha256
from native_program import verify_machine
from banked_test_memory import read as far_read

PIN = json.loads((ROOT/'toolchain/altirra-sio-device.json').read_text())
SOURCE = ROOT/'probes/sio-transactions'
BASE_HZ = 1773447.5


def build(output, *, divisor=0, phase=0, stall=0, scenario=0, vcount_phase=-1):
    require(0<=divisor<=255 and 0<=phase<=127 and 0<=stall<=1600
            and scenario in range(4) and -1<=vcount_phase<=155,'Invalid probe parameters')
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    definitions=dict(DIVISOR=divisor,PHASE=phase,STALL=stall,SCENARIO=scenario,VCOUNT_PHASE=vcount_phase)
    subprocess.run(['ca65','-I',str(SOURCE),*[arg for k,v in definitions.items()
        for arg in ('-D',f'{k}={v}')],'-l',str(output/'probe.lst'),'-o',str(output/'probe.o'),
        str(SOURCE/'probe.s')],check=True,timeout=30)
    subprocess.run(['ld65','-C',str(SOURCE/'probe.cfg'),'-o',str(output/'probe.bin'),
        '-Ln',str(output/'probe.lbl'),str(output/'probe.o')],check=True,timeout=30)
    labels={name.lstrip('.'):int(address,16) for _,address,name in
            (line.split() for line in (output/'probe.lbl').read_text().splitlines())}
    binary=(output/'probe.bin').read_bytes()
    xex=output/'probe.xex'
    xex.write_bytes(struct.pack('<HHH',0xffff,0x3000,0x3000+len(binary)-1)+binary+
                    struct.pack('<HHH',0x2e0,0x2e1,labels['start']))
    return dict(output=output,labels=labels,xex=xex,definitions=definitions,code_bytes=len(binary))


def disk_image(path):
    header=bytearray(16)
    struct.pack_into('<HHHH',header,0,0x296,720*128//16,128,0)
    body=bytes((i ^ (sector*15))&255 for sector in range(1,721) for i in range(128))
    path.write_bytes(header+body)
    return body[3*128:4*128]


def run(program,bridge_dir,rom,trace=False,disk_mode='fastest',press_key=False):
    out=program['output'];labels=program['labels']
    original_sector=disk_image(out/'test.atr')
    marker_names=['stream_start','native_irq','native_nmi','wait_call','wait_blocked',
                  'worker_wake','nmi_return','done','transaction_start','command_begin',
                  'command_end','write_begin','terminal_post','rx_service','tx_service',
                  'alarm_service','watchdog_service','critic_enter','critic_enter_next',
                  'critic_leave','critic_leave_next']
    env={'EXEC816_LATENCY_TRACE':'1','EXEC816_MASK_TRACE':'1',
         'EXEC816_LATENCY_PCS':','.join(f'{labels[n]:x}' for n in marker_names)}
    previous={k:os.environ.get(k) for k in env}
    observer=json.loads((ROOT/'toolchain/altirra-sio-observer.json').read_text())
    require(sha256(rom)==PIN['rom']['sha256'],'Unpinned ROM')
    require(sha256(bridge_dir/'AltirraBridgeServer')==
            (observer['binary_sha256'] if trace else PIN['emulator']['sha256']),'Unpinned probe emulator')
    result=dict(definitions=program['definitions'],xex_sha256=sha256(program['xex']),
                rom_sha256=sha256(rom),emulator_sha256=sha256(bridge_dir/'AltirraBridgeServer'),
                disk_mode=disk_mode,media_initial_sha256=sha256(out/'test.atr'))
    try:
        if trace:os.environ.update(env)
        else:
            for key in env:os.environ.pop(key,None)
        with emulator(bridge_dir,rom,out,pin=PIN) as bridge:
            for key,value in [('siopatch','off'),('burstio','false'),('randdelay','false'),
                              ('diskemu',disk_mode),('accuratedisk','true')]:
                bridge.config(key,value)
            bridge.boot(str(program['xex']))
            run_to(bridge,labels['start'],frame_limit=1800,timeout=60)
            result['machine']=verify_machine(bridge,rom,PIN)
            if trace:
                active=bridge.regs()
                result['verified_cpu']={key:active.get(key) for key in ('clock_multiplier','shadow_rom')}
                require(result['verified_cpu']==dict(clock_multiplier=8,shadow_rom=True),
                        'Incorrect active CPU/ROM speed')
            for key,value in {**PIN['configuration'],'diskemu':disk_mode}.items():
                require(result['machine'][key]==value,'Wrong configuration: '+key)
            bridge.mount(0,str(out/'test.atr'))
            result['pokey_before']=bridge.pokey()
            # A diagnostic snapshot is an explicit fixture input, not a claim
            # that guest software can read POKEY write-only register aliases.
            regs=result['pokey_before']
            values=[]
            for n in range(1,5):
                for name in (f'AUDF{n}',f'AUDC{n}'):
                    value=regs[name]
                    values.append(int(value.lstrip('$'),16) if isinstance(value,str) else value)
            value=regs['AUDCTL'];values.append(int(value.lstrip('$'),16) if isinstance(value,str) else value)
            result['snapshot']=values
            for n,value in enumerate(values):bridge.poke(labels['SAVED_POKEY']+n,value)
            vectors={str(a):bridge.memdump(a,n).hex() for a,n in ((0x256,9),(0x20a,10),(0x222,4))}
            old_critic=bridge.memdump(0x42,1)
            old_mask=bridge.memdump(0x10,1)
            old_skctl=bridge.memdump(0x232,1)
            if press_key:bridge.key('A')
            if trace:bridge.profile_start()
            bridge.bp_clear_all();bridge.bp_set(labels['done'])
            try:run_to(bridge,labels['done'],frame_limit=300,timeout=30)
            except Exception:
                (out/'failure.json').write_text(json.dumps(dict(regs=bridge.regs(),
                    state=bridge.memdump(0x2000,256).hex(),pokey=bridge.pokey(),
                    history=bridge.history(60)),indent=2)+'\n')
                raise
            if trace:bridge.profile_stop()
            state=bridge.memdump(0x2000,256)
            result['state_sha256']=hashlib.sha256(state).hexdigest()
            (out/'state.bin').write_bytes(state)
            result['state']={key:int.from_bytes(state[labels[key]-0x2000:labels[key]-0x2000+2],'little')
                for key in ('STATE','SENT','POSTS','WAITS','NMIS','BG_PROGRESS','WORK_S','BG_S',
                            'EMU_COUNT','TIMER_COUNT','WATCH_COUNT','RX_COUNT','DEFERRED_COUNT','ROM_IRQ_COUNT')}
            result['transactions']=[dict(error=state[80+i*4],actual=int.from_bytes(state[81+i*4:83+i*4],'little'))
                                    for i in range(result['state']['POSTS'])]
            require(result['state']['STATE']==0x600d,'Probe harness fault')
            for a,n in ((0x256,9),(0x20a,10),(0x222,4)):
                require(bridge.memdump(a,n).hex()==vectors[str(a)],'Vector restoration failed')
            for address,expected in ((0x42,old_critic),(0x10,old_mask),(0x232,old_skctl)):
                require(bridge.memdump(address,len(expected))==expected,'OS state restoration failed')
            for a,n in ((0x100,16),(0x21f0,288),(0x23f0,288),(0x41f0,16),
                        (0x4800,16),(0x49f0,16),(0x5000,16)):
                require(bridge.memdump(a,n)==b'\xa5'*n,f'Guard changed: {a:04x}')
            result['stack_written_extent']={}
            for name,address,size in (('worker',0x4200,1536),('background',0x4a00,1536),('os',0x110,224)):
                data=bridge.memdump(address,size)
                first=next((i for i,v in enumerate(data) if v!=0xa5),size)
                result['stack_written_extent'][name]=size-first
            result['buffers']={}
            for name in ('TX_BUFFER','RX_BUFFER','VERIFY_BUFFER'):
                data=far_read(bridge,labels[name]-32,256,out)
                result['buffers'][name]=data[32:160].hex()
                end=161 if name=='TX_BUFFER' else 160
                require(data[:32]==b'\xa5'*32 and data[end:]==b'\xa5'*(256-end),f'{name} guard changed')
            result['expected_original']=original_sector.hex()
            result['guards']='pass'
            result['pokey_after']=bridge.pokey()
            for name in [f'AUD{kind}{n}' for n in range(1,5) for kind in ('F','C')]+['AUDCTL','SKCTL','IRQEN']:
                require(result['pokey_after'][name]==result['pokey_before'][name],f'POKEY restoration: {name}')
            expected={0:[(0,4),(0,128),(0,128),(0,128)],1:[(1,0)],2:[(2,0)],3:[(0,0)]}
            actual=[(entry['error'],entry['actual']) for entry in result['transactions']]
            result['functional_pass']=actual==expected[program['definitions']['SCENARIO']]
            if program['definitions']['SCENARIO']==0:
                result['functional_pass'] &= result['buffers']['RX_BUFFER']==original_sector.hex()
                result['functional_pass'] &= result['buffers']['VERIFY_BUFFER']==result['buffers']['TX_BUFFER']
            require(result['state']['POSTS']==result['state']['WAITS']==len(actual),'Wrong notification count')
            require(result['state']['BG_PROGRESS'] and result['state']['NMIS'] and result['state']['DEFERRED_COUNT'],
                    'Background/VBI/deferred service did not progress')
            if not program['definitions']['STALL']:require(result['functional_pass'],'Unexpected SIO result/data')
            if press_key:require(result['state']['ROM_IRQ_COUNT']>0,'No unowned keyboard IRQ routed')
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        (out/'result.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'build/sio-transactions/smoke')
    p.add_argument('--bridge-dir',type=Path)
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--divisor',type=int,default=0)
    p.add_argument('--phase',type=int,default=0)
    p.add_argument('--vcount-phase',type=int,default=-1)
    p.add_argument('--stall',type=int,default=0)
    p.add_argument('--scenario',type=int,default=0)
    p.add_argument('--disk-mode',default='fastest')
    p.add_argument('--trace',action='store_true')
    p.add_argument('--key',action='store_true')
    a=p.parse_args()
    program=build(a.output.resolve(),divisor=a.divisor,phase=a.phase,stall=a.stall,scenario=a.scenario,
                  vcount_phase=a.vcount_phase)
    bridge=a.bridge_dir or ROOT/('build/altirra-sio-observer' if a.trace else 'build/altirra-irq-bridge')
    result=run(program,bridge.resolve(),a.rom.resolve(),a.trace,a.disk_mode,a.key)
    print(json.dumps({k:result[k] for k in ('state','transactions','guards')},indent=2))


if __name__=='__main__':main()
