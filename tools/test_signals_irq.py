#!/usr/bin/env python3
"""Measure real serial IRQ posting on the combined 8x / 4 MiB signal profile."""
import argparse
import json
import os
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,sha256,verify_machine
from os_boundary import emulator
from sio_latency import BASE_HZ
from test_cooperative import data

PIN=json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())


def events(path):
    result=[];tick=0
    for line in path.read_text().splitlines():
        if '[SIOPOC] ' not in line: continue
        fields=line.split('[SIOPOC] ',1)[1].split()
        value=int(fields[1])
        if fields[0]=='cpu':value+=round((tick-value)/(1<<32))*(1<<32)
        tick=value
        result.append((value+(int(fields[2])/int(fields[3]) if fields[0]=='cpu' else 0),fields))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-latency-bridge')
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/signals-tests/irq-timing')
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    args=p.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(args.compiler_dir)
    require(sha256(args.rom)==PIN['rom']['sha256'],'Wrong ROM')
    allowed=json.loads((ROOT/'docs/qualification/sio-latency.json').read_text())
    require(sha256(args.bridge_dir/'AltirraBridgeServer') in {c['emulator_sha256'] for c in allowed['cases'] if c.get('instrumented')},'Unqualified passive observer')
    program=build(toolchain,ROOT/'tests/programs/signals_queue.act',out/'program',tasks=True,
                  optimize=args.mode=='opt',manual_wake=True,image_data=[(a,bytes(96)) for a in (0x4ffe0,0x5ffe0,0x6ffe0)])
    names=('signal_route_begin','signal_route_return','native_irq','native_nmi')
    labels={n:program['labels'][n] for n in names}
    previous={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{v:x}' for v in labels.values())
    report=dict(schema_version=1,status='running',scope='Bounded IRQ post/route only; no continuous stream deadline claim',platform=PIN,build=program['build'],observer_sha256=sha256(args.bridge_dir/'AltirraBridgeServer'))
    try:
        with emulator(args.bridge_dir.resolve(),args.rom.resolve(),out,pin=PIN) as bridge:
            bridge.config('siopatch','off');bridge.config('burstio','false');bridge.config('randdelay','false')
            report['machine']=verify_machine(bridge,args.rom,PIN)
            at=next(d['address'] for d in program['image']['data'] if '_VARIANT_' in d['name'])
            def before(b):
                b.poke(at,2)
                b.profile_start()
            result,_=execute(bridge,program,before_run=before,timeout=240,frame_limit=2400)
            checks=data(bridge,program['image'],'checks',True)
            require(checks==[1]*15+[0]*17,'Queue FIFO fixture failed: '+str(checks))
            report['runtime']=result
        start=None;times=[]
        for t,e in events(out/'emulator.log'):
            if e[0]!='cpu':continue
            require(int(e[3])==8,'Wrong observed CPU clock')
            pc=int(e[4],16)
            if pc==labels['signal_route_begin']:start=t
            if pc==labels['signal_route_return'] and start is not None:
                if int(e[11],16)&1:times.append((t-start)/BASE_HZ*1e6)
                start=None
        require(len(times)>=3,'Too few native post observations')
        report['post_and_route_us']=dict(count=len(times),min=min(times),max=max(times),values=times)
        report['status']='pass'
        print('IRQ post + route maximum: '+str(max(times))+' us')
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value
        # Raw emulator logs contain local bridge credentials; never commit them.
        report['trace_sha256']=sha256(out/'emulator.log') if (out/'emulator.log').exists() else None
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
