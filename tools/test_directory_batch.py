#!/usr/bin/env python3
"""Focused emitted directory-batch API, scanner and retirement checks."""
import argparse
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine
from calypsi_build import emit
from library_paths import read_source, library_file
from build_command import compile_command
from make_data_disk import make
from os_boundary import emulator
from test_dos_stack import execute, ownership
from test_cooperative import data
from banked_test_memory import read

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def cancellation(out):
    out.mkdir(parents=True,exist_ok=True)
    for name in ('dirbatchprobe.act','dirbatchstate.act','directory_batch_cancel.act'):
        (out/name).write_bytes((ROOT/'tests/programs'/name).read_bytes())
    edits={
        'fsworker.act':[('    FSOPERATION.Pump(registry)',
                         '    FSOPERATION.Pump(registry)\n    DIRBATCHPROBE.Checkpoint(service)')],
        'dosclient.act':[('  EXEC.PutMsg(handler,@client.packet.sp_Msg)',
                          '  EXEC.PutMsg(handler,@client.packet.sp_Msg)\n  DIRBATCHSTATE.Queued()')],
        'fsdirectory.act':[('    service.stage=70\n    FSPACKET.Reply(service)',
                            '    service.stage=70\n    DIRBATCHSTATE.Final()\n    FSPACKET.Reply(service)'),
                           ('  LET status=FSBACKEND.BeginEntry(service.work,',
                            '  IF service.work.error<>0 THEN\n    RETURN(FSPACKET.Error(service,service.work.error))\n  FI\n  LET status=FSBACKEND.BeginEntry(service.work,')],
        'blockwire.act':[('  EXEC.SendIO(EXEC.IORequest POINTER(request))',
                          '  EXEC.SendIO(EXEC.IORequest POINTER(request))\n  DIRBATCHPROBE.OnWire(EXEC.IORequest POINTER(request))')],
    }
    for name,changes in edits.items():
        source=read_source(library_file(name)).replace('\nUSE ','\nUSE '+('DIRBATCHSTATE' if name=='dosclient.act' else 'DIRBATCHPROBE\nUSE DIRBATCHSTATE')+'\nUSE ',1)
        for old,new in changes:
            require(source.count(old)==1,'Stale batch checkpoint '+name)
            source=source.replace(old,new)
        (out/name).write_text(source)
    media=out/'media/DATA'; media.mkdir(parents=True,exist_ok=True)
    for i in range(20): (media/f'F{i:02}').write_bytes(bytes([i])*3)
    make(out/'data.atr',out/'media',filesystem='sdfs',sector_bytes=256,sectors=2880)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4352
    memory=out/'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),out/'directory_batch_cancel.act',out,
            tasks=True,task_capacity=8,optimize=True,console=True,kernel_bank=18,memory_profile=memory,
            dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,format=2,profile=4)])
    scenario=next(d['address'] for d in p['image']['data'] if '_BATCHCANCELTEST_SCENARIO_' in d['name'])
    cases=[]
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=PIN) as b:
        machine=verify_machine(b,rom,PIN)
        b.config('diskemu','generic56k'); b.mount(0,str(out/'data.atr'))
        for number,name in enumerate(('before','queued','first','prefix','wire','final','error'),1):
            if number>1: b.state_load(slot='loaded')
            def before(b):
                if number==1: b.state_save(slot='loaded')
                b.memload(scenario,number.to_bytes(2,'little'))
            caseout=out/name; caseout.mkdir(exist_ok=True)
            print('Batch cancellation',name,flush=True)
            runtime,_=execute(b,{**p,'output':caseout},before_run=before,preloaded=number>1,
                              timeout=240,frame_limit=12000)
            ownership(b,p,p['output'])
            cases.append(dict(name=name,runtime=runtime,checks=data(b,p['image'],'checks',True)))
    result=dict(status='pass',tier='development',group='cancellation',cases=cases,
                machine=machine,build=p['build'],bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def run(out, optimize=True, filesystem='sdfs', group='enumeration'):
    out.mkdir(parents=True, exist_ok=True)
    t=compiler(ROOT/'build/actionc', release=True)
    foreign=emit(out/'c', [ROOT/'tests/programs/directory_batch.c', ROOT/'c/calypsi/dos.c'],
                 [ROOT/'c/calypsi/dos.s', ROOT/'c/calypsi/image-info.s'], (), optimize,
                 roots=['ExecDosEntries','abiOnly','filesystem','completed'])
    media=out/'media'; media.mkdir(exist_ok=True)
    for name in ('DATA/ALPHA','DATA/BETA','EMPTY','EIGHT'):
        (media/name).mkdir(parents=True,exist_ok=True)
    for i in range(18): (media/'DATA'/f'F{i:02}').write_bytes(bytes([i])*i*3)
    for i in range(8): (media/'EIGHT'/f'F{i:02}').write_bytes(b'x')
    command=out/'batch.act'
    command.write_text('''MODULE BATCHCOMMAND
USE COMMAND
COMMAND.FileInfoBlock info
COMMAND.DirBatch batch
LONGINT FUNC Main()
  LET lock=COMMAND.Lock(BYTE POINTER(c"D1:DATA"),COMMAND.SHARED_LOCK)
  IF lock=NULL THEN
    RETURN(1)
  FI

  IF COMMAND.Examine(lock,BYTE POINTER(@info))=0 THEN
    RETURN(2)
  FI

  batch.capacity=1
  LET count=COMMAND.ExNextBatch(lock,BYTE POINTER(@info),BYTE POINTER(@batch))
  LET error=COMMAND.IoErr()
  COMMAND.UnLock(lock)
  IF count<>1 OR error<>0 OR batch.entries(0).name(0)=0 THEN
    RETURN(3)
  FI

RETURN(0)
ENDMODULE
''')
    compile_command(t,command,out/'native/BATCH',optimize)
    (media/'BATCH').write_bytes((out/'native/BATCH').read_bytes())
    make(out/'data.atr',media,filesystem='sdfs' if filesystem=='ram' else filesystem,
         sector_bytes=256,sectors=2880,
         binary_names={'BATCH',*(f'F{i:02}' for i in range(18))})
    binding=read_source(ROOT/'c/calypsi/dos-bridge.inc').split('; Bind once')[0]
    binding+='PROC BindDos()\n  LET entries=ADDRESS POINTER($%x)\n'%foreign['symbols']['ExecDosEntries']
    for index,name in ((2,'COpen'),(3,'CClose'),(5,'CLock'),(6,'CUnLock'),(7,'CExamine'),
                       (8,'CExNext'),(9,'DOS.IoErr'),(18,'CCreateDir'),(20,'CDeleteFile'),(24,'CExNextBatch')):
        binding+=f'  entries({index})=ADDRESS(@{name})\n'
    binding+='RETURN\n'
    source=out/'probe.act'
    source.write_text('''MODULE DIRECTORYBATCHTEST
USE EXEC
USE DOS
USE PROGRAM
USE PROGRAMFILE
USE PROCESS
USE CALYPSICALL
'''+binding+'''
LONGINT result,commandResult
PROC Main()
  PROCESS.Result outcome
  LONGCARD identity
  BindDos()
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
  LET image=PROGRAMFILE.Load(BYTE POINTER(c"D1:BATCH"))
  commandResult=1
  IF image<>NULL THEN
    identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
    IF identity<>0 AND PROCESS.Wait(identity,@outcome)<>0 THEN
      commandResult=outcome.primary
    FI
    PROGRAM.Unload(image)
  FI
  DOS.ReleaseContext()
RETURN
ENDMODULE
'''%foreign['symbols']['main'])
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4352
    memory=out/'memory.json'; memory.write_text(json.dumps(profile)+'\n')
    p=build(t,source,out/'program',tasks=True,task_capacity=8,foreign_image=foreign,
            optimize=optimize,console_deferred=True,kernel_bank=18,memory_profile=memory,
            sio_enabled=True,dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,format=1 if filesystem=='mydos' else 2,profile=4),dict(alias='RAM',format=3)],
            image_data=[(0x2dffe0,bytes([0xa5])*(1890+32))])
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=PIN) as b:
        machine=verify_machine(b,rom,PIN)
        b.config('diskemu','generic56k'); b.mount(0,str(out/'data.atr'))
        def before(b):
            b.memload(foreign['symbols']['abiOnly'],int(group=='abi').to_bytes(2,'little'))
            b.memload(foreign['symbols']['filesystem'],(3 if filesystem=='ram' else 2 if filesystem=='sdfs' else 1).to_bytes(2,'little'))
        runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=15000)
        result=int.from_bytes(bytes(data(b,p['image'],'result')),'little')
        command_result=int.from_bytes(bytes(data(b,p['image'],'commandResult')),'little')
        require(result==0,f'C batch probe failed: {result}')
        require(command_result==0,f'COMMAND batch probe failed: {command_result}')
        require(read(b,0x2dffe0,16,out)==read(b,0x2dfff0+1890,16,out)==bytes([0xa5])*16,
                'Bank-crossing batch buffer guards changed')
        ownership(b,p,p['output'])
    result=dict(status='pass',tier='development',group=group,filesystem=filesystem,
                optimize=optimize,runtime=runtime,machine=machine,build=p['build'],
                c_layout=foreign['provenance']['checked_layout'],
                bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Directory batch passed',group,filesystem,'opt' if optimize else 'raw',flush=True)
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--output',type=Path,required=True)
    a.add_argument('--raw',action='store_true')
    a.add_argument('--format',choices=('sdfs','mydos','ram'),default='sdfs')
    a.add_argument('--group',choices=('abi','enumeration','cancellation'),default='enumeration')
    args=a.parse_args()
    if args.group=='cancellation': cancellation(args.output.resolve())
    else: run(args.output.resolve(),not args.raw,args.format,args.group)
