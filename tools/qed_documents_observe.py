"""Physical Open/New policy over the real loaded QED and native read paths."""
import struct
from native_program import require
from qed_dialogs_observe import DialogEditor
from qed_editing_observe import Editor
from file_selector_model import FORM_SELECTOR,FIELDS as F
from test_shell_core import KEYS
from test_qed_documents import fixtures
from qed_viewport_observe import document

class DocumentEditor(DialogEditor):
    global_commands=DialogEditor.global_commands+('N','O')
    def name(self):
        return self.b.memdump(self.get(self.sy['text_list'],4)+self.offsets[6],256).split(b'\0')[0]
    def selector(self):return self.get(self.form()+FORM_SELECTOR,4)
    def selector_ready(self):
        self.form_open();at=self.form()+FORM_SELECTOR
        self.reach('(dw($%x)!=0)|(dw($%x)!=0)'%(at,at+2))
        self.reach('dw($%x)=1'%(self.selector()+F['valid']));self.frames(20)
    def selector_xy(self,index,end=False):
        base=self.selector();obj=base+index*24
        return (self.get(base+16)+self.get(obj+16)+(self.get(obj+20)-2 if end else self.get(obj+20)//2),
            self.get(base+18)+self.get(obj+18)+self.get(obj+22)//2)
    def type_form(self,value):
        for ch in value:
            key,shift=KEYS[ch];self.form_key(key,shift=shift,settle=4)
    def choose(self,leaf,volume=None,settle=True,menu=False):
        if menu:self.menu('TFILE','MOPEN')
        else:self.key('O',ctrl=True)
        self.selector_ready()
        if volume is not None:
            self.click(*self.selector_xy(3,end=True))
            old=self.b.memdump(self.selector()+F['path'],128).split(b'\0')[0]
            for _ in old:self.form_key('BACKSPACE',settle=3)
            self.type_form(volume+':*.*');self.form_key('RETURN',settle=20)
            self.reach('dw($%x)=1'%(self.selector()+F['valid']))
        self.click(*self.selector_xy(5,end=True))
        previous=self.b.memdump(self.selector()+F['file'],13).split(b'\0')[0]
        for _ in previous:self.form_key('BACKSPACE',settle=3)
        self.type_form(leaf)
        actual=self.b.memdump(self.selector()+F['file'],13).split(b'\0')[0]
        require(actual==leaf.encode(),'Native selector filename differs: '+repr(actual))
        old=self.form();self.form_key('RETURN',settle=0)
        self.reach('(dw($%x)=0)&(dw($%x)=0)'%(old+FORM_SELECTOR,old+FORM_SELECTOR+2))
        if settle:self.frames(20)
    def decision(self,button):self.form_open();self.alert(button);self.command_idle()
    def loaded(self,name,lines,ending=1,path=None):
        self.command_idle();self.selection(name,lines,None,0,0)
        state=self.text();require(state['ending']==ending and not state['dirty'],'Wrong clean loaded baseline')
        require(document(self)[:2]==[0,0] and self.get(self.sy['undo_valid'],1)==0,
            'Replacement retained viewport/Undo')
        if path is not None:require(self.name()==path,'Wrong document path: '+repr(self.name()))
        ids=(state['pointer'],self.get(state['pointer']+self.offsets[19]))
        if not hasattr(self,'document_owner'):self.document_owner=ids
        require(ids==self.document_owner,'Replacement changed document/window identity')
        self.scene.setdefault('replacements',[]).append(dict(name=name,path=self.name().decode('latin1'),
            text=ids[0],window=ids[1],ending=ending))
    def launched(self,name,lines,source_bytes,ending=1,path=None):
        at=self.sy['source_bytes']
        print('QED launch: waiting for',source_bytes,'bytes',flush=True)
        try:self.reach('(dw($%x)=%d)&(dw($%x)=%d)&(dw($%x)=0)'%
            (at,source_bytes&65535,at+2,source_bytes>>16,self.sy['QedStarting']))
        except Exception:
            self.scene['launch_failure']={n:self.get(self.sy[n],4 if n in ('source_bytes','cause') else 2)
                for n in ('source_bytes','cause','command_kind','QedStarting','QedLastKey','QedGlobalKeyCalls')}
            print('QED launch diagnostic:',self.scene['launch_failure'],flush=True)
            raise
        self.loaded(name,lines,ending,path)
    def unchanged(self,name,lines,span,x,y,viewport):
        self.command_idle();self.selection(name,lines,span,x,y)
        require(document(self)[:2]==viewport,'Failed/cancelled command changed viewport')
        require(self.get(self.sy['undo_valid'],1)==1,'Failed/cancelled command lost Undo')
        self.clipboard([b'head'])

def interact(b,p,app,record,owner,combined=False):
    e=DocumentEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    if cycle==0:
        long_lines=fixtures()['LONG.TXT'].split(b'\n')
        e.launched('launch-multibank',long_lines,81920,path=b'SYS:LONG.TXT')
        e.scene['loaded_bytes']=len(fixtures()['LONG.TXT'])
        if combined:
            combined_session(e)
            e.key('A',ctrl=True);e.key('MINUS',ctrl=True);e.key('ESC')
        # Keep the real multi-bank load/pixel gate, then isolate replacement
        # rollback on a small tabbed document. The core covers double large owners.
        dirty=e.get(e.get(e.sy['text_list'],4)+e.offsets[5],4);e.key('N',ctrl=True)
        if dirty:e.decision(1)
        e.loaded('new-after-large-load',[b''])
        for key in ('H','E','A','D','TAB','N','E','E','D','L','E'):e.key(key)
        e.key('A',ctrl=True);e.key('MINUS',ctrl=True)
        long_lines=[b'head\tneedle']
        e.select('loaded-copy-range',long_lines,e.cell(0,0),e.cell(4,0),(0,0,0,4),(4,0))
        e.key('C',ctrl=True);e.clipboard([b'head']);e.key('X')
        lines=[b'x'+long_lines[0][4:],*long_lines[1:]]
        e.selection('loaded-selection-edit',lines,None,1,0)
        e.select('candidate-retained-range',lines,e.cell(1,0),e.cell(8,0),(0,1,0,2),(2,0))
        span=(0,1,0,2);view=document(e)[:2]
        e.choose('NUL.TXT');e.decision(1)
        e.unchanged('format-error-retains-document',lines,span,2,0,view)
        e.key('N',ctrl=True);e.decision(2)
        e.unchanged('new-cancel-retains-document',lines,span,2,0,view)
        e.key('O',ctrl=True);e.selector_ready();e.form_key('ESC');e.command_idle()
        e.unchanged('selector-cancel-retains-document',lines,span,2,0,view)
        e.choose('SMALL.TXT');e.decision(2)
        e.unchanged('open-cancel-retains-document',lines,span,2,0,view)
        e.key('Z',ctrl=True);e.selection('undo-survives-replacement-failure',long_lines,(0,0,0,4),4,0)
        e.key('Z',ctrl=True);e.selection('undo-toggle-after-cancel',lines,span,2,0)
        e.choose('SMALL.TXT',volume='RAM');e.decision(1)
        small=fixtures()['SMALL.TXT'].split(b'\n')
        e.loaded('ram-open-commits',small,path=b'RAM:SMALL.TXT');e.clipboard([b'head'])
        e.key('Z',ctrl=True);e.selection('old-undo-cleared',small,None,0,0)
        e.key('V',ctrl=True);pasted=[b'head'+small[0],*small[1:]]
        e.selection('clipboard-survives-open',pasted,None,4,0)
        e.menu('TFILE','MNEWTEXT');e.decision(1);e.loaded('new-discard-commits',[b''])
        e.clipboard([b'head']);e.key('V',ctrl=True);e.selection('clipboard-survives-new',[b'head'],None,4,0)
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'));e.frames(30)
        e.click(100,44);e.frames(20)
        if combined:combined_overlap(e)
        e.key('O',ctrl=True);e.selector_ready();e.peer_command(1);e.command_idle()
        e.selection('selector-policy-cancels-open',[b'head'],None,4,0)
        e.choose('LONG.TXT',settle=False)
        fd=e.sy['descriptor'];candidate=e.sy['candidate']+e.offsets[17]
        e.reach('(dw($%x)!=65535)&(dw($%x)>0)'%(fd,candidate))
        before=e.get(candidate,4);require(before<80,'Read completed before cancellation checkpoint')
        e.form_key('ESC',settle=0);e.command_idle()
        require(e.get(fd)==65535 and e.get(candidate,4)==0,'Cancelled reader retained an owner')
        e.scene['read_cancel']=dict(prepared_lines=before,descriptor_retired=True)
        e.selection('read-input-cancel-retains-document',[b'head'],None,4,0)
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        b.memload(e.at('control'),struct.pack('<H',101))
        if combined:
            e.close();e.form_open();e.alert(2);e.command_idle()
            e.selection('combined-close-cancel',[b'head'],None,4,0)
        e.key('Q',ctrl=True);return e.alert(1,retiring=True)
    if cycle==1:
        e.form_open();e.alert(1);e.loaded('failed-launch-empty',[b''])
        e.choose('CRLF.TXT',menu=True);e.loaded('crlf-open-commits',[b'one',b'last'],ending=0,path=b'SYS:CRLF.TXT')
        e.choose('EMPTY.TXT');e.loaded('clean-replacement-title',[b''],path=b'SYS:EMPTY.TXT')
        b.memload(e.at('control'),struct.pack('<H',2));return e.retire_key('Q',ctrl=True)
    if cycle==2:
        e.form_open();e.alert(1);e.loaded('extra-arguments-empty',[b''])
        e.key('A');e.selection('candidate-allocation-old',[b'a'],None,1,0)
        e.b.memload(e.sy['QedEditFailLine'],struct.pack('<H',1));e.key('N',ctrl=True);e.decision(1)
        require(e.get(e.sy['QedEditFailureHits'])==1,'Candidate allocation refusal not reached')
        e.selection('candidate-allocation-rollback',[b'a'],None,1,0)
        b.memload(e.at('control'),struct.pack('<H',3));e.key('Q',ctrl=True);return e.alert(1,retiring=True)
    e.launched('launch-crlf',[b'one',b'last'],9,ending=0,path=b'CRLF.TXT')
    e.key('A');e.key('N',ctrl=True);e.form_open()
    b.memload(e.at('control'),struct.pack('<H',4));e.reach('dw($%x)=104'%e.at('phase'));e.frames(30)
    e.alert(2);e.command_idle();e.selection('replacement-stop-cancel',[b'aone',b'last'],None,1,0)
    require(e.get(e.sy['descriptor'])==65535 and e.get(e.sy['candidate']+e.offsets[17],4)==0,
        'Stop Cancel retained a replacement candidate')
    b.memload(e.at('control'),struct.pack('<H',104));return e.alert(1,retiring=True)


def combined_session(e):
    # Keep the 80 KiB launch/read-cancel gates, then combine interaction on
    # twelve maximum-length lines. Double large ownership is a reader-core gate.
    lines=fixtures()['SESSION.TXT'].split(b'\n');last=len(lines)-2
    e.choose('SESSION.TXT',menu=True);e.loaded('combined-open-long',lines,path=b'SYS:SESSION.TXT')
    e.select('combined-copy-range',lines,e.cell(0,0),e.cell(4,0),(0,0,0,4),(4,0))
    e.menu('TEDIT','MCOPY');e.clipboard([b'head'])
    e.menu('TEDIT','MCUT');cut=[lines[0][4:],*lines[1:]]
    e.selection('combined-cut',cut,None,0,0)
    e.key('Z',ctrl=True);e.selection('combined-undo-cut',lines,(0,0,0,4),4,0)
    e.key('Z',ctrl=True);e.selection('combined-toggle-cut',cut,None,0,0)
    e.menu('TEDIT','MPASTE');e.selection('combined-paste',lines,None,4,0)
    e.key('Z',ctrl=True);e.selection('combined-undo-paste',cut,None,0,0)
    e.key('Z',ctrl=True);e.selection('combined-toggle-paste',lines,None,4,0)
    e.key('A',ctrl=True);e.key('MINUS',ctrl=True)
    e.open_find();e.type_form('needle');e.accept_find();e.command_idle()
    e.selection('combined-find',lines,(0,5,0,11),11,0)
    e.key('G',ctrl=True);e.command_idle();e.selection('combined-find-next',lines,(last,5,last,11),11,last)
    e.open_find();e.clear_field();e.type_form('z'*50);e.accept_find();e.command_idle()
    for _ in range(4):e.key('G',ctrl=True);e.command_idle()
    e.selection('combined-panned-match',lines,(last,219,last,269),269,last)
    require(document(e)[0]>0,'Long-line Find did not pan horizontally')
    e.key('ESC');e.expected_range=None;e.caret_pixels('combined-panned-caret',lines,269,last)

def combined_overlap(e):
    from qed_viewport_observe import peer_pixels
    lines=fixtures()['SESSION.TXT'].split(b'\n')
    e.choose('SESSION.TXT');e.decision(1);e.loaded('combined-peer-open',lines,path=b'SYS:SESSION.TXT')
    e.peer_command(2);e.frames(30);e.covered=[(0,60,224,172)]
    e.selection('combined-covered',lines,None,0,0);peer_pixels(e,'combined-peer')
    e.click(100,44);e.frames(30);e.covered=[]
    e.selection('combined-exposed',lines,None,0,0)
    e.expected_range=None;e.caret_pixels('combined-exposed-caret',lines,0,0)
    e.key('N',ctrl=True);e.loaded('combined-peer-new',[b''])
    e.key('V',ctrl=True);e.selection('combined-return-head',[b'head'],None,4,0)
