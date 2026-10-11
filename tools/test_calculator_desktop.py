#!/usr/bin/env python3
"""Calculator lifetime walkthrough using the existing packaged desktop harness."""
import argparse,json,re,zipfile
from pathlib import Path
from native_program import require
from desktop_mouse import schedule
from gem_applications import symbols
from desktop_menu_check import Menus
from test_demo import run


class DesktopColdBoot:
    """Short second-cartridge check after the complete desktop walkthrough."""
    def exercise(self,s):
        s.saved['pointer']=schedule(s.b,s.p,[320,120],(96,32));s.frames(100)
        s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(30)
        s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='gem-desktop-cold-boot',three_apps_ready=True,shell=True)
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


from browser_model import FIELDS as BF, select as select_file, wait_listing


class CalculatorDesktop:
    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        children=shared['GEMDesktopChildren'];job=s.at('job')
        browser=symbols(b,s.p,directory,'files',s.number(children+8,4))['GEMBrowser']
        counter=symbols(b,s.p,directory,'counter',s.number(children+4,4))['GEMCounter']
        count=s.number(counter+14,4)
        position=[320,120]
        def move(x,y):
            nonlocal position
            position=schedule(b,s.p,position,(x,y));s.saved['pointer']=position
            at=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),position[0],at('cursorY'),position[1]));s.frames(3)
        def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(20)
        def click(x,y):move(x,y);edge(1);edge(0);s.frames(60)
        def key(name):b._cmd_ok('KEY '+name+' down');s.frames(3);b._cmd_ok('KEY '+name+' up');s.frames(50)
        def row(name):select_file(s,browser,name,click)
        def load():
            menus.select('Files');row('CALC.APP');old=s.number(browser+BF['launches'],4);key('RETURN')
            s.rendezvous('dw($%x)=%d'%(browser+BF['launches'],old+1))
        def current(identity):
            sy=symbols(b,s.p,directory,'calc',identity)
            s.rendezvous('dw($%x)=1'%(sy['Calculator']+4));s.frames(100)
            require(s.number(sy['shown'])==0,'Calculator did not start fresh')
            return sy
        def stop():
            menus.select('Files');key('F');key('TAB');key('TAB');key('RETURN')
            s.rendezvous('dw($%x)=0'%(browser+BF['child']));s.frames(90)
            require(s.number(browser+BF['result'],4)==0,'Calculator Stop result')
        def memory():
            click(96,32);screen=s.command('MEM').decode('ascii')
            return [int(v) for v in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',screen)][-4:]
        def work(sy):return [s.number(sy['Calculator']+22+i*2,2) for i in range(4)]
        def button(sy,index):
            tree=s.number(sy['tree']);x,y,_,_=work(sy)
            ox,oy,w,h=[s.number(tree+index*24+16+i*2,2) for i in range(4)]
            click(x+ox+w//2,y+oy+h//2)
        menus=Menus(s,click,move)
        menus.select('Files');row('C');key('RETURN');wait_listing(s,browser)
        baseline=memory();owners=s.ledger()
        load();s.rendezvous('dw($%x)=0'%(browser+BF['child']));s.frames(100)
        require(s.number(browser+BF['result'],4)==1,'Full desktop must reject a fifth window')
        after=memory();after_owners=s.ledger()
        # Files first arms its existing child-collection timer: one 32-byte
        # port and two 40-byte requests, retained until Files exits.
        require([a-z for a,z in zip(baseline,after)]==[112,0,112,0],
                'Unexpected first Files launch heap cost: '+str((baseline,after)))
        print('Files child-collection timer opened: 112 upper bytes',flush=True)
        require(after_owners==owners,'No-window failure retained ownership')
        baseline=after
        load();s.rendezvous('dw($%x)=0'%(browser+BF['child']));s.frames(100)
        require(s.number(browser+BF['result'],4)==1,'Repeated no-window result')
        require(memory()==baseline and s.ledger()==owners,'Repeated no-window failure leaked resources')
        print('Calculator no-window cleanup pass',flush=True)
        click(592,56);click(424,56);s.rendezvous('dw($%x)=0'%children)
        baseline=memory();owners=s.ledger()
        load();first=current(s.number(browser+BF['child'],4))
        for index in (3,10,9,19):button(first,index)
        require(s.number(first['shown'])==42,'Packaged calculator arithmetic')
        self.feedback(s,first,move)
        require(s.number(counter+14,4)>count,'Counter stopped beside calculator')
        s.cells('calculator-forty-two');stop()
        require(memory()==baseline and s.ledger()==owners,'Calculator Stop leaked resources')
        load();first=current(s.number(browser+BF['child'],4));stop()
        require(memory()==baseline and s.ledger()==owners,'Calculator relaunch leaked resources')
        print('Files calculator launch, Stop and relaunch pass',flush=True)
        # Retire Counter to fit two independent calculator windows in four layers.
        # MEM tops the shell and completely covers Counter's title. Move the
        # shell down four text rows to expose it, then restore the shell.
        move(96,32);edge(1);move(96,64);edge(0);s.frames(100)
        click(380,40);click(200,40);s.rendezvous('dw($%x)=0'%(children+4))
        move(96,64);edge(1);move(96,32);edge(0);s.frames(100)
        click(96,32);s.command('C:HELLO',b'Hello from disk!')
        baseline=memory();owners=s.ledger()
        load();first=current(s.number(browser+BF['child'],4));button(first,3)
        click(96,32);previous=s.begin('RUN C:CALC.APP');s.ready(previous);s.result()
        second=current(s.number(job,4))
        x,y,w,h=work(second);move(x+80,y-8);edge(1);move(x-64,y-8);edge(0);s.frames(100)
        require(work(second)[:2]==[x-144,y],'Second calculator drag')
        button(second,4)
        require(s.number(first['shown'])==7 and s.number(second['shown'])==8,'Calculator state is shared')
        roots=[s.number(item['tree']) for item in (first,second)]
        require(roots[0]!=roots[1] and s.number(roots[0]+2*24+12)!=s.number(roots[1]+2*24+12),'Calculator resources are shared')
        s.cells('two-calculators')
        x,y,w,h=work(second);click(x,y-8)
        s.rendezvous('db($%x)=3'%(job+12));s.frames(100)
        require(s.number(browser+BF['child'],4)!=0,'Closing shell calculator stopped Files child')
        stop();require(memory()==baseline and s.ledger()==owners,'Two calculator images retained heap/ownership')
        print('Independent calculator instances and idle RUN collection pass',flush=True)
        # Owner exit must collect a still-live calculator, including popup wait.
        load();first=current(s.number(browser+BF['child'],4));menus.select('Files');key('F')
        click(96,32);s.save_screen(s.p['output']/'boot-smoke.png')
        from stack_budget import stack_usage
        s.saved['gem_stacks']=stack_usage(b,s.p['build']['memory'])
        s.saved['integration']=dict(profile='calculator',no_window_cleanup=True,files_launch=True,
            stop=True,relaunch=True,counter=True,shell=True,independent_instances=2,
            resource_isolation=True,idle_run_collection=True,heap_restored=True,
            exit_with_calculator_and_popup=True,feedback=self.samples)
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()

    def feedback(self,s,sy,move):
        from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
        from gem_desktop_oracle import paint
        from test_gem_cursor import overlay
        from sio_transaction_trace import BASE_HZ
        b=s.b;model=sy['Calculator'];tree=s.number(sy['tree'])
        x,y,w,h=[s.number(model+22+i*2,2) for i in range(4)]
        ox,oy,bw,bh=[s.number(tree+3*24+16+i*2,2) for i in range(4)]
        move(x+ox+bw//2,y+oy+bh//2);s.frames(5)
        font=font_bytes(s.p['output']/s.manifest['font_source'])
        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
        colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
        region=(x+ox-2,y+oy-2,x+ox+bw+2,y+oy+bh+2)
        def visible():
            r=Raster(font);paint(b,sy,r,b'Calculator',(x-8,y-16,x+w+8,y+h+8))
            packed=overlay(r,s.saved['pointer'])
            want=b''.join(colors[(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
                          for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
            path=s.p['output']/'calculator-feedback.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            actual=b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]
                            for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
            return want==actual
        self.samples=[]
        for _ in range(6):
            start=b.eval_expr('@clk')&0xffffffff;b._cmd_ok('MOUSE AT 2000 0 0 1')
            s.rendezvous('dw($%x)=3'%(model+8))
            for attempt in range(25):
                if visible():break
                s.frames(1)
            else:raise RuntimeError('Calculator pressed button pixels did not settle')
            elapsed=((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000
            require(elapsed<500,'Calculator feedback exceeded bounded smoke limit')
            self.samples.append(elapsed)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(30)
        print('Calculator frame-granular feedback (ms):',self.samples,flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    record=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=CalculatorDesktop(),profile_commands=False)
    record['scope']='Extracted OF816 calculator: Files launch/Stop/reload, window capacity, two private instances, idle shell collection, feedback and session exit'
    (out/'calculator-results.json').write_text(json.dumps(record,indent=2)+'\n')
