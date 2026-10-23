#!/usr/bin/env python3
"""One exact-ZIP session through shell and desktop QED parents and save decisions."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from browser_model import select
from colour_desktop_model import FIELDS as D
from filesystem_audit import Audit
from gem_applications import symbols
from native_program import ROOT, require, sha256
from qed_coexist_observe import emitted_offsets
from qed_demo import verify
from test_demo import run
from test_qed_delivery_workflows import Workflow


class FinalWorkflow(Workflow):
    def __init__(self,production,offsets):
        super().__init__(production,offsets,'files')
        self.report['case']='final';self.report['parents']=['shell','desktop']

    def files(self):
        s=self.s
        s.command('CD WORK:REL')
        e=self.launch('RUN QED:QED.APP');self.focus(e);e.loaded('final-empty',[b''])
        e.key('X');e.key('N',ctrl=True);e.form_open();e.alert(2);e.loaded('final-discard',[b''])
        e.key('A');e.save_as('FINAL.TXT','WORK');e.saved('final-save-as',[b'a'],b'WORK:FINAL.TXT',x=1)
        e.key('B');e.key('S',ctrl=True);e.consents();e.saved('final-save-backup',[b'ab'],b'WORK:FINAL.TXT',x=2)
        e.choose('FINAL.TXT','WORK');e.loaded('final-shell-reopen',[b'ab'],path=b'WORK:FINAL.TXT')
        self.retire(e);s.command('CD SYS:');self.report['cases']+=['discard','shell-save-as-backup-reopen']
        directory=s.p['output']/'bitmap-console'
        resident=json.loads((directory/'c-image.json').read_text())['symbols']
        desk=symbols(s.b,s.p,directory,'desktop',s.number(resident['GEMDesktopChildren']))['GEMDesk']
        base=s.number(desk+D['folders']);children=desk+D['children']
        self.menus.select('SYS:');self.folder_path(base,'WORK:')
        def open_file(size):
            self.menus.select('WORK:');select(s,base,'FINAL.TXT',self.click);self.menus.key('RETURN')
            s.rendezvous('(dw($%x)!=0)|(dw($%x)!=0)'%(children,children+2))
            editor=self.editor(s.number(children),size);self.focus(editor);return editor
        e=open_file(2);e.loaded('final-files-open',[b'ab'],path=b'WORK:FINAL.TXT')
        e.key('C');e.key('Q',ctrl=True);e.form_open();e.form_pixels('final-quit-cancel');e.alert(3)
        e.command_idle();e.text_pixels('final-cancel-keeps-document',[b'cab'])
        require(e.text()['dirty'],'Quit Cancel cleared dirty')
        e.key('Q',ctrl=True);e.form_open();e.alert(1);e.consents(backup=True)
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(children,children+2));s.frames(80)
        e=open_file(3);e.loaded('final-files-reopen',[b'cab'],path=b'WORK:FINAL.TXT');self.retire(e,children)
        self.report['cases']+=['files-document-launch','quit-cancel-keeps-document',
            'quit-save-continuation','normal-parent-collection']


def check(output,bundle,layout_from):
    require(not output.exists(),'Use a fresh final delivery output')
    demo=json.loads((bundle/'demo-manifest.json').read_text());verify(demo,bundle)
    production=Path(demo['qed']['production_layout']).parent;offsets=emitted_offsets(production,layout_from)
    inputs={str(p.relative_to(ROOT)):sha256(p) for p in (Path(__file__),ROOT/'tools/test_qed_delivery_workflows.py',
        ROOT/'tools/test_demo.py',ROOT/'tools/qed_coexist_observe.py',ROOT/'tools/qed_saving_observe.py')}
    def ignore(directory,names):
        return [n for n in names if n in {'altirra','extracted','emulator.log'} or
                n.endswith(('-results.json','.bgra')) or n=='work-walkthrough.atr']
    shutil.copytree(bundle,output,ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    result=run(output,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
        integration=FinalWorkflow(production,offsets),profile_commands=False)
    disk=Audit((output/'work-walkthrough.atr').read_bytes());allocation=disk.sdfs()
    require(disk.files['FINAL.TXT']==b'cab' and disk.files['FINAL.BAK']==b'ab','Final saved/backup bytes differ')
    result.update(qualification=False,scope='Exact QED candidate: shell and desktop parents, save/backup/reopen and modified decisions',
        zip_sha256=sha256(output/'exec816-demo.zip'),production_app_sha256=demo['qed']['app_sha256'],
        allocation=allocation,observer_inputs=inputs)
    (output/'delivery-final-results.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--layout-from',type=Path,default=ROOT/'build/qed-separate-disk/layout-fixture')
    a=p.parse_args();check(a.output.resolve(),a.bundle.resolve(),a.layout_from.resolve())
