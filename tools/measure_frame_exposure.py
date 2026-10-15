#!/usr/bin/env python3
"""Focused cold-frame/desktop-exposure observations on an exact demo ZIP."""
import argparse,json,os,statistics,struct,zipfile
from collections import Counter
from pathlib import Path
from test_demo import run
import window_response_trace as response_trace
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from colour_desktop_model import FIELDS as D
from browser_model import FIELDS as F
from generate_desktop import layout
from generate_layers import layout as layer_layout
from native_program import require,sha256
from sio_transaction_trace import BASE_HZ,read_events


class Frames:
    def __init__(self,count,baseline,open_only=False):
        self.count,self.baseline=count,baseline
        self.open_only=open_only
        self.samples=[]

    def exercise(self,s):
        b=s.b;out=s.p['output'];rec=layout();wf=rec['Window']['fields'];sf=rec['Service']['fields']
        lr=layer_layout();lf=lr['Layer']['fields'];df=lr['Damage']['fields']
        def at(m,n):
            return next(d['address'] for d in s.p['image']['data'] if '_'+m+'_'+n.upper()+'_' in d['name'])
        def move(x,y):
            pos=[s.number(at('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,pos,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%
                         (at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(100)
        menus=Menus(s,click,move);s.saved['desktop_menu']={}
        scene=menus.service+sf['scene']
        def window(title):
            for i in range(6):
                w=menus.service+sf['windows']+i*rec['Window']['size']
                if not s.number(w+wf['id'],4):continue
                if b.memdump(w+wf['title'],65).split(b'\0')[0].decode()!=title:continue
                for j in range(9):
                    p=scene+lr['Scene']['fields']['items']+j*lr['Layer']['size']
                    if s.number(p+lf['id'],4)==s.number(w+wf['layer'],4):
                        return w,p,rect(p+lf['bounds'])
            raise RuntimeError('Missing '+title)
        def rect(a):return list(struct.unpack('<4h',b.memdump(a,8)))
        desk=next(a for a in instances(b,s.p,out/'bitmap-console') if a['name']=='desktop')['symbols']['GEMDesk']
        desktop_id=s.number(at('DESKSTATE','desktopLayer'),4)
        dl=next(scene+lr['Scene']['fields']['items']+i*lr['Layer']['size'] for i in range(9)
                if s.number(scene+lr['Scene']['fields']['items']+i*lr['Layer']['size'],4)==desktop_id)
        def capture():
            p=out/'frame-exposure.bgra';f=b.rawscreen(str(p));raw=p.read_bytes()
            return [raw[y*f.stride+64:y*f.stride+2624] for y in range(240)]
        def crop(raw,area,mask=False):
            l,t,r,bt=area;rows=[bytearray(raw[y][l*4:r*4]) for y in range(t,bt)]
            if mask:
                # The physical New Window click leaves the pointer at 304,28.
                for y in range(max(t,24),min(bt,48)):
                    a,z=max(l,300),min(r,328)
                    if a<z:rows[y-t][(a-l)*4:(z-l)*4]=bytes((z-a)*4)
            return b''.join(rows)
        def elapsed(start):return ((b.eval_expr('@clk')-start)&0xffffffff)*1000/BASE_HZ
        def begin():
            b.profile_start();start=b.eval_expr('@clk')&0xffffffff
            b._cmd_ok('MOUSE AT 2000 0 0 1');b._cmd_ok('MOUSE AT 90000 0 0 0')
            return start
        def save(row):
            b.profile_stop();self.samples.append(row)
            (out/'frame-exposure-samples.json').write_text(json.dumps(self.samples,indent=2)+'\n')
            print(row['action'],{k:v for k,v in row.items() if k!='trace'},flush=True)
        def close(name):
            _,_,bounds=window('SYS:');move(bounds[0]+6,bounds[1]+5)
            before=capture();icon=crop(before,(0,11,96,230));changes=0;rows=[];previous=None
            paints=s.number(desk+D['paints'],4);start=begin();settled=None
            for i in range(100):
                s.frames(1)
                raw=capture()
                if crop(raw,(0,11,96,230))!=icon:changes+=1
                n=s.number(dl+lf['damage']+df['count'],2)
                row=dict(damage=[rect(dl+lf['damage']+df['rects']+k*8) for k in range(n)],
                         message=list(struct.unpack('<8h',b.memdump(desk+D['message'],16))),
                         paints=s.number(desk+D['paints'],4))
                if row!=previous:rows.append(dict(frame=i,**row));previous=row
                if row['paints']>paints and settled is None:settled=elapsed(start)
            require(settled is not None,'Close did not complete desktop exposure')
            result=dict(action=name,start=start,end=b.eval_expr('@clk')&0xffffffff,
                        window_ms=settled,bounds=bounds,icon_changed_frames=changes,trace=rows)
            if not self.baseline and bounds[0]>=96:
                require(changes==0,'Unrelated icon pixels changed')
                redraws=[r['message'] for r in rows if r['message'][0]==20 and r['paints']>=paints]
                require(any(m[4:8]==[bounds[0],bounds[1],bounds[2]-bounds[0],bounds[3]-bounds[1]] for m in redraws),
                        'Close did not deliver the exact exposure')
                require(not any(r['damage'] and any(a[0]<96 for a in r['damage']) for r in rows),
                        'Desktop damage reaches unrelated icons')
            save(result);s.frames(80)

        # Only the desktop is exposed on close, forcing the uncached path.
        menus.select('Shell');_,_,(l,t,r,bt)=window('Shell');click(r-8,t+5)
        menus.select('SYS:');move(632,232);s.frames(100)
        _,_,bounds=window('SYS:');l,t,r,bt=bounds
        reference=capture()
        frame_areas=[(l,t,r,t+11),(l,bt-11,r,bt),(l,t+11,l+8,bt-11),(r-16,t+11,r,bt-11)]
        close('Close right warmup')
        for _ in range(self.count):
            click(296,8);move(304,28);start=begin();frame_ms=None;full_ms=None
            for i in range(240):
                s.frames(1);raw=capture()
                if frame_ms is None and all(crop(raw,a,True)==crop(reference,a,True) for a in frame_areas):
                    frame_ms=elapsed(start)
                if frame_ms is not None and crop(raw,bounds,True)==crop(reference,bounds,True):
                    full_ms=elapsed(start);break
            require(full_ms is not None,'New Window did not settle')
            changed=0
            for _ in range(80):
                s.frames(1)
                if crop(capture(),bounds,True)!=crop(reference,bounds,True):changed+=1
            folder=s.number(desk+D['active'],4)
            paints=s.number(folder+F['paints'],4)
            save(dict(action='New Window',start=start,end=b.eval_expr('@clk')&0xffffffff,
                      frame_ms=frame_ms,window_ms=full_ms,content_paints=paints,
                      changed_frames_after_complete=changed))
            if not self.baseline:
                require(paints==1,'New Window painted its contents more than once')
                require(changed==0,'New Window pixels changed after the first complete image')
            if self.open_only:break
            close('Close right')
        if self.open_only and not self.baseline:
            # Deferring the opening paint must not suppress an explicit refresh.
            menus.key('L',ctrl=True)
            for _ in range(100):
                if s.number(folder+F['paints'],4)>paints:break
                s.frames(1)
            s.frames(80)
            refreshed=s.number(folder+F['paints'],4)-paints
            require(refreshed==1,'Explicit Refresh did not paint once')
            require(crop(capture(),bounds,True)==crop(reference,bounds,True),
                    'Explicit Refresh did not restore the complete listing')
            (out/'new-window-checks.json').write_text(json.dumps(dict(
                initial_content_paints=paints,changed_frames_after_complete=changed,
                explicit_refresh_paints=refreshed),indent=2)+'\n')
        # A genuinely covered icon strip must still be restored.
        if not self.open_only:
            click(296,8);click(304,28)
            _,_,(l,t,r,bt)=window('SYS:');move(l+80,t+5)
            b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20);move(96,t+5)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(140)
            close('Close covering icons')
        move(632,232);s.frames(120);s.cells('frame-exposure-final')
        s.save_screen(out/'frame-exposure.png');s.save_screen(out/'boot-smoke.png')
        menus.select('Shell')
        for c in 'EXIT':s.press(c)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--count',type=int,default=3)
    p.add_argument('--baseline',action='store_true');p.add_argument('--analyze-only',action='store_true')
    p.add_argument('--open-only',action='store_true',help='One New Window and its settled pixels, then normal EXIT')
    p.add_argument('--bookkeeping',action='store_true',help='Passive presenter costs, empty reads and visibility rebuilds')
    a=p.parse_args();out=a.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    image=json.loads((out/'program.a816.json').read_text())
    names=['CONSOLEBITMAP_FRAME','CONSOLEBITMAP_COPYSTART']
    points={r['address']:n for r in image['routines'] for n in names if r['name'].startswith('M_'+n+'_')}
    foreign=json.loads((out/'bitmap-console/c-image.json').read_text())['symbols']
    points.update({foreign[n]:n for n in ('VbxeOwnerSubmit','VbxeOwnerFence','GemDrawingFrameBatch') if n in foreign})
    tracing=response_trace.setup(out,bookkeeping=True) if a.bookkeeping else response_trace.setup(out)
    if a.bookkeeping:
        (out/'bookkeeping-definition.json').write_text(json.dumps(tracing,indent=2)+'\n')
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in response_trace.pcs(tracing)))
    probe=Frames(a.count,a.baseline,a.open_only)
    if a.analyze_only:
        probe.samples=json.loads((out/'frame-exposure-samples.json').read_text())
        runtime=out/'frame-exposure-runtime.json'
        result=json.loads(runtime.read_text()) if runtime.exists() else {'runtime':None}
    else:
        result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
        (out/'frame-exposure-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    events=read_events(out/'emulator.log',kinds={'cpu'})
    for row in probe.samples:
        row['calls']=dict(Counter(points[int(e[4],16)] for tick,e in events if int(e[4],16) in points and
            (tick-row['start'])%(1<<32)<(row['end']-row['start'])%(1<<32)))
        if not a.baseline and row['action']=='New Window':
            # Files supplies its known path before the initial frame is drawn.
            require(row['calls'].get('CONSOLEBITMAP_FRAME')==4,
                    'Expected four cold frame batches without a later title repaint')
            require(row['calls'].get('GemDrawingFrameBatch')==2,'Expected two complete frame sides')
    response_trace.report(out,events,tracing,probe.samples,'frame-exposure')
    if a.bookkeeping and not a.baseline:
        costs=json.loads((out/'frame-exposure-bookkeeping.json').read_text())
        for row in costs['actions']:
            if row['action']=='New Window':
                require(row['prepared_open_rebuilds']==[1],
                        'Expected one visibility rebuild inside the prepared AES open')
    summary={}
    for name in sorted({r['action'] for r in probe.samples}):
        rows=[r for r in probe.samples if r['action']==name]
        summary[name]={field:dict(samples=[r[field] for r in rows],median=statistics.median(r[field] for r in rows),maximum=max(r[field] for r in rows))
                       for field in ('frame_ms','window_ms') if field in rows[0]}
    report=dict(tier='development',qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),
                baseline=a.baseline,sampling='Once per PAL frame; three samples do not estimate p95',
                samples=probe.samples,summary=summary,runtime=result['runtime'])
    (out/'frame-exposure-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':main()
