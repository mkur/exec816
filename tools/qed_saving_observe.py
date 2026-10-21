"""Physical saving over the actual loaded editor, with independent pixels."""
import struct
from native_program import require
from qed_documents_observe import DocumentEditor
from qed_editing_observe import Editor
from test_qed_documents import fixtures

class SavingEditor(DocumentEditor):
    global_commands=DocumentEditor.global_commands+('S','M','U','Q')
    def alert(self,button,retiring=False):
        # Three-button recovery/modified decisions have a different default.
        # Select the requested button physically instead of assuming button 2.
        self.frames(30);session=self.form();require(session,'Expected native alert')
        for _ in range(button-1):self.form_key('TAB',settle=8)
        if retiring:return self.retire_key('SPACE')
        self.form_key('SPACE',settle=0)
        from generate_aes_server import expected_layout
        at=self.context()+dict(expected_layout())['C context form']
        self.reach('(dw($%x)=0)&(dw($%x)=0)'%(at,at+2))
        self.frames(10)
    def command_idle(self):
        self.reach('(dw($%x)=0)&(dw($%x)=0)'%(self.sy['command_kind'],self.sy['saving_kind']),timeout=480)
        self.frames(10)
    def save_as(self,leaf,volume,menu=False):
        if menu:self.menu('TFILE','MSAVENEW')
        else:self.key('M',ctrl=True)
        self.choose_path(leaf,volume);self.command_idle()
    def saved(self,name,lines,path,span=None,x=None,y=0):
        self.command_idle();self.selection(name,lines,span,x if x is not None else len(lines[-1]),y)
        require(not self.text()['dirty'] and self.name()==path,name+': identity/dirty did not commit')
        require(self.get(self.sy['undo_valid'],1)==1,name+': Save discarded Undo')
    def consents(self,backup=False,pixels=False):
        self.form_open()
        if pixels:self.form_pixels('replace-default-cancel')
        self.alert(1)
        if backup:self.form_open();self.alert(1)
    def report(self,details=True,review=False):
        self.form_open();self.form_pixels('save-failure-summary')
        if not details:self.alert(2);self.command_idle();return
        self.alert(1)
        for _ in range(16):
            if self.get(self.sy['saving_kind'])!=6:break
            self.form_open();self.alert(1)
        if not review:self.command_idle()
    def put(self,name,value):self.b.memload(self.sy[name],struct.pack('<H',value))
    def write_held(self,before):self.reach('dw($%x)!=%d'%(self.sy['QedSaveWriteCalls'],before),timeout=180)


def interact(b,p,app,record,owner):
    e=SavingEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        e.launched('saving-launch',fixtures()['LONG.TXT'].split(b'\n'),81920,path=b'D1:LONG.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'))
        e.click(100,44);e.key('N',ctrl=True);e.loaded('saving-new',[b''])
        for key in ('A','B','C'):e.key(key)
        e.select('saving-range',[b'abc'],e.cell(0,0),e.cell(1,0),(0,0,0,1),(1,0))
        e.key('C',ctrl=True);e.clipboard([b'a'])
        e.save_as('SAVED.TXT','RAM',menu=True)
        e.saved('ram-save-as-full-document',[b'abc'],b'RAM:SAVED.TXT',(0,0,0,1),1);e.clipboard([b'a'])
        e.key('Z',ctrl=True);e.selection('saved-undo-retained',[b''],None,0,0)
        e.key('Z',ctrl=True);e.selection('saved-undo-toggle',[b'abc'],(0,0,0,1),1,0)
        e.key('ESC');e.click(*e.cell(3,0));e.key('D')
        e.key('S',ctrl=True);e.form_open();e.form_pixels('save-cancel-default')
        e.form_key('RETURN');e.command_idle();e.selection('save-cancel-keeps-document',[b'abcd'],None,4,0)
        require(e.text()['dirty']==1,'Cancelled Save cleared dirty')
        e.menu('TFILE','MSAVE');e.consents();e.saved('ram-named-save',[b'abcd'],b'RAM:SAVED.TXT')
        e.key('E');e.key('Z',ctrl=True);e.selection('save-typing-boundary',[b'abcd'],None,4,0)
        e.key('Z',ctrl=True);e.selection('save-typing-toggle',[b'abcde'],None,5,0)
        e.save_as('SAVED.TXT','D1');e.saved('disk-save-as',[b'abcde'],b'D1:SAVED.TXT')
        e.key('F');before=e.get(e.sy['QedSaveWriteCalls']);e.put('QedSaveHoldWrite',1)
        e.key('S',ctrl=True);e.consents();e.write_held(before)
        paints=e.get(e.peer()['QedPeerPaints']);e.reach('dw($%x)!=%d'%(e.peer()['QedPeerPaints'],paints))
        Editor.key(e,'X',dispatch=False);Editor.key(e,'Y',dispatch=False)
        e.put('QedSaveHoldWrite',0);e.reach('dw($%x)=7'%e.sy['saving_kind'],timeout=240)
        Editor.key(e,'ESC',dispatch=False);e.saved('busy-input-dropped',[b'abcdef'],b'D1:SAVED.TXT')
        e.key('G');e.put('QedSaveFailWrite',1);e.key('S',ctrl=True);e.consents(backup=True)
        e.report();e.selection('failed-write-keeps-document',[b'abcdefg'],None,7,0)
        require(e.text()['dirty']==1 and e.name()==b'D1:SAVED.TXT','Failure committed state')
        e.key('S',ctrl=True);e.consents(backup=True);e.saved('save-after-logical-failure',[b'abcdefg'],b'D1:SAVED.TXT')
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101))
        before=e.get(e.sy['QedSaveWriteCalls']);e.put('QedSaveHoldWrite',1);e.put('QedSaveFailClose',1)
        e.key('S',ctrl=True);e.consents(backup=True);e.write_held(before)
        e.put('QedSaveFailAlert',1);e.put('QedSaveHoldWrite',0)
        e.reach('dw($%x)=1'%e.sy['QedSaveAlertFailures'],timeout=240)
        require(e.get(e.sy['active_save'],4) and e.text()['dirty']==1,'Reporting failure lost record/document')
        Editor.key(e,'ESC',dispatch=False);e.report()
        recovery=e.get(e.sy['recovery'],4);require(recovery,'Uncertain Close lost recovery')
        e.selection('close-uncertain-forces-dirty',[b'abcdefg'],None,7,0)
        e.key('S',ctrl=True);e.form_open();e.alert(3);e.command_idle()
        require(e.get(e.sy['recovery'],4)==recovery,'Cancelled recovery review overwrote record')
        e.close();e.form_open();e.alert(2);e.command_idle()
        e.selection('failed-save-close-cancel',[b'abcdefg'],None,7,0)
        e.put('QedSaveHoldRename',1);before=e.get(e.sy['QedSaveRenameCalls'])
        e.key('S',ctrl=True);e.form_open();e.alert(2);e.consents(backup=True)
        e.reach('dw($%x)!=%d'%(e.sy['QedSaveRenameCalls'],before),timeout=180)
        e.close();e.put('QedSaveHoldRename',0)
        e.scene['saving_gate']=dict(full_document=True,undo=True,typing_boundary=True,busy_keys=True,
            reporting_allocation_refusal=True,recovery_retained=True,deferred_close=True)
        return
    if cycle==1:
        e.form_open();e.alert(1);e.loaded('saving-invalid-launch',[b''])
        e.save_as('EMPTY.TXT','RAM');e.command_idle()
        require(e.name()==b'RAM:EMPTY.TXT' and not e.text()['dirty'],'Empty Save As failed')
        e.choose('EMPTY.TXT','RAM');e.loaded('reopen-empty-save',[b''],path=b'RAM:EMPTY.TXT')
        b.memload(e.at('control'),struct.pack('<H',2));return e.retire_key('Q',ctrl=True)
    if cycle==2:
        path=b'D1:'+b'LONGNAME.LNG/'*16+b'DEEP.TXT'
        e.launched('long-canonical-launch',[b'deep'],4,path=path)
        e.key('A');e.put('QedSaveFailRename',2);e.key('S',ctrl=True)
        # Both the consent and recovery pages show the complete >160-byte path.
        for _ in range(2):e.form_open();e.form_pixels('long-target-consent');e.alert(1)
        e.report();e.selection('long-publication-failure-keeps-document',[b'adeep'],None,1,0)
        require(e.name()==path and e.text()['dirty']==1,'Long failure committed state')
        b.memload(e.at('control'),struct.pack('<H',3));e.key('Q',ctrl=True);return e.alert(1,retiring=True)
    e.launched('saving-stop-launch',[b'one',b'last'],9,ending=0,path=b'D1:CRLF.TXT')
    e.key('A');before=e.get(e.sy['QedSaveWriteCalls']);e.put('QedSaveHoldWrite',1)
    e.key('S',ctrl=True);e.consents();e.write_held(before)
    b.memload(e.at('control'),struct.pack('<H',4));e.reach('dw($%x)=104'%e.at('phase'))
    e.put('QedSaveHoldWrite',0);e.form_open();e.alert(2);e.command_idle()
    e.selection('staging-stop-cancel',[b'aone',b'last'],None,1,0)
    b.memload(e.at('control'),struct.pack('<H',104));return e.alert(1,retiring=True)
