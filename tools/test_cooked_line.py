#!/usr/bin/env python3
"""Compare raw/optimized native cooked sessions with independent line semantics."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from test_dos_stack import execute,ownership
from test_cooperative import data
from os_boundary import emulator
from banked_test_memory import read

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())

def vectors():
    ops=[]
    def op(kind,value=0,count=1,session=0):ops.append((kind,value,count,session))
    for length in (0,1,36,37,255,256):
        op(5);op(0,97,length);op(3);op(0,13);op(2,count=0)
        for n in (1,35,1,218,256):op(2,count=n)
        op(4)
    for length in (0,1,37):
        op(5);op(0,98,length);op(0,4);op(2,count=0);op(2,count=1);op(2,count=256);op(2,count=256)
        op(0,99);op(0,10);op(2,count=256)
    for key in (3,8,9):
        op(5);op(0,120,37);op(3);op(0,key);op(3) if key!=3 else op(2)
        op(4);op(0,10);op(2,count=256)
    # Loss while editing, sealed, partially drained, EOF pending, invalidated.
    for state in range(5):
        op(5);op(0,65,256 if state==4 else 4)
        if state in (1,2):op(0,10)
        if state==2:op(2)
        if state==3:op(0,4)
        op(1);op(0,4);op(0,3);op(0,90);op(0,10);op(2,count=256);op(4)
        op(0,66);op(0,10);op(2,count=256)
    op(5);op(5,session=1);op(0,65,session=0);op(0,66,session=1)
    op(0,13,session=1);op(2,count=256,session=1);op(0,13);op(2,count=256)
    # Incremental echo, including Tab and several appends before one Render.
    # Kind 7 additionally requires the exact new suffix, with no backspaces.
    op(5);op(0,97);op(3)
    op(0,8);op(3);op(0,120);op(7,120)
    op(0,98);op(7,98)
    op(0,9);op(7,32);op(0,99,3);op(7,99,3)
    # A delete/retype batch must not qualify merely because length grew.
    op(0,8,2);op(0,100,3);op(3)
    op(0,8);op(3);op(0,101);op(7,101)
    # Enter and leave the hidden tail; the width-boundary append stays cheap.
    op(5);op(0,97,35);op(3);op(0,98);op(7,98)
    op(0,99);op(3);op(0,8);op(3);op(0,8);op(3);op(0,100);op(7,100)
    # Width changes must not mistake a previously shifted tail for a prefix.
    op(5);op(6,1);op(0,65);op(3);op(0,66);op(3)
    op(6,3);op(0,67);op(3)
    # Loss erases the visible prefix even when incremental echo was possible.
    op(5);op(0,65);op(3);op(1);op(3)
    # Middle insertions, beginning/end movement and deletion remain byte edits.
    def text(value):
        for char in value:op(0,ord(char))
    op(5);text('abcd');op(3)
    for key in (1,6,ord('X'),8,6,ord('Y'),5,2,11,1,2,8,23,21,21):
        op(0,key);op(3)
    text('one  two   tail');op(1)  # damaged input ignores every edit/history key
    for key in (1,5,2,6,8,11,14,16,21,23):op(0,key);op(3)
    op(0,13);op(2,count=256);op(4)
    op(5);text('one  two   ');op(0,23);op(3);op(0,23);op(3)
    text('abc def');op(0,2,4);op(0,23);op(3);op(0,13);op(2,count=256)
    # Sliding view and caret under the next character, not just at EOF.
    for width in (1,3,36):
        op(5);op(6,width);op(0,97,40);op(3)
        for key,n in ((1,1),(6,width),(6,1),(5,1),(2,2),(8,1),(11,1),(1,1),(21,1)):
            op(0,key,n);op(3)
    op(5);op(0,97,255);op(0,1);op(3);op(0,8);op(0,5);op(3)
    op(0,2,120);op(3);op(0,ord('x'));op(3);op(0,21);op(0,16)
    op(0,13);op(2,count=256);op(4)
    # Ring fill, wrap, exact duplicate/blank filtering and partial drains.
    op(5);op(8,1)
    for entry in ('','   ','one','one','two','three','four','five','six','seven','eight','nine','ten','eleven'):
        text(entry);op(0,13);op(2,count=1);op(2,count=256)
    text('draft');op(0,2,2);op(3)
    for _ in range(12):op(0,16);op(3)
    for _ in range(12):op(0,14);op(3)
    op(0,16);op(0,ord('!'));op(3);op(0,16);op(3);op(0,14);op(3)
    op(0,ord('?'));op(0,13);op(2,count=256)
    op(0,16);op(3);op(0,3);op(2,count=256);op(4)
    # Disabled readers neither recall nor record; toggles preserve a live line.
    op(8,0);text('data');op(0,16);op(3);op(0,13);op(2,count=256)
    op(8,1);op(0,16);op(3);op(0,21);text('abc');op(8,0);op(3)
    op(0,4);op(2,count=1);op(8,1);op(2,count=256);op(2,count=256)
    op(0,16);op(3);op(0,21);op(0,97,256);op(8,0);op(8,1)
    op(0,16);op(0,13);op(2,count=256);op(4);op(0,16);op(3)
    op(9,1);op(8,0);op(9,0);op(8,0)
    # Independent second session, including blank history and draft restore.
    op(5,session=1);op(8,1,session=1);op(0,16,session=1);op(3,session=1)
    op(0,90,session=1);op(0,13,session=1);op(2,count=256,session=1)
    op(0,16,session=1);op(3,session=1);op(0,14,session=1);op(3,session=1)
    require(len(ops)<=1000,'Vector storage exceeded')
    return ops

class Model:
    def __init__(self):
        self.line=bytearray();self.position=0;self.error=0;self.caret=0;self.start=0
        self.ready=self.eof=self.discard=self.drawn=self.screen_cursor=0
        self.width=36;self.history=[];self.selected=0;self.enabled=0;self.busy=0
        self.draft=(b'',0)
        self.screen=bytearray(b'> '+b' '*38);self.cursor=2
    def empty(self):
        self.line.clear();self.position=self.caret=self.start=0
    def feed(self,key):
        if self.ready or self.eof:return 0
        if self.discard:
            if key in (10,13):self.discard=0;self.ready=1;return 2
            return 0
        if key==3:self.empty();self.selected=0;self.error=304;self.ready=1;return 2
        if key==4:self.eof=self.ready=1;self.selected=0;return 2
        if key in (10,13):
            value=bytes(self.line)
            if self.enabled and value.strip(b' ') and (not self.history or self.history[-1]!=value):
                self.history=(self.history+[value])[-10:]
            self.selected=0;self.line.append(10);self.ready=1;return 2
        if key in (14,16):
            if not self.enabled or not self.history:return 0
            if key==16:
                if self.selected==len(self.history):return 0
                if not self.selected:self.draft=(bytes(self.line),self.caret)
                self.selected+=1
            else:
                if not self.selected:return 0
                self.selected-=1
            text,caret=(self.history[-self.selected],len(self.history[-self.selected])) if self.selected else self.draft
            self.line=bytearray(text);self.caret=caret;return 1
        target={1:0,5:len(self.line),2:max(0,self.caret-1),6:min(len(self.line),self.caret+1)}.get(key,self.caret)
        if target!=self.caret:self.caret=target;return 1
        if key in (8,23):
            if not self.caret:return 0
            left=bytes(self.line[:self.caret])
            if key==8:target=self.caret-1
            else:
                left=left.rstrip(b' ')
                target=left.rfind(b' ')+1
            del self.line[target:self.caret];self.caret=target;return 1
        if key==21:
            if not self.line:return 0
            self.empty();return 1
        if key==11:
            if self.caret==len(self.line):return 0
            del self.line[self.caret:];return 1
        if key==9:key=32
        if not 32<=key<=126:return 0
        if len(self.line)==255:self.lose(120)
        else:self.line[self.caret:self.caret]=bytes([key]);self.caret+=1
        return 1
    def lose(self,error):
        self.empty();self.error=error;self.selected=0
        self.ready=self.eof=0;self.discard=1
    def drain(self,limit):
        if limit==0:return 0,b''
        if not (self.ready or self.eof):return -2,b''
        if self.error:self.ready=0;return -1,b''
        payload=bytes(self.line[self.position:self.position+limit])
        if payload:
            self.position+=len(payload)
            if self.position==len(self.line):self.empty();self.ready=0
        else:self.ready=self.eof=0;self.empty()
        return len(payload),payload
    def render(self,payload):
        # Apply bytes to an independent terminal, then inspect text/caret. No
        # oracle reproduces the guest's backspace/clear/output sequence.
        for byte in payload:
            if byte==8:self.cursor=max(0,self.cursor-1)
            else:
                require(self.cursor<39,'Cooked echo wrapped or touched the final column')
                self.screen[self.cursor]=byte;self.cursor+=1
        self.start=min(self.start,max(0,len(self.line)-self.width))
        if self.caret<self.start:self.start=self.caret
        right=self.caret if self.caret==len(self.line) else self.caret+1
        self.start=max(self.start,right-self.width)
        visible=self.line[self.start:self.start+self.width]
        expected=b'> '+(b'<' if self.start else b' ')+visible+b' '*(37-len(visible))
        self.screen_cursor=1+self.caret-self.start
        require(self.screen==expected and self.cursor==2+self.screen_cursor,'View/prompt/cursor mismatch')
        self.drawn=1+len(visible)

def check(ops,raw):
    require(raw[:16]==raw[-16:]==b'\xa5'*16,'Output guard changed')
    models=[Model(),Model()]
    for i,(kind,value,limit,which) in enumerate(ops):
        m=models[which];record=raw[16+i*280:16+(i+1)*280]
        actual,length,position,error,ready,eof,discard,drawn,caret,start,screen_cursor,history,selected,enabled=struct.unpack('<iHHiBBBBHHBBBB',record[:24])
        result=0;payload=b''
        if kind==0:
            for _ in range(limit):result=m.feed(value)
        elif kind==1:m.lose(303)
        elif kind==2:result,payload=m.drain(limit)
        elif kind in (3,7):
            require(0<actual<=128,'Unbounded echo');payload=record[24:24+actual];m.render(payload);result=actual
            if kind==7:
                require(payload==bytes([value])*limit,
                        f'Append redrew existing text at operation {i}: {payload!r}')
        elif kind==4:m.error=0
        elif kind==5:models[which]=m=Model()
        elif kind==6:m.width=value
        elif kind==8:
            result=202 if m.busy else 0
            if not result:
                m.enabled=bool(value)
                if not value:m.selected=0
        elif kind==9:m.busy=value
        observed=(actual,length,position,error,ready,eof,discard,drawn,caret,start,screen_cursor,history,selected,enabled)
        expected=(result,len(m.line),m.position,m.error,m.ready,m.eof,m.discard,m.drawn,m.caret,m.start,m.screen_cursor,len(m.history),m.selected,m.enabled)
        require(observed==expected,f'Cooked state mismatch at operation {i}: {ops[i]}: {observed} != {expected}')
        require(record[24:]==payload+b'\xa5'*(256-len(payload)),f'Copied bytes/guard mismatch at operation {i}')

def run(out,optimize,bank):
    out.mkdir(parents=True,exist_ok=True);ops=vectors()
    commands=struct.pack('<H',len(ops))+b''.join(struct.pack('<BBHBB',k,v,n,s,0) for k,v,n,s in ops)
    size=32+280*len(ops)
    p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/cooked_line.act',out,
            optimize=optimize,tasks=True,task_capacity=8,kernel_bank=bank,console=False,
            image_data=[(0x200000,b'\xa5'*size),(0x300000,commands)])
    bridge=ROOT/'build/shell-paced-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Cooked checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out);snapshot=read(b,0x200000,size,out)
        (out/'observations.bin').write_bytes(snapshot)
        check(ops,snapshot)
        return dict(status='pass',build=p['build'],machine=machine,runtime=runtime,
                    operations=len(ops),checks=data(b,p['image'],'checks',True),session_bytes=json.loads((ROOT/'abi/dos.json').read_text())['cooked']['session']['size'],
                    fixed_bank_zero_delta=0,per_task_bank_zero_delta=0)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--bank',type=int,choices=(2,3),default=2);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    try:result=run(out,args.case=='opt',args.bank)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Cooked line passed',args.case,args.bank,flush=True)
