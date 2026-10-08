#!/usr/bin/env python3
"""Two private Files images use independent public menu trees and lifetimes."""
import argparse,json
from pathlib import Path
import adapter_state as adapter
from native_program import read_build,require,verify_machine
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols
from stack_budget import stack_usage


def run(program,out):
    p=read_build(program);out.mkdir(parents=True,exist_ok=True)
    report=dict(status='running',tier='development',qualification=False)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            for key,value in PIN['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.mount(0,str(p['output'].parent/'system.atr'))
            class Session:
                def number(self,address,size=2):return int.from_bytes(b.memdump(address,size),'little')
                def rendezvous(self,condition):
                    b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
                    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                    run_to(b,p['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
                def frames(self,n=70):self.rendezvous('@frame>=%d'%(b.eval_expr('@frame')+n))
            s=Session();s.p=p;s.b=b;s.saved={'desktop_menu':{}}
            at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
            def move(x,y):
                position=[s.number(at('DESKINPUT',n)) for n in ('cursorX','cursorY')]
                position=schedule(b,p,position,(x,y))
                s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
            def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(30)
            def click(x,y):move(x,y);edge(1);edge(0);s.frames()
            def before(_):
                b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
                s.rendezvous('dw($%x)=1'%at('MENUINSTANCES','ready'))
                models=[symbols(b,p,p['output'].parent,'files',s.number(at('MENUINSTANCES',n),4))['GEMBrowser'] for n in ('one','two')]
                for base in models:s.rendezvous('dw($%x)=1'%(base+8))
                s.frames(180);menus=Menus(s,click,move)
                require(models[0]!=models[1],'Two Files instances share the model')
                require(all(s.number(base+2268)==1 for base in models),'Missing installed Files menu')
                require(len([w for w in menus.windows() if w['title']=='Files'])==2,'Missing Files windows')
                # Move the focused second instance; both title bars are reachable.
                move(100,64);edge(1);move(348,64);edge(0);s.frames(130)
                require(s.number(models[1]+26)==272,'Second Files window did not move')
                click(32,64);s.frames()
                require(s.number(models[0]+1966)==65535,'Unexpected initial selection')
                click(80,108);s.frames()
                require(s.number(models[0]+1966)==0 and s.number(models[1]+1966)==65535,'Selection crossed application instances')
                require(s.number(models[0]+2028+6*24+10)==0 and s.number(models[1]+2028+6*24+10)==8,'Menu enable state crossed instances')
                click(24,8);click(32,40)
                require(s.number(models[0]+1966)==65535,'Pointer menu Refresh failed')
                click(80,108);menus.key('ESC',ctrl=True,shift=True);menus.key('TAB');menus.key('RETURN')
                require(b.memdump(models[0]+178,128).split(b'\0')[0]==b'SYS:C','Keyboard menu Open failed')
                first_focus=menus.focus();click(280,64);s.frames()
                require(menus.focus()!=first_focus,'Second instance did not focus')
                # Open is disabled: keyboard navigation starts with Refresh.
                menus.key('ESC',ctrl=True,shift=True);menus.key('TAB');menus.key('RETURN')
                require(b.memdump(models[1]+178,128).split(b'\0')[0]==b'SYS:','Disabled Open acted')
                menus.key('ESC',ctrl=True,shift=True);menus.key('TAB');menus.key('TAB');menus.key('RETURN')
                s.rendezvous('dw($%x)=0'%(models[1]+8));s.frames(100)
                require(menus.focus()==first_focus,'Quit did not restore other Files menu')
                require(s.number(models[0]+2268)==1 and not s.number(models[1]+2268),'Menu withdrawal crossed owners')
                click(24,8);click(32,72)
                s.rendezvous('dw($%x)=0'%(models[0]+8))
                report.update(private_models=models,commands=['pointer Refresh','keyboard Open','disabled Open','keyboard Quit','pointer Quit'],focus_restoration=True)
                b.poke16(at('MENUINSTANCES','mode'),9);b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,p['output']);report['stack_usage']=stack_usage(b,p['build']['memory'])
            report.update(status='pass',reserved_bank_zero_delta=dict(fixed=0,per_public_task=[0]*8,private_idle=0))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Two Files menu instances passed',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--program',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();run(args.program.resolve(),args.output.resolve())
