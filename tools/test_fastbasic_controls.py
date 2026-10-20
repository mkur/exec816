#!/usr/bin/env python3
"""Original integer compiler controls in pinned mini65's Atari OS simulator."""
import argparse
import json
from pathlib import Path
import shutil

from build_fastbasic import ROOT, PIN, command, prepare, sha256


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    _,source,_,_=prepare(ROOT/'build/fastbasic')
    cases=('arrays','cstring','diskio','err-loop-1','proc-line')
    controls=source/'build/exec-controls'
    controls.mkdir(parents=True,exist_ok=True)
    for name in cases:
        shutil.copyfile(source/f'testsuite/tests/{name}.bas',controls/(name+'.bas'))
        original=(source/f'testsuite/tests/{name}.chk').read_text()
        lines=original.replace('\r\n','\n').splitlines()
        mode='compile-error' if name.startswith('err-') else 'run'
        original='\n'.join('Test: '+mode+' int native' if line.startswith('Test:') else line
                           for line in lines)+'\n'
        (controls/(name+'.chk')).write_text(original)
    (source/'build/tests').mkdir(exist_ok=True)
    with (output/'controls.log').open('w') as log:
        command(['make','-j4','build/bin/fbtest','build/bin/fbci.xex'],source,log)
        command([source/'build/bin/fbtest',*[controls/(name+'.chk') for name in cases]],source,log)
    result=dict(status='pass',tier='development',qualification=False,
        scope='Unmodified integer compiler/runtime in mini65 Atari OS simulation; no physical Atari/SDX or Exec interrupt qualification',
        revision=PIN['revision'],cases=cases,
        compiler_sha256=sha256(source/'build/bin/fbci.xex'),
        harness_sha256=sha256(source/'build/bin/fbtest'))
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/fastbasic/controls')
    args=parser.parse_args()
    print(json.dumps(run(args.output.resolve()),indent=2))
