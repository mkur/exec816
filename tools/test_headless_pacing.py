#!/usr/bin/env python3
"""Same native image and 50-tick sleep on original/paced shell test servers."""
import argparse,json,time
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(t,out):
    out.mkdir(parents=True,exist_ok=True)
    p=build(t,ROOT/'tests/programs/headless_pacing.act',out,optimize=False,tasks=True,task_capacity=8,console=False,dos_mounts=[])
    cases=[]
    for name,bridge,pinfile in [('original','shell-console-bridge','altirra-shell-console.json'),('paced','shell-paced-bridge','altirra-shell-paced.json')]:
        target=out/name;target.mkdir(exist_ok=True);pin=json.loads((ROOT/'toolchain'/pinfile).read_text())
        require(sha256(ROOT/'build'/bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned pacing binary')
        with emulator(ROOT/'build'/bridge,ROOT/'build/firmware/altirraos-816.rom',target,pin=pin)as b:
            require(sha256(p['xex'])==p['build']['xex_sha256'],'Pacing image changed between executions')
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin);start=time.monotonic()
            rt,_=execute(b,p,timeout=90,frame_limit=3000)
            elapsed=time.monotonic()-start
            require(data(b,p['image'],'finished')==[1],'Missing completed sleep')
            require(50<=rt['native_nmi_count']<=54,'Guest timer count changed')
            ownership(b,p,out)
            cases.append(dict(name=name,pin=pin,machine=machine,runtime=rt,host_seconds=elapsed,xex_sha256=sha256(p['xex'])))
    require(cases[1]['host_seconds']<cases[0]['host_seconds'],'Pacing did not reduce host time')
    return dict(schema_version=1,status='pass',scope='Identical native XEX, fifty guest ticks, intact context/guards/ownership; host pacing only, no SIO throughput claim.',build=p['build'],cases=cases,
                inputs={s:sha256(ROOT/s)for s in ('tests/programs/headless_pacing.act','tools/test_headless_pacing.py','toolchain/patches/altirra-headless-frame-pacing.patch')})
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');p.add_argument('--output',type=Path,default=ROOT/'build/headless-pacing');a=p.parse_args()
    r=run(compiler(a.compiler_dir),a.output.resolve());(a.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Headless pacing passed',[(c['name'],c['host_seconds'],c['runtime']['native_nmi_count'])for c in r['cases']],flush=True)
