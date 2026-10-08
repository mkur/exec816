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
            position=schedule(s.b,s.p,position,(x,y));s.saved["pointer"]=position;s.frames(15)
        def click(x,y):
            move(x,y)
            s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(35)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        click(458,56);click(456,104)
        require(s.number(panel+178+2*24+10,2)==1,'Packaged panel toggle')
        require(s.number(counter+14,4)>0,'Packaged counter did not advance')
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
        browser=launch_files();click(250,64)
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
        click(24,64);row('C');key('RETURN');row('PANEL.APP');key('RETURN')
        s.rendezvous('(dw($%x)!=0)|(dw($%x)=$6143)'%(browser+1980,browser+1386))
        child=s.number(browser+1980,4);require(child!=0,'Relaunched Files lost its GUI child')
        loaded_panel=symbols(s.b,s.p,s.p['output']/'bitmap-console','panel',child)['GEMPanel']
        s.rendezvous('dw($%x)=1'%(loaded_panel+8));click(24,64);key('F')
        click(96,32)
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='gem-desktop',panel_toggle=True,counter=True,shell=True,
            files_relaunch=True,idle_job_collection=True,heap_restored=True,exit_with_gui_child_and_popup=True)
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    record=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=DesktopBoot(),profile_commands=False)

    (out/"gem-desktop-results.json").write_text(json.dumps(record,indent=2)+"\n")
