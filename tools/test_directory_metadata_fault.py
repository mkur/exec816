#!/usr/bin/env python3
"""Actual directory-sector checksum error, unchanged FIB and successful retry."""
import argparse
import json
import os
import shutil
from pathlib import Path

from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    selector=out/'fault.txt';selector.write_text('none\n')
    os.environ['EXEC816_SIO_FAULT_FILE']=str(selector)
    pin=json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
    binary=ROOT/'build/altirra-sio-sector-faults'
    require(sha256(binary/'AltirraBridgeServer')==pin['fault_responder']['binary_sha256'],
            'Unpinned fault responder')
    media=out/'volume.atr'
    shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media)
    digest=sha256(media)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'memory.json';memory.write_text(json.dumps(profile)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),
            ROOT/'tests/programs/directory_metadata_fault.act',out,
            optimize=True,tasks=True,task_capacity=8,console_deferred=True,
            memory_profile=memory,
            dos_mounts=[dict(alias='D1',unit=56,sectors=720,sector_bytes=128,profile=1)])
    def at(name):
        return next(d['address'] for d in p['image']['data']
                    if '_DIRECTORYMETADATAFAULT_'+name.upper()+'_' in d['name'])
    inspected=dict(p['image'],data=[d for d in p['image']['data']
                                  if '_DIRECTORYMETADATAFAULT_' in d['name']])
    try:
        with emulator(binary,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
            b.config('diskemu','fastest');b.mount(7,str(media))
            def before(b):
                for phase,fault in ((1,'checksum'),(2,'none')):
                    b.bp_clear_all()
                    condition=f'db(${at("phase"):x})={phase}'
                    b.bp_set(p['labels']['native_nmi'],condition=condition)
                    run_to(b,p['labels']['native_nmi'],12000,240,condition)
                    selector.write_text(fault+'\n')
                    b.poke(at('gate'),1)
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            ownership(b,p,out)
            require(data(b,inspected,'phase')==[3],'Incomplete failed-query recovery')
            require(sha256(media)==digest,'Read-only media changed')
            result=dict(status='pass',tier='development',runtime=runtime,machine=machine,
                        build=p['build'],checks=data(b,inspected,'checks',True),
                        error=data(b,inspected,'error'),media_sha256=digest,
                        bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    finally:
        os.environ.pop('EXEC816_SIO_FAULT_FILE',None)
        selector.write_text('none\n')
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
