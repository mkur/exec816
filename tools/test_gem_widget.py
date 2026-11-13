#!/usr/bin/env python3
"""Run the three Widget/Counter cases in the actual packaged Exec desktop."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import zipfile
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from native_program import read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from shell_inspect import address
from stack_budget import stack_usage
from test_dos_stack import execute,ownership
from test_gem_acceptance import Session,bootstrap
from test_mouse_observe import BRIDGE,PIN
from widget_model import SIZE
from widget_observe import widget_state
from console_model import read_cells


class WidgetPair:
    interrupt_marker='native_nmi'

    def exercise(self,s):
        b=s.b;directory=s.directory;out=s.out
        cases=[]
        s.report['cases']=cases
        def move(x,y):
            ax,ay=[address(s.p['image'],name,'DESKINPUT') for name in ('cursorX','cursorY')]
            schedule(b,s.p,[s.number(ax,2),s.number(ay,2)],(x,y))
            s.rendezvous(f'(dw(${ax:x})={x})&(dw(${ay:x})={y})');s.frames(3)
        def edge(down,frames=20):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(frames)
        def click(x,y):move(x,y);edge(1);edge(0,60)
        def key(name):
            b._cmd_ok('KEY '+name+' down');s.frames(3)
            b._cmd_ok('KEY '+name+' up');s.frames(3)
        menus=Menus(s,click,move)
        def loaded(name):return [a for a in instances(b,s.p,directory) if a['name']==name]
        def find(name):
            for _ in range(100):
                rows=loaded(name)
                if rows:return rows[0]
                s.frames(10)
            s.command('JOBS')
            s.report['launch_diagnostic']=dict(name=name,windows=menus.windows(),
                cells=read_cells(s.far,s.source(s.index())).decode('latin1'),
                apps=[(a['name'],a['identity'],a['state']) for a in instances(b,s.p,directory)])
            b.screenshot(str(out/'launch-failure.png'))
            raise RuntimeError(name+' did not launch')
        def region(name,rect):
            x,y,w,h=rect
            path=out/(name+'.bgra');frame=b.rawscreen(str(path));raw=path.read_bytes()
            require((frame.width,frame.height)==(672,240),'Wrong Exec scanout dimensions')
            return b''.join(raw[row*frame.stride+(col+16)*4:row*frame.stride+(col+16)*4+3]
                            for row in range(y,y+h) for col in range(x,x+w))
        for mode in ('solo','silent','paint'):
            menus.select('Terminal')
            s.command('RUN SYS:C/PAIR.APP '+mode)
            widget=find('widget');base=widget['symbols']['GEMWidget']
            s.rendezvous(f'dw(${base+6:x})=1');s.frames(100)
            def state():return widget_state(b.memdump(base,SIZE),'little')
            pulse=find('pulse') if mode!='solo' else None
            def counter():
                at=pulse['symbols']['GEMCounter'];raw=b.memdump(at,46)
                return dict(count=int.from_bytes(raw[14:18],'little'),
                    paints=int.from_bytes(raw[18:22],'little'),
                    work=[int.from_bytes(raw[i:i+2],'little',signed=True) for i in (38,40,42,44)])
            if pulse:require(pulse['identity']!=widget['identity'],'Pair shares one Process')
            else:require(not loaded('pulse'),'Solo launched a Counter')
            menus.select('GEM widget');move(632,232);s.frames(100)
            initial=state();before=region(mode+'-initial',initial['work'])
            count_before=counter() if pulse else None
            digits_before=region(mode+'-counter-initial',
                (count_before['work'][0]+64,count_before['work'][1]+8,48,8)) if pulse else None
            s.frames(80)
            idle=state();count_idle=counter() if pulse else None
            digits_idle=region(mode+'-counter-idle',
                (count_before['work'][0]+64,count_before['work'][1]+8,48,8)) if pulse else None
            require(initial['work']==[32,56,304,128],'Mismatched Widget canvas')
            require((idle['actions'],idle['paints'])==(initial['actions'],initial['paints']),
                    'Idle Widget repainted or activated')
            if pulse:require(count_idle['count']>count_before['count'],'Counter timer stalled')
            if mode=='silent':require(count_idle['paints']==count_before['paints'],
                                     'Silent Counter painted on a timer')
            if mode=='paint':require(count_idle['paints']>count_before['paints'],
                                    'Counter did not paint on a timer')
            if mode=='silent':require(digits_before==digits_idle,'Silent Counter changed its displayed digits')
            if mode=='paint':require(digits_before!=digits_idle,'Counter model advanced without digit pixels')
            x,y,_,_=initial['work']
            move(x+64,y+56);edge(1,100)
            s.rendezvous(f'(dw(${base+8:x})=1)&(dw(${base+12:x})>{idle["paints"]})')
            require(state()['actions']==1,'Held button repeated activation')
            edge(0,80);move(632,232)
            key('SPACE');s.frames(100)
            s.rendezvous(f'(dw(${base+8:x})=2)&(dw(${base+12:x})>{idle["paints"]+1})')
            key('SPACE');s.frames(100)
            s.rendezvous(f'(dw(${base+8:x})=3)&(dw(${base+12:x})>{idle["paints"]+2})')
            changed=state();after=region(mode+'-activated',initial['work'])
            require(changed['label']=='Clicks: 000003' and changed['selected']==1,
                    'Widget label or selected button did not change')
            # Check label and button regions separately, not just their model.
            def part(raw,rx,ry,w,h):
                return b''.join(raw[(row*304+rx)*3:(row*304+rx+w)*3] for row in range(ry,ry+h))
            for rect in ((16,12,112,16),(16,44,128,24)):
                require(part(before,*rect)!=part(after,*rect),'Widget pixels did not change')
            b.screenshot(str(out/(mode+'-widget.png')))
            # Close Widget normally. The independently owned Counter must keep
            # progressing until its own physical close box is used.
            key('Q');s.frames(100)
            require(not loaded('widget'),'Widget did not retire')
            if pulse:
                last=counter()['count'];s.frames(80)
                require(counter()['count']>last,'Counter stopped with Widget')
                menus.select('Counter / '+mode);click(384,48);s.frames(100)
                require(not loaded('pulse'),'Counter did not retire')
            menus.select('Terminal');s.command('JOBS')
            cases.append(dict(mode=mode,initial=initial,idle=idle,activated=changed,
                counter_before=count_before,counter_idle=count_idle,widget_exit=True,
                counter_digit_hashes=[hashlib.sha256(p).hexdigest() for p in (digits_before,digits_idle)] if pulse else [],
                counter_exit=bool(pulse),physical_input='mouse press/hold/release, Space, Q, close box'))
            print('Exec Widget:',mode,'passed',flush=True)
        s.report['cases']=cases
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def run(bundle,out):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(bundle);directory=bundle/'bitmap-console'
    report=dict(status='running',tier='development',qualification=False,scope=__doc__,
                boot_route='xex',zip_sha256=sha256(bundle/'exec816-demo.zip'))
    try:
        with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
            archive.extractall(out/'extracted')
        extracted=out/'extracted/exec816-demo'
        manifest=json.loads((bundle/'demo-manifest.json').read_text())
        shutil.copyfile(extracted/manifest['media'],out/'system.atr')
        with emulator(BRIDGE,extracted/'altirraos-816.rom',out,pin=PIN) as b:
            for name,value in PIN['configuration'].items():
                b.config(name,str(value).lower() if isinstance(value,bool) else value)
            report['machine']=verify_machine(b,extracted/'altirraos-816.rom',PIN)
            b.mount(0,str(out/'system.atr'))
            bootstrap(b,p,bundle,extracted,report)
            def before(b):
                b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE ST')
                selected=address(p['image'],'selectedSession')
                marker=p['labels']['native_nmi'];condition=f'dw(${selected:x})=1'
                b.bp_clear_all();b.bp_set(marker,condition=condition)
                run_to(b,marker,12000,180,condition)
                # Session snapshots the live desktop service pointer. Construct
                # it after native startup, as the production acceptance runner does.
                session=Session(b,p,directory,out,report)
                session.ready()
                try:session.startup()
                except Exception:
                    report['startup_diagnostic']=dict(windows=session.menus.windows(),
                        children=b.memdump(session.provider['GEMDesktopChildren'],12).hex(),
                        terminal=b.memdump(session.number(session.terminal),82).hex()
                            if hasattr(session,'terminal') else None,
                        apps=[(a['name'],a['identity'],a['state']) for a in instances(b,p,directory)])
                    b.screenshot(str(out/'startup-failure.png'))
                    raise
                WidgetPair().exercise(session)
            report['runtime'],_=execute(b,{**p,'output':out},before_run=before,
                timeout=300,frame_limit=20000,preloaded=True)
            ownership(b,p,p['output'])
            report['stacks']=stack_usage(b,p['build']['memory'])
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.bundle.resolve(),args.output.resolve())
