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
    require(len(ops)<=200,'Vector storage exceeded')
    return ops

class Model:
    def __init__(self):
        self.line=bytearray();self.position=0;self.error=0
        self.ready=self.eof=self.discard=self.drawn=0
        self.screen=bytearray(b'> '+b' '*38);self.cursor=2
    def feed(self,key):
        if self.ready or self.eof:return 0
        if self.discard:
            if key in (10,13):self.discard=0;self.ready=1;return 2
            return 0
        if key==3:self.line.clear();self.position=0;self.error=304;self.ready=1;return 2
        if key==4:self.eof=self.ready=1;return 2
        if key in (10,13):self.line.append(10);self.ready=1;return 2
        if key==8:
            if self.line:self.line.pop();return 1
            return 0
        if key==9:key=32
        if not 32<=key<=126:return 0
        if len(self.line)==255:self.lose(120)
        else:self.line.append(key)
        return 1
    def lose(self,error):
        self.line.clear();self.position=0;self.error=error
        self.ready=self.eof=0;self.discard=1
    def drain(self,limit):
        if limit==0:return 0,b''
        if not (self.ready or self.eof):return -2,b''
        if self.error:self.ready=0;return -1,b''
        payload=bytes(self.line[self.position:self.position+limit])
        if payload:
            self.position+=len(payload)
            if self.position==len(self.line):self.line.clear();self.position=0;self.ready=0
        else:self.ready=self.eof=0;self.line.clear();self.position=0
        return len(payload),payload
    def render(self,payload):
        # Interpret emitted editing bytes as a terminal, then inspect visible
        # contents and cursor. This does not reproduce the native redraw loop.
        for byte in payload:
            if byte==8:self.cursor=max(0,self.cursor-1)
            else:
                require(self.cursor<39,'Cooked echo wrapped or touched the final column')
                self.screen[self.cursor]=byte;self.cursor+=1
        tail=self.line[-36:];marker=b'<' if len(self.line)>36 else b' '
        expected=b'> '+marker+tail+b' '*(37-len(tail))
        require(self.screen==expected and self.cursor==3+len(tail),'Tail/prompt/cursor mismatch')
        self.drawn=1+len(tail)

def check(ops,raw):
    require(raw[:16]==raw[-16:]==b'\xa5'*16,'Output guard changed')
    models=[Model(),Model()]
    for i,(kind,value,limit,which) in enumerate(ops):
        m=models[which];record=raw[16+i*272:16+(i+1)*272]
        actual,length,position,error,ready,eof,discard,drawn=struct.unpack('<iHHiBBBB',record[:16])
        result=0;payload=b''
        if kind==0:
            for _ in range(limit):result=m.feed(value)
        elif kind==1:m.lose(303)
        elif kind==2:result,payload=m.drain(limit)
        elif kind==3:
            require(0<actual<=128,'Unbounded echo');payload=record[16:16+actual];m.render(payload);result=actual
        elif kind==4:m.error=0
        elif kind==5:models[which]=m=Model()
        observed=(actual,length,position,error,ready,eof,discard,drawn)
        expected=(result,len(m.line),m.position,m.error,m.ready,m.eof,m.discard,m.drawn)
        require(observed==expected,f'Cooked state mismatch at operation {i}: {ops[i]}: {observed} != {expected}')
        require(record[16:]==payload+b'\xa5'*(256-len(payload)),f'Copied bytes/guard mismatch at operation {i}')

def run(out,optimize,bank):
    out.mkdir(parents=True,exist_ok=True);ops=vectors()
    commands=struct.pack('<H',len(ops))+b''.join(struct.pack('<BBHBB',k,v,n,s,0) for k,v,n,s in ops)
    size=32+272*len(ops)
    p=build(compiler(ROOT/'build/actionc'),ROOT/'tests/programs/cooked_line.act',out,
            optimize=optimize,tasks=True,task_capacity=8,kernel_bank=bank,console=False,
            image_data=[(0xd0000,b'\xa5'*size),(0xe0000,commands)])
    bridge=ROOT/'build/shell-paced-bridge'
    require(sha256(bridge/'AltirraBridgeServer')==PIN['emulator']['sha256'],'Unpinned emulator')
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=240,frame_limit=12000)
        except Exception:
            print('Cooked checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out);snapshot=read(b,0xd0000,size,out)
        (out/'observations.bin').write_bytes(snapshot)
        check(ops,snapshot)
        return dict(status='pass',build=p['build'],machine=machine,runtime=runtime,
                    operations=len(ops),checks=data(b,p['image'],'checks',True),session_bytes=json.loads((ROOT/'abi/dos.json').read_text())['cooked']['session']['size'],
                    fixed_bank_zero_delta=0,per_task_bank_zero_delta=0)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True)
    a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    try:result=run(out,args.case=='opt',args.bank)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Cooked line passed',args.case,args.bank,flush=True)
