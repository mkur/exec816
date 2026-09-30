#!/usr/bin/env python3
"""Native SDFS namespace checks; whole-file contents were covered in S3."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine,read_build
from banked_test_memory import write as far_write
from library_paths import read_source
from os_boundary import emulator
from test_sio_device import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from make_sdfs_fixtures import Media
from test_sdfs_files import provider

def run(t,out,mode,size,replay=False):
    source=ROOT/f'tests/fixtures/sdfs/namespace-{size}.atr';raw=source.read_bytes();m=Media(raw);root=m.word(25)
    def row(directory,name):return m.row(m.entry(directory,name))
    def start(directory,name):return int.from_bytes(row(directory,name)[1:3],'little')
    rootdata=m.word(m.at(root)+4);tools=start(root,'TOOLS');sub=start(tools,'SUB');subdata=m.word(m.at(sub)+4)
    flag=m.entry(root,'BINARY.BIN')[0];sector=next(n for n in range(1,2001) if m.at(n)<=flag<m.at(n)+(128 if n<=3 else size))
    values=[size,root,0,0,0,0,0,0,rootdata,sector,flag-m.at(sector),subdata,0,0]
    for position in m.entry(root,'EMPTY')[6:17]+m.entry(root,'TOOLS')[1:3]:
        number=next(n for n in range(1,2001) if m.at(n)<=position<m.at(n)+(128 if n<=3 else size))
        values += [number,position-m.at(number)]
    values += list(b'BINARY  BIN')
    config=struct.pack('<'+str(len(values))+'H',*values)
    paths=('', 'BINARY.BIN','LARGE.BIN','TOOLS/SUB/TEXT.TXT','MANY/F299.BIN','many/f255.bin','MANY','MISSING','TOOLS/SUB','TOOLS','binary.bin','bad.','MANY/F000.BIN','EMPTY','BiNaRy.BiN')
    names=b''.join(n.encode().ljust(32,b'\0') for n in paths)
    classes=bytearray(2001)
    def classify(directory):
        maps,sectors=m.chain(directory)
        for s in maps:classes[s]=3
        for s in sectors:
            if s:classes[s]=2
        contents=b''.join(bytes(m.raw[m.at(s):m.at(s)+size]) for s in sectors if s)
        length=int.from_bytes(contents[3:6],'little')
        for pos in range(23,length,23):
            item=contents[pos:pos+23]
            if item[0]&0x10 or not item[0]&8:continue
            first=int.from_bytes(item[1:3],'little')
            if item[0]&0x20:classify(first)
            else:
                pages,payload=m.chain(first)
                for s in pages:classes[s]=3
                for s in payload:
                    if s:classes[s]=1
    classify(root)
    text=(ROOT/'tests/programs/sdfs_files.act').read_text()
    text=text.replace('USE SDFSFILE','USE SDFSFILE\nUSE SDFSDIR\nUSE SDFSNAME\nUSE SDFSDATE')
    mutations='''
  IF phase>=30 THEN Require(BYTE POINTER($a1000)(sector)<>1) FI
  IF phase=31 AND sector=config(8) THEN buffer(3)=1 FI
  IF phase=32 AND sector=volume.root THEN buffer(4)=0 buffer(5)=0 FI
  IF phase=33 AND sector=config(9) THEN buffer(config(10))=buffer(config(10)) OR $80 FI
  IF phase=34 AND sector=config(11) THEN buffer(1)=0 buffer(2)=0 FI
  IF phase=35 AND sector=config(9) THEN buffer(config(10))=buffer(config(10)) OR 1 FI
  IF phase=36 OR phase=37 THEN
    FOR index=0 TO 10 DO
      IF sector=config(14+index*2) THEN
        buffer(config(15+index*2))=BYTE(config(40+index))
        IF phase=37 AND config(40+index)<>32 THEN buffer(config(15+index*2))==+32 FI
      FI
    OD
  FI
  IF phase=38 THEN
    IF sector=config(36) THEN buffer(config(37))=BYTE(volume.root) FI
    IF sector=config(38) THEN buffer(config(39))=0 FI
  FI
'''
    # A named pointer keeps provider indexing in the language's ordinary syntax.
    text=text.replace('BYTE POINTER source','BYTE POINTER source,kinds').replace('sector=work.neededSector\n  table=', 'kinds=BYTE POINTER($a1000) sector=work.neededSector table=')
    mutations=mutations.replace('BYTE POINTER($a1000)(sector)','kinds(sector)')
    text=text.replace('  FOR index=0 TO amount-1 DO\n    buffer(index)=source(index)\n  OD',
        '  IF phase=30 THEN\n    Require(kinds(sector)<>1) work.operations==+1 adapter.buffer=source RETURN\n  FI\n  adapter.buffer=buffer\n  FOR index=0 TO amount-1 DO buffer(index)=source(index) OD')
    text=text.replace('  work.operations==+1','  work.operations==+1'+mutations)
    text=text[:text.index('PROC Main()')]+(ROOT/'tests/programs/sdfs_namespace.inc').read_text()+'''
PROC Main()
  Setup()
  IF config(12)<>0 THEN operation.result=1 MOD LONGINT(config(13)) finished=2 RETURN FI
  Mount() Paths() Enumeration() BadDirectories()
  SDFS.DestroyVolume(@volume) SDFS.DestroyWork(@work) Require(EXEC.AvailMem(0)=before) finished=1
RETURN
ENDMODULE
'''
    fixture=out/'sdfs_namespace.act';fixture.write_text(text)
    p=read_build(out) if replay else build(t,fixture,out,optimize=mode=='opt',tasks=True,console=False,dos_mounts=[],
            image_data=[(0xa0000,bytes(514)),(0xa0800,config),(0xa1000,bytes(classes)),(0xa2000,names),*provider(raw)])
    if replay:
        require(p['build']['source_sha256']==sha256(fixture),'Changed namespace replay source')
        require(all(sha256(ROOT/name)==digest for name,digest in p['build']['task_inputs'].items()),'Changed namespace replay inputs')
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,p,timeout=300,frame_limit=15000)
        except Exception:
            print('Namespace checks',data(b,p['image'],'checks',True),'phase',data(b,p['image'],'phase'),flush=True)
            for item in p['image']['data']:
                if item['name'].startswith('M_SDFSTEST_WORK_'):print(b.memdump(item['address'],item['size']).hex(' '),flush=True)
            raise
        ownership(b,p,out);require(data(b,p['image'],'finished')==[1],'Incomplete namespace fixture')
        checks=data(b,p['image'],'checks',True)
        fault,_=execute(b,p,expected_status=0xff97,before_run=lambda bridge:far_write(bridge,0xa0818,b'\x01\x00',out),timeout=90,frame_limit=4500)
        require(fault['fault_required']==1 and fault['fault_s']!=0 and data(b,p['image'],'finished')==[0],'Arithmetic fault resumed or lost its raw ABI state')
        ownership(b,p,out)
    return dict(status='pass',mode=mode,sector_bytes=size,build=p['build'],runtime=runtime,machine=machine,checks=checks,arithmetic_fault=fault,fixture_sha256=sha256(source),generated_fixture_sha256=sha256(fixture),scope='Native namespace; guest asserts zero ordinary-payload reads during lookup and accounting')
if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--case',choices=('raw','opt'),required=True);parser.add_argument('--size',type=int,choices=(128,256),required=True);parser.add_argument('--output',type=Path,required=True);parser.add_argument('--replay',action='store_true');args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(None if args.replay else compiler(ROOT/'build/actionc'),out,args.case,args.size,args.replay)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDFS namespace passed',args.case,args.size,flush=True)
