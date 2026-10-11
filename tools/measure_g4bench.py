#!/usr/bin/env python3
"""Run the packaged G4BENCH through normal shell/input paths, with named loads."""
import argparse
import json
import zipfile
from pathlib import Path
from native_program import ROOT, require, sha256
from desktop_mouse import schedule
from desktop_menu_check import Menus
from gem_applications import symbols
from g4bench_results import read
from stack_budget import stack_usage
from test_demo import run


class BenchmarkDesktop:
    def __init__(self,load):self.load=load;self.result=None

    def exercise(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        shared=json.loads((directory/'c-image.json').read_text())['symbols']
        position=[320,120]
        def move(x,y):
            nonlocal position
            position=schedule(b,s.p,position,(x,y));s.saved['pointer']=position
            at=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),position[0],at('cursorY'),position[1]));s.frames(3)
        def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(20)
        def click(x,y):move(x,y);edge(1);edge(0);s.frames(60)
        def key(name):
            b._cmd_ok('KEY '+name+' down');s.frames(3)
            b._cmd_ok('KEY '+name+' up');s.frames(20)
        def drag(a,z):move(*a);edge(1);move(*z);edge(0);s.frames(100)
        s.saved['desktop_menu']={}
        menus=Menus(s,click,move)
        for title in ('Control Panel','Files')+(() if self.load=='counter' else ('Counter',)):
            menus.select(title);menus.close();s.frames(100)
        peer=None;count=0
        if self.load=='counter':
            peer=symbols(b,s.p,directory,'counter',s.number(shared['GEMDesktopChildren']+4,4))['GEMCounter']
            menus.select('Counter');drag((280,40),(96,40))
        menus.select('Shell')
        previous=s.begin('RUN C:G4BENCH.APP');s.ready(previous);s.result()
        job=s.at('job');identity=s.number(job,4)
        sy=symbols(b,s.p,directory,'g4bench',identity)
        s.rendezvous('dw($%x)=1'%sy['g4b_ready']);s.frames(100)
        # Same canvas in both loads; leave the counter's count visible at left.
        drag((200,48),(272,48))
        if peer:
            # Shell launch tops the shell above the counter. Restore the
            # counter above it, then keep the benchmark's canvas unobscured.
            menus.select('Counter');menus.select('G4BENCH')
        move(630,230);s.frames(100)
        if peer:count=s.number(peer+14,4)
        key('RETURN')
        for row in range(5):
            s.rendezvous('(dw($%x)>=%d)|(dw($%x)=1)'%(sy['g4b_row'],row,sy['g4b_done']))
            print('G4BENCH',self.load,'row',row+1,flush=True)
        s.rendezvous('dw($%x)=1'%sy['g4b_done']);s.frames(100)
        result=read(b,sy)
        require(all(r['status'] in ('complete','low resolution') for r in result['rows']),
                'Benchmark did not complete: '+str(result))
        require(result['save']==1,'Benchmark could not save WORK:G4BENCH.TXT')
        require(result['canvas']==[152,56,480,160],'Unexpected benchmark canvas: '+str(result['canvas']))
        if peer:require(s.number(peer+14,4)>count,'Counter stopped during benchmark')
        result.update(load=self.load,pointer=position,other_apps=['idle shell']+(['counter'] if peer else []),
                      counter_advanced=bool(peer),bank_zero_slice_delta=dict(fixed=0,per_public_task=[0]*8,idle=0))
        screenshot=s.p['output']/('g4bench-'+self.load+'.png');s.save_screen(screenshot)
        result['screenshot_sha256']=sha256(screenshot)
        self.result=result
        s.saved['gem_stacks']=stack_usage(b,s.p['build']['memory'])
        key('ESC');s.rendezvous('db($%x)=3'%(job+12));s.frames(100)
        menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        s.saved['integration']=dict(profile='g4bench',benchmark=result,closed=True,shell=True)
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def measure(bundle,load):
    out=Path(bundle).resolve();extracted=out/('g4bench-extracted-'+load)
    manifest=json.loads((out/'demo-manifest.json').read_text())
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:archive.extractall(extracted)
    exercise=BenchmarkDesktop(load)
    result=run(out,boot_smoke=True,distribution_root=extracted/'exec816-demo',
               integration=exercise,profile_commands=False)
    result.update(scope='Exact OF816 package, normal shell launch, Return, five drawing rows and clean close',
                  benchmark=exercise.result,archive_sha256=sha256(out/'exec816-demo.zip'),
                  actionc_revision=manifest['kernel']['revision'],
                  emulator_sha256=sha256(ROOT/'build/mouse-bridge/AltirraBridgeServer'),
                  application=json.loads((out/'bitmap-console/apps/g4bench/app.json').read_text()),
                  donor=json.loads((out/'bitmap-console/apps/g4bench/g4bench.json').read_text()),
                  runner_sha256=sha256(Path(__file__)))
    (out/('g4bench-'+load+'.json')).write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--load',choices=('idle','counter','both'),default='both')
    args=parser.parse_args()
    for load in ('idle','counter') if args.load=='both' else (args.load,):measure(args.bundle,load)
