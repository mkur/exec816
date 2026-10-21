#!/usr/bin/env python3
"""WB6 emitted combined-wait races and raw/optimized public layout."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine

LAYOUT=[('Wait size',58)]+list(zip(
    ('flags','buttonClicks','buttonMask','buttonState','m1Flags','m1X','m1Y','m1Width','m1Height',
     'milliseconds','signalMask','received','message','mouseX','mouseY','mouseButtons','keyState','key','clicks'),
    (0,2,4,6,8,10,12,14,16,18,22,26,30,46,48,50,52,54,56)))


def prepare(out):
    from build_c_program import build as application
    from build_bitmap_console import drawing,prepare as launcher
    from build_command import compile_command
    from c_program import ABI,binding
    from generate_aes_server import expected_layout
    from generate_memory import PROFILE
    from make_data_disk import make
    out.mkdir(parents=True,exist_ok=True)
    driver=out/'layout-driver.c';driver.write_text('#include <string.h>\nvolatile unsigned short value;\nchar name[]="layout";\nint main(void) { return strcmp(name,(const char *)&value); }\n')
    for name,optimize in [('layout',True),('layout-raw',False)]:
        application(out/name,[driver],optimize,probes=[(ROOT/'tests/programs/aes_wait_layout.c',LAYOUT)])
    source=(ROOT/'c/calypsi/aes-events.c').read_text().replace('#include "aes-private.h"',
        '#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\n'+
        'void AESWaitBeforeForbid(struct ExecAESContext *);\n'+
        'void AESWaitBeforeWait(struct ExecAESContext *,ULONG);\n'+
        'void AESWaitBeforeCancel(struct ExecAESContext *);')
    for old,new in [
        ('        Forbid();','        AESWaitBeforeForbid(c);\n        Forbid();'),
        ('        seen|=Wait(mask)&externalMask;','        AESWaitBeforeWait(c,mask);\n        seen|=Wait(mask)&externalMask;'),
        ('        t->state = AES_ALARM_RETIRING;','        t->state = AES_ALARM_RETIRING;\n        AESWaitBeforeCancel(c);')]:
        require(source.count(old)==1,'Changed combined-wait boundary: '+old);source=source.replace(old,new)
    instrumented=out/'aes-events.c';instrumented.write_text(source)
    f=drawing(out,True,widgets=True,client_sources=[ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',
        instrumented,ROOT/'c/calypsi/program.c',ROOT/'tests/programs/aes_exec_wait.c'],
        client_entries=['AESWaitPeer'],client_roots=['AESWaitRun','AESService','AESWaitChecks','AESWaitFailures','AESWaitFirstFailure','AESWaitStage',
            'ExecProgramRun',*ABI['imports']],client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
                (ROOT/'tests/programs/aes_wait_layout.c',LAYOUT)])
    binding(f,out)
    child=out/'child.act';child.write_text('MODULE WAITCHILD\nUSE COMMAND\nLONGINT FUNC Main()\n\nRETURN(0)\nENDMODULE\n')
    compile_command(compiler(ROOT/'build/actionc',release=True),child,out/'native/CHILD',True)
    media=out/'media';media.mkdir(exist_ok=True);(media/'CHILD').write_bytes((out/'native/CHILD').read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names={'CHILD'})
    p=out/'probe.act';p.write_text('''MODULE AESWAITPROBE
USE EXEC
USE DOS
USE PROGRAMFILE
USE PROGRAMLOAD
USE PROGRAM
USE AESBOOT
USE CALYPSICALL
USE HEAPCORE
LONGINT result
PROC Main()

  LET image=PROGRAMFILE.Load(BYTE POINTER(c"SYS:CHILD"))
  IF image=NULL THEN
    HEAPCORE.Abort($fce0)
  FI

  PROGRAM.Unload(image)
  LET service=LONGCARD POINTER($%x)
  service^=LONGCARD(ADDRESS(AESBOOT.Port()))
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
  IF result<>0 THEN
    HEAPCORE.Abort($fce1)
  FI

  IF DOS.ReleaseContext()=0 THEN
    HEAPCORE.Abort($fce2)
  FI

RETURN
ENDMODULE
'''%(f['symbols']['AESService'],f['symbols']['AESWaitRun']))
    source=launcher(p,out,f,desktop=True,aes=True)
    memory=out/'fixture-memory.json';profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192;memory.write_text(json.dumps(profile,indent=2)+'\n')
    build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,
        foreign_image=f,console_deferred=True,memory_profile=memory,system_mount='D1',stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)])


def exercise(out):
    from os_boundary import emulator
    from test_mouse_observe import PIN,BRIDGE,ROM
    from test_dos_stack import execute,ownership
    from stack_budget import stack_usage
    p=read_build(out/'program');f=json.loads((out/'c-image.json').read_text())
    report=dict(status='running',slice='WB6',tier='development',qualification=False,
        instrumented_source_sha256=sha256(out/'aes-events.c'),
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'));report['machine']=verify_machine(b,ROM,PIN)
            try:report['runtime'],_=execute(b,p,timeout=180,frame_limit=9000)
            finally:
                for name in ('AESWaitChecks','AESWaitFailures','AESWaitFirstFailure','AESWaitStage'):
                    report[name]=b.peek16(f['symbols'][name])
            require(report['AESWaitFailures']==0 and report['AESWaitChecks']>=35,'Incomplete combined-wait checks')
            ownership(b,p,p['output']);report['stack_usage']=stack_usage(b,p['build']['memory'])
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--from-build',action='store_true');a=p.parse_args();out=a.output.resolve()
    if not a.from_build:prepare(out)
    exercise(out)
