#!/usr/bin/env python3
"""Development checks for QED's real resource and startup path."""
import argparse,json,struct
from pathlib import Path
from native_program import ROOT
from prepare_qed import prepare
from build_qed_resource import build as resource_build
from test_qed_native import process_run


def resources(out,optimize=True,reuse=False,native_from=None,binding=False,drawing=False):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:
        from test_c_process import variant
        variant(Path(native_from).resolve(),out,'sdfs');reuse=True
    prepare(out/'inputs');resource=resource_build(out/'resource',out/'inputs')
    raw=(out/'resource/QED.RSC').read_bytes();h=struct.unpack_from('>18H',raw)
    bad=bytearray(raw);struct.pack_into('>I',bad,h[5],len(raw))
    tree=bytearray(raw);struct.pack_into('>H',tree,22,17)
    source=ROOT/'tests/programs'/('qed_startup_binding.c' if binding else 'qed_startup_resource.c')
    sources=[source]
    options=dict(includes=[out/'resource'],probes=[] if binding else [(source,[('huge pointer',4),('OBJECT',24),('TEDINFO',28)])])
    if drawing:
        from prepare_qed import PORT
        source=ROOT/'tests/programs/qed_startup_drawing.c'
        sources=[source,out/'inputs/source/qed/src/ausgabe.c']
        options=dict(includes=[PORT/'native',out/'inputs/source/qed/src',out/'inputs/source/cflib'],
            definitions={str(p):['--char-is-unsigned','-DQED_INITIAL_SCOPE=1','--no-cross-call',
                '--no-interprocedural-cross-jump','-Dv_bar=QedRecordBar','-Dv_gtext=QedRecordText',
                '-Dvsf_color=QedRecordFill','-Dvst_color=QedRecordInk'] for p in sources})
    fixture=out/'resources.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+'''
PROC Main()
  BYTE cycle

  FOR cycle=0 TO 1 DO
    BEGIN
      LET image=Load()
      Collected(Start(image,BYTE POINTER(c"R")),-321)
      PROGRAM.Unload(image)
      IF cycle=0 THEN
        baseline=EXEC.AvailMem(0)
      ELSE
        Require(EXEC.AvailMem(0)=baseline)
      FI
    END
  OD

  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    result=process_run(out,optimize,reuse=reuse,rebuild_app=reuse,
        app_sources=sources,app_options=options,
        fixture_source=fixture,expected_completed=2,native_optimize=True,release_compiler=True,
        media_files={'QED.RSC':raw,'BADFREE.RSC':bytes(bad),'BADTREE.RSC':bytes(tree)})
    result['resource']=resource
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--group',choices=['resources','binding','drawing'],default='resources');p.add_argument('--raw',action='store_true')
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--native-from',type=Path,help='Reuse unchanged native provider/fixture; rebuild this C probe')
    a=p.parse_args()
    result=resources(a.output,not a.raw,a.from_build,a.native_from,a.group=='binding',a.group=='drawing');print(result['status'],result['completed'])
