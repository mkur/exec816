#!/usr/bin/env python3
"""Bounded QED startup failure on explicitly identified diagnostic SYS copies."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from desktop_menu_check import Menus
from desktop_mouse import schedule
from make_data_disk import make
from native_program import ROOT, require, sha256
from prime_observer import process_record
from qed_demo import verify
from test_demo import run


class StartupFailure:
    def exercise(self,s):
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            target=schedule(s.b,s.p,current,(x,y));s.saved['pointer']=target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),target[0],at('cursorY'),target[1]))
        def click(x,y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(15)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(50)
        s.saved['desktop_menu']={};menus=Menus(s,click,move);menus.select('Shell')
        baseline=s.ledger();fields={n:o for n,_,o in json.loads((ROOT/'abi/process.json').read_text())['record']}
        results=[]
        for cycle in range(2):
            old=s.begin('RUN C:QED.APP');s.ready(old);s.result()
            identity=s.number(s.at('job'));row=process_record(s.far,s.p,identity)
            s.rendezvous('db($%x)=4'%(row+fields['state']))
            result=s.number(row+fields['primary'])
            require(result==20,'Missing/unreadable resource did not return failure')
            menus.select('Shell');s.command('JOBS',b'finished')
            require(s.ledger()==baseline,'Failed startup retained native ownership')
            require(not any('QED' in w['title'] for w in menus.windows()),'Failed startup retained a QED window')
            results.append(dict(identity=identity,result=result,normal_collection=True))
        s.saved['integration']=dict(startup_failures=results,normal_collection=True)
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def check(output,bundle,case):
    require(not output.exists(),'Use a fresh diagnostic output')
    record=json.loads((bundle/'demo-manifest.json').read_text());verify(record,bundle)
    def ignore(directory,names):
        return [n for n in names if n in {'altirra','extracted','emulator.log'} or
                n.endswith(('-results.json','.bgra')) or n=='work-walkthrough.atr']
    shutil.copytree(bundle,output,ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    source=output/'diagnostic-source';shutil.copytree(output/'media',source)
    if case=='missing':(source/'QED.RSC').unlink()
    else:(source/'QED.RSC').write_bytes(b'invalid resource')
    diagnostic=output/'diagnostic-system.atr'
    make(diagnostic,source,binary_names={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()},
         filesystem='sdfs',sector_bytes=256,sectors=2880,label='SYS')
    inputs={str(p.relative_to(ROOT)):sha256(p) for p in (Path(__file__),ROOT/'tools/test_demo.py')}
    result=run(output,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
        media_path=diagnostic,diagnostic_media_sha256=sha256(diagnostic),
        integration=StartupFailure(),profile_commands=False)
    result.update(qualification=False,scope='QED diagnostic '+case+' resource; not a healthy exact-package run',
        zip_sha256=sha256(output/'exec816-demo.zip'),observer_inputs=inputs)
    (output/'startup-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--case',choices=('missing','malformed'),required=True)
    a=p.parse_args();check(a.output.resolve(),a.bundle.resolve(),a.case)
