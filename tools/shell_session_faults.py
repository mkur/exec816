"""Build-only allocation observer; production controller and cleanup stay real."""
import json
from pathlib import Path

from library_paths import read_source
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

FAULT='''MODULE SESSIONFAULT
USE EXEC
PUBLIC CARD wanted,remaining,count
PUBLIC LONGCARD failedSize
PUBLIC BYTE active,fired
PUBLIC PROC Begin()
  remaining=wanted
  count=0
  fired=0
  active=1
RETURN
PUBLIC BYTE POINTER FUNC AllocMem(LONGCARD size,attributes)
  BYTE fail
  fail=0
  EXEC.Forbid()
  IF active<>0 THEN
    count==+1
    IF remaining<>0 THEN
      remaining==-1
      IF remaining=0 THEN
        fired=1
        failedSize=size
        fail=1
      FI
    FI
  FI
  EXEC.Permit()
  IF fail<>0 THEN
    RETURN(NULL)
  FI
RETURN(EXEC.AllocMem(size,attributes))
ENDMODULE
'''


def run(out, reuse=False):
    import generate_tasks
    out.mkdir(parents=True,exist_ok=True)
    (out/'sessionfault.act').write_text(FAULT)
    includes={}
    # Rewrite app allocations and the independently allocated READY reply port.
    for name in ('shell-session-client.inc','shell-sessions.inc','shell-session.inc','shell-controller.inc'):
        source=read_source(ROOT/'examples/shell'/name,includes=includes)
        source=source.replace('EXEC.AllocMem(', 'SESSIONFAULT.AllocMem(')
        if name=='shell-session.inc':source=source.replace('USE EXEC\n','USE EXEC\nUSE SESSIONFAULT\n',1)
        if name=='shell-controller.inc':
            source=source.replace('  IF controllerLive>=SESSION_CAPACITY',
                                  '  SESSIONFAULT.Begin()\n  IF controllerLive>=SESSION_CAPACITY',1)
            source=source.replace('  request.primary=primary\n',
                '  IF request.operation=SESSION_CREATE OR request.operation=SESSION_READY THEN\n    SESSIONFAULT.active=0\n  FI\n\n  request.primary=primary\n',1)
        if name=='shell-controller.inc':
            source=source.replace('    WHILE context.shell.done=0 DO',
                                  '    ClientFailure(context)\n    WHILE context.shell.done=0 DO',1)
        target=out/name;target.write_text(source);includes[name]=target
    source=out/'shell_session_failures.act'
    source.write_text(read_source(ROOT/'tests/programs/shell_session_failures.act',includes=includes))
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    original=generate_tasks.generate_kernel
    observed={}
    def generated(output,*args,**kwargs):
        result=original(output,*args,**kwargs)
        # Prefer the generated platform variant where one exists. Reapply after
        # each generator pass so recorded hashes match the emitted sources.
        for path in (ROOT/'lib').glob('*/*.act'):
            target=Path(output)/'task-kernel'/path.name
            if not target.exists():target=Path(output)/path.name
            content=target.read_text() if target.exists() else read_source(path)
            if 'EXEC.AllocMem(' not in content:continue
            content=content.replace('EXEC.AllocMem(', 'SESSIONFAULT.AllocMem(')
            if 'USE SESSIONFAULT\n' not in content:
                lines=content.splitlines();index=next(i for i,line in enumerate(lines) if line.startswith('MODULE '))
                lines.insert(index+1,'USE SESSIONFAULT');content='\n'.join(lines)+'\n'
            target.write_text(content);observed[str(target.relative_to(out))]=sha256(target)
        return result
    try:
        generate_tasks.generate_kernel=generated
        program=read_build(out) if reuse else build(compiler(ROOT/'build/actionc',release=True),
            source,out,optimize=True,tasks=True,task_capacity=8,console=True,
            dos_mounts=[],memory_profile=memory)
    finally:generate_tasks.generate_kernel=original
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        for key,value in pin['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        try:runtime,_=execute(b,program,timeout=180,frame_limit=15000)
        except Exception:
            print('Failure fixture checks/case/size',data(b,program['image'],'failedSize',True),data(b,program['image'],'checks',True),
                  data(b,program['image'],'faultCase',True),flush=True)
            raise
        require(data(b,program['image'],'finished')==[1],'Incomplete allocation failures')
        ownership(b,program,out)
        details={name:data(b,program['image'],name,True)[0]
                 for name in ('checks','allocations','acceptedFailures')}
    return dict(status='pass',tier='development',group='allocation',mode='opt',
                observed_sources=observed,build=program['build'],runtime=runtime,machine=machine,**details)
