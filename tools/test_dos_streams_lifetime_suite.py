#!/usr/bin/env python3
"""Slice 5: deterministic stream ownership plus existing device/FS lifetime gates."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,require
from test_dos_streams_lifetime import run as life
from dos_streams_recovery import run as recovery
from test_dos_streams import nil
from test_console_lifetime import run as console
from test_dos_lifetime import run as filesystem


def run(t,out,modes,only=None,reuse=None):
    results=[]
    for mode in modes:
        cases=[('lifetime-bank1',lambda p:life(t,p,mode)),
               ('lifetime-bank3',lambda p:life(t,p,mode,3,1)),
               ('console-only',lambda p:life(t,p,mode,1,3)),
               ('stream-removal-guard',lambda p:life(t,p,mode,1,2)),
               ('headless',lambda p:nil(t,p,mode)),
               ('serial-128',lambda p:recovery(t,p,mode,128)),
               ('serial-256',lambda p:recovery(t,p,mode,256)),
               ('direct-console-clean',lambda p:console(t,p,0,mode=='opt')),
               ('direct-console-guard',lambda p:console(t,p,2,mode=='opt')),
               ('filesystem-lifetime',lambda p:filesystem(t,p,mode)),
               ('filesystem-retry',lambda p:filesystem(t,p,mode,retry=True))]
        for name,action in cases:
            if only and name!=only:continue
            if reuse and (mode,name) in reuse:
                previous=reuse[mode,name]
                require(json.loads((ROOT/previous).read_text())['status']=='pass','Cannot reuse failed case')
                results.append(dict(mode=mode,name=name,result=previous))
                print('Reusing passing',mode,name,flush=True)
                continue
            print('Running',mode,name,flush=True)
            path=out/mode/name;path.mkdir(parents=True,exist_ok=True)
            result=dict(status='running')
            try:result=action(path)
            except Exception as e:result.update(status='fail',error=str(e));raise
            finally:(path/'results.json').write_text(json.dumps(result,indent=2)+'\n')
            require(result['status']=='pass','Failed '+name)
            results.append(dict(mode=mode,name=name,result=str(path.relative_to(ROOT)/'results.json')))
            (out/'cases.json').write_text(json.dumps(results,indent=2)+'\n')
    return dict(status='pass',suite='lifetime',cases=results)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'));a.add_argument('--only');a.add_argument('--output',type=Path,required=True);a.add_argument('--reuse',type=Path)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    require(not (out/'results.json').exists(),'Choose a fresh artifact path')
    reuse={(x['mode'],x['name']):x['result'] for x in json.loads(args.reuse.read_text())} if args.reuse else None
    try:r=run(compiler(args.compiler_dir),out,[args.case] if args.case else ['raw','opt'],args.only,reuse)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS streams lifetime suite passed',flush=True)
