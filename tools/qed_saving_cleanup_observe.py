"""Loaded-editor post-publication cleanup failure, with real native files."""
import struct
from native_program import require
from qed_saving_observe import SavingEditor,interact as normal


def interact(b,p,app,record,owner):
    e=SavingEditor(b,p,app,record,owner)
    if e.native('cycle')!=0:
        record['qed_editing'].pop();return normal(b,p,app,record,owner)
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=1'%e.at('phase'));e.frames(40)
    e.launched('cleanup-launch',[b'd'],1,path=b'D1:LONG.TXT')
    b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'));e.click(100,44)
    e.key('A');e.save_as('CLEAN.TXT','D1');e.saved('cleanup-initial-save',[b'ad'],b'D1:CLEAN.TXT',x=1)
    e.key('B');e.key('S',ctrl=True);e.consents();e.saved('cleanup-first-backup',[b'abd'],b'D1:CLEAN.TXT',x=2)
    e.key('C');e.put('QedSaveFailDelete',1);e.key('S',ctrl=True);e.consents(backup=True)
    e.report();e.selection('published-cleanup-failure-dirty',[b'abcd'],None,3,0)
    require(e.text()['dirty'] and e.name()==b'D1:CLEAN.TXT' and e.get(e.sy['recovery'],4),
            'Published cleanup failure lost dirty identity or recovery')
    e.key('M',ctrl=True);e.form_open();e.alert(1);e.report(review=True);e.form_open();e.alert(3);e.command_idle()
    e.selection('recovery-details-return-to-cancel',[b'abcd'],None,3,0)
    e.key('M',ctrl=True);e.form_open();e.alert(2);e.selector_ready();e.form_key('ESC');e.command_idle()
    e.selection('save-as-selector-cancel',[b'abcd'],None,3,0);require(e.text()['dirty'],'Cancelled selector cleared dirty')
    e.save_as('RECOVER.TXT','D1');e.saved('fresh-save-after-cleanup-failure',[b'abcd'],b'D1:RECOVER.TXT',x=3)
    b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
    b.memload(e.at('control'),struct.pack('<H',101));return e.retire_key('Q',ctrl=True)
