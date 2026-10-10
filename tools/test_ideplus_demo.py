"""OF816 autoboot and a small command scope on the optional IDE demo."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from test_demo import run

COMMANDS=['DEVICES','MOUNT','DIR IDE:','IDE:C/HELLO','HEAD IDE:STORY.TXT LINES 2','COPY IDE:STORY.TXT WORK:IDE.TXT','CMP IDE:STORY.TXT WORK:IDE.TXT']

def check(command,screen):
    expected={'DEVICES':b'ideplus.device','MOUNT':b'IDE','DIR IDE:':b'STORY','IDE:C/HELLO':b'Hello from disk!','HEAD IDE:STORY.TXT LINES 2':b'Exec816'}
    if command in expected:require(expected[command] in screen,'Missing IDE command result: '+command)

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,default=ROOT/'build/development/ideplus-demo');a.add_argument('--distribution-root',type=Path)
    v=a.parse_args();result=run(v.bundle.resolve(),boot_smoke=True,measurement_commands=COMMANDS,profile_commands=False,measurement_validate=check,distribution_root=v.distribution_root)
    result['scope']='Development: packaged OF816 autoboot, IDE diagnostics/directory/command load/read, COPY to SIO WORK, CMP and guarded EXIT'
    (v.bundle/'ideplus-demo-results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Packaged IDE demo commands passed',flush=True)
