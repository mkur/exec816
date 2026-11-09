#!/usr/bin/env python3
"""Load/list and cooperative retirement of real GemARC windows and instances."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from build_gemarc import build as application
from test_gemarc_host import corpus,member
from test_c_process import run as process_run


def run(out):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Build first so native observations use emitted offsets from this APP.
    app=application(out/'prepared-app')
    offset=app['image']['symbols']['nlist']-(app['abi']['link_bank']<<16)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    source=out/'gemarc-ui.act'
    source.write_text(prefix+'''
PROC Ready(PROGRAMIMAGE.Image POINTER image)
  CARD turn

  LET count=CARD POINTER(ADDRESS(LONGCARD(ADDRESS(image.text))+LONGCARD($'''+format(offset,'x')+''')))
  FOR turn=0 TO 19999 DO
    IF count^=7 THEN
      RETURN
    FI

    EXEC.Yield()
  OD

  HEAPCORE.Abort($fbf0)

RETURN

LONGCARD FUNC Launch(PROGRAMIMAGE.Image POINTER image)

RETURN(PROCESS.StartLoaded(BYTE POINTER(image),BYTE POINTER(c"SYS:CORPUS.ARC"),14,0))

PROC Main()

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  LET warm=Load()
  LET first=Launch(warm)
  Require(first<>0)
  Ready(warm)
  Require(PROCESS.RequestStop(first)<>0)
  Collected(first,0)
  PROGRAM.Unload(warm)
  baseline=EXEC.AvailMem(0)
  LET one=Load()
  LET two=Load()
  LET a=Launch(one)
  LET b=Launch(two)
  Require(a<>0 AND b<>0)
  Ready(one)
  Ready(two)
  Require(PROCESS.RequestStop(a)<>0 AND PROCESS.RequestStop(b)<>0)
  Collected(a,0)
  Collected(b,0)
  PROGRAM.Unload(one)
  PROGRAM.Unload(two)
  Require(EXEC.AvailMem(0)=baseline)
  LET service=AESSTATE.Get()
  Require(service.count=0 AND AESCORE.Idle(service)<>0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    def staged(target):
        import shutil
        target.mkdir(exist_ok=True)
        shutil.copyfile(out/'prepared-app/program.app',target/'program.app')
        return app
    result=process_run(out,True,app_builder=staged,fixture_source=source,
        expected_completed=3,native_optimize=True,release_compiler=True,task_capacity=12,
        loader_failures=False,media_files={'GEMARC.RSC':(out/'prepared-app/GEMARC.RSC').read_bytes(),
            'CORPUS.ARC':b''.join(member(*row) for row in corpus())+b'\x1a\0'})
    result['gemarc_ui']=dict(instances=3,concurrent=2,listed_members=7,
        cooperative_stop=True,exact_heap_restoration=True)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output)
