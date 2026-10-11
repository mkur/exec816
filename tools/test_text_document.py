#!/usr/bin/env python3
"""Emitted viewer document code: actual SDFS reads and controlled failures."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256,read_build
from calypsi_build import emit
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from library_paths import read_source

def run(out,mock,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        from calypsi_image import read_image
        p=read_build(out/'program');f=read_image(out/'c/program.elf')
        f['provenance']=p['build']['foreign_image']
        return exercise(out,mock,p,f)
    sources=[ROOT/'tests/programs/text_document.c',ROOT/'examples/gem-text/document.c',ROOT/'c/calypsi/exec.c']
    assembly=[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s']
    if not mock:
        sources.append(ROOT/'c/calypsi/dos.c');assembly.append(ROOT/'c/calypsi/dos.s')
    f=emit(out/'c',sources,assembly,(),True,roots=['TextDocumentProbe','TextChecks',*(['ExecDosEntries'] if not mock else [])],
        definitions={'document.c':['-DAllocMem=TextTestAlloc'],'text_document.c':['-DTEXT_MOCK'] if mock else []})
    binding=''
    mounts=[]
    if not mock:
        from make_data_disk import make
        media=out/'media';media.mkdir(exist_ok=True)
        for name,payload in {'MIX.TXT':b'A\tB\r\nC\rD\n\x9b\0\x80Z','FULL.TXT':b'A'*65536,
            'LINES.TXT':b'\n'*4096,'OVER.TXT':b'A'*65537,'MANY.TXT':b'\n'*4097,
            'SPLIT.TXT':b'A'*1023+b'\r\nBB','EMPTY.TXT':b''}.items(): (media/name).write_bytes(payload)
        make(out/'data.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names=set(p.name for p in media.iterdir()))
        mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)]
        binding='CONST C_EXECDOSENTRIES=$%x\n'%f['symbols']['ExecDosEntries']
        # This fixture needs only file calls, not the program-launch table roots.
        binding+=read_source(ROOT/'c/calypsi/dos-bridge.inc').split('; A launched command')[0]
        binding+='PROC BindDos()\n  LET entries=ADDRESS POINTER(C_EXECDOSENTRIES)\n'
        for index,name in ((2,'COpen'),(3,'CClose'),(4,'CRead'),(5,'CLock'),(6,'CUnLock'),(7,'CExamine'),(9,'DOS.IoErr')):
            binding+=f'  entries({index})=ADDRESS(@{name})\n'
        binding+='\nRETURN\n'
    source=out/'probe.act'
    source.write_text('MODULE TEXTDOCUMENT\nUSE EXEC\nUSE CALYPSICALL\n'+('USE DOS\n' if not mock else '')+binding+'''
LONGINT result
PROC Main()
%s
  result=CALYPSICALL.Invoke(ADDRESS($%x),0)
%s

RETURN
ENDMODULE
'''%('  BindDos()' if not mock else '',f['symbols']['TextDocumentProbe'],'  DOS.ReleaseContext()' if not mock else ''))
    memory=None
    if not mock:
        from generate_memory import PROFILE
        profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
        memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc'),source,out/'program',tasks=True,task_capacity=8,
        foreign_image=f,optimize=True,console=False,console_deferred=not mock,dos_mounts=mounts,
        memory_profile=memory)
    return exercise(out,mock,p,f)

def exercise(out,mock,p,f):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text());rom=ROOT/'build/firmware/altirraos-816.rom'
    with emulator(ROOT/'build/shell-paced-bridge',rom,out,pin=pin) as b:
        for key,value in pin['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        if not mock:b.config('diskemu','generic56k')
        machine=verify_machine(b,rom,pin)
        if not mock:b.mount(0,str(out/'data.atr'))
        before=sha256(out/'data.atr') if not mock else None
        # SIO owns POKEY timer resources; the unrelated ROM timer stimulus is
        # appropriate only for the controlled, disk-free fixture.
        runtime,_=execute(b,p,timeout=180,frame_limit=12000,timer_irq=mock)
        observed=data(b,p['image'],'result',True)
        if observed!=[0,0]:
            import re
            storage=(p['output']/'dos-storage-action.inc').read_text()
            base=int(re.search(r'DS_BASE=\$(\w+)',storage)[1],16)
            print('Failure DOS slots',b.memdump(base,128).hex(),flush=True)
            print('Failure C bindings',b.memdump(f['symbols']['ExecDosEntries'],60).hex() if not mock else '',flush=True)
        require(observed==[0,0],'Text document assertion failed: '+str(observed))
        checks=int.from_bytes(b.memdump(f['symbols']['TextChecks'],2),'little')
        ownership(b,p,p['output'])
        if not mock:require(sha256(out/'data.atr')==before,'Viewer wrote to its input disk')
    r=dict(status='pass',tier='development',mock=mock,checks=checks,machine=machine,runtime=runtime,
        c_elf_sha256=f['provenance']['elf_sha256'],bank_zero_delta=dict(fixed=0,per_task=0,idle=0))
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Text document passed',mock,checks,flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--mock',action='store_true');parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.mock,args.from_build)
