#!/usr/bin/env python3
"""Cold boot the packaged GEM desktop through OF816 and exercise the shell."""
import argparse,json,re,zipfile
from pathlib import Path
from native_program import require
from desktop_mouse import schedule
from test_demo import run

class DesktopBoot:
    def exercise(self,s):
        sy=json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
        from gem_applications import symbols
        for index,name in enumerate(('panel','counter','files')):
            sy.update(symbols(s.b,s.p,s.p['output']/'bitmap-console',name,
                              s.number(sy['GEMDesktopChildren']+index*4,4)))
        panel=sy['GEMPanel'];counter=sy['GEMCounter']
        state={name:s.b.memdump(sy[name],178 if name=='GEMBrowser' else 24).hex() for name in ('GEMPanel','GEMCounter','GEMBrowser') if name in sy}
        state['failure']=s.number(sy['GEMDesktopFailure'],2)
        (s.p['output']/'gem-startup.json').write_text(json.dumps(state,indent=2)+'\n')
        require(s.number(panel+8,2)==1,'GEM desktop startup failed; see gem-startup.json')
        s.frames(150)
        position=[320,120]
        def move(x,y):
            nonlocal position
            cursor=lambda name:next(d['address'] for d in s.p['image']['data']
                if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            position=[s.number(cursor(name),2) for name in ("cursorX","cursorY")]
            position=schedule(s.b,s.p,position,(x,y));s.saved["pointer"]=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%
                (cursor('cursorX'),position[0],cursor('cursorY'),position[1]))
            s.frames(3)
        def click(x,y):
            move(x,y)
            s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(35)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        from desktop_menu_check import exercise as check_menus
        s.menus=check_menus(s,sy,click,move)
        click(458,56);click(456,104)
        require(s.number(panel+400,2)==1 and s.number(panel+178+2*24+10,2)==0,'Packaged panel Defaults')
        require(s.number(counter+14,4)>0,'Packaged counter did not advance')
        from loadable_gem_feedback import measure
        measure(s,panel,move,'initial')
        from panel_settings_check import exercise
        exercise(s,sy,click,move)
        actions=s.number(panel+10,4)
        s.b._cmd_ok('KEY RETURN down');s.frames(3)
        s.b._cmd_ok('KEY RETURN up');s.frames(70)
        require(s.number(panel+10,4)==actions+1,'Loaded panel keyboard activation')
        origin=[s.number(panel+34+2*i,2) for i in range(2)]
        for start,end,expected in [((480,56),(488,64),[v+8 for v in origin]),
                                   ((488,64),(480,56),origin)]:
            move(*start);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
            move(*end);s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(90)
            actual=[s.number(panel+34+2*i,2) for i in range(2)]
            require(actual==expected,'Loaded panel title drag: '+str((actual,expected)))
        if s.manifest.get('gem_desktop') and 'GEMBrowser' in sy:
            from test_gem_files import exercise
            exercise(s,sy,click,move)
        click(96,32)
        s.command('HELLO',b'Hello from disk!')
        s.command('CAT STORY.TXT | WC')
        # RUN uses the ordinary shell job. Its completion must be collected
        # while the prompt waits, before another key or command is entered.
        job=s.at('job')
        def launch_files():
            previous=s.begin('RUN C:FILES.APP');s.ready(previous);s.result()
            identity=s.number(job,4)
            model=symbols(s.b,s.p,s.p['output']/'bitmap-console','files',identity)['GEMBrowser']
            s.rendezvous('dw($%x)=1'%(model+8));s.frames(120)
            return model
        def memory():
            screen=s.command('MEM').decode('ascii')
            return [int(v) for v in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',screen)][-4:]
        baseline=memory();owners=s.ledger()
        browser=launch_files();click(24,8);click(32,72)
        s.rendezvous('db($%x)=3'%(job+12))
        require(s.ledger()==owners,'Idle RUN completion retained ownership')
        click(96,32);require(memory()==baseline,'Files restart leaked heap storage')
        browser=launch_files()
        # Launch a GUI child and leave a popup active when EXIT closes Files.
        def key(name):s.b._cmd_ok('KEY '+name+' down');s.frames(3);s.b._cmd_ok('KEY '+name+' up');s.frames(70)
        def row(name):
            for _ in range(12):
                raw=s.b.memdump(browser+306,8*108)
                names=[raw[i*108:(i+1)*108].split(b'\0')[0].decode('ascii')
                       for i in range(s.number(browser+1962,2))]
                if name in names:click(80,108+names.index(name)*12);return
                click(204,88);s.frames(100)
            raise RuntimeError('Missing relaunched Files entry '+name)
        # Quit from the application menu follows the same child-stop/collect path.
        s.menus.select('Files');row('C');key('RETURN');row('TICK');key('RETURN')
        s.rendezvous('dw($%x)!=0'%(browser+1980));s.frames(80)
        click(24,8);click(32,72)
        s.rendezvous('db($%x)=3'%(job+12));s.frames(100)
        require(s.ledger()==owners,'Menu Quit retained its native child')
        click(96,32);require(memory()==baseline,'Menu Quit with child leaked heap storage')
        s.saved['menu_quit_with_child']=True
        browser=launch_files()
        s.menus.select('Files');row('C');key('RETURN');row('PANEL.APP');key('RETURN')
        s.rendezvous('(dw($%x)!=0)|(dw($%x)=$6143)'%(browser+1980,browser+1386))
        child=s.number(browser+1980,4);require(child!=0,'Relaunched Files lost its GUI child')
        loaded_panel=symbols(s.b,s.p,s.p['output']/'bitmap-console','panel',child)['GEMPanel']
        s.rendezvous('dw($%x)=1'%(loaded_panel+8));s.menus.select('Files');key('F')
        click(96,32)
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='gem-desktop',desktop_menu=s.saved['desktop_menu'],panel_settings=s.saved['panel_settings'],panel_keyboard=True,panel_drag=True,counter=True,shell=True,
            files_relaunch=True,idle_job_collection=True,heap_restored=True,menu_quit_with_child=True,exit_with_gui_child_and_popup=True)
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    record=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=DesktopBoot(),profile_commands=False)

    (out/"gem-desktop-results.json").write_text(json.dumps(record,indent=2)+"\n")
