#!/usr/bin/env python3
"""D4: loaded pipeline lifetime, partial launch, BREAK and real file I/O."""
import argparse
import json
import shutil
from pathlib import Path
from build_command import compile_command
from library_paths import read_source
from make_shell_disk import make
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(out,mode,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    toolchain=compiler(ROOT/'build/actionc')
    blobs=[];commands={}
    for name,source,address in [('HELLO','examples/commands/hello.act',0xe0000),
                                ('WC','examples/commands/wc.act',0xe4000),
                                ('FLOW','tests/programs/loaded_flow.act',0xe8000)]:
        commands[name]=compile_command(toolchain,ROOT/source,out/name,mode=='opt')
        payload=(out/name).read_bytes();require(len(payload)<16384,'Oversize group fixture command')
        blobs.append((address,payload))
    (out/'pipeline-fixture.inc').write_text(''.join(f'CONST {name}_BYTES={len(blob[1])}\n' for name,blob in zip(commands,blobs)))
    source=out/'probe.act'
    source.write_text(read_source(ROOT/'tests/programs/pipeline_group.act',{'pipeline-fixture.inc':out/'pipeline-fixture.inc'}))
    shutil.copyfile(ROOT/'tests/programs/groupprobe.act',out/'groupprobe.act')
    text=read_source(ROOT/'lib/dos/process.act').replace('USE EXEC\n','USE EXEC\nUSE GROUPPROBE\n',1)
    needle='PROCESSSTATE.Entry POINTER FUNC Control(BYTE operation BYTE POINTER argument)\n'
    require(text.count(needle)==1,'Stale launch override')
    text=text.replace(needle,needle+'''  IF operation=PROCESSSTATE.OP_LAUNCH AND GROUPPROBE.failLaunch<>0 THEN
    GROUPPROBE.failLaunch==-1
    IF GROUPPROBE.failLaunch=0 THEN DOSCLIENT.SetError(ERROR_NO_FREE_STORE) RETURN(PROCESSSTATE.Entry POINTER(0)) FI
  FI
''')
    (out/'process.act').write_text(text)
    text=read_source(ROOT/'lib/dos/dosgroup.act').replace('USE EXEC\n','USE EXEC\nUSE GROUPPROBE\n',1)
    needle='  scope=DOSBREAK.Allocate(client,console)'
    require(text.count(needle)==1,'Stale group scope override')
    text=text.replace(needle,'''  IF GROUPPROBE.failJoin<>0 THEN
    GROUPPROBE.failJoin=0 DOSCLIENT.SetError(ERROR_NO_FREE_STORE) RETURN(0)
  FI
'''+needle)
    (out/'dosgroup.act').write_text(text)
    media=out/'files';media.mkdir(exist_ok=True)
    shutil.copyfile(ROOT/'examples/demo-disk/LONG.TXT',media/'LONG.TXT')
    make(out/'volume.atr',media)
    p=read_build(out) if reuse else build(toolchain,source,out,optimize=mode=='opt',tasks=True,task_capacity=8,
         console=True,dos_mounts=[dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4)],image_data=blobs)
    require(p['build']['source_sha256']==sha256(source),'Stale group fixture')
    for address,payload in blobs:
        require(any(s['address']==address and bytes(s['bytes'])==payload for s in p['image']['segments']),'Stale loaded command')
    binary=ROOT/'build/shell-paced-bridge/AltirraBridgeServer';rom=ROOT/'build/firmware/altirraos-816.rom'
    require(sha256(binary)==PIN['emulator']['sha256'] and sha256(rom)==PIN['rom']['sha256'],'Unpinned machine')
    with emulator(binary.parent,rom,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        b.config('diskemu','generic56k');b.mount(0,str(out/'volume.atr'))
        machine=verify_machine(b,rom,PIN)
        try:runtime,_=execute(b,p,timeout=360,frame_limit=18000)
        except Exception:
            print('Group progress:',{n:data(b,p['image'],n) for n in ('checks','cancellations','firstMode','secondMode','finished','warmRead','warmError','warmClose')},flush=True)
            raise
        require(data(b,p['image'],'finished')==[1] and data(b,p['image'],'cancellations',True)==[3],'Incomplete group scenarios')
        ownership(b,p,out);checks=data(b,p['image'],'checks',True)
    return dict(status='pass',tier='development',mode=mode,checks=checks,build=p['build'],runtime=runtime,machine=machine,
                pin=PIN,commands=commands,media_sha256=sha256(out/'volume.atr'),bank_zero_delta=dict(fixed=0,per_task=0),
                source_inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                 (ROOT/'tests/programs/pipeline_group.act',ROOT/'tests/programs/loaded_flow.act',ROOT/'tests/programs/groupprobe.act',
                  ROOT/'lib/dos/process.act',ROOT/'lib/dos/dosprocess.act',ROOT/'lib/dos/dosgroup.act',ROOT/'lib/dos/pipeline.act',
                  ROOT/'lib/console/consoleforeground.act',Path(__file__))},
                overrides={name:sha256(out/name) for name in ('process.act','dosgroup.act')})


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    result=run(args.output.resolve(),args.case,args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Pipeline group checks passed:',args.case,result['checks'])
