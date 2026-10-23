#!/usr/bin/env python3
"""Compare actual QED runtime outputs from two empty-output, clean-source builds."""
import argparse
import json
import subprocess
import sys
from pathlib import Path

from native_program import require, sha256
from package_demo import GEM_NOTICES, CALCULATOR_NOTICES, G4BENCH_NOTICES, QED_NOTICES

RUNTIME=('program.xex','of816/Exec-of816.xex','system.atr','work.atr','README.md','exec816-demo.zip',
         'of816/altirraos-816.rom','of816/ALTIRRAOS-LICENSE.txt','of816/OF816-LICENSE.txt',
         'qed-production/program.app','qed-production/inputs/resource/QED.RSC',
         *GEM_NOTICES,*CALCULATOR_NOTICES,*G4BENCH_NOTICES,*QED_NOTICES)


def check(checkout,first,second,prerequisites,second_checkout=None):
    checkouts=[checkout.resolve(),(second_checkout or checkout).resolve()]
    first,second=first.resolve(),second.resolve()
    revisions=[]
    for source in checkouts:
        revisions.append(subprocess.check_output(['git','-C',str(source),'rev-parse','HEAD'],text=True).strip())
        require(not subprocess.check_output(['git','-C',str(source),'status','--porcelain']),
                'Reproduction source checkout is not clean: '+str(source))
    require(revisions[0]==revisions[1],'Reproduction source revisions differ')
    revision=revisions[0]
    require(first!=second and first.is_dir() and second.is_dir(),'Use two separate completed builds')
    files={}
    for checkout,directory in zip(checkouts,(first,second)):
        demo=json.loads((directory/'demo-manifest.json').read_text())
        require(demo['kernel']['exec_build']['revision']==revision and not demo['kernel']['exec_build']['dirty'],
                'Build does not identify the clean frozen source revision')
        # The validator runs in the source tree it audits, including generated
        # provider paths relative to that tree. No executable artifact is imported.
        script=('import sys,json;from pathlib import Path;sys.path.insert(0,"tools");'
                'from qed_demo import verify;p=Path(sys.argv[1]);'
                'verify(json.loads((p/"demo-manifest.json").read_text()),p)')
        subprocess.run([sys.executable,'-c',script,str(directory)],cwd=checkout,check=True)
        current={name:sha256(directory/name) for name in RUNTIME}
        if files:require(current==files,'QED runtime builds differ: '+', '.join(n for n in files if files[n]!=current[n]))
        files=current
    return dict(schema_version=1,status='pass',tier='development',qualification=False,
        clean_checkout=True,source_revision=revision,checkouts=list(map(str,checkouts)),
        builds=[str(first),str(second)],runtime_files=files,zip_sha256=files['exec816-demo.zip'],
        prerequisites=dict(path=str(prerequisites),sha256=sha256(prerequisites)),
        scope='Byte-for-byte runtime reproducibility; delivery grants and final candidate execution are separate',
        bank_zero_delta=dict(fixed=0,per_public_task=0,private_idle=0))

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkout',type=Path,required=True);p.add_argument('--first',type=Path,required=True)
    p.add_argument('--second-checkout',type=Path)
    p.add_argument('--second',type=Path,required=True);p.add_argument('--prerequisites',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();a.output.write_text(json.dumps(check(a.checkout,a.first,a.second,a.prerequisites,a.second_checkout),indent=2)+'\n')
