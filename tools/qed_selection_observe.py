"""Known physical selections compared with donor bytes and independent pixels."""
import hashlib,json,struct
from pathlib import Path
from native_program import ROOT,require
from generate_aes_server import ABI,layout,expected_layout
from program_image_layout import LAYOUT as IMAGE_LAYOUT,FIELDS as IMAGE_FIELDS
from qed_editing_observe import Editor
from qed_viewport_observe import document,origin,peer_pixels
from gem_render_oracle import DESKTOP_PALETTE


class SelectionEditor(Editor):
    expected_range=None
    def __init__(self,*args):
        super().__init__(*args)
        self.extra=struct.unpack('<4H',self.b.memdump(self.sy['QedEditingLayout']+54,8))
    def stage(self,value):self.reach('dw($%x)=%d'%(self.sy['pointer_state'],value))
    def key(self,name,ctrl=False,**options):
        if ctrl and name=='A':
            before=self.get(self.sy['QedGlobalKeyCalls'])
            options.setdefault('dispatch',False)
            result=super().key(name,ctrl=ctrl,**options)
            self.reach('dw($%x)!=%d'%(self.sy['QedGlobalKeyCalls'],before))
            return result
        return super().key(name,ctrl=ctrl,**options)
    def text(self):
        state=super().text();t=state['pointer'];o=self.offsets
        state['block']=self.get(t+o[7],1)
        state['range']=[self.get(t+o[8],4),self.get(t+o[9]),
                        self.get(t+o[10],4),self.get(t+o[11])]
        return state
    def cell(self,column,row):
        work=self.geometry()['work'];return work[0]+column*8+1,work[1]+row*8+4
    def edge(self,down):
        self.b._cmd_ok('MOUSE AT 2000 0 0 '+str(int(down)))
        self.reach('dw($%x)=%d'%(self.input_at('buttons'),int(down)))
    def select(self,name,lines,start,end,span,cursor):
        self.move(*start);self.edge(True);self.stage(1)
        self.move(*end);self.edge(False);self.stage(0)
        return self.selection(name,lines,span,*cursor)
    def selection(self,name,lines,span,x,y):
        self.frames(10);state=self.text()
        require(bool(state['block'])==bool(span),name+': selection presence')
        if span:require(state['range']==list(span),name+': range '+str(state['range']))
        self.expected_range=span
        return self.check(name,lines,x,y)
    def _pixels(self,name,lines,state,caret=False):
        if not self.expected_range:return super()._pixels(name,lines,state,caret)
        left,top,right,bottom=self.geometry()['work'];dx,dy,_,_=document(self)
        target=self.p['output'].parent/('selection-'+name+'.bgra')
        capture=self.b.rawscreen(str(target));raw=target.read_bytes()
        colors=[bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[i*3:i*3+3])[::-1] for i in range(2)]
        pointer=[self.get(self.input_at(n)) for n in ('cursorX','cursorY')]
        y1,x1,y2,x2=self.expected_range;checked=selected=0
        for row in range((bottom-top+7)//8):
            logical=dy+row;line=lines[logical] if logical<len(lines) else b''
            text=line.expandtabs(8)
            start=len(line[:x1].expandtabs(8)) if logical==y1 else 0
            end=len(line[:x2].expandtabs(8)) if logical==y2 else len(text)+(logical<len(lines)-1)
            for yy in range(8):
                y=top+row*8+yy
                if y>=bottom:continue
                for col in range((right-left+7)//8):
                    column=dx+col;ch=text[column] if column<len(text) else 32
                    marked=y1<=logical<=y2 and start<=column<end
                    for xx in range(8):
                        x=left+col*8+xx
                        if x>=right:continue
                        if any(l<=x<r and t<=y<b for l,t,r,b in getattr(self,'covered',[])):continue
                        if pointer[0]<=x<pointer[0]+16 and pointer[1]<=y<pointer[1]+16:continue
                        ink=bool(self.font[yy*256+ch]&(128>>xx));pen=int(ink)^int(marked)
                        at=y*capture.stride+64+x*4
                        require(raw[at:at+3]==colors[pen],f'{name}: text pixel {x},{y} ({ch})')
                        checked+=1;selected+=marked
        require(selected>0,name+': no selected pixels in work area')
        return dict(checked=checked,selected_checked=selected,caret_checked=0,
                    sha256=hashlib.sha256(raw).hexdigest())
    def peer(self):
        fields={n:o for n,_,o in json.loads((ROOT/'abi/process.json').read_text())['record']}
        table=next(d for d in self.p['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
        candidates=[]
        for i in range((table['size']-4)//128):
            at=table['address']+i*128
            if self.get(at+fields['state'],1)!=2 or at==self.owner['record']:continue
            image=self.get(at+fields['image'],3)
            if image and self.get(image+IMAGE_FIELDS['kind'],1)==1:
                candidates.append(self.get(image+IMAGE_FIELDS['text'],3))
        require(len(candidates)==1,'No unique ordinary peer Process')
        app=json.loads((self.p['output'].parent/'peer/app.json').read_text())
        delta=candidates[0]-(app['abi']['link_bank']<<16)
        return {n:v+delta for n,v in app['image']['symbols'].items()}
    def peer_command(self,command):
        peer=self.peer();before=self.get(peer['QedPeerCalls'])
        state=self.text();bounds=self.geometry()['bounds']
        self.b.memload(peer['QedPeerDestination'],struct.pack('<H',self.get(self.sy['gl_apid'])))
        self.b.memload(peer['QedPeerHandle'],struct.pack('<H',self.get(state['pointer']+self.offsets[19])))
        self.b.memload(peer['QedPeerBounds'],struct.pack('<4h',bounds[0]+8,bounds[1],
            bounds[2]-bounds[0],bounds[3]-bounds[1]))
        self.b.memload(peer['QedPeerCommand'],struct.pack('<H',command))
        self.reach('dw($%x)!=%d'%(peer['QedPeerCalls'],before))
    def wait_inside(self):
        c=self.context();endpoint=self.get(c+self.extra[0],4)
        inbox=self.get(endpoint+layout()['Endpoint']['fields']['input'],3)
        offsets=dict(expected_layout());condition='&'.join([
            'db($%x)=4'%(self.task+self.extra[3]),
            'dw($%x)=7'%(inbox+layout()['InputInbox']['fields']['interest']),
            'dw($%x)=0'%(c+offsets['C context updateDepth']),
            'dw($%x)=0'%(c+offsets['C context mouseDepth']),
            'db($%x)=0'%(c+self.extra[1])])
        self.reach(condition)
        peer=self.peer();before=self.get(peer['QedPeerPaints'])
        self.reach('dw($%x)!=%d'%(peer['QedPeerPaints'],before))
        self.reach(condition)
        self.scene['inside_wait']=dict(task_state=4,interest=7,update=0,mctrl=0,
            alarm_state=0,peer_paints_before=before,peer_paints_after=self.get(peer['QedPeerPaints']))
        return inbox


def interact(b,p,app,record,owner,scroll=True):
    e=SelectionEditor(b,p,app,record,owner);cycle=e.native('cycle')
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(40)
    e.check('selection-empty',[b''],0,0)
    if cycle in (1,2):
        b.memload(e.at('control'),struct.pack('<H',cycle+1));return e.retire_key('Q',ctrl=True)
    if cycle==3:
        e.key('X');e.move(*e.cell(0,0));e.edge(True);e.stage(1)
        b.memload(e.at('control'),struct.pack('<H',4));e.alert(2)
        e.stage(2);e.edge(False);e.stage(0)
        e.selection('selection-stop-cancel',[b'x'],None,0,0)
        b.memload(e.at('control'),struct.pack('<H',104))
        return e.alert(1,retiring=True)

    for key in ('A','B','TAB','C','D','RETURN','RETURN','E','F','G','H'):e.key(key)
    lines=[b'ab\tcd',b'',b'efgh']
    e.select('forward-range',lines,e.cell(1,0),e.cell(2,2),(0,1,2,2),(2,2))
    e.select('backward-range',lines,e.cell(3,2),e.cell(1,0),(0,1,2,3),(1,0))
    e.key('ESC');e.selection('escape-clears',lines,None,1,0)
    before=e.get(e.sy['QedEditKeyCalls'])
    e.key('ASTERISK',ctrl=True,shift=True,dispatch=False,settle=50)
    if e.get(e.sy['QedEditKeyCalls'])!=before:
        e.selection('shift-right',lines,(0,1,0,2),2,0)
    else:
        e.scene['physical_shift_right']='No delivered document key observed on the pinned keyboard path'
        e.selection('shift-right-unavailable',lines,None,1,0)
    b._cmd_ok('KEY SHIFT down');e.click(*e.cell(9,0));b._cmd_ok('KEY SHIFT up');e.stage(0)
    e.selection('shift-click',lines,(0,1,0,4),4,0)
    e.key('A',ctrl=True);e.selection('select-all',lines,(0,0,2,4),4,2)
    e.key('MINUS',ctrl=True);e.selection('collapse-start',lines,None,0,0)
    # Press and release retained before the application completes the paint.
    e.move(*e.cell(2,0));e.edge(True);e.frames(1);e.edge(False);e.stage(0)
    e.selection('fast-click',lines,None,2,0)

    b.memload(e.at('control'),struct.pack('<H',1))
    e.reach('dw($%x)=100'%e.at('phase'));e.frames(30)
    e.covered=[(0,60,224,172)];peer_pixels(e,'selection-peer-on-top')
    e.click(100,44);e.covered=[]
    # Use the uncovered right side for a held gesture while both clients paint.
    e.move(*e.cell(30,0));e.edge(True);e.stage(1)
    inbox=e.wait_inside()
    e.edge(False);e.stage(0)
    e.selection('held-inside-release',lines,None,5,0)
    e.move(*e.cell(30,0));e.edge(True);e.stage(1)
    e.peer_command(1);e.stage(2);e.edge(False);e.stage(0)
    e.selection('geometry-cancels',lines,None,5,0)
    require(e.geometry()['bounds'][0]==24,'Geometry message was not accepted')
    e.move(*e.cell(30,0));e.edge(True);e.stage(1)
    e.peer_command(2);e.stage(2);e.edge(False);e.stage(0)
    e.covered=[(0,60,224,172)]
    e.selection('focus-cancels',lines,None,5,0)
    e.click(100,44);e.covered=[]
    e.move(*e.cell(30,0));e.edge(True);e.stage(1)
    e.b.memload(inbox+layout()['InputInbox']['fields']['loss'],struct.pack('<H',2))
    e.move(*e.cell(31,0));e.stage(2);e.edge(False);e.stage(0)
    e.selection('input-loss-cancels',lines,None,5,0)
    e.move(*e.cell(30,0));e.edge(True);e.stage(1)
    e.peer_command(3);e.alert(2);e.stage(2);e.edge(False);e.stage(0)
    e.selection('selection-close-cancel',lines,None,5,0)
    b.memload(e.at('control'),struct.pack('<H',100))
    e.reach('dw($%x)=101'%e.at('phase'));e.covered=[]
    e.select('exposed-range',lines,e.cell(1,0),e.cell(2,2),(0,1,2,2),(2,2))
    e.key('ESC');e.selection('exposed-cleared',lines,None,2,2)
    e.caret_pixels('selection-exposed-caret',lines,2,2)
    if scroll:lines=autoscroll(e,lines)
    b.memload(e.at('control'),struct.pack('<H',101))
    e.key('Q',ctrl=True);return e.alert(1,retiring=True)


def byte_at_column(line,column):
    expanded=0
    for i,ch in enumerate(line):
        step=8-expanded%8 if ch==9 else 1
        if expanded+step>column:return i
        expanded+=step
    return len(line)


def autoscroll(e,lines):
    e.key('A',ctrl=True);e.key('MINUS',ctrl=True)
    e.selection('scroll-start',lines,None,0,0)
    for _ in range(5):e.key('ASTERISK',ctrl=True)
    for _ in range(16):e.key('TAB')
    lines=[lines[0]+b'\t'*16,*lines[1:]]
    e.selection('scroll-tabbed-line',lines,None,21,0)
    require(document(e)[0]>0,'Tabbed document did not pan')
    columns=e.get(e.get(e.sy['used_list'],4)+e.offsets[22]-4)
    for direction in (-1,1):
        work=e.geometry()['work'];before=document(e)[0]
        anchor=byte_at_column(lines[0],before+1)
        e.move(*e.cell(1,0));e.edge(True);e.stage(1)
        e.move(work[0]-3 if direction<0 else work[2]+3,work[1]+4)
        start=e.b.eval_expr('@frame');e.frames(18);finish=e.b.eval_expr('@frame')
        during=document(e)[0];steps=(during-before)*direction
        require(1<=steps<=(finish-start)//5+1,'Unbounded or absent horizontal autoscroll')
        e.edge(False);e.stage(0)
        endpoint=byte_at_column(lines[0],document(e)[0]+(0 if direction<0 else columns-1))
        first,last=sorted((anchor,endpoint))
        e.selection('scroll-left' if direction<0 else 'scroll-right',lines,
            (0,first,0,last),endpoint,0)
        e.scene.setdefault('autoscroll',[]).append(dict(axis='x',direction=direction,
            frames=finish-start,steps=steps))
    e.key('A',ctrl=True);e.key('MINUS',ctrl=True)
    e.selection('before-tall-document',lines,None,0,0)
    for _ in range(32):e.key('RETURN')
    lines=[b'']*32+lines
    e.selection('tall-document',lines,None,0,32)
    rows=e.get(e.get(e.sy['used_list'],4)+e.offsets[22]-2)
    for direction,row in ((1,10),(-1,6)):
        work=e.geometry()['work'];before=document(e)[1];anchor=before+row
        e.move(*e.cell(0,row));e.edge(True);e.stage(1)
        e.move(work[0]+1,work[3]+3 if direction>0 else work[1]-3)
        start=e.b.eval_expr('@frame');e.frames(18);finish=e.b.eval_expr('@frame')
        during=document(e)[1];steps=(during-before)*direction
        require(1<=steps<=(finish-start)//5+1,'Unbounded or absent vertical autoscroll')
        e.edge(False);e.stage(0)
        endpoint=document(e)[1]+(rows-1 if direction>0 else 0)
        endpoint=min(endpoint,len(lines)-1);first,last=sorted((anchor,endpoint))
        e.selection('scroll-down' if direction>0 else 'scroll-up',lines,
            (first,0,last,0),0,endpoint)
        e.scene.setdefault('autoscroll',[]).append(dict(axis='y',direction=direction,
            frames=finish-start,steps=steps))
    e.key('ESC');e.expected_range=None
    e.b.memload(e.sy['QedSelectionFailClock'],struct.pack('<H',1))
    before=e.get(e.sy['QedSelectionClockFailures'])
    e.move(*e.cell(1,1));e.edge(True);e.stage(1)
    work=e.geometry()['work'];e.move(work[0]-3,work[1]+12)
    e.alert(1);e.stage(2);e.edge(False);e.stage(0)
    require(e.get(e.sy['QedSelectionClockFailures'])==before+1,'Clock refusal was not reached')
    e.key('ESC');e.expected_range=None
    state=e.text();e.selection('clock-failure-retains-document',lines,None,state['x'],state['y'])
    e.select('after-clock-failure',lines,e.cell(0,1),e.cell(0,3),
        (document(e)[1]+1,0,document(e)[1]+3,0),(0,document(e)[1]+3))
    e.key('ESC');e.expected_range=None
    return lines
