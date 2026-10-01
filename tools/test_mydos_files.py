#!/usr/bin/env python3
"""Run bounded guest file operations with a sector-only fixture provider."""
import adapter_state as adapter
import argparse,json,shutil,time
from library_paths import read_source
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
from mydos_fixtures import Image
import mydos_file_cases

def symbol(p,name,module='MYDOSFILETEST'):
    matches=[d['address'] for d in p['image']['data'] if d['name'].startswith('M_'+module+'_') and '_'+name.upper()+'_' in d['name']]
    require(len(matches)==1,'Ambiguous diagnostic: '+module+'.'+name)
    return matches[0]

def serve(b,p,image):
    ready=symbol(p,'ready','BLOCKWIRE');sector=symbol(p,'sector','BLOCKWIRE');length=symbol(p,'length','BLOCKWIRE');staging=symbol(p,'staging','BLOCKWIRE')
    done=p['labels']['done'];condition=adapter.STOPPED
    b.bp_set(done,condition=condition)
    requests=[];deadline=time.monotonic()+600;initial_frame=b.eval_expr('@frame');b.resume()
    while time.monotonic()<deadline:
        status=b.peek16(adapter.STATE)
        if status!=65535:
            regs=b.regs()
            if int(regs['PC'].lstrip('$'),16)==done:break
        if b.peek(ready)[0]==1:
            b.pause()
            number=b.peek16(sector);size=b.peek16(length)
            phase=b.peek(symbol(p,'phase'))[0]
            payload=mydos_file_cases.sector(image,phase,number);require(len(payload)==size,'Guest chose wrong physical sector size')
            b.memload(staging,payload);requests.append(dict(phase=phase,sector=number))
            if phase==51 and number==mydos_file_cases.fault_sector(image):b.poke(symbol(p,'error','BLOCKWIRE'),4)
            if phase==52 and number==mydos_file_cases.fault_sector(image):b.poke16(symbol(p,'actual','BLOCKWIRE'),size-1)
            b.poke(ready,2);b.resume()
        require(len(requests)<=4096,'Unbounded metadata I/O')
        require(b.eval_expr('@frame')-initial_frame<=30000,'Parser frame deadline exceeded')
        time.sleep(0.005)
    b.pause();require(int(b.regs()['PC'].lstrip('$'),16)==done,'Parser did not complete')
    return requests

def run(t,out,optimize,size):
    out.mkdir(parents=True,exist_ok=True)
    shutil.copyfile(ROOT/'tests/fixtures/mydos/blockwire.act',out/'blockwire.act')
    image=Image((ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr').read_bytes())
    procedures,calls,paths,cases=mydos_file_cases.generated(size)
    text=read_source(ROOT/'tests/programs/mydos_files.act').replace('PROC Main()',procedures+'PROC Main()').replace('Setup()\n  Boundaries()\n  SeekChecks(0)\n  BadReads(0)\n  Cleanup()','Setup()\n  Boundaries()\n  SeekChecks(0)\n  BadReads(0) '+calls+' Cleanup()')
    source=out/'mydos_files.act';source.write_text(text)
    p=build(t,source,out,optimize=optimize,tasks=True,image_data=[(0xa0000,paths),(0xa1000,b''.join(image.sector(n)[:128] for n in range(361,369))),(0xaffd0,bytes([165])*32+bytes(70004)+bytes([165])*32)])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);requests=[]
        def before(b):
            b.poke16(symbol(p,'dataSize'),size);b.poke16(symbol(p,'sectorCount'),image.count)
            requests.extend(serve(b,p,image))
        try:runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=30000)
        except Exception:
            print('checks',data(b,p['image'],'checks',True),'phase',b.peek(symbol(p,'phase'))[0],flush=True);raise
        clean_ownership(b,p,out)
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True),sector_bytes=size,requests=requests,cases=cases,fixture_provider_sha256=sha256(out/'blockwire.act'),driver_sha256=sha256(ROOT/'tests/fixtures/mydos/driver.inc'),block_driver_sha256=sha256(ROOT/'tests/fixtures/block/driver.inc'),fixture_sha256=sha256(ROOT/f'tests/fixtures/mydos/mydos450-{size}.atr'))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--case',choices=('raw','opt'),required=True);p.add_argument('--size',type=int,choices=(128,256),required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,a.case=='opt',a.size)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('MyDOS files passed',a.case,a.size,flush=True)
