#!/usr/bin/env python3
"""ARC mutation on native SDFS: protected source, full media, BREAK, leases."""
import argparse,json,time,random
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine,read_build
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership
from sdfs_reference import make,extract
from arc_archive import creation_corpus,read
from filesystem_audit import Audit
from sdx_attribute_fixture import attributes


def fixture(out):
    payload=bytearray();setup=[]
    for name in ['ARC.COM','ARCLST.OVL','ARCADD.OVL']:
        raw=(ROOT/'build/sdx-inputs/arc'/name).read_bytes();at=0x300000+len(payload);payload+=raw
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
    source=(ROOT/'tests/programs/sdx_arc_mutate.act').read_text().split('PROC Main()')[0]
    source=source.replace('USE O65READ','USE O65READ\nUSE SDXABI').replace('c"RAM:NEW.XAR"','c"D1:NEW.XAR"').replace('c"RAM:NEW.BAK"','c"D1:NEW.BAK"')
    source+='LONGINT expectedError\nINCLUDE "'+str(ROOT/'tests/programs/sdx_arc_mutation_break.inc')+'"\n'
    source+='''PROC Main()
  LONGCARD baseline

  baseline=EXEC.AvailMem(0)
'''+ '\n'.join(setup)+'''
  IF expectedError=304 THEN
    BreakRun()
  ELSEIF expectedError<>0 THEN
    Run(0,BYTE POINTER(c"A NEW.ARC BIG.BIN"),17,20,expectedError)
  ELSE
    Run(0,BYTE POINTER(c"A NEW.ARC BIG.BIN"),17,0,0)
    Run(1,BYTE POINTER(c"D NEW.ARC REPEAT.BIN"),20,0,0)
  FI
  NoTemporary()
  Run(4,BYTE POINTER(c"L NEW.ARC"),9,0,0)
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)

RETURN

ENDMODULE
'''
    (out/'probe.act').write_text(source)
    return out/'probe.act',[(0x300000,bytes(payload))]


def media(out,kind):
    source=out/'source';source.mkdir(parents=True,exist_ok=True)
    original=(ROOT/'build/sdx-arc/reference-create/readback/NEW.ARC').read_bytes()
    (source/'NEW.ARC').write_bytes(original)
    value=random.Random(816).randbytes(1024 if kind=='normal' else 65537)
    (source/'BIG.BIN').write_bytes(value)
    if kind=='full':(source/'FILL.BIN').write_bytes(bytes([0x6d])*150000)
    make(out/'volume.atr',source,1024,256,'ARCMUT')
    flags={'BIG.BIN':1}
    if kind=='protected':flags['NEW.ARC']=1
    attributes(out/'volume.atr',flags)
    return original,value


def run(out,reuse=False):
    source,payload=fixture(out)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=32768
    (out/'memory.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,sdx_drive_a='D1:',image_data=payload,memory_profile=out/'memory.json',dos_mounts=[dict(alias='RAM',format=3),dict(alias='D1',device='sio.device',unit=49,sectors=1024,sector_bytes=256,format=2,access='readwrite',profile=4)])
    runs={}
    for kind,error in [('normal',0),('full',221),('break',304),('protected',223)]:
        directory=out/kind;original,value=media(directory,kind)
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',directory,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.config('diskemu','generic56k');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            b.mount(0,str(directory/'volume.atr'))
            def before(b):
                address=next(d['address'] for d in program['image']['data'] if '_EXPECTEDERROR_' in d['name'])
                for i,v in enumerate(error.to_bytes(4,'little')):b.poke(address+i,v)
            try:runtime,_=execute(b,program,timeout=240,frame_limit=12000,before_run=before)
            except Exception:
                print(kind,{k:data(b,program['image'],k) for k in ['checks','currentCase','primary','secondary','reason','breakTicks','breakEvent']},flush=True);raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
            ticks=int.from_bytes(bytes(data(b,program['image'],'breakTicks')),'little')
            time.sleep(3);b._cmd_ok('EJECT drive=0')
        disk=(directory/'volume.atr').read_bytes();Audit(disk).sdfs()
        extract(directory/'volume.atr',directory/'readback')
        assert not (directory/'readback'/'NEW.XAR').exists()
        assert not (directory/'readback'/'NEW.BAK').exists()
        assert (directory/'readback'/'BIG.BIN').read_bytes()==value
        raw=(directory/'readback'/'NEW.ARC').read_bytes()
        if kind=='normal':
            expected=creation_corpus();del expected['REPEAT.BIN'];expected['BIG.BIN']=value
            actual,entries=read(raw);assert actual==expected
            assert all(e['date']==23865 for e in entries)
        else:
            assert raw==original
            if kind=='full':assert (directory/'readback'/'FILL.BIN').read_bytes()==bytes([0x6d])*150000
        runs[kind]=dict(status='pass',checks=checks,break_ticks=ticks,runtime=runtime,machine=machine)
        print('ARC mutation disk',kind,'pass',checks,'checks',flush=True)
    return dict(status='pass',tier='development',runs=runs,build=program['build'])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--reuse',action='store_true');a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(out,a.reuse)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
