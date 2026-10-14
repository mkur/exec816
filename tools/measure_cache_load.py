#!/usr/bin/env python3
"""Matched physical button latency with Counter and sustained CAT output.

Boot/SYS remain the exact ZIP. WORK contains the same bounded development load
in each run. Observations are passive and outside timed regions; no guest patch.
"""
import argparse,json,shutil,zipfile
from pathlib import Path
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances,symbols
from loadable_gem_feedback import measure
from make_data_disk import make
from native_program import require,sha256
from test_demo import run
from gem_render_oracle import DESKTOP_PALETTE,PENS
from test_gem_cursor import ARROW
from measure_desktop import distribution
from sio_transaction_trace import BASE_HZ


class Load:
    def __init__(self,count):self.count=count

    def prepare_work(self,path,item):
        source=path.parent/'cache-load-media';source.mkdir(exist_ok=True)
        payload=(b'Cache latency load: the shell keeps printing while GUI runs.    '+b'\x9b')*1024
        (source/'LOAD.TXT').write_bytes(payload)
        make(path,source,binary_names={'LOAD.TXT'},sector_bytes=item['sector_bytes'],
             filesystem=item['filesystem'],sectors=item['sectors'])
        self.media=dict(sha256=sha256(path),payload_sha256=sha256(source/'LOAD.TXT'),bytes=len(payload))

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        desk=symbols(b,s.p,directory,'desktop',s.number(shared['GEMDesktopChildren'],4))['GEMDesk']
        def at(module,name):return next(d['address'] for d in s.p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
        def move(x,y):
            old=[s.number(at('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,old,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(60)
        menus=Menus(s,click,move)
        def launch(row,name,model):
            menus.select('SYS:');click(296,8);click(304,28+row*11)
            for _ in range(60):
                apps=[a for a in instances(b,s.p,directory) if a['name']==name]
                if apps:break
                s.frames(20)
            require(apps,'Cannot launch '+name)
            return apps[0]['symbols'][model]
        counter=launch(4,'counter','GEMCounter');s.rendezvous('dw($%x)=1'%(counter+12));s.frames(100)
        move(216,40);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        move(24,168);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(100)
        panel=launch(1,'panel','GEMPanel');s.rendezvous('dw($%x)=1'%(panel+8));s.frames(100)
        menus.select('Shell');cat=s.begin('CAT WORK:LOAD.TXT')
        menus.select('Counter');menus.select('Control Panel')
        window=s.p['build']['memory']['console_storage']['WINDOWS']+s.console['WINDOWS_ITEMS']
        def running():return s.number(window+s.console['WINDOW_SCOPE'],3) not in (0,s.saved['scope'])
        console=s.number(window+s.console['WINDOW_INSTANCE'],3)
        generation=console+s.console['INSTANCE_GENERATION']
        first_generation=s.number(generation,4)
        ticks=s.number(counter+14,4);paints=s.number(counter+18,4)
        progress=[]
        def before(index):
            s.frames((index%5)*2)
            require(running(),'CAT finished before sample '+str(index))
        def after(index):
            require(running(),'CAT finished during sample '+str(index))
            progress.append(dict(index=index,ticks=s.number(counter+14,4),paints=s.number(counter+18,4),
                                 console_generation=s.number(generation,4)))
        samples=measure(s,panel,move,'counter-and-cat',count=self.count,before_sample=before,after_sample=after)
        move(600,80);motion=[]
        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
        colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
        for index in range(self.count):
            before(index)
            target=(602 if index%2==0 else 600,80)
            old=[s.number(at('DESKINPUT',n),2) for n in ('cursorX','cursorY')]
            started=b.eval_expr('@clk')&0xffffffff
            pos=schedule(b,s.p,old,target);s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]))
            for _ in range(30):
                path=s.p['output']/'loaded-pointer.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
                if all(raw[(target[1]+y)*frame.stride+(target[0]+x+16)*4:
                           (target[1]+y)*frame.stride+(target[0]+x+16)*4+3]==colors[15 if char=='X' else 0]
                       for y,line in enumerate(ARROW) for x,char in enumerate(line) if char!='.'):break
                s.frames(1)
            else:raise RuntimeError('Loaded pointer did not reach scanout')
            motion.append(((b.eval_expr('@clk')-started)&0xffffffff)/BASE_HZ*1000)
            require(running(),'CAT finished during pointer sample')
            s.frames(5)
        require(s.number(counter+14,4)>ticks and s.number(counter+18,4)>paints,'Counter did not progress')
        require(s.number(generation,4)>first_generation,'Console output made no progress')
        self.results=dict(button=samples,pointer=dict(samples_ms=motion,**distribution(motion)),progress=progress,work=self.media,
            console_updates=s.number(generation,4)-first_generation,
            scope='Physical press to independently reconstructed button scanout; 0/2/4/6/8-frame phase offsets; Counter and CAT active throughout')
        (s.p['output']/'loaded-samples.json').write_text(json.dumps(self.results,indent=2)+'\n')
        menus.select('Shell')
        if running():s.press('\x03')
        s.ready(cat);s.frames(60)
        # Check the complete final retained desktop against its model after the
        # normal cancellation/retirement boundary, outside the timing cohort.
        move(632,232);s.frames(100);s.cells('cache-loaded-final')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--count',type=int,default=30);p.add_argument('--layout-revision')
    a=p.parse_args();require(a.count>=30,'At least 30 loaded interactions required')
    if a.layout_revision:
        import subprocess,generate_layers,generate_desktop,generate_aes_server
        for module,name in [(generate_layers,'layers'),(generate_desktop,'desktop'),(generate_aes_server,'aes-server')]:
            module.ABI=json.loads(subprocess.check_output(['git','show',a.layout_revision+':abi/'+name+'.json'],text=True))
    out=a.output.resolve();require(not out.exists(),'Use a fresh measurement directory')
    shutil.copytree(a.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    probe=Load(a.count)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=probe,profile_commands=False)
    result.update(qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),loaded=probe.results)
    (out/'loaded-results.json').write_text(json.dumps(result,indent=2)+'\n')

if __name__=='__main__':main()
