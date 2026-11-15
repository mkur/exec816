#!/usr/bin/env python3
"""Native raw-COP overlay on one frozen semaphore diagnostic image."""
import argparse
import json
import shutil
from pathlib import Path
from native_program import ROOT, command, execute, read_build, require, sha256
from os_boundary import emulator
from test_banked import changed_image
from test_cooperative import data
from test_semaphores import PIN
from generate_semaphores import ABI as SEMAPHORES
from banked_test_memory import read


def run(base,out):
    out.mkdir(parents=True,exist_ok=True)
    shutil.copytree(base/'program',out/'program',dirs_exist_ok=True)
    p=read_build(out/'program')
    address=lambda n:next(d['address'] for d in p['image']['data'] if '_'+n+'_' in d['name'])
    definitions=dict(RESULT=0x04fff0,DEVICE=address('DEVICE'),VARIANT=address('VARIANT'),REACHED=address('REACHED'))
    entry=p['image']['entry']
    (out/'probe.cfg').write_text(f'MEMORY {{ RAM: start=${entry:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',out/'program',*[v for k,a in definitions.items() for v in ('-D',f'{k}={a}')],
        '-o',out/'probe.o',ROOT/'tests/programs/semaphores_context.s'])
    command(['ld65','-C',out/'probe.cfg','-o',out/'probe.bin',out/'probe.o'])
    blob=(out/'probe.bin').read_bytes()
    segment=next(s for s in p['image']['segments'] if s['address']==entry)
    require(len(blob)<=len(segment['bytes']),'Context overlay exceeds Main')
    original=list(segment['bytes'])
    segment['bytes'][:len(blob)]=blob
    changed_image(p)
    report=dict(tier='development',qualification=False,status='running',cases=[],
                overlay_sha256=sha256(out/'probe.bin'),base_image_sha256=p['build']['image_sha256'],pin=PIN)
    try:
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            for variant in (0,1,2,3,4,5,6,8):
                fault=variant not in (0,8)
                runtime,_=execute(b,p,expected_status=4 if fault else 0,
                    before_run=lambda b:b.poke(definitions['VARIANT'],variant),timer_irq=True,timeout=120)
                require(data(b,p['image'],'reached')==[0 if fault else 1],'Unexpected overlay return')
                result=read(b,definitions['RESULT'],20,out)
                if not fault:
                    word=lambda o:int.from_bytes(result[o:o+2],'little')
                    expected=(1,0,p['build']['task_storage']['PROFILE_TAG']|(definitions['DEVICE']>>16),
                              word(16),word(14)-1,0x12,9+(4 if variant==8 else 0))
                    require((word(0),word(2),word(4),word(6),word(8),result[10],result[11])==expected,
                            'Semaphore complete context: '+result.hex())
                    require(data(b,p['image'],'device',True)==[0]*6,'Released object remains owned')
                else:
                    words=data(b,p['image'],'device',True)
                    require(words[2]==(1 if variant==7 else 0) and words[3:]==[0,0,0],
                            'Rejected call changed semaphore')
                report['cases'].append(dict(variant=variant,status='pass',runtime=runtime,snapshot=result.hex()))
            # Genuine contention: original root owns, first admitted worker masks.
            segment['bytes']=original
            worker=next(r for r in p['image']['routines'] if r['name'].startswith('M_SEMAPHORES_BLOCKINGWORKER_'))
            target=next(s for s in p['image']['segments'] if s['address']==worker['address'])
            device=definitions['DEVICE']
            packet=bytes([0x78,0xa2])+int(device&65535).to_bytes(2,'little')+bytes([0xa0])+int(
                p['build']['task_storage']['PROFILE_TAG']|(device>>16)).to_bytes(2,'little')+bytes([0xa9,SEMAPHORES['services']['OBTAIN_SEMAPHORE'],0,0x02,0x50,0x6b])
            target['bytes'][:len(packet)]=packet
            changed_image(p)
            runtime,_=execute(b,p,expected_status=4,
                before_run=lambda b:b.poke(definitions['VARIANT'],11),timer_irq=True,timeout=120)
            words=data(b,p['image'],'device',True)
            require(words[2]==1 and words[3:]==[0,0,0],'Masked contention mutated queue')
            require(all(r[52:55]==[0,0,0] for r in runtime['task_records']),'Masked waiter was published')
            report['cases'].append(dict(variant='masked-contention',status='pass',runtime=runtime))
        report['status']='pass'
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed nine native semaphore context/admission cases')


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--from-build',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    run(a.from_build.resolve(),a.output.resolve())
