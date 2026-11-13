#!/usr/bin/env python3
"""Directory-watch ownership, real C bridge, coalescing and lost-wake boundaries."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,require,sha256
from os_boundary import emulator
from test_mouse_observe import BRIDGE,ROM,PIN
from native_program import verify_machine
from test_dos_stack import execute,ownership
from test_cooperative import data


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    text=(ROOT/'lib/console/consoleviewcore.act').read_text()
    start=text.index('PUBLIC LONGCARD FUNC WatchDirectory(');end=text.index('; The publisher commits',start)
    body=text[start:end].replace('EXEC.AllocMem(','DIRECTORYPROBE.Allocate(').replace('EXEC.RetainTask(','DIRECTORYPROBE.Retain(')
    text=(text[:start]+body+text[end:]).replace('USE HEAPCORE\n','USE HEAPCORE\nUSE DIRECTORYPROBE\n',1)
    (out/'consoleviewcore.act').write_text(text)
    shutil.copyfile(ROOT/'tests/programs/directoryprobe.act',out/'directoryprobe.act')
    source=out/'probe.act';source.write_text((ROOT/'tests/programs/console_directory.act').read_text())
    # The source's entry is filled after the actual foreign C image is linked.
    from build_bitmap_console import drawing,prepare
    from native_program import build,compiler
    foreign=drawing(out,mode=='opt',client_sources=[ROOT/'c/calypsi/console.c',ROOT/'tests/programs/console_directory.c'],
        client_roots=['DirectoryProbe','DirectoryChecks'])
    source.write_text(source.read_text().replace('$DIRECTORYPROBE',f"${foreign['symbols']['DirectoryProbe']:x}"))
    launcher=prepare(source,out,foreign)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',optimize=mode=='opt',
        tasks=True,task_capacity=8,console=False,console_deferred=True,foreign_image=foreign,memory_profile=memory)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN)
        try:runtime,_=execute(b,p,frame_limit=2400,timeout=180)
        except Exception:
            print('Directory checks',data(b,p['image'],'checks',True),'C result',data(b,p['image'],'result'),
                'stage',data(b,p['image'],'stage'),'before',data(b,p['image'],'beforeMemory'),
                'after',data(b,p['image'],'afterMemory'),flush=True)
            raise
        ownership(b,p,p['output'])
        checks=data(b,p['image'],'checks',True)[0]
        record_bytes=data(b,p['image'],'recordBytes',True)[0]
        heap=int.from_bytes(bytes(data(b,p['image'],'watchHeap')),'little')
        c_checks=[int.from_bytes(b.memdump(foreign['symbols']['DirectoryChecks']+i*2,2),'little') for i in range(2)]
        require(checks>=50 and min(c_checks)>10,'Incomplete directory cases')
    record=dict(status='pass',tier='development',qualification=False,mode=mode,checks=checks,c_checks=c_checks,
        record_bytes=record_bytes,four_watch_heap_bytes=heap,runtime=runtime,machine=machine,build=p['build'],
        inputs={str(x.relative_to(ROOT)):sha256(x) for x in [ROOT/'lib/console/consoleviewcore.act',ROOT/'lib/console/consoleview.act',
            ROOT/'tests/programs/console_directory.act',ROOT/'tests/programs/console_directory.c',ROOT/'tests/programs/directoryprobe.act',Path(__file__)]})
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Directory watch checks passed:',mode,checks,c_checks,'record',record_bytes,'heap',heap,flush=True)


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');args=a.parse_args();run(args.output.resolve(),args.mode)
