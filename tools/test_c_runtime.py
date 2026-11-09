#!/usr/bin/env python3
"""Focused common C runtime components in ordinary loaded Processes."""
import argparse,fcntl,json
from pathlib import Path
from native_program import ROOT,require
from generate_c_runtime import expected_layout
from c_program import ABI
from test_c_process import run as process_run


def fixture(out,group):
    out.mkdir(parents=True,exist_ok=True)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    path=out/'runtime.act'
    body='''
PROC Main()
  BYTE index

  FOR index=0 TO 1 DO
    BEGIN
      LET image=Load()
      Collected(Start(image,BYTE POINTER(c"F")),-321)
      PROGRAM.Unload(image)
    END
  OD
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
'''
    if group!='abi':
        body='''
PROC Main()
  PROGRAMIMAGE.Image POINTER first,second
  LONGCARD one,two

  first=Load()
  Collected(Start(first,BYTE POINTER(c"F")),-321)
  PROGRAM.Unload(first)
  baseline=EXEC.AvailMem(0)
  first=Load()
  second=Load()
  one=Start(first,BYTE POINTER(c"F"))
  two=Start(second,BYTE POINTER(c"F"))
  Collected(one,-321)
  Collected(two,-321)
  Collected(Start(first,BYTE POINTER(c"F")),-322)
  PROGRAM.Unload(first)
  PROGRAM.Unload(second)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
'''
    if group!='abi':
        body=body.replace('  first=Load()', '  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)\n  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)\n  Require(input<>NULL AND output<>NULL)\n  LET oldInput=DOS.SelectInput(input)\n  LET oldOutput=DOS.SelectOutput(output)\n  first=Load()',1)
        body=body.replace('  Require(DOS.ReleaseContext()<>0)', '  DOS.SelectInput(oldInput)\n  DOS.SelectOutput(oldOutput)\n  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)\n  Require(DOS.ReleaseContext()<>0)')
    path.write_text(prefix+body)
    return path


def _run(out,group,mode,reuse=False,filesystem="sdfs"):
    if group=='retirement-failure':
        from test_c_runtime_retirement import run as retirement
        require(mode=='opt','Retirement failure is an optimized lifecycle check')
        return retirement(out,reuse)
    if group in ('lifecycle','coexistence'):
        from test_c_runtime_process import run as lifecycle
        return lifecycle(out,mode,reuse,coexistence=group=='coexistence')
    abi=group=='abi'
    source=ROOT/('tests/programs/c_runtime_abi.c' if abi else
        'tests/programs/c_runtime_prefix.c' if mode=='raw' else 'tests/programs/c_runtime_allocation.c')

    if group=='files':
        source=ROOT/('tests/programs/c_runtime_io_abi.c' if mode=='raw' else 'tests/programs/c_runtime_files.c')
    if group=='unwind':
        source=ROOT/'tests/programs/c_runtime_unwind.c'
    if group=='relocation':source=ROOT/'tests/programs/c_program_app.c'
    probes=[(ROOT/'c/runtime/layout.c',expected_layout())]
    if group=='files':
        probes.append((ROOT/'c/runtime/stdio-layout.c',[
            ('size_t',2),('fpos_t',4),('FILE',25),('stream list',20),
            ('FILE fd',4),('FILE oflags',22),('FILE flags',24)]))
    if group=='unwind':probes.append((source,[('jmp_buf',16)]))
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[source]+([ROOT/'tests/programs/c_program.c'] if group=='relocation' else []),
        app_options=dict(minimum_stack=ABI['stack_floor_bytes'],includes=[ROOT/'c/runtime'],probes=probes,
            definitions={} if abi or group in ('unwind','relocation') else {name:['-DEXEC_CRT_TEST'] for name in
                (('allocation.c','files.c') if group=='files' else ('allocation.c',))},
            runtime_attributes={'printf':'nofloat'},
            extra_assembly=[ROOT/'tests/programs/c_runtime_unwind_registers.s'] if group=='unwind' else []),
        fixture_source=fixture(out,group),expected_completed=2 if abi else 4,native_optimize=True,
        release_compiler=True,loader_failures=False,observe_stacks=not abi,
        filesystem=filesystem,writable=not abi,ram=not abi)
    if group=='files' and mode=='opt':
        from filesystem_audit import Audit
        audit=Audit((out/'system.atr').read_bytes())
        summary=getattr(audit,filesystem)()
        persisted={name:payload for name,payload in audit.files.items()
                   if name.startswith('CRT') and name.endswith('.DAT')}
        require(len(persisted)>=2 and all(payload==bytes([97,128,255,13,10,155,0,99,10,13])
                                         for payload in persisted.values()),
                'Independent filesystem audit found incorrect persisted runtime bytes')
        record['persisted_files']=dict(names=sorted(persisted),bytes_each=10,audit=summary)
    require(record['runtime']['native_irq_count']>0 and record['runtime']['native_nmi_count']>0,
            'Missing asynchronous entry evidence')
    record['c_runtime_component']=dict(group=group,mode=mode,
        production_app_abi=record['app']['abi']['version'])
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record



def run(out,group,mode,reuse=False,filesystem="sdfs"):
    out.mkdir(parents=True,exist_ok=True)
    with (out/'.runtime.lock').open('a') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('Runtime verification already running in '+str(out)) from None
        return _run(out,group,mode,reuse,filesystem)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=['abi','allocation','arguments','files','unwind','lifecycle','coexistence','retirement-failure','relocation'],required=True)
    parser.add_argument('--case',choices=['raw','opt'],default='opt')
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--filesystem',choices=['sdfs','mydos'],default='sdfs')
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args()
    run(args.output.resolve(),args.group,args.case,args.from_build,args.filesystem)
