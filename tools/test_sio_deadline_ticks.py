"""Emit the actual private timeout helper at every admitted quotient boundary."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,sha256,require
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out,mode):
    values={4041,4042,65535,65536,1000000,2000000}
    for n in range(1,496):values.update(v for v in (4041*n-1,4041*n,4041*n+1) if 4041<=v<=2000000)
    cases=[(0,1,248),(0,2,495),(0,3,248)]
    cases += [(v,2,(v+4040)//4041) for v in sorted(values)]
    raw=b''.join(struct.pack('<IHH',*c) for c in cases)
    p=build(t,ROOT/'tests/programs/sio_deadline_ticks.act',out,tasks=True,task_capacity=8,optimize=mode=='opt',image_data=[(0xd0000,raw)])
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            a=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_SIODEADLINETEST_COUNT_'));b.memload(a,len(cases).to_bytes(2,'little'))
        runtime,_=execute(b,p,before_run=before,timeout=600,frame_limit=30000);ownership(b,p,out)
        require(data(b,p['image'],'checks',True)==[len(cases)],'Incomplete rounding oracle')
    return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,cases=len(cases),oracle_sha256=__import__('hashlib').sha256(raw).hexdigest(),rounding='ceil(microseconds/4041), defaults 1s or stock 2s; independent integer host oracle')
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(ROOT/'build/actionc'),out,args.case)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('SIO deadline arithmetic passed',args.case,r['cases'],flush=True)
