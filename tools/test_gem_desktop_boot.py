#!/usr/bin/env python3
"""Cold boot the packaged GEM desktop through OF816 and exercise the shell."""
import argparse,json,zipfile
from pathlib import Path
from native_program import require
from desktop_mouse import schedule
from test_demo import run

class DesktopBoot:
    def exercise(self,s):
        sy=json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
        panel=sy['GEMPanel'];counter=sy['GEMCounter']
        s.rendezvous('dw($%x)=1'%(panel+8));s.frames(150)
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
        click(96,32)
        s.command('HELLO',b'Hello from disk!')
        s.command('CAT STORY.TXT | WC')
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='gem-desktop',panel_toggle=True,counter=True,shell=True)
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args();out=args.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    record=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=DesktopBoot(),profile_commands=False)

    (out/"gem-desktop-results.json").write_text(json.dumps(record,indent=2)+"\n")
