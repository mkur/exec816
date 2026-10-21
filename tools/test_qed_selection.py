#!/usr/bin/env python3
"""Physical loaded-editor selection, cancellation and ordinary-client progress."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT
from prepare_qed import prepare
from build_c_program import build as application
from build_qed import selected
from test_qed_editing import build_editor
from test_qed_native import process_run
from qed_selection_observe import interact


def run(out,reuse=False,reuse_app=False,native_from=None,scroll=True,interaction=None,
        fixture_source=None,media_files=None,filesystem='sdfs',provider_from=None,writable=False,saving=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:
        from test_c_process import variant
        variant(native_from.resolve(),out,filesystem);reuse=True
        shutil.copytree(native_from.resolve()/'selected',out/'selected',dirs_exist_ok=True)
    prepare(out/'inputs')
    application(out/'peer',[ROOT/'tests/programs/qed_selection_peer.c'],minimum_stack=1024)
    provider=out/'c-image.json' if reuse else provider_from or ROOT/'build/qed-editing/qe2/c-image.json'
    return process_run(out,True,reuse=reuse,rebuild_app=reuse,
        app_builder=lambda target:build_editor(target,provider,reuse_app,selection=True,saving=saving),
        fixture_source=fixture_source or ROOT/'tests/programs/qed_selection.act',expected_completed=4,
        native_optimize=True,release_compiler=True,stack_observation_index=3,
        profile_all=True,ram=True,writable=writable,filesystem=filesystem,interaction=interaction or (lambda *args:interact(*args,scroll=scroll)),loader_failures=False,
        retirement_timeout=90,media_files={
            'PEER.APP':(out/'peer/program.app').read_bytes(),
            'QED.RSC':(out/'inputs/resource/QED.RSC').read_bytes(),**(media_files or {})})


def logical(out,reuse=False,native_from=None,optimize=True,shortcuts=False,clipboard=False,interaction=None):
    from prepare_qed import PORT
    from test_c_process import variant
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:variant(native_from.resolve(),out,'sdfs');reuse=True
    prepare(out/'inputs')
    qed=out/'inputs/source/qed/src';native=PORT/'native'
    if shortcuts:
        sources=[ROOT/'tests/programs/qed_shortcuts.c']
        sources += [out/'inputs/source/cflib'/name for name in ('menuisk.c','nkccuppr.c')]
    else:
        sources=[ROOT/'tests/programs'/('qed_clipboard_core.c' if clipboard else 'qed_selection_core.c')]
        sources += [qed/name for name in ('tasten.c','memory.c','clipbrd.c','ausgabe.c','block.c')]
    sources += [native/name for name in ('entry.c','allocation.c','files.c','library.c')]
    definitions={str(p):([] if '/source/cflib/' in str(p) else ['--char-is-unsigned'])+
        ['-DQED_BANKED_MALLOC=1',
        *selected()['compiler_options']] for p in sources}
    if not shortcuts:definitions[str(qed/'tasten.c')].append('-Dform_alert=QedRecordAlert')
    if clipboard:
        for name in ('clipbrd.c','block.c'):
            definitions[str(qed/name)].append('-Dnew_col=QedCoreNewCol')
        definitions[str(qed/'clipbrd.c')].append('-Dform_alert=QedRecordAlert')
    else:definitions[str(out/'inputs/source/cflib/menuisk.c')].append(
        '-Dmenu_tnormal=QedRecordMenuNormal')
    fixture=out/'logical.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+"""
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
""")
    return process_run(out,optimize,reuse=reuse,rebuild_app=reuse,app_sources=sources,
        app_options=dict(includes=[native,qed,out/'inputs/source/cflib'],definitions=definitions,
                         runtime_attributes={'printf':'nofloat'}),
        fixture_source=fixture,expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=False,interaction=interaction)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--reuse-app',action='store_true')
    p.add_argument('--native-from',type=Path)
    p.add_argument('--no-scroll',action='store_true')
    p.add_argument('--group',choices=['editor','logical','shortcuts'],default='editor')
    p.add_argument('--raw',action='store_true',help='Focused actual-source logical probe only')
    a=p.parse_args()
    if a.raw and a.group=='editor':p.error('--raw requires a focused probe')
    r=logical(a.output,a.from_build,a.native_from,not a.raw,a.group=='shortcuts') if a.group!='editor' else run(
        a.output,a.from_build,a.reuse_app,a.native_from,not a.no_scroll)
    print(r['status'],r['completed'])
