#!/usr/bin/env python3
"""Focused emitted-code checks for shell prefix completion and token boundaries."""
import argparse
import json
from pathlib import Path

from native_program import ROOT,build,compiler,require,sha256,verify_machine,read_build
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership
from library_paths import read_source
from make_data_disk import make
from filesystem_formats import RAM,MYDOS,SDFS

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def run(output,mode,group='matching',reuse=False):
    output.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/shell_completion.act'
    mounts=[]
    media=[]
    if group=='filesystem':
        source=output/'shell_completion_fs.act'
        observed=output/'shell-observed.inc'
        completion=output/'completion-observed.inc'
        completion.write_text(read_source(ROOT/'examples/shell/shell-completion.inc')
            .replace('DOS.ExNextBatch(', 'CompletionBatch(').replace('DOS.UnLock(', 'CompletionUnlock('))
        observed.write_text(read_source(ROOT/'examples/shell/shell-session.inc',
            {'shell-completion.inc':completion}))
        source.write_text(read_source(ROOT/'tests/programs/shell_completion_fs.act',
            {'shell-session.inc':observed}))
        mounts=[dict(alias='RAM',format=RAM,access='readwrite'),
                dict(alias='D1',format=MYDOS,unit=49,sectors=720,sector_bytes=128,profile=1),
                dict(alias='D2',format=SDFS,unit=50,sectors=720,sector_bytes=128,profile=1)]
        files=output/'files'
        (files/'TOOLS').mkdir(parents=True,exist_ok=True)
        for name in ('README.TXT','READER.TXT','TOOLS/NOTE.TXT'):
            (files/name).write_text('completion fixture\n')
        for filesystem in ('mydos','sdfs'):
            disk=output/(filesystem+'.atr')
            make(disk,files,filesystem=filesystem)
            media.append(disk)
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=8192
    memory=output/'memory-profile.json'
    memory.write_text(json.dumps(profile,indent=2)+'\n')
    program=read_build(output) if reuse else build(compiler(ROOT/'build/actionc',release=True),
                  source,output,
                  optimize=mode=='opt',tasks=True,task_capacity=8,
                  console=True,dos_mounts=mounts,memory_profile=memory)
    bridge_dir=ROOT/'build/shell-paced-bridge'
    rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(bridge_dir,rom,output,pin=PIN) as bridge:
        for key,value in PIN['configuration'].items():
            bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(bridge,rom,PIN)
        bridge.config('diskemu','fastest')
        for index,disk in enumerate(media):bridge.mount(index,str(disk))
        try:runtime,_=execute(bridge,program,timeout=240,frame_limit=12000)
        except Exception:
            print('Completion check',data(bridge,program['image'],'checks',True),flush=True)
            if group=='filesystem':print('Batches',data(bridge,program['image'],'batches',True),flush=True)
            raise
        ownership(bridge,program,output)
        observations=dict(checks=data(bridge,program['image'],'checks',True),
                          finished=data(bridge,program['image'],'finished'))
        require(observations['finished']==[1],'Completion fixture did not finish')
    return dict(status='pass',tier='development',mode=mode,group=group,
                build=program['build'],machine=machine,runtime=runtime,
                observations=observations,runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('raw','opt'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--group',choices=('matching','filesystem','editor','lifetime'),default='matching')
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args()
    if args.group in ('editor','lifetime'):
        from test_console_edit import run as edit
        result=edit(args.output.resolve(),args.case=='opt',2,abi_only=args.group=='editor',reuse=args.reuse)
    else:result=run(args.output.resolve(),args.case,args.group,args.reuse)
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Shell completion checks passed',args.case,flush=True)
