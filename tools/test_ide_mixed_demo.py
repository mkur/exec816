"""Boot the mixed floppy/IDE demo and load a command from native IDE SYS data."""
import argparse,json,shutil,zipfile
from pathlib import Path
from native_program import ROOT,require,sha256
from test_demo import run

class Walkthrough:
    def exercise(self,c):
        screen=c.command('DEVICES',b'ideplus.device')
        require(b'sio.device' in screen,'Mixed demo omitted SIO')
        c.command('MOUNT',b'ideplus.device/2')
        c.command('IDE:C/HELLO',b'Hello from disk!')
        c.command('CAT IDE:README.TXT',b'Exec816 text shell')
        c.command('ECHO live >RAM:PROBE.TXT')
        c.command('CAT RAM:PROBE.TXT',b'live')
        c.save_screen(c.p['output']/'boot-smoke.png')
        for character in 'EXIT':c.press(character)
        c.b._cmd_ok('KEY RETURN down');c.b.bp_clear_all()

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,required=True);a.add_argument('--output',type=Path,required=True);v=a.parse_args()
    root=v.output/'extracted'
    with zipfile.ZipFile(v.bundle/'exec816-demo.zip') as z:
        require(all(n.startswith('exec816-demo/') and '..' not in Path(n).parts for n in z.namelist()),'Unsafe ZIP member')
        z.extractall(root)
    root=root/'exec816-demo'
    for row in (root/'SHA256SUMS').read_text().splitlines():
        digest,name=row.split('  ',1);require(sha256(root/name)==digest,'Extracted checksum mismatch')
    case=v.output/'demo';shutil.copytree(v.bundle,case,dirs_exist_ok=True)
    result=run(case,boot_smoke=True,distribution_root=root,integration=Walkthrough())
    (v.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Extracted mixed IDE demo passed',flush=True)
