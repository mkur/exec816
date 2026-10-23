"""One current Open/Edit/Find/Save/Close workflow with independent pixels."""
import struct
from native_program import require
from qed_saving_observe import SavingEditor
from qed_editing_observe import Editor
from qed_documents_observe import combined_session
from qed_viewport_observe import document,peer_pixels
from test_qed_documents import fixtures


def expected():
    original=fixtures()['SESSION.TXT'].split(b'\n');last=len(original)-2
    one=[*original[:last],original[last][:269],b'a'+original[last][269:],b'']
    two=[*one[:last+1],b'ab'+original[last][269:],b'']
    three=[b'c',*two]
    return original,one,two,three


def interact(b,p,app,record,owner):
    e=SavingEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        e.launched('gate-launch',[b'd'],1,path=b'D1:LONG.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'));e.click(100,44)
        combined_session(e);original,one,two,three=expected();last=len(original)-2
        view=document(e)[:2];e.save_as('COMBO.TXT','D1')
        e.saved('gate-save-as',original,b'D1:COMBO.TXT',x=269,y=last);e.clipboard([b'head'])
        require(document(e)[:2]==view,'Save As changed the panned viewport')
        e.key('RETURN');e.key('A');e.selection('gate-long-edit',one,None,1,last+1)
        e.key('S',ctrl=True);e.form_open();e.form_pixels('gate-default-cancel');e.form_key('RETURN');e.command_idle()
        require(e.text()['dirty'],'Cancelled Save cleared modified state')
        e.key('S',ctrl=True);e.consents(pixels=True);e.saved('gate-named-backup',one,b'D1:COMBO.TXT',x=1,y=last+1)
        e.peer_command(2);e.frames(30);e.covered=[(0,60,224,172)]
        e.selection('gate-covered',one,None,1,last+1);peer_pixels(e,'gate-peer')
        e.click(100,44);e.frames(30);e.covered=[];e.selection('gate-exposed',one,None,1,last+1)
        e.key('B');e.put('QedSaveFailWrite',1);e.key('S',ctrl=True);e.consents(backup=True);e.report()
        e.selection('gate-write-failure',two,None,2,last+1)
        e.put('QedSaveFailClose',1);e.key('S',ctrl=True);e.consents(backup=True);e.report()
        require(e.get(e.sy['recovery'],4) and e.text()['dirty'],'Uncertain Save lost recovery')
        e.key('M',ctrl=True);e.form_open();e.form_key('RETURN');e.command_idle()
        require(e.get(e.sy['recovery'],4),'Default recovery Cancel lost record')
        e.key('M',ctrl=True);e.form_open();e.alert(2);e.choose_path('FRESH.TXT','D1')
        e.saved('gate-fresh-save',two,b'D1:FRESH.TXT',x=2,y=last+1);e.clipboard([b'head'])
        e.choose('FRESH.TXT','D1');e.loaded('gate-reopen',two,path=b'D1:FRESH.TXT')
        e.key('RETURN');e.key('MINUS',ctrl=True);e.key('C');e.selection('gate-modified-open-source',three,None,1,0)
        e.choose('SESSION.TXT','D1');e.form_open();before=e.get(e.sy['QedSaveWriteCalls'])
        e.put('QedSaveHoldWrite',1);e.alert(1);e.consents();e.write_held(before)
        live=list(struct.unpack('<4I',b.memdump(e.sy['totals'],16)))
        paints=e.get(e.peer()['QedPeerPaints']);e.reach('dw($%x)!=%d'%(e.peer()['QedPeerPaints'],paints))
        e.scene['combined_live_save']=dict(private_heap=live,candidate_lines=e.get(e.sy['candidate']+e.offsets[17],4),
            clipboard=True,undo=True,peer_progress=True)
        e.put('QedSaveHoldWrite',0);e.loaded('gate-modified-open',original,path=b'D1:SESSION.TXT');e.clipboard([b'head'])
        e.key('RETURN');e.key('MINUS',ctrl=True);e.key('D')
        dirty=[b'd',*original];e.close();e.form_open();e.alert(3);e.command_idle()
        e.selection('gate-close-cancel',dirty,None,1,0)
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101));e.key('Q',ctrl=True);return e.alert(2,retiring=True)
    if cycle==1:
        e.form_open();e.alert(1);e.loaded('gate-failed-launch',[b'']);e.key('A')
        e.key('N',ctrl=True);e.form_open();e.alert(1);e.choose_path('EMPTY.TXT','RAM')
        e.loaded('gate-save-before-new',[b'']);b.memload(e.at('control'),struct.pack('<H',2))
        return e.retire_key('Q',ctrl=True)
    if cycle==2:
        path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT'
        e.launched('gate-long-path',[b'deep'],4,path=path);e.key('A')
        b.memload(e.at('control'),struct.pack('<H',3));e.close();e.form_open();e.alert(1)
        for _ in range(2):e.form_open();e.alert(1)
        return
    from qed_cleanup_stop_observe import large_stop
    return large_stop(e)
