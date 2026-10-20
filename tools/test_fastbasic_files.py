#!/usr/bin/env python3
"""WB3: emitted editor transactions against controlled and actual filesystems."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from library_paths import read_source


def run(out,mock=True,reuse=False,filesystem='sdfs'):
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'tests/programs/basic_files.c',ROOT/'examples/gem-basic/document.c',
             ROOT/'examples/gem-basic/files.c',ROOT/'c/calypsi/exec.c']
    inputs={str(q.relative_to(ROOT)):sha256(q) for q in sources+[ROOT/'examples/gem-basic/document.h',ROOT/'examples/gem-basic/files.h']}
    input_path=out/'inputs.json'
    if reuse:require(json.loads(input_path.read_text())==inputs,'Changed emitted file fixture inputs')
    else:input_path.write_text(json.dumps(inputs,indent=2)+'\n')
    if not reuse:
        assembly=[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s']
        definitions={}
        if mock:
            definitions={'basic_files.c':['-DBASIC_FILE_MOCK'],
                'document.c':['-DAllocMem=BasicFileTestAlloc'],'files.c':['-DAllocMem=BasicFileTestAlloc']}
        else:
            sources.append(ROOT/'c/calypsi/dos.c');assembly.append(ROOT/'c/calypsi/dos.s')
            definitions={'basic_files.c':['-DBASIC_VOLUME="RAM:"' if filesystem=='ram' else '-DBASIC_VOLUME="D1:"']}
        foreign=emit(out/'c',sources,assembly,(),True,
            roots=['BasicFileProbe','BasicFileChecks',*(['ExecDosEntries'] if not mock else [])],definitions=definitions)
        (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
        binding='';mounts=[]
        if not mock:
            if filesystem=='ram':mounts=[dict(alias='RAM',format=3)]
            else:
                from make_data_disk import make
                media=out/'media';media.mkdir(exist_ok=True)
                make(out/'data.atr',media,filesystem=filesystem,sector_bytes=256,sectors=2880)
                mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,
                             format=2 if filesystem=='sdfs' else 1,access='readwrite')]
            binding='CONST C_EXECDOSENTRIES=$%x\n'%foreign['symbols']['ExecDosEntries']
            binding+=read_source(ROOT/'c/calypsi/dos-bridge.inc').split('; A launched command')[0]
            binding+='''
LONGINT FUNC CFileRename(LONGCARD previous,next,unused)

RETURN(DOS.Rename(BYTE POINTER(ADDRESS(previous)),BYTE POINTER(ADDRESS(next))))

LONGINT FUNC CFileDelete(LONGCARD name,unused,other)

RETURN(DOS.DeleteFile(BYTE POINTER(ADDRESS(name))))

'''
            binding+='PROC BindDos()\n  LET entries=ADDRESS POINTER(C_EXECDOSENTRIES)\n'
            for i,name in ((1,'CWrite'),(2,'COpen'),(3,'CClose'),(4,'CRead'),(9,'DOS.IoErr'),(19,'CFileRename'),(20,'CFileDelete')):
                binding+=f'  entries({i})=ADDRESS(@{name})\n'
            binding+='RETURN\n'
        source=out/'probe.act'
        source.write_text('MODULE BASICFILES\nUSE EXEC\nUSE CALYPSICALL\n'+('USE DOS\n' if not mock else '')+
            binding+'\nLONGINT result\nPROC Main()\n'+('  BindDos()\n' if not mock else '')+
            '  result=CALYPSICALL.Invoke(ADDRESS($%x),0)\n'%foreign['symbols']['BasicFileProbe']+
            ('  DOS.ReleaseContext()\n' if not mock else '')+'RETURN\nENDMODULE\n')
        memory=None
        if not mock:
            from generate_memory import PROFILE
            profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
            memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
        p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,
            foreign_image=foreign,optimize=True,console=False,console_deferred=not mock,dos_mounts=mounts,
            stack_checks=True,memory_profile=memory)
    else:p=read_build(out/'program');foreign=json.loads((out/'c-image.json').read_text())
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    report=dict(status='running',tier='development',qualification=False,slice='WB3',mock=mock,filesystem=filesystem,
        source_inputs=inputs,
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
            if not mock and filesystem!='ram':b.config('diskemu','generic56k');b.mount(0,str(out/'data.atr'))
            report['machine']=verify_machine(b,rom,pin)
            runtime,_=execute(b,p,timeout=600,frame_limit=30000,timer_irq=mock)
            observed=data(b,p['image'],'result',True)
            require(observed==[0,0],'File assertion line: '+str(observed))
            ownership(b,p,p['output'])
            require(all(sha256(ROOT/n)==h for n,h in inputs.items()),'Source changed during fixture execution')
            report.update(status='pass',checks=b.peek16(foreign['symbols']['BasicFileChecks']),runtime=runtime)
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--filesystem',choices=('mock','ram','sdfs','mydos'),default='mock')
    p.add_argument('--from-build',action='store_true');a=p.parse_args()
    run(a.output.resolve(),a.filesystem=='mock',a.from_build,a.filesystem)
