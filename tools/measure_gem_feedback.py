#!/usr/bin/env python3
"""Matched physical Panel presses and Files selection changes in an exact ZIP.

Completion is matching scanout, sampled once per frame after the input reaches
the application. These distributions include input, scheduling and drawing;
they are not CPU-only or sub-frame completion measurements.
"""
import argparse,json,shutil,zipfile
from pathlib import Path
from native_program import require,sha256
from test_demo import run
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols
from browser_model import FIELDS as F,wait_listing
from loadable_gem_feedback import measure
from measure_desktop import distribution
from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
from gem_desktop_oracle import paint
from test_gem_cursor import overlay
from sio_transaction_trace import BASE_HZ


class Feedback:
    def __init__(self,count):self.count=count

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        sy=json.loads((directory/'c-image.json').read_text())['symbols']
        colour='desktop' in s.p['build'].get('gem_applications',{})
        if colour:
            sy.update(symbols(b,s.p,directory,'desktop',s.number(sy['GEMDesktopChildren'],4)))
            from colour_desktop_model import FIELDS as D
            sy['GEMBrowser']=s.number(sy['GEMDesk']+D['folders'],4)
        else:
            for i,name in enumerate(('panel','counter','files')):
                sy.update(symbols(b,s.p,directory,name,s.number(sy['GEMDesktopChildren']+i*4,4)))
        cursor=lambda name:next(d['address'] for d in s.p['image']['data']
            if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(cursor(n),2) for n in ('cursorX','cursorY')]
            position=schedule(b,s.p,old,(x,y));s.saved['pointer']=position
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%
                (cursor('cursorX'),position[0],cursor('cursorY'),position[1]))
            s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(35)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        menus=Menus(s,click,move)
        if colour:
            menus.select('SYS:')
            click(168,8);click(176,40);s.frames(500)
            child=s.number(sy['GEMDesk']+D['children'],4)
            require(child,'Panel launch: '+repr(b.memdump(sy['GEMDesk']+D['status'],65)))
            sy.update(symbols(b,s.p,directory,'panel',child))
        menus.select('Control Panel')
        measure(s,sy['GEMPanel'],move,'repeated',count=self.count)
        base=sy['GEMBrowser'];wait_listing(s,base)
        title=b.memdump(base+F['path'],65).split(b'\0')[0][:64]
        menus.select(title.decode('ascii'))
        require(s.number(base+F['visible'],2)>=2 and s.number(base+F['count'],2)>=2,'Need two Files rows')
        font=font_bytes(s.p['output']/s.manifest['font_source'])
        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
        colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
        x,y,w,h=[s.number(base+F['work']+i*2,2) for i in range(4)]
        icons=s.number(base+F['iconView'],2)
        region=(x,y+31,x+w,y+(72 if icons else 56))
        def expected():
            r=Raster(font);paint(b,sy,r,title,(x-8,y-28,x+w+16,y+h+16))
            packed=overlay(r,s.saved['pointer'])
            return b''.join(colors[(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
                for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
        def visible(want):
            path=s.p['output']/'files-feedback.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            return want==b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]
                for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
        samples=[]
        for i in range(self.count):
            first=s.number(base+F['first'],2)
            selected=s.number(base+F['selected'],2)
            row=1 if selected==first else 0;target=first+row
            move(x+48+row*104 if icons else x+40,y+44 if icons else y+36+row*12)
            b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(4)
            start=b.eval_expr('@clk')&0xffffffff
            b._cmd_ok('MOUSE AT 2000 0 0 0')
            s.rendezvous('dw($%x)=%d'%(base+F['selected'],target))
            # Both object states are authoritative only after the redraw call
            # returns; the independent model must describe the desired state.
            tree=s.number(base+F['tree'],4)
            s.rendezvous('(dw($%x)=1)&(dw($%x)=0)'%
                (tree+(4+row)*24+10,tree+(5-row)*24+10))
            want=expected()
            for attempt in range(30):
                if visible(want):break
                s.frames(1)
            else:raise RuntimeError('Files selection did not reach scanout')
            samples.append(((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000)
            s.frames(15)
        s.saved['files_feedback']=dict(samples_ms=samples,**distribution(samples),
            view='icons' if icons else 'list',
            scope='Release submission to matching two-cell scanout; frame-granular polling after state change.')
        print('Files feedback:',s.saved['files_feedback'],flush=True)
        self.results=dict(panel=s.saved['loaded_panel_feedback']['repeated'],files=s.saved['files_feedback'])
        (s.p['output']/'feedback-samples.json').write_text(json.dumps(self.results,indent=2)+'\n')
        s.save_screen(s.p['output']/'boot-smoke.png')
        menus.select('Shell')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--bundle',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--count',type=int,default=40);args=a.parse_args()
    out=args.output.resolve();require(not out.exists(),'Use a fresh measurement directory')
    shutil.copytree(args.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','g4bench-extracted-*','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
    probe=Feedback(args.count)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
               integration=probe,profile_commands=False)
    result.update(qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),feedback=probe.results)
    (out/'feedback-results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':main()
