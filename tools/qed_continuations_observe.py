"""Physical modified decisions and fresh post-save reads."""
import struct
from native_program import require
from qed_saving_observe import SavingEditor
from qed_editing_observe import Editor
from test_qed_documents import fixtures


def interact(b,p,app,record,owner,short_launch=False):
    e=SavingEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        e.launched('continuation-launch',[b'd'] if short_launch else fixtures()['LONG.TXT'].split(b'\n'),
            1 if short_launch else 81920,path=b'D1:LONG.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'));e.click(100,44)
        e.key('N',ctrl=True);e.loaded('continuation-new',[b''])
        for key in ('A','B','C'):e.key(key)
        e.key('N',ctrl=True);e.form_open();e.form_key('RETURN');e.command_idle()
        e.selection('new-default-cancel',[b'abc'],None,3,0)
        e.key('N',ctrl=True);e.form_open();e.alert(1);e.selector_ready();e.form_key('ESC');e.command_idle()
        e.selection('new-save-selector-cancel',[b'abc'],None,3,0)
        e.choose('SMALL.TXT');e.form_open();e.alert(3);e.command_idle()
        e.selection('open-cancel',[b'abc'],None,3,0)
        e.choose('SMALL.TXT');e.form_open();e.alert(1);e.choose_path('SAVED.TXT','RAM');e.command_idle()
        small=fixtures()['SMALL.TXT'].split(b'\n')
        e.loaded('open-after-unnamed-save',small,path=b'D1:SMALL.TXT')
        e.key('X');e.key('N',ctrl=True);e.form_open();e.alert(2);e.loaded('new-discard',[b''])
        for key in ('X','Y','Z'):e.key(key)
        e.choose('SAVED.TXT','RAM');e.form_open();e.alert(1);e.choose_path('SAVED.TXT','RAM');e.consents()
        e.loaded('save-as-to-pending-open-rereads',[b'xyz'],path=b'RAM:SAVED.TXT')
        e.save_as('SAVED.TXT','D1');e.command_idle()
        lines=[b'xyz']
        for volume,key in (('D1','A'),('SYS','B'),('QW','C')):
            e.key(key);lines=[key.lower().encode()+lines[0]]
            e.choose('SAVED.TXT',volume);e.form_open();e.alert(1)
            e.consents(backup=volume!='D1');e.loaded('fresh-reread-'+volume,lines,path=b'D1:SAVED.TXT')
        e.key('N',ctrl=True);e.loaded('reread-unnamed-new',[b''])
        for key in ('A','B','C'):e.key(key)
        e.choose('SMALL.TXT','D1');e.form_open();e.alert(1);e.selector_ready()
        e.put('QedSaveFailOpen',1);e.choose_path('REREAD.TXT','D1');e.form_open();e.alert(1);e.command_idle()
        lines=[b'abc'];e.selection('reread-failure-retains-saved-as',lines,None,3,0)
        require(not e.text()['dirty'] and e.name()==b'D1:REREAD.TXT','Reread failure lost successful Save As')
        require(e.get(e.sy['candidate']+e.offsets[17],4)==0,'Reread failure retained candidate')
        e.key('D');lines=[b'abcd'];e.key('N',ctrl=True);e.form_open()
        e.put('QedSaveFailWrite',1);e.alert(1);e.consents();e.report()
        e.selection('failed-save-cancels-new',lines,None,4,0);require(e.text()['dirty'],'Failed continuation cleaned text')
        e.save_as('FRESH.TXT','D1');e.command_idle()
        # Supersede a pending New while its Save borrows the old document.
        e.key('E');e.key('N',ctrl=True);e.form_open();e.put('QedSaveHoldRename',1)
        before=e.get(e.sy['QedSaveRenameCalls']);e.alert(1);e.consents()
        e.reach('dw($%x)!=%d'%(e.sy['QedSaveRenameCalls'],before),timeout=180)
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101));e.close();e.put('QedSaveHoldRename',0)
        e.reach('(dw($%x)=10)&(dw($%x)=0)'%(e.sy['command_kind'],e.sy['saving_kind']),timeout=240)
        require(e.text()['lines']==[b'abcde'] and not e.text()['dirty'],
            'New continued before the newer Close')
        require(e.get(e.sy['candidate']+e.offsets[17],4)==0,'Superseded New retained its candidate')
        e.scene['continuation_gate']=dict(unnamed_save=True,default_cancel=True,same_target_reread=True,
            physical_sys_assign=True,reread_failure_keeps_saved=True,failed_save_cancels_new=True,
            newer_close_supersedes_new=True)
        return
    if cycle==1:
        e.form_open();e.alert(1);e.loaded('continuation-missing-launch',[b'']);e.key('A')
        e.key('Q',ctrl=True);e.form_open();e.alert(1);e.selector_ready();e.form_key('ESC');e.command_idle()
        e.selection('quit-save-selector-cancel',[b'a'],None,1,0)
        e.close();e.form_open();e.alert(3);e.command_idle();e.selection('close-cancel',[b'a'],None,1,0)
        b.memload(e.at('control'),struct.pack('<H',2));e.close();e.form_open();e.alert(1)
        e.choose_path('EMPTY.TXT','RAM',settle=False);return
    if cycle==2:
        path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT'
        e.launched('continuation-deep-launch',[b'deep'],4,path=path)
        e.key('A');e.choose('SMALL.TXT','D1');e.form_open();e.alert(2)
        small=fixtures()['SMALL.TXT'].split(b'\n');e.loaded('open-discard',small,path=b'D1:SMALL.TXT')
        e.key('B');e.key('Q',ctrl=True);e.form_open();e.alert(3);e.command_idle()
        e.selection('quit-cancel',[b'balpha\tbeta',b'second',b''],None,1,0)
        b.memload(e.at('control'),struct.pack('<H',3));e.key('Q',ctrl=True);return e.alert(2,retiring=True)
    e.launched('continuation-stop-launch',[b'one',b'last'],9,ending=0,path=b'D1:CRLF.TXT')
    e.key('A');e.key('N',ctrl=True);e.form_open()
    b.memload(e.at('control'),struct.pack('<H',4));e.reach('dw($%x)=104'%e.at('phase'))
    e.reach('dw($%x)=10'%e.sy['command_kind'])
    e.form_open();e.alert(3);e.command_idle();e.selection('stop-cancel-candidate-retired',[b'aone',b'last'],None,1,0)
    require(e.get(e.sy['candidate']+e.offsets[17],4)==0,'Declined Stop retained candidate')
    b.memload(e.at('control'),struct.pack('<H',104));e.form_open();e.alert(1)
    e.form_open();return e.alert(1,retiring=True)
