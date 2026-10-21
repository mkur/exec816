#!/usr/bin/env python3
"""Focused loaded-QED editing checks; optimized ordinary Process execution."""
import argparse,json
from pathlib import Path
from native_program import ROOT
from prepare_qed import prepare
from build_qed import build
from test_qed_native import process_run
from qed_editing_observe import interact


def build_editor(target,provider,reuse_app=False,selection=False,saving=False):
    if reuse_app:
        from native_program import require,sha256
        from c_program import ABI
        from build_qed import selected
        prepare(target/'inputs')
        app=json.loads((target/'app.json').read_text())
        layout=json.loads((target/'layout.json').read_text())
        require(app['abi']==ABI and layout['selection']==selected(),'Changed APP contract')
        options=layout['image']['provenance']['source_options']
        editing=next(v for n,v in options.items() if n.endswith('/qed/src/edit.c'))
        require(('-DCreateIORequest=QedSelectionCreateIORequest' in editing)==selection,
                'Changed selection fixture contract')
        require(sha256(target/'program.app')==app['sha256'],'Changed serialized APP')
        for name,digest in layout['build_inputs'].items():
            require(sha256(Path(name))==digest,'Changed APP input: '+name)
        return app
    calls={'tasten.c':{'new_col':'QedEditNewCol'},
           'clipbrd.c':{'new_col':'QedEditNewCol'},
           'block.c':{'new_col':'QedEditNewCol'},
           'commands.c':{'form_do':'QedEditFormDo'},
           'document.c':{'new_col':'QedEditNewCol'},
           'ausgabe.c':{'cursor':'QedEditCursor'},
           'event.c':{'key_window':'QedEditKeyWindow','key_global':'QedEditGlobalKey',
                      'handle_menu':'QedEditMenu'}}
    if selection:calls['edit.c']={'CreateIORequest':'QedSelectionCreateIORequest'}
    if saving:
        calls['document.c']['Fopen']='QedSaveDocumentOpen'
        calls['saving.c']={'form_alert':'QedSaveAlert'}
        calls['stage.c']={'Fwrite':'QedSaveFaultWrite'}
        calls['files.c']={'Close':'QedSaveFaultClose'}
        calls['save.c']={'Rename':'QedSaveFaultRename','DeleteFile':'QedSaveFaultDelete'}
    build(target,provider,executable=True,
          fixture=ROOT/'tests/programs'/('qed_saving_faults.c' if saving else 'qed_editing_faults.c'),
          fixture_inputs=[ROOT/'tests/programs/qed_editing_faults.c'] if saving else (),
          fixture_calls=calls,
          fixture_roots=['QedEditingLayout',*(['QedSavingLayout'] if saving else [])])
    return json.loads((target/'app.json').read_text())

def run(out,reuse=False,reuse_app=False,scenario='all',interaction=None):
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    prepare(out/'inputs')
    provider=out/'c-image.json' if reuse else ROOT/'build/qed-startup/qs2-binding-opt/c-image.json'
    def application(target):return build_editor(target,provider,reuse_app)
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,app_builder=application,
        fixture_source=ROOT/'tests/programs/qed_editing.act',expected_completed=4,
        native_optimize=True,release_compiler=True,stack_observation_index=3,
        profile_all=True,ram=True,
        interaction=interaction or (lambda *args:interact(*args,keys_only=scenario=='keys')),loader_failures=False,
        retirement_timeout=90,media_files={'QED.RSC':(out/'inputs/resource/QED.RSC').read_bytes()})


def core(out,reuse=False,native_from=None):
    from prepare_qed import PORT
    from build_qed import selected
    from test_c_process import variant
    out=Path(out).resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:variant(Path(native_from).resolve(),out,'sdfs');reuse=True
    prepare(out/'inputs')
    qed=out/'inputs/source/qed/src';native=PORT/'native'
    sources=[ROOT/'tests/programs/qed_editing_core.c',qed/'tasten.c',qed/'memory.c',qed/'clipbrd.c']
    sources += [native/name for name in ('entry.c','allocation.c','files.c','library.c')]
    definitions={str(p):['--char-is-unsigned','-DQED_BANKED_MALLOC=1',
        *selected()['compiler_options']] for p in sources}
    definitions[str(qed/'tasten.c')].append('-Dform_alert=QedRecordAlert')
    definitions[str(qed/'clipbrd.c')].append('-Dform_alert=QedRecordAlert')
    definitions[str(native/'allocation.c')].append('-DAllocMem=QedFixtureAlloc')
    fixture=out/'core.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+'''
PROC Main()
  BYTE cycle

  FOR cycle=0 TO 1 DO
    BEGIN
      LET image=Load()
      Collected(Start(image,BYTE POINTER(c"F")),-321)
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
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,app_sources=sources,
        app_options=dict(includes=[native,qed,out/'inputs/source/cflib'],definitions=definitions,
                         runtime_attributes={'printf':'nofloat'}),
        fixture_source=fixture,expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--from-build',action='store_true')
    p.add_argument('--group',choices=['editor','core'],default='editor')
    p.add_argument('--scenario',choices=['all','keys'],default='all')
    p.add_argument('--reuse-app',action='store_true',help='Verify unchanged APP inputs for observer-only reruns')
    p.add_argument('--native-from',type=Path)
    a=p.parse_args();result=core(a.output,a.from_build,a.native_from) if a.group=='core' else run(a.output,a.from_build,a.reuse_app,a.scenario)
    print(result['status'],result['completed'])
