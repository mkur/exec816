"""Selected emitted kernel and loader regressions for the complete DOS stack."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,verify_machine
from os_boundary import emulator
from test_sio_device import PIN
from dos_client_regressions import run as core_case
from test_lists import named_case,preemptive_case
from test_preemptive import check as preemptive_check

def run(t,out,mode,names):
    cases=[]
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        for name in names:
            target=out/name;target.mkdir(parents=True,exist_ok=True);print('DOS regression',mode,name,flush=True)
            if name in ('heap','ports','io','signals','tasks'):r=core_case(b,t,target,mode=='opt',name)
            elif name=='lists-named':r=dict(observed=named_case(b,t,target,mode=='opt'))
            elif name=='lists-shared':r=dict(observed=preemptive_case(b,t,target,mode=='opt',True,True,timeout=240))
            elif name=='loader3':
                p=build(t,ROOT/'examples/preemptive.act',target,optimize=mode=='opt',banked=True,preemptive=True,kernel_bank=3)
                runtime,screen=execute(b,p,frame_limit=12000,timeout=240);r=dict(build=p['build'],runtime=runtime,observed=preemptive_check(b,p,'demo',runtime,screen))
            else:raise ValueError(name)
            r.update(status='pass',name=name);cases.append(r);(target/'results.json').write_text(json.dumps(r,indent=2)+'\n');(out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    return dict(status='pass',mode=mode,machine=machine,cases=cases)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--suite',default='heap,ports,io,signals,tasks,lists-named,lists-shared,loader3');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case,args.suite.split(','))
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS regressions passed',args.case,flush=True)
