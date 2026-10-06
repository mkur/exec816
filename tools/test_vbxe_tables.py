#!/usr/bin/env python3
"""Raw/optimized emitted loads and ownership of the renderer table bank."""
import argparse
import json
from pathlib import Path
from calypsi_build import emit
from generate_vbxe_tables import generate
from library_paths import read_source
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from stack_budget import stack_usage


def run(out,mode):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    report=dict(tier='development',mode=mode,status='running')
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
        require(sha256(ROM)==PIN['rom']['sha256'],'Unpinned ROM')
        report['pin']=PIN
        report['tables']=generate(out/'gem-vbxe-tables.h')
        f=emit(out,[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/vbxe_tables.c'],
            [ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],[],optimize=mode=='opt')
        inc=out/'c-image.inc';inc.write_text(f'CONST C_MAIN=${f["symbols"]["main"]:x}\n')
        src=out/'launcher.act';src.write_text(read_source(ROOT/'tests/programs/gem_vdi_launcher.act',{'c-image.inc':inc}))
        p=build(compiler(ROOT/'build/actionc'),src,out/'program',optimize=mode=='opt',
                tasks=True,task_capacity=8,console=False,foreign_image=f)
        require(p['build']['memory']['profile']['code_origin']==0x100000,'Native code overlaps table bank')
        tables=next(s for s in f['segments'] if s['address']==0xf0000)
        require(not tables['writable'] and not tables['executable'],'Table permissions')
        require(len(tables['bytes'])==report['tables']['payload_bytes'],'Table payload/layout')
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            report['runtime'],_=execute(b,p,frame_limit=12000,timeout=180)
            ownership(b,p,p['output'])
            require(b.peek16(f['symbols']['completed'])==1 and b.peek16(f['symbols']['failures'])==0,'Target table/address assertion')
            # Read bank F as linear CPU RAM, after OS restoration.
            require(b.memdump(0xf0000,len(tables['bytes']))==bytes(tables['bytes']),'Loaded table bytes changed')
            report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(s['remaining_above_floor']>0 for s in report['stack_usage'].values()),'Stack floor')
        report.update(status='pass',build_sha256=sha256(out/'program/build.json'),
            xex_sha256=sha256(p['xex']),provenance=f['provenance'])
    except Exception as e:
        report.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Table loads passed',mode,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),required=True)
    args=a.parse_args();run(args.output,args.mode)
