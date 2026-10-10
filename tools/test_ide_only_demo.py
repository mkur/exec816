"""Extracted IDE-only cartridge boot and persistent WORK walkthrough."""
import argparse,hashlib,json,zipfile
from pathlib import Path
from native_program import ROOT,require,sha256
from test_cartridge import run as cartridge_run

class Walkthrough:
    def __init__(self,full=False):self.full=full
    def exercise(self,c):
        screen=c.command('DEVICES',b'ideplus.device')
        require(b'sio.device' not in screen,'SIO advertised')
        mounts=c.command('MOUNT',b'ideplus.device/2')
        require(mounts.count(b'ideplus.device/1')==1 and mounts.count(b'ideplus.device/2')==1,'Duplicate/missing IDE mounts')
        c.command('C:HELLO',b'Hello from disk!')
        c.command('PATH',b'C:')
        c.command('ASSIGN',b'SYSTEM:C')
        if self.full:
            for command,output in [('COPY SYS:LONG.TXT WORK:COPY.TXT',None),
                    ('CMP SYS:LONG.TXT WORK:COPY.TXT',None),
                    ('ECHO saved >WORK:NOTE.TXT',None),('ECHO again >>WORK:NOTE.TXT',None),
                    ('MAKEDIR WORK:SUB',None),('RENAME WORK:NOTE.TXT WORK:SUB/NOTE.TXT',None),
                    ('CAT WORK:SUB/NOTE.TXT',b'saved'),('DELETE WORK:SUB/NOTE.TXT',None),
                    ('DELETE WORK:SUB',None),('ECHO volatile >RAM:NOTE.TXT',None),
                    ('CAT RAM:NOTE.TXT',b'volatile')]:
                c.command(command,output)
            c.command('CD RAM:')
            c.command('MOUNT WORK: REMOVE')
            c.command('MOUNT WORK:')
            c.command('CMP SYS:LONG.TXT WORK:COPY.TXT')
        c.save_screen(c.p['output']/'boot-smoke.png')
        for character in 'EXIT':c.press(character)
        c.b._cmd_ok('KEY RETURN down');c.b.bp_clear_all()

def extract(bundle):
    dest=bundle/'extracted';dest.mkdir(exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as z:
        require(all(n.startswith('exec816-demo/') and '..' not in Path(n).parts for n in z.namelist()),'Unsafe ZIP member')
        z.extractall(dest)
    root=dest/'exec816-demo'
    checks=(root/'SHA256SUMS').read_text().splitlines()
    for row in checks:
        digest,name=row.split('  ',1);require(sha256(root/name)==digest,'Extracted checksum mismatch')
    require(not any(p.suffix=='.atr' or p.name.endswith('.json') for p in root.rglob('*')),'Development file in ZIP')
    return root

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,default=ROOT/'build/development/ide-only/demo')
    a.add_argument('--full',action='store_true');v=a.parse_args();bundle=v.bundle.resolve();root=extract(bundle)
    run=cartridge_run(bundle/'carts/cartridge-build/Exec-of816',bundle,ROOT,
            bundle.parent/('full-cart' if v.full else 'cart-smoke'),'new',False,
            integration=Walkthrough(v.full),distribution_root=root)
    print('Extracted IDE-only cartridge passed',flush=True)
