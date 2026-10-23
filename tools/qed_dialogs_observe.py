"""Physical QE5 dialogs, literal Find and policy interruption through a peer."""
import hashlib,struct
from native_program import require
from qed_editing_observe import Editor
from qed_clipboard_observe import ClipboardEditor
from generate_aes_server import expected_layout
from gem_render_oracle import Raster,DESKTOP_PALETTE,PENS
from qed_form_oracle import paint

class DialogEditor(ClipboardEditor):
    global_commands=ClipboardEditor.global_commands+('F','G')
    def field_address(self):
        tree=self.get(self.sy['replace'],4)
        ted=self.get(tree+24*self.ids['RPTEXT1']+12,4)
        return self.get(ted,4)
    def field(self):return self.b.memdump(self.field_address(),51).split(b'\0')[0]
    def accepted(self):return self.b.memdump(self.sy['s_str'],51).split(b'\0')[0]
    def form_key(self,key,**options):return Editor.key(self,key,dispatch=False,**options)
    def form_open(self):
        at=self.context()+dict(expected_layout())['C context form']
        self.reach('(dw($%x)!=0)|(dw($%x)!=0)'%(at,at+2))
    def form_closed(self):
        at=self.context()+dict(expected_layout())['C context form']
        self.reach('(dw($%x)=0)&(dw($%x)=0)'%(at,at+2))
    def command_idle(self):self.reach('dw($%x)=0'%self.sy['command_kind'])
    def open_find(self):
        print('QED Find: cycle',self.native('cycle'),'starts',self.get(self.sy['QedFormStarts']),flush=True)
        self.key('F',ctrl=True);self.form_open()
    def object_xy(self,index,tree=None):
        tree=tree or self.get(self.sy['replace'],4)
        root=struct.unpack('<hhhHHHI4h',self.b.memdump(tree,24))
        obj=struct.unpack('<hhhHHHI4h',self.b.memdump(tree+24*index,24))
        return root[7]+obj[7]+obj[9]//2,root[8]+obj[8]+obj[10]//2
    def clear_field(self):
        tree=self.get(self.sy['replace'],4);i=self.ids['RPTEXT1']
        root=struct.unpack('<hhhHHHI4h',self.b.memdump(tree,24))
        obj=struct.unpack('<hhhHHHI4h',self.b.memdump(tree+24*i,24))
        self.click(root[7]+obj[7]+obj[9]-2,root[8]+obj[8]+4)
        for _ in range(len(self.field())):self.form_key('BACKSPACE')
        require(self.field()==b'','Find field did not clear')
    def form_pixels(self,name):
        self.move(630,20);self.frames(20)
        for attempt in range(40):
            raster=Raster(self.font);x,y,w,h=paint(self.b,self.context(),raster)
            target=self.p['output'].parent/('form-'+name+'.bgra')
            capture=self.b.rawscreen(str(target));raw=target.read_bytes()
            rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
            colors={pen:rgb[i*3:i*3+3][::-1] for i,pen in enumerate(PENS)}
            mismatch=next(((xx,yy) for yy in range(y,y+h) for xx in range(x,x+w)
                if raw[yy*capture.stride+64+xx*4:yy*capture.stride+67+xx*4]!=colors[raster.pixels[yy*640+xx]]),None)
            if mismatch is None:
                self.scene.setdefault('forms',[]).append(dict(name=name,pixels=w*h,
                    sha256=hashlib.sha256(raw).hexdigest()));return
            self.frames(3)
        raise RuntimeError('Form pixel mismatch '+name+': '+str(mismatch))
    def accept_find(self):self.form_key('RETURN');self.form_closed()
    def cancel_find(self):self.form_key('ESC');self.form_closed();self.command_idle()
    def peer_draws_during_form(self):
        c=self.context();o=dict(expected_layout());peer=self.peer();before=self.get(peer['QedPeerPaints'])
        condition='&'.join(['db($%x)=4'%(self.task+self.extra[3]),
            'dw($%x)=0'%(c+o['C context updateDepth']),
            'dw($%x)=0'%(c+o['C context mouseDepth'])])
        self.reach(condition);self.reach('dw($%x)!=%d'%(peer['QedPeerPaints'],before));self.reach(condition)
        self.scene['form_peer']=dict(task_state=4,update=0,mctrl=0,
            paints_before=before,paints_after=self.get(peer['QedPeerPaints']))

def interact(b,p,app,record,owner):
    e=DialogEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    e.selection('dialogs-empty',[b''],None,0,0)
    if cycle==0:
        for key in ('A','B','SPACE','A','ASTERISK','B','SPACE','A','ASTERISK','B','RETURN','L','A','S','T'):e.key(key)
        lines=[b'ab a*b a*b',b'last']
        e.click(*e.cell(0,0));e.stage(0)
        e.open_find();e.form_pixels('find-empty')
        e.form_key('A');e.form_key('ASTERISK')
        e.form_key('TAB');e.form_key('TAB',shift=True)
        require(e.field()==b'a*','Find field/focus bytes');e.form_pixels('find-literal')
        e.accept_find();e.command_idle();e.selection('literal-find',lines,(0,3,0,5),5,0)
        e.key('G',ctrl=True);e.command_idle();e.selection('literal-find-next',lines,(0,7,0,9),9,0)
        e.key('G',ctrl=True);e.alert(1);e.selection('find-not-found-retains-range',lines,(0,7,0,9),9,0)
        e.open_find();e.clear_field();e.form_key('Z')
        # A release outside the pressed Find button must not accept the field.
        e.move(*e.object_xy(e.ids['RPOK']));e.edge(True);e.move(*e.cell(0,0));e.edge(False)
        require(e.form()!=0 and e.accepted()==b'a*','Outside release accepted Find')
        e.cancel_find();require(e.accepted()==b'a*','Cancel replaced the accepted pattern')
        e.selection('find-cancel-retains-pattern',lines,(0,7,0,9),9,0)
        # Add the ordinary periodic peer only after the initial field session.
        b.memload(e.at('control'),struct.pack('<H',1));e.reach('dw($%x)=100'%e.at('phase'));e.frames(30)
        e.click(100,44);e.frames(20)
        e.open_find();e.clear_field();e.form_key('A');e.peer_draws_during_form()
        starts=e.get(e.sy['QedFormStarts']);before=e.geometry()['bounds']
        e.peer_command(1);e.reach('dw($%x)=%d'%(e.sy['QedFormStarts'],starts+1));e.form_open()
        require(e.field()==b'a' and e.geometry()['bounds'][0]==before[0]+8,'Move lost the Find draft')
        e.scene['form_move']=dict(starts_before=starts,starts_after=e.get(e.sy['QedFormStarts']),
            last_diagnostic=e.get(e.sy['QedFormDiagnostic']))
        e.cancel_find();e.selection('find-move-resumes-draft',lines,(0,7,0,9),9,0)
        e.open_find();e.peer_command(3);e.alert(3);e.command_idle()
        e.selection('find-close-cancel',lines,(0,7,0,9),9,0)
        e.open_find();e.peer_command(3);e.frames(30)
        require(e.form()!=0,'Missing modified decision for alert-zero case')
        e.form_key('ESC');e.form_closed();e.command_idle()
        e.selection('find-close-escape-zero',lines,(0,7,0,9),9,0)
        original=e.geometry()['bounds'];bounds=[original[0],original[1],400,196]
        e.peer_command(4,bounds);e.frames(30)
        starts=e.get(e.sy['QedFormStarts']);e.key('F',ctrl=True);e.alert(1)
        require(e.get(e.sy['QedFormStarts'])==starts,'Non-fitting Find entered form_do')
        e.selection('find-too-small',lines,(0,7,0,9),9,0)
        e.peer_command(4,[original[0],original[1],original[2]-original[0],original[3]-original[1]])
        e.frames(30)
        b.memload(e.at('control'),struct.pack('<H',100));e.reach('dw($%x)=101'%e.at('phase'))
        e.key('ESC');e.expected_range=None;e.caret_pixels('find-exposed-caret',lines,9,0)
        b.memload(e.at('control'),struct.pack('<H',101));e.key('Q',ctrl=True);return e.alert(2,retiring=True)
    if cycle==1:
        e.key('A');e.open_find()
        for i in range(51):
            e.form_key('A')
            if i<50:e.reach('(db($%x)=97)&(db($%x)=0)'%(e.field_address()+i,e.field_address()+i+1))
        require(e.field()==b'a'*50,'Find field exceeded or lost its 50-byte capacity')
        e.accept_find();e.alert(1);e.selection('find-field-limit',[b'a'],None,1,0)
        e.scene['accepted_pattern_bytes']=len(e.accepted())
        b.memload(e.at('control'),struct.pack('<H',2));e.key('Q',ctrl=True);return e.alert(2,retiring=True)
    if cycle==2:
        e.b.memload(e.sy['QedFormFailAllocation'],struct.pack('<H',1))
        e.key('F',ctrl=True);e.alert(1);e.command_idle()
        require(e.get(e.sy['QedFormAllocationFailures'])==1,'Actual form allocation failure was not reached')
        e.selection('find-allocation-rollback',[b''],None,0,0)
        require(not e.text()['dirty'],'Failed Find dirtied the document')
        e.menu('TDESK','MABOUT');e.form_open();e.form_pixels('about')
        starts=e.get(e.sy['QedFormStarts'])
        e.click(*e.object_xy(e.ids['AINFO'],e.get(e.sy['about'],4)))
        e.reach('dw($%x)=%d'%(e.sy['QedFormStarts'],starts+1));e.form_open()
        e.form_pixels('about-native-details');e.form_key('ESC');e.form_closed();e.command_idle()
        e.selection('about-cancel',[b''],None,0,0)
        b.memload(e.at('control'),struct.pack('<H',3));return e.retire_key('Q',ctrl=True)
    e.key('A');e.open_find();b.memload(e.at('control'),struct.pack('<H',4))
    e.alert(3);e.command_idle();e.selection('find-stop-cancel',[b'a'],None,1,0)
    b.memload(e.at('control'),struct.pack('<H',104));return e.alert(2,retiring=True)
