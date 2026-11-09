"""Bounded ordinary resident main/context check without an APP entry."""
import argparse,json
from pathlib import Path
from calypsi_build import emit
from native_program import ROOT,build,compiler,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute
from test_mouse_observe import PIN,BRIDGE,ROM


def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        previous=json.loads((out/'results.json').read_text());p=read_build(out/'program')
        for name,digest in previous['source_inputs'].items():
            require(sha256(ROOT/name)==digest,'Changed standalone source: '+name)
        require(previous['c_image']==p['build']['foreign_image'],'Changed resident C image')
        return execute_image(out,p,previous['c_image'],previous['source_inputs'])
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'tests/programs/c_runtime_standalone.c']
    image=emit(out/'c',sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/image-info.s'],())
    require(image['provenance']['entry_symbol']=='main' and
            '__exec_c_runtime_entry' not in image['symbols'],'Resident entry was reinterpreted as an APP')
    source=out/'standalone.act'
    source.write_text('''MODULE CRESIDENT
USE EXEC
USE HEAPCORE
INT FUNC POINTER entry()
CARD checks
PROC Main()

  LET before=EXEC.AvailMem(0)
  LET target=ADDRESS POINTER(@entry)
  target^=ADDRESS($'''+format(image['symbols']['main'],'x')+''')
  IF entry()<>-123 OR EXEC.AvailMem(0)<>before THEN
    HEAPCORE.Abort($fb00)
  FI

  checks=1

RETURN

ENDMODULE
''')
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    profile['image_data_bytes']=4096
    config=out/'fixture-memory.json';config.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,
        banked=True,memory_profile=config,foreign_image=image)
    return execute_image(out,p,image['provenance'],{str(s.relative_to(ROOT)):sha256(s) for s in sources})


def execute_image(out,p,image,inputs):
    result=dict(status='running',tier='development',qualification=False,build=p['build'],pin=PIN,
        scope='Ordinary resident main returns a signed int; private data and public allocation/Yield survive IRQ/NMI',
        c_image=image,source_inputs=inputs)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            result['machine']=verify_machine(b,ROM,PIN)
            runtime,_=execute(b,p,timeout=120,frame_limit=6000,timer_irq=True)
            result['runtime']=runtime
            require(runtime['native_irq_count']>0 and runtime['native_nmi_count']>0,'Missing asynchronous entry')
            result.update(status='pass',runtime=runtime)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.from_build)
