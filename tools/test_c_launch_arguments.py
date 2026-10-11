#!/usr/bin/env python3
"""Small raw/optimized C -> native launcher probes with real disk children."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256,read_build
from calypsi_build import emit
from library_paths import read_source
from build_command import compile_command
from make_data_disk import make
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data

def run(out,optimize,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        p=read_build(out/'program')
        from calypsi_image import read_image
        f=read_image(out/'c/program.elf')
        require(f['provenance']['elf_sha256']==p['build']['foreign_image']['elf_sha256'],'Changed C fixture')
    else:
        f=emit(out/'c',[ROOT/'tests/programs/c_launch_arguments.c',ROOT/'c/calypsi/dos.c',ROOT/'c/calypsi/exec.c'],
            [ROOT/'c/calypsi/dos.s',ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],(),optimize,
            roots=['LaunchProbe','LaunchRelease','LaunchChecks','ExecDosEntries'])
        child=out/'child.act'
        child.write_text('''MODULE ARGUMENTCHILD
USE COMMAND
USE CSTRING AS STR
LONGINT FUNC Main()
  BYTE POINTER released
  CARD index

  released=BYTE POINTER($%x)
  WHILE released(0)=0 DO
    COMMAND.Yield()
  OD

  LET args=COMMAND.GetArgStr()
  LET length=CARD(STR.strlen(args))
  LET bytes=BYTE POINTER(args)
  IF length<>0 THEN
    FOR index=0 TO length-1 DO
      IF bytes(index)<>65 THEN
        RETURN(41)
      FI
    OD
  FI

RETURN(IF length=0 THEN 7 ELSE IF length=1 THEN 8 ELSE IF length=255 THEN 9 ELSE 42 FI FI FI)
ENDMODULE
'''%f['symbols']['LaunchRelease'])
        media=out/'media';media.mkdir(exist_ok=True)
        compile_command(compiler(ROOT/'build/actionc'),child,out/'native/ARGS',optimize)
        (media/'ARGS').write_bytes((out/'native/ARGS').read_bytes())
        make(out/'data.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names={'ARGS'})
        binding='CONST C_EXECDOSENTRIES=$%x\n'%f['symbols']['ExecDosEntries']+read_source(ROOT/'c/calypsi/dos-bridge.inc')
        source=out/'probe.act'
        source.write_text('''MODULE CLAUNCHTEST
USE EXEC
USE DOS
USE PROCESS
USE PROGRAM
USE PROGRAMFILE
USE CALYPSICALL
'''+binding+'''
LONGINT result
PROC Main()

  BindDos(0)
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
  DOS.ReleaseContext()

RETURN
ENDMODULE
'''%f['symbols']['LaunchProbe'])
        from generate_memory import PROFILE
        profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
        memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
        p=build(compiler(ROOT/'build/actionc'),source,out/'program',tasks=True,task_capacity=8,
            foreign_image=f,optimize=optimize,console=True,
            dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)],
            memory_profile=memory)
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','generic56k');b.mount(0,str(out/'data.atr'))
        machine=verify_machine(b,rom,pin)
        runtime,_=execute(b,p,timeout=180,frame_limit=12000,timer_irq=False)
        result=data(b,p['image'],'result',True)
        require(result==[0,0],'Launch argument assertion: '+str(result))
        checks=int.from_bytes(b.memdump(f['symbols']['LaunchChecks'],2),'little')
        ownership(b,p,p['output'])
    record=dict(status='pass',tier='development',optimize=optimize,checks=checks,machine=machine,
        runtime=runtime,c_elf_sha256=f['provenance']['elf_sha256'],native_image_sha256=p['build']['image_sha256'])
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n');print('Launch arguments pass',optimize,checks,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True)
    p.add_argument('--raw',action='store_true');p.add_argument('--from-build',action='store_true');a=p.parse_args()
    run(a.output.resolve(),not a.raw,a.from_build)
