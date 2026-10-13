#!/usr/bin/env python3
"""Compact loaded Counter: exact-package pixels, tick calls and exposure."""
import argparse
import json
import os
import zipfile
from pathlib import Path

from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances, symbols
from native_program import require
from stack_budget import stack_usage
from test_demo import run


class CounterApp:
    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        desk=symbols(b,s.p,directory,'desktop',s.number(resident['GEMDesktopChildren'],4))['GEMDesk']
        def at(name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            position=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            s.saved['pointer']=schedule(b,s.p,position,(x,y))
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y))
            s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        def shot(name):
            move(632,232);s.frames(5);s.cells(name)
            s.save_screen(s.p['output']/(name+'.png'))
            print(name,flush=True)
        menus=Menus(s,click,move)
        menus.select('SYS:')
        click(296,8);click(304,88)  # Desk > Counter
        for _ in range(60):
            found=[a for a in instances(b,s.p,directory) if a['name']=='counter']
            if found:break
            s.frames(20)
        require(found,'Desk > Counter did not launch the app')
        sy=found[0]['symbols'];app=sy['GEMCounter']
        s.rendezvous('dw($%x)=1'%(app+12));s.frames(100)
        work=lambda:[s.number(app+38+i*2,2) for i in range(4)]
        require(work()==[200,48,128,24],'Counter window is not 144x48')
        shot('counter-compact')

        # No guest code or state is patched. Passive shared-VDI call markers
        # check each quiet timer update, including the natural 9 -> 10 carry.
        ticks=[]
        b.profile_start()
        while s.number(app+14,4)<10:
            old=s.number(app+14,4);paints=s.number(app+18,4)
            start=b.eval_expr('@clk') & 0xffffffff
            s.rendezvous('(dw($%x)=%d)&(dw($%x)>%d)'%(app+14,old+1,app+18,paints))
            end=b.eval_expr('@clk') & 0xffffffff
            count=s.number(app+14,4)
            require(count==old+1,'Wrong counter increment/carry')
            require(b.memdump(app+46,14)==('Count: %06d\0'%count).encode(),'Wrong decimal label')
            ticks.append(dict(before=old,after=count,start=start,end=end))
        b.profile_stop()
        require(any(t['before']==9 and t['after']==10 for t in ticks),'Decimal carry not observed')
        shot('counter-carry')

        # Odd-X movement keeps the small digit update on the native text path.
        x,y,w,h=work();move(x+64,y-8)
        b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(x+65,y-8);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(100)
        require(work()==[x+1,y,w,h],'Counter did not move to odd X')
        shot('counter-odd-x')

        # Place SYS:'s left edge inside a digit cell to exercise clipping.
        menus.select('SYS:')
        from browser_model import FIELDS as F
        folder=s.number(desk+D['folders'],4)
        fx,fy=[s.number(folder+F['work']+i*2,2) for i in range(2)]
        delta=work()[0]+64+5-(fx-8)
        move(fx+120,fy-8);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(fx+120+delta,fy-8);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(120)
        require(s.number(folder+F['work'],2)==fx+delta,'Covering folder did not move')
        count=s.number(app+14,4);s.frames(120)
        require(s.number(app+14,4)>count,'Partially covered Counter stopped')
        shot('counter-partly-covered')
        menus.select('Counter');shot('counter-exposed')
        menus.select('Shell');count=s.number(app+14,4);s.frames(120)
        require(s.number(app+14,4)>count,'Fully covered Counter stopped')
        shot('counter-covered')
        menus.select('Counter');shot('counter-restored')
        x,y,_,_=work();click(x,y-8);s.frames(100)
        require(not any(a['name']=='counter' for a in instances(b,s.p,directory)),
                'Closed Counter retained its Process')
        shot('counter-closed')
        self.report=dict(window=[144,48],tick_area=[48,8],ticks=ticks,
            odd_x=True,partial_cover=True,full_cover=True,exposure=True,close=True,
            stacks=stack_usage(b,s.p['build']['memory']))
        s.saved['integration']=self.report
        menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    resident=json.loads((out/'bitmap-console/c-image.json').read_text())['symbols']
    markers={resident[name]:name for name in ('v_bar','v_gtext')}
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join('%x'%pc for pc in markers)
    probe=CounterApp()
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
               integration=probe,profile_commands=False)
    from sio_transaction_trace import read_events
    events=read_events(out/'emulator.log',{'cpu'})
    for tick in probe.report['ticks']:
        start=tick['start']+round((events[0][0]-tick['start'])/(1<<32))*(1<<32)
        end=start+((tick['end']-tick['start']) & 0xffffffff)
        calls=[markers[int(e[4],16)] for t,e in events
               if start<=t<=end and int(e[4],16) in markers]
        require(calls==['v_gtext'],'Timer update did not use one text call without clearing: '+str(calls))
        tick['calls']=calls
    result.update(tier='development',qualification=False,counter=probe.report)
    (out/'counter-results.json').write_text(json.dumps(result,indent=2)+'\n')
