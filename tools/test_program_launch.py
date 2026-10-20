#!/usr/bin/env python3
"""WB5: explicit native/C/FB65 child contexts, setup ACK and fitting stacks."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from library_paths import read_source,library_file


def prepare(out):
    from build_c_program import build as application
    from build_bitmap_console import drawing,prepare as launcher
    from build_command import compile_command
    from build_fastbasic import compile_program
    from c_program import ABI,binding,pack
    from generate_aes_server import expected_layout
    from make_data_disk import make
    from test_process_lifetime import overrides
    from generate_memory import PROFILE
    out.mkdir(parents=True,exist_ok=True)
    app=application(out/'controller',[ROOT/'tests/programs/program_launch.c'])
    child=application(out/'child',[ROOT/'tests/programs/program_launch_child.c'],minimum_stack=ABI['stack_floor_bytes'])
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'CONTROL.APP').write_bytes((out/'controller/program.app').read_bytes())
    (media/'CHILD.APP').write_bytes((out/'child/program.app').read_bytes())
    (media/'LARGE.APP').write_bytes(pack(child['image'],child['relocations'],2560)[0])
    compile_command(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/program_launch_child.act',out/'native/NATIVE',True)
    (media/'NATIVE').write_bytes((out/'native/NATIVE').read_bytes())
    compile_program(ROOT/'build/fastbasic/source',ROOT/'tests/fastbasic/launch.bas',out/'guest/GUEST.COM')
    (media/'GUEST.COM').write_bytes((out/'guest/GUEST.COM').read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names={p.name for p in media.iterdir()})
    f=drawing(out,True,widgets=True,client_sources=[ROOT/'c/calypsi'/n for n in ('aes.c','aes-messages.c','aes-events.c','program.c')],
        client_roots=['ExecProgramRun',*ABI['imports']],client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout())])
    binding(f,out)
    changes=overrides(out)
    (out/'processcontrol.act').write_text('MODULE PROCESSCONTROL\nPUBLIC BYTE fault,cloneFail\nPUBLIC CARD clones,scopeChecks\nENDMODULE\n')
    changes['processcontrol.act']=sha256(out/'processcontrol.act')
    # Exercise public scope operations at the normal user-entry boundary,
    # inside the actual child context, with both bound and private scopes.
    path=out/'process.act';text=path.read_text().replace('USE PROCESSCONTROL\n','USE PROCESSCONTROL\nUSE DOSBREAK\n',1)
    marker='  IF image.kind=PROGRAMIMAGE.KIND_SDX THEN'
    require(text.count(marker)==1,'Changed loaded child entry boundary')
    text=text.replace(marker,'''  IF (process.breakFlags & PROCESSSTATE.BREAK_BACKGROUND)<>0 THEN
    BEGIN
      LET scope=DOSBREAK.Current()
      LET cause=DOSCLIENT.IoErr()
      IF DOS.EndForeground()<>0 OR DOSCLIENT.IoErr()<>DOS.ERROR_OBJECT_IN_USE
          OR DOSBREAK.Current()<>scope THEN
        HEAPCORE.Abort($fcf0)
      FI

      IF scope.handle<>NULL THEN
        IF DOS.BeginForeground(DOS.FileHandle POINTER(scope.handle))<>0
            OR DOSCLIENT.IoErr()<>DOS.ERROR_OBJECT_IN_USE
            OR DOSBREAK.Current()<>scope THEN
          HEAPCORE.Abort($fcf1)
        FI
      FI

      PROCESSCONTROL.scopeChecks==+1
      DOSCLIENT.SetError(cause)
    END
  FI

'''+marker)
    path.write_text(text);changes['process.act']=sha256(path)
    text=read_source(library_file('dosinherit.act')).replace('USE EXEC\n','USE EXEC\nUSE PROCESSCONTROL\n',1)
    marker='  FSTYPES.Object POINTER file\n\n  IF identity=BYTE POINTER(0) THEN'
    require(text.count(marker)==1,'Changed wrapper clone entry')
    text=text.replace(marker,'  FSTYPES.Object POINTER file\n\n  PROCESSCONTROL.clones==+1\n  IF PROCESSCONTROL.cloneFail<>0\n      AND PROCESSCONTROL.clones=PROCESSCONTROL.cloneFail THEN\n    DOSCLIENT.SetError(ERROR_NO_FREE_STORE)\n    RETURN(NULL)\n  FI\n\n  IF identity=BYTE POINTER(0) THEN')
    (out/'dosinherit.act').write_text(text);changes['dosinherit.act']=sha256(out/'dosinherit.act')
    text=read_source(library_file('dosbreak.act')).replace('USE EXEC\n','USE EXEC\nUSE PROCESSCONTROL\n',1)
    marker='  signal=EXEC.AllocSignal($ff)';require(text.count(marker)==1,'Changed scope signal allocation')
    text=text.replace(marker,'  signal=$ff\n  IF PROCESSCONTROL.fault<>7 THEN\n    signal=EXEC.AllocSignal($ff)\n  FI')
    marker='  scope=DOSBREAKTYPES.Scope POINTER(EXEC.AllocMem(DOSBREAKTYPES.SCOPE_SIZE,\n      EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))'
    require(text.count(marker)==1,'Changed scope heap allocation')
    text=text.replace(marker,'  scope=NULL\n  IF PROCESSCONTROL.fault<>8 THEN\n  '+marker+'\n  FI')
    (out/'dosbreak.act').write_text(text);changes['dosbreak.act']=sha256(out/'dosbreak.act')
    source=out/'probe.act'
    source.write_text(read_source(ROOT/'tests/programs/program_launch.act').replace('CONTROLLER_CHECKS_OFFSET',str(app['image']['symbols']['LaunchChecks']-(app['abi']['link_bank']<<16))))
    source=launcher(source,out,f,desktop=True,aes=True)
    memory=out/'fixture-memory.json';profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192;memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,
        foreign_image=f,console_deferred=True,memory_profile=memory,system_mount='D1',sdx=True,stack_checks=True,
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2),dict(alias='RAM',format=3)])
    (out/'overrides.json').write_text(json.dumps(changes,indent=2)+'\n')


def exercise(out):
    from os_boundary import emulator
    from test_mouse_observe import PIN,BRIDGE,ROM
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    from stack_budget import stack_usage
    p=read_build(out/'program')
    result=dict(status='running',slice='WB5',tier='development',qualification=False,
        fixture_overrides=json.loads((out/'overrides.json').read_text()),
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'))
            result['machine']=verify_machine(b,ROM,PIN)
            try:result['runtime'],_=execute(b,p,timeout=240,frame_limit=12000)
            finally:
                for name in ('checks','controllerChecks','phase','primary','secondary','reason'):
                    symbol=next(x for x in p['image']['data'] if x['name'].startswith('M_PROGRAMLAUNCH_'+name.upper()+'_'))
                    result[name]=int.from_bytes(b.memdump(symbol['address'],symbol['size']),'little',signed=name in ('primary','secondary','reason'))
                symbol=next(x for x in p['image']['data'] if x['name'].startswith('M_PROCESSCONTROL_SCOPECHECKS_'))
                result['scope_checks']=b.peek16(symbol['address'])
                symbol=next(x for x in p['image']['data'] if x['name'].startswith('M_PROGRAMLAUNCH_APPBASE_'))
                base=int.from_bytes(b.memdump(symbol['address'],4),'little')
                if base and result.get('phase')==1:
                    app=json.loads((out/'controller/app.json').read_text())
                    result['observed_controller_checks']=b.peek16(base+app['image']['symbols']['LaunchChecks']-(app['abi']['link_bank']<<16))
                result['task_placements']=[]
                for slot,pool in enumerate(p['build']['memory']['task_pools'][:8]):
                    row=b.memdump(p['build']['task_storage']['BASE']+slot*64,64)
                    task=int.from_bytes(row[:3],'little');name=''
                    if task and row[8]:
                        pointer=int.from_bytes(b.memdump(task+8,3),'little')
                        if pointer:name=b.memdump(pointer,32).split(b'\0')[0].decode('ascii','replace')
                    result['task_placements'].append(dict(slot=slot,state=row[8],task=task,name=name,stack=pool['stack_bytes']))
            ownership(b,p,p['output']);result['stack_usage']=stack_usage(b,p['build']['memory'])
        result['status']='pass'
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--from-build',action='store_true');args=a.parse_args()
    out=args.output.resolve()
    if not args.from_build:prepare(out)
    exercise(out)
