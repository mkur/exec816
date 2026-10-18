#!/usr/bin/env python3
"""ARC mutation after settled native read/partial-write/seek/Close/rename faults."""
import argparse, hashlib, json
from pathlib import Path
from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from test_sdx_md5 import PIN
from test_cooperative import data
from test_dos_stack import execute,ownership


def replace_once(text, old, new):
    assert text.count(old)==1,old
    return text.replace(old,new)


def fixture(out):
    files=(ROOT/'lib/dos/sdxfiles.act').read_text()
    mutation=(ROOT/'lib/dos/sdxmutation.act').read_text()
    files=files.replace('; Errors use', 'PUBLIC BYTE fault\n\n; Errors use',1)
    mutation=mutation.replace('PUBLIC BYTE FUNC Active', 'PUBLIC BYTE fault\n\nPUBLIC BYTE FUNC Active',1)
    files=replace_once(files,'    IF got<0 THEN', '''    IF fault=1 AND state.tempOwned<>0 THEN
      fault=0
      DOS.SetIoErr(219)
      got=-1
    FI
    IF got<0 THEN''')
    files=replace_once(files,'    sent=DOS.Write(state.handles(slot-1),source+SIZE(total),LONGINT(count)-total)', '''    IF fault=2 AND count>27 THEN
      sent=DOS.Write(state.handles(slot-1),source+SIZE(total),1)
      fault=0
      DOS.SetIoErr(221)
    ELSE
      sent=DOS.Write(state.handles(slot-1),source+SIZE(total),LONGINT(count)-total)
    FI''')
    files=replace_once(files,'  IF result<0 THEN', '''  IF fault=3 AND operation=0 AND state.writeSlot=slot THEN
    fault=0
    DOS.SetIoErr(219)
    result=-1
  FI
  IF result<0 THEN''')
    files=replace_once(files,'  IF state.writeSlot=slot THEN', '''  IF fault=4 AND state.writeSlot=slot THEN
    fault=0
    DOS.SetIoErr(777)
    error=MapError(state)
  FI
  IF state.writeSlot=slot THEN''')
    mutation=replace_once(mutation,'  IF DOS.Rename(@state.tempPath,@state.archivePath)=0 THEN', '''  IF fault=5 AND state.backupOwned<>0 THEN
    fault=0
    RETURN(Error(DOS.ERROR_OBJECT_EXISTS))
  FI
  IF DOS.Rename(@state.tempPath,@state.archivePath)=0 THEN''')
    (out/'sdxfiles.act').write_text(files);(out/'sdxmutation.act').write_text(mutation)
    fixture={n:(ROOT/'build/sdx-inputs/arc'/n).read_bytes() for n in ['ARC.COM','ARCLST.OVL','ARCADD.OVL']}
    fixture['NEW.ARC']=(ROOT/'build/sdx-arc/reference-create/readback/NEW.ARC').read_bytes()
    fixture['BINARY.BIN']=bytes(range(256))*4
    payload=bytearray();setup=[]
    for name,raw in fixture.items():
        at=0x300000+len(payload);payload+=raw
        setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(ADDRESS(${at:x})),{len(raw)})')
    source=(ROOT/'tests/programs/sdx_arc_mutate.act').read_text().split('PROC Main()')[0]
    source=source.replace('USE SDXSTATE','USE SDXFILES\nUSE SDXMUTATION\nUSE SDXSTATE')
    source+='''PROC Main()
  LONGCARD baseline
  BYTE index
  LONGINT expected

  baseline=EXEC.AvailMem(0)
'''+ '\n'.join(setup)+'''
  Snapshot(0,BYTE POINTER(c"RAM:NEW.ARC"))
  FOR index=1 TO 5 DO
    IF index=5 THEN
      SDXMUTATION.fault=index
    ELSE
      SDXFILES.fault=index
    FI
    expected=219
    IF index=2 THEN
      expected=221
    ELSEIF index=4 THEN
      expected=777
    ELSEIF index=5 THEN
      expected=203
    FI
    Run(index,BYTE POINTER(c"A NEW.ARC BINARY.BIN"),20,20,expected)
    Require(SDXFILES.fault=0 AND SDXMUTATION.fault=0)
    SameArchive(0,BYTE POINTER(c"RAM:NEW.ARC"))
    NoTemporary()
  OD
  Run(6,BYTE POINTER(c"L NEW.ARC"),9,0,0)
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)

RETURN

ENDMODULE
'''
    (out/'probe.act').write_text(source)
    return out/'probe.act',[(0x300000,bytes(payload))]


def run(out):
    source,payload=fixture(out)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=32768
    (out/'memory.json').write_text(json.dumps(profile,indent=2)+'\n')
    program=build(compiler(ROOT/'build/actionc',release=True),source,out,tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,image_data=payload,memory_profile=out/'memory.json',dos_mounts=[dict(alias='RAM',format=3)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:runtime,_=execute(b,program,timeout=180,frame_limit=9000)
        except Exception:
            print({k:data(b,program['image'],k) for k in ['checks','currentCase','primary','secondary','reason']},flush=True);raise
        ownership(b,program,out)
        checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
    return dict(status='pass',tier='development',checks=checks,runtime=runtime,machine=machine,build=program['build'],overrides={n:hashlib.sha256((out/n).read_bytes()).hexdigest() for n in ['sdxfiles.act','sdxmutation.act']})

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True);result=dict(status='running')
    try:result=run(out)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('ARC faults',result['status'],result['checks'],flush=True)
