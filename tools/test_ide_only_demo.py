"""Extracted IDE-only cartridge boot and persistent WORK walkthrough."""
import argparse,json,zipfile
from pathlib import Path
from native_program import ROOT,require,sha256
from test_cartridge import run as cartridge_run

class Walkthrough:
    def __init__(self,full=False,copy_break=False):self.full=full;self.copy_break=copy_break
    def observe_boot(self,b,p):
        from serial_watch import install
        return install(b)
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
                    ('ECHO saved >WORK:NOTE.TXT',None),('ECHO again >>WORK:NOTE.TXT',None),
                    ('MAKEDIR WORK:SUB',None),('RENAME WORK:NOTE.TXT WORK:RENAMED.TXT',None),
                    ('COPY WORK:RENAMED.TXT WORK:SUB/NOTE.TXT',None),
                    ('CAT WORK:SUB/NOTE.TXT',b'saved'),('DELETE WORK:SUB/NOTE.TXT',None),
                    ('DELETE WORK:RENAMED.TXT',None),
                    ('DELETE WORK:SUB',None),('ECHO volatile >RAM:NOTE.TXT',None),
                    ('CAT RAM:NOTE.TXT',b'volatile')]:
                c.command(command,output)
            c.command('CD RAM:')
            c.command('CMP SYS:LONG.TXT WORK:COPY.TXT')
        if self.copy_break:
            c.command('RUN PRIMES')
            identity=c.number(c.at('job'))
            require(identity!=0,'Background PRIMES did not start')
            from prime_observer import state,symbols
            objects=symbols(c.far,c.p,c.p['output'],identity)
            # RUN returns before the child has opened and painted its pane.
            c.rendezvous(f'dw(${objects["candidate"][0]:x})>200')
            before=state(c.far,c.p,c.p['output'],identity)['progress']
            clock=c.b.eval_expr('@frame')
            timer=c.p['build']['memory']['timer_device_storage']['BASE']+4
            ticks=c.number(timer)
            previous=c.begin('COPY SYS:LONG.TXT WORK:BREAK.TXT')
            registry=c.p['build']['memory']['dos_storage']['SHARED']
            service=c.number(registry+68,3)
            # Current nine-slot Service: packet 42, committing 457.
            packet=f'dw(${service+42:x})+db(${service+44:x})*65536'
            c.rendezvous(f'(db(${service+457:x})=1)&(dw({packet}+22)=87)')
            c.frames(10)
            c.press('\x03');c.ready(previous);c.result(304)
            after=state(c.far,c.p,c.p['output'],identity)['progress']
            elapsed=c.number(timer)-ticks
            c.saved['integration']=dict(copy_break=True,peer_progress=[before,after],
                                      timer_ticks=elapsed,vbi_frames=c.b.eval_expr('@frame')-clock)
            (c.p['output']/'peer-copy.json').write_text(json.dumps(c.saved['integration'],indent=2)+'\n')
            require(after>before,'Peer did not advance during IDE copy')
            require(elapsed>0,'Timer clock did not advance during IDE copy')
            require(c.b.eval_expr('@frame')>clock,'VBI did not advance during IDE copy')
            c.command('HELLO',b'Hello from disk!')
            c.command('BREAK '+str(identity))
            c.frames(10)
            c.command('JOBS',b'finished')
        c.save_screen(c.p['output']/'boot-smoke.png')
        for character in 'EXIT':c.press(character)
        c.b._cmd_ok('KEY RETURN down');c.b.bp_clear_all()

def extract(bundle,destination=None):
    dest=destination or bundle/'extracted';dest.mkdir(parents=True,exist_ok=True)
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
    a.add_argument('--variant',choices=('old','new'),default='new')
    a.add_argument('--copy-break',action='store_true')
    a.add_argument('--full',action='store_true');v=a.parse_args();bundle=v.bundle.resolve()
    root=extract(bundle,bundle/('extracted-old' if v.variant=='old' else 'extracted'))
    destination=bundle.parent/(('old-' if v.variant=='old' else '')+('full-cart' if v.full else 'copy-break-cart' if v.copy_break else 'cart-smoke'))
    run=cartridge_run(bundle/'carts/cartridge-build/Exec-of816',bundle,ROOT,
            destination,v.variant,False,
            integration=Walkthrough(v.full,v.copy_break),distribution_root=root)
    if v.full:
        files=run['shell']['ide_work_files']
        source=bundle/'media/LONG.TXT';payload=source.read_bytes()
        require(len(payload)>16384,'COPY fixture is not larger than 16 KiB')
        require(files['COPY.TXT']==dict(bytes=len(payload),sha256=sha256(source)),
                'Persisted COPY contents differ')
        require(not any(name.startswith('SUB/') or name in ('RENAMED.TXT','NOTE.TXT') for name in files),
                'Temporary WORK entries survived deletion')
    if v.copy_break:
        source=bundle/'media/LONG.TXT';payload=source.read_bytes()
        files=run['shell']['ide_work_files']
        from filesystem_audit import Audit
        # The persisted image is reconstructed by test_demo before this check.
        from ideplus_media import filesystem_atr
        image=Path(run['shell']['ide_media']).read_bytes()
        mapping=json.loads((bundle/'demo-manifest.json').read_text())['ide_mapping']['partitions'][1]
        audit=Audit(filesystem_atr(image,mapping,(bundle/'work.atr').read_bytes()));audit.sdfs()
        prefix=audit.files['BREAK.TXT']
        require(0<len(prefix)<len(payload) and payload.startswith(prefix),
                'Cancelled COPY did not persist an exact confirmed prefix')
        (destination/'persistence.json').write_text(json.dumps(dict(
            status='pass',source_bytes=len(payload),cancelled_bytes=len(prefix),
            files=files),indent=2)+'\n')
    print('Extracted IDE-only cartridge passed',flush=True)
