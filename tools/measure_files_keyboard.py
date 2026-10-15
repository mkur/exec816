#!/usr/bin/env python3
"""Focused Files key selection, unchanged summary and stationary pointer probe."""
import argparse,json,os,zipfile
from collections import Counter
from pathlib import Path
from browser_model import FIELDS as F,wait_listing
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_aes_server import ABI,layout,expected_layout
from native_program import require,sha256
from sio_transaction_trace import read_events
from test_demo import run
from test_gem_cursor import ARROW


class Keyboard:
    def __init__(self,baseline,preservation=False):
        self.baseline=baseline
        self.preservation=preservation
        self.samples=[]
        self.restorations=[]

    def exercise(self,s):
        b=s.b;out=s.p['output']
        symbols=json.loads((out/'bitmap-console/c-image.json').read_text())['symbols']
        def at(name,module='DESKINPUT'):
            return next(d['address'] for d in s.p['image']['data']
                        if '_'+module+'_'+name.upper()+'_' in d['name'])
        def position():return [s.number(at(n),2) for n in ('cursorX','cursorY')]
        def move(x,y):
            p=schedule(b,s.p,position(),(x,y));s.saved['pointer']=p
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%
                         (at('cursorX'),p[0],at('cursorY'),p[1]));s.frames(12)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(4)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(100)
        menus=Menus(s,click,move);s.saved['desktop_menu']={}
        desktop=next(a for a in instances(b,s.p,out/'bitmap-console') if a['name']=='desktop')
        desk=desktop['symbols']['GEMDesk']
        base=s.number(desk+D['active'],4)
        n=lambda name:s.number(base+F[name],2)
        menus.select('SYS:')
        if self.preservation:
            request=layout()['Request']['fields'];vf=layout()['WindowView']['fields']
            contexts=[s.number(symbols['contexts']+i*4,4) for i in range(ABI['constants']['CONTEXTS'])]
            context=next(c for c in contexts if c and s.number(c+request['owner'],3)==desktop['task'])
            views=context+dict(expected_layout())['C context views']
            view=next(v for i in range(ABI['constants']['WINDOWS'])
                      if (v:=s.number(views+i*4,4)) and s.number(v+vf['handle'],2)==s.number(base+4,2))
        x,y,w,h=[s.number(base+F['work']+i*2,2) for i in range(4)]
        raw=b'';stride=0
        def screen(area):
            nonlocal raw,stride
            p=out/'keyboard.bgra';f=b.rawscreen(str(p));raw=p.read_bytes();stride=f.stride
            l,t,r,bt=area
            return b''.join(raw[yy*f.stride+(l+16)*4:yy*f.stride+(r+16)*4]
                            for yy in range(t,bt))
        def pointer_ink(p):
            return b''.join(raw[(p[1]+yy)*stride+(p[0]+xx+16)*4:
                               (p[1]+yy)*stride+(p[0]+xx+16)*4+4]
                           for yy,line in enumerate(ARROW) for xx,char in enumerate(line)
                           if char!='.' and p[0]+xx<640 and p[1]+yy<240)
        summary=(x+8,y,x+136,y+12)
        def restored_selection(name):
            p=position();final=screen((x,y,x+w,y+h))
            def counts():
                return dict(paints=s.number(base+F['paints'],4),**{
                    k:s.number(at(k,'DESKCACHE'),4) for k in ('captures','patches','restores')})
            before=counts()
            menus.select('Shell');menus.select('SYS:');move(*p)
            after=counts();delta={k:after[k]-v for k,v in before.items()}
            self.restorations.append(dict(action=name,delta=delta))
            print('restored selection',self.restorations[-1],flush=True)
            require(screen((x,y,x+w,y+h))==final,'Cache restored stale selection pixels: '+name)
            if not self.baseline:
                require(delta['paints']==0,'Selection lost cache eligibility: '+name)
                require(delta['captures']==delta['patches']==0,'Exposure caused cache maintenance: '+name)
                require(delta['restores']>0,'Selection was not restored from cache: '+name)
        def arrow(key,shift=False):
            b._cmd_ok('KEY CTRL down')
            if shift:b._cmd_ok('KEY SHIFT down')
            s.frames(3);b._cmd_ok('KEY '+key+' down');s.frames(3)
            b._cmd_ok('KEY '+key+' up');b._cmd_ok('KEY ALL up')
            s.frames(100)
        def observe(name,key,selected):
            before=s.number(base+F['paints'],4)
            original=screen(summary);p=position();ink=pointer_ink(p)
            moved=hidden=changed=inkChanged=0
            b._cmd_ok('KEY CTRL down');s.frames(3)
            b.profile_start();start=b.eval_expr('@clk')&0xffffffff
            b._cmd_ok('KEY '+key+' down')
            for frame in range(80):
                s.frames(1)
                if frame==2:
                    b._cmd_ok('KEY '+key+' up');b._cmd_ok('KEY ALL up')
                moved+=position()!=p or [s.number(symbols[n],2) for n in ('cursorX','cursorY')]!=p
                hidden+=not s.number(symbols['cursorDrawn'],2)
                changed+=screen(summary)!=original
                inkChanged+=pointer_ink(p)!=ink
            end=b.eval_expr('@clk')&0xffffffff;b.profile_stop()
            require(n('selected')==selected and n('selectionCount')==1,'Wrong selection: '+name)
            require(b.memdump(base+F['status'],128).split(b'\0')[0]==b'1 selected','Wrong summary')
            require(position()==p and s.number(symbols['cursorDrawn'],2),'Pointer did not settle')
            row=dict(action=name,start=start,end=end,pointer=p,position_changed_frames=moved,
                     pointer_hidden_frames=hidden,summary_changed_frames=changed,
                     pointer_pixel_changed_frames=inkChanged,
                     paints=s.number(base+F['paints'],4)-before)
            self.samples.append(row)
            (out/'keyboard-samples.json').write_text(json.dumps(self.samples,indent=2)+'\n')
            print(row,flush=True)
            if self.preservation and name in ('icons-outside-pointer','list-summary-pointer'):
                if not self.baseline:
                    require(s.number(view+vf['pixelsReady'],1)==1,'Settled selection did not start with complete pixels')
                restored_selection(name)
            if not self.baseline:
                require(not changed,'Unchanged selection summary flickered: '+name)
                require(not moved,'Stationary pointer moved: '+name)
                # A normal full repaint is an independent check of the
                # incremental label/focus result, retaining the same selection.
                final=screen((x,y,x+w,y+h))
                menus.key('L',ctrl=True);wait_listing(s,base)
                require(screen((x,y,x+w,y+h))==final,
                        'Incremental selection differs from a complete repaint: '+name)
        move(x+w-40,y+1)
        arrow('ASTERISK');require(n('selected')==0,'Initial keyboard selection')
        observe('icons-summary-pointer','ASTERISK',1)
        move(x+44,y+20)
        observe('icons-cell-pointer','MINUS',0)
        move(632,232)
        observe('icons-outside-pointer','ASTERISK',1)
        click(216,8);click(224,27)
        require(not n('iconView'),'List menu did not select List')
        move(x+w-40,y+1)
        observe('list-summary-pointer','MINUS',0)
        if not self.baseline:
            observe('list-first-item-noop','MINUS',0)
            require(self.samples[-1]['paints']==0,'Boundary key repainted unchanged selection')
        arrow('EQUALS',True)
        require(n('selectionCount')==2 and b'2 selected' in b.memdump(base+F['status'],128),
                'Changed selection count was not published')
        arrow('MINUS')
        require(n('selectionCount')==1 and b'1 selected' in b.memdump(base+F['status'],128),
                'Selection count did not return to one')
        if not self.baseline:
            click(216,8);click(224,16)
            require(n('iconView'),'Icons menu did not select Icons')
            menus.key('RETURN');wait_listing(s,base)
            path=b.memdump(base+F['path'],128).split(b'\0')[0]
            require(path==b'SYS:C','Did not enter C: '+repr(path))
            move(632,232)
            for _ in range(4):arrow('EQUALS')
            before=s.number(base+F['paints'],4);arrow('EQUALS')
            require(n('first')==n('columns'),'Keyboard did not scroll one icon row')
            require(s.number(base+F['paints'],4)==before+1,'Keyboard scroll added a selection repaint')
            final=screen((x,y,x+w,y+h));menus.key('L',ctrl=True);wait_listing(s,base)
            require(screen((x,y,x+w,y+h))==final,'Scrolled selection differs from full repaint')
        s.save_screen(out/'keyboard-selection.png');s.save_screen(out/'boot-smoke.png')
        menus.select('Shell')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--baseline',action='store_true')
    p.add_argument('--update-trace',action='store_true',help='Passive UPDATE and Task CPU boundaries')
    p.add_argument('--preservation',action='store_true',help='Switch to Shell and back after icon/list selection')
    a=p.parse_args();out=a.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    symbols=json.loads((out/'bitmap-console/c-image.json').read_text())['symbols']
    points={symbols[n]:n for n in ('cursor_hide','cursor_render','GemDrawingBorrow','GemDrawingCopyStart')}
    tracing=None
    if a.update_trace:
        import window_response_trace as response_trace
        tracing=response_trace.setup(out)
        points.update({pc:'trace' for pc in response_trace.pcs(tracing) if pc not in points})
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{p:x}' for p in points))
    probe=Keyboard(a.baseline,a.preservation)
    runtime=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
                integration=probe,profile_commands=False)
    events=read_events(out/'emulator.log',kinds={'cpu'})
    for row in probe.samples:
        calls=[points[int(e[4],16)] for tick,e in events
            if int(e[4],16) in points and
            (tick-row['start'])%(1<<32)<(row['end']-row['start'])%(1<<32)]
        row['calls']=dict(Counter(calls))
        if not a.baseline and row['action'].startswith('icons-'):
            source=None
            for name in calls:
                if name in ('GemDrawingBorrow','GemDrawingCopyStart'):source=name
                if name=='cursor_hide':
                    # Cache maintenance must exclude the screen pointer from
                    # its source. Unchanged object drawing must not hide it.
                    require(source=='GemDrawingCopyStart',
                            'Object draw erased a pointer outside changed labels/outlines: '+row['action'])
            if not row['calls'].get('GemDrawingCopyStart'):
                require(not row['pointer_pixel_changed_frames'],
                        'Stationary pointer pixels flickered: '+row['action'])
    if tracing:
        response_trace.report(out,events,tracing,probe.samples,'keyboard-update')
    (out/'keyboard-results.json').write_text(json.dumps(dict(status='pass',tier='development',
        qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),baseline=a.baseline,
        samples=probe.samples,restorations=probe.restorations,runtime=runtime),indent=2)+'\n')


if __name__=='__main__':main()
