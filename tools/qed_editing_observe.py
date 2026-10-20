"""Read actual QED state/pixels; stimulate only physical keys and pointer input."""
import hashlib,json,re,struct
import adapter_state as adapter
from native_program import ROOT,require
from os_boundary import run_to
from desktop_mouse import schedule
from generate_aes_server import ABI,layout,expected_layout
from gem_render_oracle import font_bytes,DESKTOP_PALETTE


class Editor:
    def __init__(self,b,p,app,record,owner):
        self.b,self.p,self.app,self.record,self.owner=b,p,app,record,owner
        self.pending_dispatch=None
        delta=owner['image_base']-(app['abi']['link_bank']<<16)
        self.sy={n:a+delta for n,a in app['image']['symbols'].items()}
        self.offsets=struct.unpack('<27H',b.memdump(self.sy['QedEditingLayout'],54))
        self.font=font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c')
        self.provider=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']
        fields=layout()['Request']['fields']
        task=owner['record']+next(f[2] for f in json.loads((ROOT/'abi/process.json').read_text())['record'] if f[0]=='task')
        def contexts():
            return [self.get(self.provider['contexts']+i*4,4) for i in range(ABI['constants']['CONTEXTS'])]
        self.contexts=contexts
        self.task=task;self.owner_offset=fields['owner']
        self.scene=dict(process=owner['identity'],image_base=owner['image_base'],
                        cycle=self.native('cycle'),snapshots=[],keys=[])
        record.setdefault('qed_editing',[]).append(self.scene)
        self.ids={n:int(v) for n,v in re.findall(r'^#define\s+(\w+)\s+(\d+)',
            (p['output'].parent/'app/inputs/source/qed/src/qed.h').read_text(encoding='latin1'),re.M)}

    def get(self,at,size=2):return int.from_bytes(self.b.memdump(at,size),'little')
    def at(self,name):
        return next(d['address'] for d in self.p['image']['data']
                    if d['name'].startswith('M_CPROCESSTEST_'+name.upper()+'_'))
    def native(self,name,size=2):return self.get(self.at(name),size)
    def input_at(self,name):
        return next(d['address'] for d in self.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    def reach(self,condition,timeout=120):
        b,p=self.b,self.p
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        original=b.regs
        def regs():
            result=original()
            require(not b.eval_expr(adapter.STOPPED),
                    'Editing fixture stopped: checks='+str(self.native('checks')))
            return result
        b.regs=regs
        try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=timeout,frame_limit=9000)
        finally:b.regs=original
    def frames(self,n=30):self.reach('@frame>='+str(self.b.eval_expr('@frame')+n))
    def key(self,name,ctrl=False,shift=False,settle=12,dialog=False,dispatch=True):
        before=self.get(self.sy['QedEditKeyCalls'])
        if ctrl:self.b._cmd_ok('KEY CTRL down')
        if shift:self.b._cmd_ok('KEY SHIFT down')
        require(self.b._cmd_ok('KEY '+name+' down')['raw_scan'],'Physical key unavailable: '+name)
        self.frames(3);self.b._cmd_ok('KEY '+name+' up')
        if shift:self.b._cmd_ok('KEY SHIFT up')
        if ctrl:self.b._cmd_ok('KEY CTRL up')
        if dispatch and dialog:self.pending_dispatch=before
        if dispatch and not dialog and not (ctrl and name=='Q'):
            self.reach('dw($%x)!=%d'%(self.sy['QedEditKeyCalls'],before))
            self.scene['keys'].append(dict(physical=name,control=ctrl,shift=shift,
                key=self.get(self.sy['QedLastKey']),qualifiers=self.get(self.sy['QedLastQualifiers'])))
        self.frames(settle)
    def move(self,x,y):
        current=[self.get(self.input_at(n)) for n in ('cursorX','cursorY')]
        target=schedule(self.b,self.p,current,(x,y))
        self.reach('(dw($%x)=%d)&(dw($%x)=%d)'%
                   (self.input_at('cursorX'),target[0],self.input_at('cursorY'),target[1]))
    def click(self,x,y):
        self.move(x,y)
        self.b._cmd_ok('MOUSE AT 2000 0 0 1');self.frames(15)
        self.b._cmd_ok('MOUSE AT 2000 0 0 0');self.frames(50)
    def context(self):
        result=[c for c in self.contexts() if c and self.get(c+self.owner_offset,3)==self.task]
        require(len(result)==1,'No unique editor AES context');return result[0]
    def form(self):return self.get(self.context()+dict(expected_layout())['C context form'],4)
    def retire_key(self,name,ctrl=False):
        # capture() releases keys after observing ordinary Process retirement.
        if ctrl:self.b._cmd_ok('KEY CTRL down')
        require(self.b._cmd_ok('KEY '+name+' down')['raw_scan'],'Unavailable retirement key')
        return lambda:self.b._cmd_ok('KEY ALL up')
    def alert(self,button,retiring=False):
        self.frames(30);session=self.form();require(session,'Expected native alert')
        # The first eligible button has focus; Cancel is the explicit default.
        key='RETURN' if button==2 else 'SPACE'
        if retiring:return self.retire_key(key)
        self.key(key,settle=0,dialog=True,dispatch=False)
        at=self.context()+dict(expected_layout())['C context form']
        self.reach('(dw($%x)=0)&(dw($%x)=0)'%(at,at+2))
        if self.pending_dispatch is not None:
            self.reach('dw($%x)!=%d'%(self.sy['QedEditKeyCalls'],self.pending_dispatch))
            self.pending_dispatch=None
        self.frames(10)
    def close(self):
        self.click(self.native('windowX')+6,self.native('windowY')+5)
    def menu(self,title,item):
        from application_menu_oracle import source
        tree=self.get(self.sy['menu'],4)
        objects,labels,positions=source(self.b,tree)
        heading,entry=self.ids[title],self.ids[item]
        parent=next(i for i,obj in enumerate(objects) if obj[1]>=0 and
            entry in self.children(objects,i))
        # Native application headings begin at BAR_LEFT=128. Popup geometry
        # is independently recomposed from the borrowed source OBJECT tree.
        self.click(128+positions[heading][0]+objects[heading][9]//2,5)
        left=max(0,min(128+positions[parent][0],640-objects[parent][9]))
        top=max(11,positions[parent][1]);top=min(top,240-objects[parent][10])
        # Leave the title bar vertically before moving across a popup row;
        # diagonal ST motion can otherwise enter the neighbouring heading.
        self.move(128+positions[heading][0]+objects[heading][9]//2,
                  top+positions[entry][1]-positions[parent][1]+objects[entry][10]//2)
        self.click(left+positions[entry][0]-positions[parent][0]+objects[entry][9]//2,
                   top+positions[entry][1]-positions[parent][1]+objects[entry][10]//2)
        if item in ('MOOVERW','MOEINF'):
            self.reach('db($%x)=%d'%(self.sy['overwrite'],item=='MOOVERW'))
        self.scene.setdefault('menus',[]).append(dict(title=title,item=item))
    @staticmethod
    def children(objects,parent):
        result=[];child=objects[parent][1]
        while child>=0 and child!=parent:
            result.append(child);child=objects[child][0]
        return result
    def text(self):
        o=self.offsets;t=self.get(self.sy['text_list'],4);require(t,'Missing text owner')
        require(self.get(t,4)==0,'Editor acquired a second document')
        ring=t+o[1];n=self.get(ring+o[17],4);line=self.get(ring+o[15]+o[13],4)
        lines=[]
        require(0<n<10000,'Invalid observed line count')
        for _ in range(n):
            length=self.get(line+o[14]);require(length<=1023,'Invalid logical line length')
            lines.append(self.b.memdump(line+o[12],length));line=self.get(line+o[13],4)
        require(line==ring+o[16],'Broken text ring tail')
        return dict(pointer=t,lines=lines,x=self.get(t+o[3]),y=self.get(t+o[4],4),
                    dirty=self.get(t+o[5],4),ending=self.get(ring+o[18]),
                    blink=self.get(t+o[23],1),caret=self.get(t+o[24],1))
    def check(self,name,lines,x=None,y=None,pixels=True):
        self.frames(20);state=self.text()
        require(state['lines']==lines,f'{name}: expected {lines!r}, got {state["lines"]!r}')
        require(x is None or state['x']==x,name+': wrong cursor column '+str(state['x']))
        require(y is None or state['y']==y,name+': wrong cursor row '+str(state['y']))
        item={k:v for k,v in state.items() if k!='lines'}
        item.update(name=name,lines=[v.hex() for v in lines])
        item['private_heap']=list(struct.unpack('<4I',self.b.memdump(self.sy['totals'],16)))
        o=self.offsets;w=self.get(self.sy['used_list'],4)
        item['window']=dict(pointer=w,columns=self.get(w+o[22]-4),rows=self.get(w+o[22]-2),
            document=list(struct.unpack('<4i',self.b.memdump(w+o[21],16))),
            work=list(struct.unpack('<4h',self.b.memdump(w+o[22],8))),
            title=self.b.memdump(w+o[25],128).split(b'\0')[0].decode('latin1'),
            font=[self.get(self.sy['font_wcell']),self.get(self.sy['font_hcell'])])
        self.scene['snapshots'].append(item)
        if pixels:item['pixels']=self.pixels(name,lines,state)
        print('QED editing:',name,flush=True)
        return state
    def geometry(self):
        c=self.context();view=layout()['WindowView']['fields']
        views=c+dict(expected_layout())['C context views']
        shown=[self.get(views+i*4,4) for i in range(ABI['constants']['WINDOWS'])
               if self.get(views+i*4,4) and self.get(self.get(views+i*4,4)+view['shown'])]
        require(len(shown)==1,'Not exactly one editor window')
        return {n:list(struct.unpack('<4h',self.b.memdump(shown[0]+view[n],8)))
                for n in ('bounds','work')}
    def pixels(self,name,lines,state,caret=False):
        # Publication and completed video scanout can lag an application return.
        # Require the exact independent image within a bounded frame interval.
        for attempt in range(120):
            if caret:
                state=self.text()
                if state['blink'] or not state['caret']:
                    self.frames(2);continue
            try:
                result=self._pixels(name,lines,state,caret)
                if caret:require(result['caret_checked']>0,'Caret was entirely excluded from the pixel oracle')
                return dict(**result,observations=attempt+1)
            except RuntimeError as error:
                if ': text pixel ' not in str(error) or attempt==119:raise
                self.frames(2)
        raise RuntimeError('No completed visible caret frame: '+name)
    def _pixels(self,name,lines,state,caret=False):
        left,top,right,bottom=self.geometry()['work']
        w=self.get(self.sy['used_list'],4)
        dx,dy,_,_=struct.unpack('<4i',self.b.memdump(w+self.offsets[21],16))
        target=self.p['output'].parent/('edit-'+str(self.scene['cycle'])+'-'+name+'.bgra')
        capture=self.b.rawscreen(str(target));raw=target.read_bytes()
        colors=[bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[i*3:i*3+3])[::-1] for i in range(2)]
        pointer=[self.get(self.input_at(n)) for n in ('cursorX','cursorY')]
        checked=caret_checked=0
        for row in range((bottom-top+7)//8):
            logical=dy+row;line=lines[logical] if logical<len(lines) else b''
            display=line.expandtabs(8)
            for yy in range(8):
                y=top+row*8+yy
                if y>=bottom:continue
                for col in range((right-left+7)//8):
                    column=dx+col
                    ch=display[column] if column<len(display) else 32
                    for xx in range(8):
                        x=left+col*8+xx
                        if x>=right:continue
                        cursor_column=len(line[:state['x']].expandtabs(8))
                        at_cursor=logical==state['y'] and column==cursor_column
                        if not caret and at_cursor:continue
                        if any(l<=x<r and t<=y<b for l,t,r,b in getattr(self,'covered',[])):continue
                        if pointer[0]<=x<pointer[0]+16 and pointer[1]<=y<pointer[1]+16:continue
                        ink=bool(self.font[yy*256+ch]&(128>>xx))
                        if caret and state['caret'] and not state['blink'] and at_cursor and \
                           xx<(8 if self.get(self.sy['overwrite'],1) else 2):
                            ink=True;caret_checked+=1
                        expected=colors[ink]
                        at=y*capture.stride+64+x*4
                        require(raw[at:at+3]==expected,f'{name}: text pixel {x},{y} ({ch})')
                        checked+=1
        return dict(checked=checked,caret_checked=caret_checked,sha256=hashlib.sha256(raw).hexdigest())
    def caret_pixels(self,name,lines,x,y):
        self.move(630,20)
        state=self.text();t=state['pointer'];before=self.get(self.sy['QedCursorPaints'])
        c=self.context();offset=dict(expected_layout())['C context updateDepth']
        condition='&'.join(['dw($%x)!=%d'%(self.sy['QedCursorPaints'],before),
            'dw($%x)=0'%self.sy['QedPaintedBlink'],
            'db($%x)=0'%(t+self.offsets[23]),'db($%x)!=0'%(t+self.offsets[24]),
            'dw($%x)=%d'%(self.sy['QedPaintedX'],x),'dw($%x)=%d'%(self.sy['QedPaintedY'],y),
            'dw($%x)=0'%(c+offset)])
        for _ in range(12):
            self.reach(condition)
            # RAWSCREEN returns the completed scanout, rather than live VRAM.
            # A frame after the painter's return may still contain its clear.
            self.frames(2);state=self.text()
            if not state['blink'] and self.get(c+offset)==0:break
        else:raise RuntimeError('Caret never reached a completed visible video frame')
        require(state['lines']==lines and state['x']==x and state['y']==y,'Caret checkpoint changed text')
        self.scene.setdefault('carets',[]).append(dict(name=name,pixels=self.pixels(name,lines,state,caret=True)))


def interact(b,p,app,record,owner,keys_only=False):
    # Wait until normal startup has published its document before reading it.
    cycle_at=next(d['address'] for d in p['image']['data'] if d['name'].startswith('M_CPROCESSTEST_CYCLE_'))
    cycle=int.from_bytes(b.memdump(cycle_at,2),'little')
    e=Editor(b,p,app,record,owner)
    if cycle==0:b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    e.reach('dw($%x)=%d'%(e.at('phase'),cycle+1));e.frames(80)
    e.check('empty',[b''],0,0)
    if keys_only and cycle!=1:
        b.memload(e.at('control'),struct.pack('<H',cycle+1))
        return None if cycle==3 else e.retire_key('Q',ctrl=True)
    if cycle==0:
        for key in ('A','B','C'):e.key(key)
        e.check('insert',[b'abc'],3,0)
        e.key('RETURN');e.key('D');e.check('split',[b'abc',b'd'],1,1)
        e.key('BACKSPACE');e.key('BACKSPACE');e.check('join',[b'abc'],3,0)
        e.b.memload(e.sy['QedEditFailLine'],struct.pack('<H',1))
        e.key('E',dialog=True);e.alert(1);e.check('allocation-rollback',[b'abc'],3,0)
        e.b.memload(e.sy['QedEditFailLine'],struct.pack('<H',2))
        e.key('RETURN',dialog=True);e.alert(1);e.check('split-allocation-rollback',[b'abc'],3,0)
        require(e.get(e.sy['QedEditFailureHits'])==2,'Line failures were not reached')
        e.key('TAB');e.key('D');e.check('literal-tab',[b'abc\td'],5,0)
        e.key('BACKSPACE');e.key('BACKSPACE');e.check('tab-delete',[b'abc'],3,0)
        e.key('S',ctrl=True);e.check('save-disabled',[b'abc'],3,0)
        e.close();e.alert(2);e.check('close-cancel',[b'abc'],3,0)
    elif cycle==1:
        for key in ('A','B','C'):e.key(key)
        e.key('RETURN');e.key('MINUS',ctrl=True)
        e.check('native-up',[b'abc',b''],0,0)
        e.key('ASTERISK',ctrl=True);e.key('ASTERISK',ctrl=True)
        e.check('native-right',[b'abc',b''],2,0)
        e.menu('TOPTIONS','MOOVERW');e.key('X');e.check('overwrite',[b'abx',b''],3,0)
        e.key('BACKSPACE',ctrl=True);e.check('forward-delete-join',[b'abx'],3,0)
        e.key('Q',ctrl=True);e.alert(2);e.check('quit-cancel',[b'abx'],3,0)
    elif cycle==2:
        e.key('S',ctrl=True);e.check('clean-shortcut',[b''],0,0)
    else:
        e.key('A');e.check('stop-dirty',[b'a'],1,0)
    # Fixture control coordinates its ordinary RequestStop; it never edits QED.
    b.memload(e.at('control'),struct.pack('<H',cycle+1))
    if cycle==3:
        e.alert(2);e.check('stop-cancel',[b'a'],1,0)
    if cycle==2:return e.retire_key('Q',ctrl=True)
    else:
        e.key('Q',ctrl=True);return e.alert(1,retiring=True)
