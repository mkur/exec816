#!/usr/bin/env python3
"""Physical delivery workflows against an extracted, unchanged QED boot ZIP."""
import argparse
import hashlib
import json
import shutil
import zipfile
from pathlib import Path

from browser_model import FIELDS as F, select, wait_listing
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from filesystem_audit import Audit
from gem_applications import symbols
from make_data_disk import make
from native_program import ROOT, require, sha256
from qed_coexist_observe import ProductionEditor, emitted_offsets, heap_checkpoint
from qed_demo import verify, SAMPLE
from test_demo import run
from test_shell_core import KEYS

FORMATS = {'LF.TXT': b'one\nlast\n', 'CRLF.TXT': b'one\r\nlast',
           'TABS.TXT': b'one\ttwo\n', 'EMPTY.TXT': b'', 'NOEND.TXT': b'last',
           'BOUND.TXT': b'x'*1023, 'OVER.TXT': b'x'*1024,
           'MIXED.TXT': b'a\nb\r\n', 'CR.TXT': b'a\rb', 'NUL.TXT': b'a\0b'}


class Workflow:
    def __init__(self, production, offsets, case, work_from=None):
        self.production, self.offsets, self.case, self.work_from = production, offsets, case, work_from
        self.report = dict(case=case, cases=[], lifetimes=0, physical_input=True)

    def prepare_work(self, target, item):
        if self.work_from:
            shutil.copyfile(self.work_from, target)
            return
        source = target.parent/'delivery-work-source'
        shutil.copytree(target.parent/'workspace-source', source)
        for name, content in FORMATS.items(): (source/name).write_bytes(content)
        (source/'REL').mkdir()
        (source/'REL/REL.TXT').write_bytes(b'relative\n')
        if self.case == 'files':
            (source/'DESKTOP.CFG').write_bytes(b'EXEC816_DESKTOP 1\nFOLDER 120 16 432 220 1 1 SYS:\nASSOC TXT C:QED.APP\n')
        make(target, source, binary_names=set(FORMATS), filesystem='sdfs', sector_bytes=256,
             sectors=2880, label='WORK')

    def exercise(self, s):
        self.s = s
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x, y):
            position = [s.number(at(n), 2) for n in ('cursorX','cursorY')]
            target = schedule(s.b, s.p, position, (x,y));s.saved['pointer'] = target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' % (at('cursorX'),target[0],at('cursorY'),target[1]))
        def click(x, y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(15)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(50)
        self.move,self.click = move,click
        s.saved['desktop_menu'] = {};self.menus = Menus(s,click,move)
        self.menus.select('Shell');self.baseline = s.ledger()
        if self.case == 'files':self.files()
        elif self.case == 'shell':self.shell()
        elif self.case == 'reopen':
            e=self.launch('RUN C:QED.APP WORK:SAMPLE.TXT')
            self.focus(e);e.loaded('persistent-reopen',(b'cab'+SAMPLE).split(b'\n'),path=b'WORK:SAMPLE.TXT')
            self.retire(e);self.report['cases'].append('persistent-reopen')
        else:self.storage()
        self.menus.select('Shell')
        require(s.ledger()==self.baseline,'Delivery workflow retained native ownership')
        self.report['normal_collection']=True;s.saved['integration']=self.report
        s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

    def editor(self, identity, expected_bytes=None):
        self.s.frames(80)
        e=ProductionEditor(self.s,self.production,self.offsets,identity,self.s.p['output'],self.report,self.report['lifetimes'])
        e.reach('(dw($%x)!=0)|(dw($%x)!=0)'%(e.sy['text_list'],e.sy['text_list']+2))
        e.reach('dw($%x)=0'%e.sy['QedStarting'])
        if expected_bytes is not None:
            e.reach('(dw($%x)=%d)&(dw($%x)=%d)'%(e.sy['source_bytes'],expected_bytes&65535,e.sy['source_bytes']+2,expected_bytes>>16))
        self.report['lifetimes']+=1
        return e

    def launch(self, command, expected_bytes=None):
        print('Delivery launch:',command,flush=True)
        self.menus.select('Shell')
        old=self.s.begin(command);self.s.ready(old);self.s.result()
        return self.editor(self.s.number(self.s.at('job')),expected_bytes)

    def focus(self,e):
        e.command_idle();self.s.frames(50);e.click(*e.cell(0,0));e.move(632,20)

    def retire(self,e,desktop=None):
        e.key('Q',ctrl=True)
        if desktop is None:
            self.s.rendezvous('db($%x)=4'%(e.owner['record']+e.fields['state']))
            self.s.frames(80);self.menus.select('Shell');self.s.command('JOBS',b'finished')
        else:
            self.s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desktop,desktop+2));self.s.frames(80)

    def shell(self):
        e=self.launch('RUN C:QED.APP');self.focus(e);e.loaded('no-argument',[b'']);self.retire(e)
        self.report['cases'].append('shell-no-argument')
        e=self.launch('RUN C:QED.APP "WORK:SAMPLE.TXT"',len(SAMPLE));self.focus(e)
        e.loaded('quoted-argument',SAMPLE.split(b'\n'),path=b'WORK:SAMPLE.TXT');self.retire(e)
        self.report['cases'].append('shell-quoted-path')
        self.s.command('CD WORK:REL')
        e=self.launch('RUN C:QED.APP REL.TXT',9);self.focus(e)
        e.loaded('relative-argument',[b'relative',b''],path=b'WORK:REL/REL.TXT');self.retire(e)
        self.s.command('CD SYS:');self.report['cases'].append('inherited-relative-path')
        for argument in ('WORK:ABSENT.TXT','WORK:NUL.TXT','WORK:SAMPLE.TXT WORK:LF.TXT'):
            e=self.launch('RUN C:QED.APP '+argument);e.form_open();e.form_pixels('rejected-launch')
            e.alert(1);self.focus(e);e.loaded('rejected-argument',[b'']);self.retire(e)
            self.report['cases'].append('rejected:'+argument)
        self.menus.select('Shell');old=self.s.begin('RUN C:QED.APP "WORK:SAMPLE.TXT')
        self.s.ready(old);self.s.result(error=115)
        require(self.s.ledger()==self.baseline,'Rejected shell syntax retained ownership')
        self.report['cases'].append('shell-rejected-malformed-syntax')

    def folder_path(self,base,value):
        def key(name,shift=False):
            if shift:self.s.b._cmd_ok('KEY SHIFT down')
            self.s.b._cmd_ok('KEY '+name+' down');self.s.frames(3)
            self.s.b._cmd_ok('KEY '+name+' up')
            if shift:self.s.b._cmd_ok('KEY SHIFT up')
            self.s.frames(10)
        key('P');self.s.rendezvous('dw($%x)=1'%(base+F['dialog']))
        previous=self.s.far(base+F['editText'],128).split(b'\0')[0]
        for _ in previous:key('BACKSPACE')
        for ch in value:k,shift=KEYS[ch];key(k,shift)
        key('RETURN');self.s.rendezvous('dw($%x)=0'%(base+F['dialog']));wait_listing(self.s,base)

    def files(self):
        s=self.s;directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        desk=symbols(s.b,s.p,directory,'desktop',s.number(resident['GEMDesktopChildren']))['GEMDesk']
        s.rendezvous('dw($%x)=1'%(desk+D['ready']))
        base=s.number(desk+D['folders']);require(base,'No initial Files folder')
        require(s.number(desk+D['settingsLoaded'],2)==1,'Association settings not loaded')
        children=desk+D['children']
        self.menus.select('SYS:');self.folder_path(base,'SYS:C')
        for activation in ('keyboard','double-click'):
            select(s,base,'QED.APP',self.click)
            if activation=='keyboard':self.menus.key('RETURN')
            else:
                for _ in range(2):
                    s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(3)
                    s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(3)
                s.frames(50)
            s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)'%(children,children+2))
            identity=s.number(children);e=self.editor(identity);self.focus(e);e.loaded('files-empty',[b''])
            self.retire(e,children);self.report['cases'].append('files-app-'+activation)
            self.menus.select('SYS:C')
        self.folder_path(base,'WORK:');select(s,base,'SAMPLE.TXT',self.click);self.menus.key('RETURN')
        s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)'%(children,children+2))
        identity=s.number(children);e=self.editor(identity,len(SAMPLE));self.focus(e)
        e.loaded('files-association',SAMPLE.split(b'\n'),path=b'WORK:SAMPLE.TXT')
        self.menus.select('WORK:');self.click(296,8);self.click(304,72)
        s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)'%(children+4,children+6))
        self.menus.select('WORK:');require(s.ledger()['live']==8,'Counter+QED did not occupy capacity')
        admitted=s.far(children,12);before=heap_checkpoint(s.rendezvous,s.far,s.p['build']['memory'])
        self.click(296,8);self.click(304,39)
        s.rendezvous('db($%x)=67'%(desk+D['status']))
        s.frames(50)
        require(s.far(children,12)==admitted and s.ledger()['live']==8,'Full-capacity launch changed children')
        status=s.far(desk+D['status'],65).split(b'\0')[0]
        require(status.startswith(b'Cannot launch'),'Full-capacity launch did not report failure')
        after=heap_checkpoint(s.rendezvous,s.far,s.p['build']['memory'])
        require(before['extents']==after['extents'],'Rejected launch retained upper backing')
        self.menus.select('Counter');self.menus.close()
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(children+4,children+6))
        self.report['cases'].append('full-capacity-launch-refused-and-unwound')
        self.menus.select('WORK:');x,y=[s.number(base+F['work']+i*2,2) for i in range(2)]
        self.click(x,y-8);s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['folders'],desk+D['folders']+2))
        require(s.number(children)==identity,'Folder close retired desktop-owned QED')
        self.focus(e);e.text_pixels('survives-folder-close',SAMPLE.split(b'\n'));self.retire(e,children)
        # Restore a normal folder before comparing baseline lock/owner counts.
        self.click(600,236);s.frames(100)
        self.click(296,8);self.click(304,28)
        s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)'%(desk+D['folders'],desk+D['folders']+2))
        base=s.number(desk+D['folders']);wait_listing(s,base)
        self.report['cases'].append('association-child-survives-folder-close')

    def storage(self):
        e=self.launch('RUN C:QED.APP');self.focus(e);e.loaded('storage-new',[b''])
        for name in ('LF.TXT','CRLF.TXT','TABS.TXT','EMPTY.TXT','NOEND.TXT','BOUND.TXT'):
            e.choose(name,'WORK');raw=FORMATS[name];ending=0 if b'\r\n' in raw else 1
            lines=raw.replace(b'\r\n',b'\n').split(b'\n')
            e.loaded('format-'+name,lines,ending=ending,path=('WORK:'+name).encode())
            e.key('S',ctrl=True);e.consents();e.command_idle()
            require(not e.text()['dirty'],'Round trip did not commit')
            self.report['cases'].append('roundtrip:'+name)
        e.choose('LF.TXT','WORK');e.loaded('rejection-baseline',[b'one',b'last',b''],path=b'WORK:LF.TXT')
        for name in ('OVER.TXT','MIXED.TXT','CR.TXT','NUL.TXT'):
            e.choose(name,'WORK');e.form_open();e.form_pixels('unsupported-'+name);e.alert(1)
            e.command_idle();e.text_pixels('preserved-'+name,[b'one',b'last',b''])
            self.report['cases'].append('non-destructive-reject:'+name)
        self.retire(e)


def check(output,bundle,case,layout_from,work_from=None):
    require(not output.exists(),'Use a fresh delivery workflow directory')
    record=json.loads((bundle/'demo-manifest.json').read_text());verify(record,bundle)
    production=Path(record['qed']['production_layout']).parent
    offsets=emitted_offsets(production,layout_from)
    def ignore(directory,names):
        return [n for n in names if n in {'altirra','extracted','emulator.log'} or
                n.endswith(('-results.json','.bgra')) or n=='work-walkthrough.atr']
    shutil.copytree(bundle,output,ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:
        for line in archive.read('exec816-demo/SHA256SUMS').decode().splitlines():
            digest,name=line.split('  ',1)
            require(hashlib.sha256(archive.read('exec816-demo/'+name)).hexdigest()==digest,'Changed ZIP member')
        archive.extractall(output/'extracted')
    observer=Workflow(production,offsets,case,work_from)
    result=run(output,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
               integration=observer,profile_commands=False)
    disk=Audit((output/'work-walkthrough.atr').read_bytes());allocation=disk.sdfs()
    if case=='storage':
        for name in FORMATS:
            require(disk.files[name]==FORMATS[name],'Roundtrip/rejection changed bytes: '+name)
        for name in ('LF','CRLF','TABS','EMPTY','NOEND','BOUND'):
            require(disk.files[name+'.BAK']==FORMATS[name+'.TXT'],'Roundtrip backup differs: '+name)
    result.update(qualification=False,scope='QED delivery '+case,allocation=allocation,
        zip_sha256=sha256(bundle/'exec816-demo.zip'),production_app_sha256=record['qed']['app_sha256'],
        observer_inputs={str(Path(__file__).relative_to(ROOT)):sha256(Path(__file__))})
    (output/'delivery-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--case',choices=('shell','files','storage','reopen'),required=True)
    p.add_argument('--layout-from',type=Path,default=ROOT/'build/qed-coexist/qc3-caption/app')
    p.add_argument('--work-from',type=Path)
    a=p.parse_args();check(a.output.resolve(),a.bundle.resolve(),a.case,a.layout_from.resolve(),a.work_from)
