#!/usr/bin/env python3
"""GemARC, production QED and a computing GUI peer on unchanged Task pools."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,require
from test_c_process import run as process_run


def run(out,bundle):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    apps=bundle/'bitmap-console/apps';arc=json.loads((apps/'gemarc/app.json').read_text())
    count=json.loads((apps/'counter/app.json').read_text())
    offset=count['image']['symbols']['GEMCounter']-(count['abi']['link_bank']<<16)+14
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0].replace('USE AESCORE\n','USE AESCORE\nUSE AESTYPES\n')
    fixture=out/'coexist.act'
    fixture.write_text(prefix+'''

LONGCARD computed

PROC Ready(BYTE expected)
  CARD turn
  BYTE index,shown

  LET service=AESSTATE.Get()
  FOR turn=0 TO 29999 DO
    shown=0
    FOR index=0 TO AESTYPES.WINDOWS-1 DO
      IF service.windows(index).view<>NULL AND service.windows(index).view.shown<>0 THEN
        shown==+1
      FI
    OD

    IF shown=expected AND service.count=expected THEN
      RETURN
    FI

    EXEC.Yield()
  OD

  HEAPCORE.Abort($fbf1)

RETURN

PROGRAMIMAGE.Image POINTER FUNC Open(BYTE POINTER path)

  LET image=PROGRAMFILE.Load(path)
  Require(image<>NULL)

RETURN(image)

LONGCARD FUNC Launch(PROGRAMIMAGE.Image POINTER image)

RETURN(PROCESS.StartLoaded(BYTE POINTER(image),NULL,0,0))

PROC Warm(BYTE POINTER path)

  LET image=Open(path)
  LET id=Launch(image)
  Require(id<>0)
  Ready(1)
  Require(PROCESS.RequestStop(id)<>0)
  Collected(id,0)
  PROGRAM.Unload(image)
  Ready(0)

RETURN

PROC Main()
  LONGCARD turn

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  Require(DOS.AssignPath(BYTE POINTER(c"QED"),BYTE POINTER(c"SYS:"))<>0)
  Warm(BYTE POINTER(c"SYS:PROBE.APP"))
  Warm(BYTE POINTER(c"SYS:QED.APP"))
  Warm(BYTE POINTER(c"SYS:COUNTER.APP"))
  baseline=EXEC.AvailMem(0)
  LET arc=Open(BYTE POINTER(c"SYS:PROBE.APP"))
  LET qed=Open(BYTE POINTER(c"SYS:QED.APP"))
  LET peer=Open(BYTE POINTER(c"SYS:COUNTER.APP"))
  LET a=Launch(arc)
  LET q=Launch(qed)
  LET c=Launch(peer)
  Require(a<>0 AND q<>0 AND c<>0)
  Ready(3)
  LET ticks=LONGCARD POINTER(ADDRESS(LONGCARD(ADDRESS(peer.text))+LONGCARD($'''+format(offset,'x')+''')))
  LET previous=ticks^
  FOR turn=0 TO 99999 DO
    computed==+1
    IF ticks^<>previous THEN
      EXIT
    FI

    EXEC.Yield()
  OD

  Require(ticks^<>previous AND computed<>0)
  Require(PROCESS.RequestStop(a)<>0 AND PROCESS.RequestStop(q)<>0 AND PROCESS.RequestStop(c)<>0)
  Collected(a,0)
  Collected(q,0)
  Collected(c,0)
  PROGRAM.Unload(arc)
  PROGRAM.Unload(qed)
  PROGRAM.Unload(peer)
  Ready(0)
  Require(EXEC.AvailMem(0)=baseline)
  Require(DOS.AssignPath(BYTE POINTER(c"QED"),NULL)<>0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    def application(target):
        target.mkdir(exist_ok=True);shutil.copyfile(apps/'gemarc/program.app',target/'program.app');return arc
    result=process_run(out,True,app_builder=application,fixture_source=fixture,expected_completed=6,
        native_optimize=True,release_compiler=True,task_capacity=12,loader_failures=False,
        media_files={'GEMARC.RSC':(apps/'gemarc/GEMARC.RSC').read_bytes(),
            'QED.APP':(bundle/'qed-production/program.app').read_bytes(),
            'QED.RSC':(bundle/'qed-production/inputs/resource/QED.RSC').read_bytes(),
            'COUNTER.APP':(apps/'counter/program.app').read_bytes()})
    result['coexistence']=dict(applications=['GemARC','production QED','Counter'],
        computing_root=True,peer_timer_progress=True,exact_heap_restoration=True,
        profile='12 public Tasks, root fixture without the production desktop APP')
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--bundle',type=Path,required=True);args=parser.parse_args()
    run(args.output,args.bundle.resolve())
