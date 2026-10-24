#!/usr/bin/env python3
"""Packaged two-shell pipeline beside BASIC, then Run/Stop with both shells live."""
import argparse
import json
from pathlib import Path
import hashlib
import zipfile

from basic_build_model import FIELDS as JOB
from console_model import read_cells
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from generate_aes_server import expected_layout, layout
from native_program import require, sha256
from shell_session_walkthrough import Sessions
from test_demo import run
from test_shell_core import KEYS
from workbench_interaction import FIELDS


class TwelveTasks(Sessions):
    interrupt_marker='native_nmi'

    def source_shell(self):
        pass

    def source_checks(self,**context):
        pass

    def source_after_quit(self):
        pass

    def screen(self,label):
        # Sessions' flat bitmap oracle does not include GEM application layers.
        # Inspect the retained shell model; this case validates Task coexistence.
        self.s.frames(3)
        return read_cells(self.s.far,self.s.saved['top'])

    def exercise(self,s):
        self.out.mkdir(parents=True,exist_ok=True)
        self.prepare(s)
        b=s.b
        n=s.number
        frames=s.frames
        reach=s.rendezvous
        live=s.p['build']['task_storage']['LIVE']

        def at(name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_DESKINPUT_'+name.upper()+'_' in d['name'])

        def move(x,y):
            position=[n(at(name),2) for name in ('cursorX','cursorY')]
            x,y=schedule(b,s.p,position,(x,y))
            s.saved['pointer']=(x,y)
            reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y))
            frames(3)

        def click(x,y):
            move(x,y)
            b._cmd_ok('MOUSE AT 2000 0 0 1');frames(12)
            b._cmd_ok('MOUSE AT 2000 0 0 0');frames(30)

        def key(name,ctrl=False,shift=False):
            if ctrl:b._cmd_ok('KEY CTRL down')
            if shift:b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down');frames(4)
            b._cmd_ok('KEY '+name+' up')
            if shift:b._cmd_ok('KEY SHIFT up')
            if ctrl:b._cmd_ok('KEY CTRL up')
            frames(4)

        menus=Menus(s,click,move)
        menus.select('Shell')
        require(n(live,1)==6,'Unexpected standard desktop census')
        self.source_shell()
        self.command('RUN C:BASIC.APP')
        basic_app=next(item for item in instances(b,s.p,self.bundle/'bitmap-console')
                       if item['name']=='basic')
        basic=basic_app['symbols']['Basic']
        job=basic_app['symbols']['b']
        reach('dw($%x)=1'%(basic+FIELDS['ready']))
        menus.select('Shell')
        s.begin('NEWSHELL')
        self.wait_selected(2)
        self.bind(2)
        s.ready()
        reach('db($%x)=8'%live)
        require(n(live,1)==8,'Workbench and two shells did not coexist')

        route=s.begin('CAT SYS:LONG.TXT | WC')
        reach('(db($%x)=10)&(dw($%x)!=0)&(dw($%x)!=0)'%
              (live,s.saved['scope']+48,s.saved['scope']+51))
        self.pipeline_peak=n(live,1)
        s.ready(route);s.result()
        require(n(live,1)==8,'Pipeline did not release both Tasks')
        self.screen('two-shell-pipeline')
        print('Two shells + BASIC + pipeline:',self.pipeline_peak,'Tasks',flush=True)

        def replace(text):
            menus.select('FastBasic')
            key('A',ctrl=True)
            document=basic+FIELDS['document']
            reach('(dw($%x)=0)&(dw($%x)=%d)'%(basic+FIELDS['anchor'],basic+FIELDS['caret'],n(document+20,4)))
            reach('dw($%x)=0'%(basic+FIELDS['dirty']))
            for char in text:
                previous=n(basic+FIELDS['edits'],2)
                name,shift=KEYS[char]
                key(name,shift=shift)
                reach('dw($%x)!=%d'%(basic+FIELDS['edits'],previous))

        def output():
            unit=n(job+JOB['unit'],4)
            windows=s.p['build']['memory']['console_storage']['WINDOWS']
            row=windows+s.console['WINDOWS_ITEMS']+(unit&3)*s.console['WINDOW_SIZE']
            require(n(row+s.console['WINDOW_UNIT'],4)==unit,'Stale BASIC output window')
            return read_cells(s.far,n(row+s.console['WINDOW_INSTANCE'],3))

        b.state_save(str(self.bundle/'before-initial-run.altstate2'))
        (self.bundle/'before-initial-run.json').write_text(json.dumps(dict(basic=basic,job=job))+'\n')
        replace('PRINT 1.25*2.0: DO : LOOP')
        key('RETURN',ctrl=True)
        reach('db($%x)=9'%live)
        self.execution_peak=n(live,1)
        for _ in range(1200):
            if b'2.5' in output():break
            frames(3)
        else:raise RuntimeError('Floating-point BASIC output missing')
        menus.select('FastBasic')
        key('K',ctrl=True)
        reach('(dw($%x)=0)&(dw($%x)!=0)'%(job+JOB['phase'],job+JOB['job']))
        require(n(job+JOB['cause'],4)==304 and n(live,1)==9,'Stop did not retain the interpreter')
        replace('PRINT 1.25*2.0')
        previous=n(job+JOB['job'],4)
        key('RETURN',ctrl=True)
        reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job+JOB['phase'],job+JOB['job'],job+JOB['job'],previous))
        require(n(job+JOB['cause'],4)==0 and b'2.5' in output(),'Finite Run failed')
        print('Two shells + BASIC + execution:',self.execution_peak,'Tasks',flush=True)
        self.source_checks(basic=basic,job=job,replace=replace,output=output,
            key=key,reach=reach,frames=frames,menus=menus,n=n,click=click)
        s.save_screen(self.bundle/'twelve-task.png')

        # Quit through the real unsaved-source Discard dialog.
        menus.select('FastBasic')
        key('Q',ctrl=True)
        foreign=json.loads((self.bundle/'bitmap-console/c-image.json').read_text())['symbols']
        contexts=[n(foreign['contexts']+4*i,4) for i in range(4)]
        context=next(c for c in contexts if c and
                     n(c+layout()['Request']['fields']['global']+4,2)==n(basic,2))
        where=context+dict(expected_layout())['C context form']
        reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
        tree=n(n(where,4),4)
        obj=tree+8*24
        click(n(tree+16,2)+n(obj+16,2)+n(obj+20,2)//2,
              n(tree+18,2)+n(obj+18,2)+8)
        reach('db($%x)=7'%live)
        menus.select('Shell')
        for char in 'EXIT\n':s.press(char)
        self.wait_selected(1)
        self.bind(1)
        s.ready()
        require(n(live,1)==6,'Closing the second shell retained a Task')
        self.source_after_quit()
        s.saved['integration']=dict(twelve_tasks=True,pipeline_peak=self.pipeline_peak,
                                    execution_peak=self.execution_peak,run_stop=True,two_shells=True)
        s.save_screen(self.bundle/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def check(bundle,session_class=TwelveTasks,bootstrap=None):
    session=session_class(bundle/'twelve-task',bundle)
    require(json.loads((bundle/'demo-manifest.json').read_text())['task_capacity']==12,
            'Select a twelve-Task demo')
    extracted=bundle/'twelve-task-extracted'
    require(not extracted.exists(),'Use a fresh extraction directory')
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        names=archive.namelist()
        require(len(names)==len(set(names)),'Duplicate ZIP members')
        verified={'exec816-demo/SHA256SUMS'}
        for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe ZIP member')
            member='exec816-demo/'+name
            require(hashlib.sha256(archive.read(member)).hexdigest()==digest,'ZIP checksum: '+name)
            verified.add(member)
        require(verified==set(names),'ZIP checksum coverage differs')
        require(all('/cartridge/' in name for name in names
                    if name.lower().endswith(('.car','.bin'))),
                'Cartridge artifacts must use the distribution cartridge directory')
        archive.extractall(extracted)
    result=run(bundle,boot_smoke=True,distribution_root=extracted/'exec816-demo',integration=session,bootstrap=bootstrap)
    record=dict(status='pass',tier='development',result=result,
                zip_sha256=sha256(bundle/'exec816-demo.zip'),runner_sha256=sha256(Path(__file__)))
    (bundle/'twelve-task-results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    check(parser.parse_args().bundle.resolve())
