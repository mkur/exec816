#!/usr/bin/env python3
"""Frame-sampled focus/menu restoration in an exact OF816 demo ZIP.

Observe the guest without patching it. Warm images provide timing references;
the independent scene oracle checks settled pixels. A conventional baseline
can use the same observer without the new preservation acceptance assertions.
"""
import argparse
import json
import os
import statistics
import zipfile
from collections import Counter
from pathlib import Path

from browser_model import FIELDS as F
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_layers import layout as layer_layout
from native_program import require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run
import window_response_trace as response_trace


class Probe:
    def __init__(self, count, conventional, contracts=True):
        self.count, self.conventional = count, conventional
        self.contracts = contracts
        self.samples = []

    def exercise(self, s):
        b = s.b
        out = s.p['output']
        def at(module, name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_'+module+'_'+name.upper()+'_' in d['name'])
        def move(x, y):
            old = [s.number(at('DESKINPUT', n), 2) for n in ('cursorX', 'cursorY')]
            pos = schedule(b, s.p, old, (x, y)); s.saved['pointer'] = pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                         (at('DESKINPUT', 'cursorX'), pos[0], at('DESKINPUT', 'cursorY'), pos[1]))
            s.frames(3)
        def click(x, y):
            move(x, y); b._cmd_ok('MOUSE AT 2000 0 0 1'); s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0'); s.frames(100)
        def key(name, ctrl=False, shift=False):
            start = b.eval_expr('@clk') & 0xffffffff
            if ctrl: b._cmd_ok('KEY CTRL down')
            if shift: b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down'); s.frames(1)
            b._cmd_ok('KEY '+name+' up')
            if shift: b._cmd_ok('KEY SHIFT up')
            if ctrl: b._cmd_ok('KEY CTRL up')
            return start
        s.saved['desktop_menu'] = {}
        menus = Menus(s, click, move)
        desk = next(a for a in instances(b, s.p, out/'bitmap-console')
                    if a['name']=='desktop')['symbols']['GEMDesk']
        folder = s.number(desk+D['folders'], 4)
        wf, sf = menus.types['Window']['fields'], menus.types['Service']['fields']
        ll = layer_layout(); lf = ll['Layer']['fields']
        scene = menus.service+sf['scene']
        def window(title):
            for i in range(6):
                w = menus.service+sf['windows']+i*menus.types['Window']['size']
                if not s.number(w+wf['id'], 4): continue
                if b.memdump(w+wf['title'], 65).split(b'\0')[0].decode('ascii')!=title: continue
                lid = s.number(w+wf['layer'], 4)
                for j in range(9):
                    layer = scene+ll['Scene']['fields']['items']+j*ll['Layer']['size']
                    if s.number(layer+lf['id'], 4)==lid:
                        bounds = [int.from_bytes(b.memdump(layer+lf['bounds']+k*2, 2),
                                  'little', signed=True) for k in range(4)]
                        return w, layer, bounds
            raise RuntimeError('Missing '+title)
        addresses = {n: at('DESKCACHE', n) for n in
                     ('captures', 'restores', 'capturedBytes', 'restoredBytes', 'patches', 'patchedBytes')}
        addresses.update({'menu_'+n: at('DESKMENUCACHE', n) for n in ('captures', 'restores')})
        addresses['files_paints'] = folder+F['paints']
        def counts(): return {n: s.number(a, 4) for n, a in addresses.items()}
        def elapsed(start): return ((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000
        def capture():
            path = out/'preservation.bgra'; frame = b.rawscreen(str(path)); raw = path.read_bytes()
            return [raw[y*frame.stride+64:y*frame.stride+2624] for y in range(240)]
        def crop(raw, rect, caret=None):
            l,t,r,bt = rect
            rows = [bytearray(raw[y][l*4:r*4]) for y in range(t,bt)]
            if caret:
                x,y = caret
                for yy in range(max(t,y), min(bt,y+8)):
                    left,right=max(l,x),min(r,x+8)
                    if left<right: rows[yy-t][(left-l)*4:(right-l)*4]=bytes((right-left)*4)
            return b''.join(rows)
        def observed(name, start, before, client, full, reference, caret=None):
            client_ms = None
            for _ in range(120):
                raw = capture()
                if client_ms is None and crop(raw,client,caret)==crop(reference,client,caret):
                    client_ms = elapsed(start)
                if client_ms is not None and crop(raw,full,caret)==crop(reference,full,caret): break
                s.frames(1)
            else:
                (out/'preservation-reference.bgra').write_bytes(b''.join(reference))
                (out/'preservation-actual.bgra').write_bytes(b''.join(raw))
                (out/'preservation-mismatch.json').write_text(json.dumps(dict(
                    name=name,client=client,full=full,caret=caret,client_ms=client_ms,
                    counts=counts()),indent=2)+'\n')
                raise RuntimeError('Unsettled pixels: '+name)
            settled = elapsed(start)
            b._cmd_ok('MOUSE AT 2000 0 0 0')
            s.frames(100)
            after = counts()
            sample = dict(action=name,start=start,end=b.eval_expr('@clk')&0xffffffff,
                          client_ms=client_ms,window_ms=settled,
                          delta={n:after[n]-v for n,v in before.items()})
            self.samples.append(sample)
            (out/'window-preservation-samples.json').write_text(json.dumps(self.samples,indent=2)+'\n')
            print(name,sample,flush=True)
            if not self.conventional:
                require(sample['delta']['files_paints']==0,'Unchanged Files repainted: '+name)
                require(sample['delta']['patches']==0 and sample['delta']['captures']==0,
                        'Exposure caused client cache maintenance: '+name)
            return sample

        if self.count==0:
            menus.select('SYS:')
        else:
            # Same arrangement as the earlier diagnostic: both titles exposed.
            menus.select('Shell'); _,_,(l,t,r,bt)=window('Shell')
            move(l+80,t+5);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
            move(144,69);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(160)
            reference = {}; areas = {}; carets = {}
            model = s.saved['top']
            for title in ('Shell','SYS:'):
                menus.select(title);_,_,bounds=window(title);l,t,r,bt=bounds
                move(l+55,t+5);s.frames(100)
                # Shell's current fixed terminal origin; Files uses ordinary work geometry.
                client = (l+8, ((t+11+7)//8)*8, r-8, ((t+11+7)//8)*8+160) if title=='Shell' else (l+8,t+11,r-16,bt-11)
                caret = None
                if title=='Shell':
                    cursor=s.number(model+54,2)+s.number(model+10,2)
                    caret=(client[0]+(cursor%64)*8,client[1]+(cursor//64)*8)
                areas[title]=(client,bounds);carets[title]=caret
                reference[title]=capture()
                s.cells('preservation-reference-'+title.replace(':',''))
            for _ in range(self.count):
                for title in ('Shell','SYS:'):
                    _,_,(l,t,r,bt)=window(title);move(l+55,t+5);s.frames(20)
                    before=counts();b.profile_start();start=b.eval_expr('@clk')&0xffffffff
                    # Release the title before requiring settled frame/menu pixels;
                    # holding it leaves the native move outline active.
                    b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(2)
                    b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(1)
                    row=observed(title,start,before,*areas[title],reference[title],carets[title])
                    b.profile_stop()
                    if not self.conventional and title=='SYS:':
                        require(row['delta']['restores']==1,'SYS: client was not restored in one copy')
            before=counts();_,_,(l,t,r,bt)=window('SYS:');click(l+55,t+5)
            require(counts()==before,'Clicking an already focused title did work')

            # Keyboard keeps the pointer away from both menu footprints.
            move(632,232);s.frames(100);menu_area=(128,0,640,208)
            menu_refs=[]
            for name,args in [('File',('ESC',True,True)),('View',('ASTERISK',True)),('Dismiss',('ESC',))]:
                key(*args);s.frames(100);menu_refs.append(capture())
            for i in range(self.count+1 if self.count else 0):
                for (name,args),ref in zip([('File',('ESC',True,True)),('View',('ASTERISK',True)),('Dismiss',('ESC',))],menu_refs):
                    before=counts();b.profile_start();start=key(*args)
                    observed(('Cold '+name) if i==0 else name,start,before,menu_area,menu_area,ref)
                    b.profile_stop()
            s.cells('preservation-final');s.save_screen(out/'window-preservation.png')
            s.save_screen(out/'boot-smoke.png')
        if not self.conventional and self.contracts:
            from browser_model import select,wait_listing
            # Shared tree state must follow the active folder, not the last
            # state cached by that folder before a different owner used it.
            click(296,8);click(304,28)
            second=s.number(desk+D['active'],4)
            require(second and second!=folder,'New Window did not create a second folder')
            select(s,second,'C',click);menus.key('RETURN');wait_listing(s,second)
            require(b.memdump(second+F['path'],128).split(b'\0')[0]==b'SYS:C','Subdirectory path')
            window('SYS:C')
            menus.key('ESC');wait_listing(s,second)
            require(b.memdump(second+F['path'],128).split(b'\0')[0]==b'SYS:','Parent path')
            select(s,second,'C',click);menus.key('RETURN');wait_listing(s,second)
            click(216,8);click(224,27);wait_listing(s,second)
            require(s.number(second+F['iconView'],2)==0,'Second folder did not select List')
            select(s,second,'ASSIGN',click)
            tree=s.number(second+F['applicationMenu'],4)
            def bits(item):return s.number(tree+item*24+10,2)
            def root():
                row=next(i for i,w in enumerate(menus.windows()) if w['title']=='SYS:')
                click(600,8);click(472,16+row*11)
            menus.select('Shell');menus.select('SYS:C')
            require(bits(16)&4 and not bits(15)&4 and not bits(6)&8,
                    'Selected List folder menu state lost on return')
            root()
            require(bits(15)&4 and not bits(16)&4 and bits(6)&8,
                    'Root icon folder inherited another folder menu state')
            # Refresh publishes the service revision after this settled boundary.
            revision=at('DESKAPPMENU','revision')
            before=s.number(revision,4)
            menus.select('Shell');root()
            require(s.number(revision,4)==before,'Unchanged root activation changed menu revision')
            (out/'response-contract.json').write_text(json.dumps(dict(
                two_folders=True,different_view_and_selection=True,navigation=True,
                unchanged_activation_revision=before),indent=2)+'\n')
        menus.select('Shell')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--count',type=int,default=2)
    p.add_argument('--conventional',action='store_true',help='Observe an older baseline without preservation assertions')
    p.add_argument('--analyze-only',action='store_true',help='Analyze already captured passive samples without executing the guest')
    p.add_argument('--baseline',action='store_true',help='Skip new shared-menu/title contract checks for the frozen baseline')
    a=p.parse_args();out=a.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    image=json.loads((out/'program.a816.json').read_text())
    names=('CONSOLEBITMAP_COPYSTART','CONSOLEBITMAP_FRAME')
    points={r['address']:name for r in image['routines'] for name in names
            if r['name'].startswith('M_'+name+'_')}
    foreign=json.loads((out/'bitmap-console/c-image.json').read_text())['symbols']
    if 'GemDrawingFrameBatch' in foreign:
        points[foreign['GemDrawingFrameBatch']]='GemDrawingFrameBatch'
    tracing=response_trace.setup(out)
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in response_trace.pcs(tracing)))
    probe=Probe(a.count,a.conventional,not a.baseline)
    if a.analyze_only:
        probe.samples=json.loads((out/'window-preservation-samples.json').read_text())
        runtime=out/'window-preservation-runtime.json'
        result=json.loads(runtime.read_text()) if runtime.exists() else {'runtime':None}
    else:
        result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
        (out/'window-preservation-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    events=read_events(out/'emulator.log',kinds={'cpu'}) if probe.samples else []
    for sample in probe.samples:
        sample['calls']=dict(Counter(points[int(e[4],16)] for tick,e in events
            if (tick-sample['start'])%(1<<32)<(sample['end']-sample['start'])%(1<<32) and int(e[4],16) in points))
    if not a.conventional:
        for sample in probe.samples:
            if sample['action']=='SYS:':
                # The outgoing Shell also repaints its visible title pieces.
                require(sample['calls'].get('GemDrawingFrameBatch',0)==0,
                        'Warm SYS: reconstructed frame sides')
                require(sample['delta']['restoredBytes']==462*185//2,
                        'Warm SYS: did not restore exactly the body below its title')
    if probe.samples:
        response_trace.report(out,events,tracing,probe.samples,'window-preservation')
    summary={}
    for name in sorted({s['action'] for s in probe.samples}):
        rows=[s for s in probe.samples if s['action']==name]
        summary[name]={field:dict(samples=[r[field] for r in rows],median=statistics.median(r[field] for r in rows),maximum=max(r[field] for r in rows)) for field in ('client_ms','window_ms')}
    report=dict(tier='development',qualification=False,sampling='Once per PAL frame; guest clock from physical stimulus scheduling, caret cell excluded; a few samples are not a p95 distribution',
                zip_sha256=sha256(out/'exec816-demo.zip'),conventional=a.conventional,
                samples=probe.samples,summary=summary,runtime=result['runtime'])
    (out/'window-preservation-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
