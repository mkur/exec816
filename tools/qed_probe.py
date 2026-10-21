"""Small actual-source QED probes in two ordinary loaded Process lifetimes."""
from pathlib import Path
from native_program import ROOT
from prepare_qed import PORT,prepare
from build_qed import selected
from test_qed_native import process_run

def run_probe(out,fixture,native_units=(),qed_units=(),calls=None,native_from=None,
              interaction=None,media_files=None,filesystem='sdfs',interactive_lifetimes=False,
              minimum_stack=0,probes=(),writable=False,ram=False,loader_failures=False):
    from test_c_process import variant
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    reuse=native_from is not None
    if reuse:variant(native_from.resolve(),out,filesystem)
    prepare(out/'inputs')
    native=PORT/'native';qed=out/'inputs/source/qed/src'
    sources=[ROOT/'tests/programs'/fixture]
    sources += [native/name for name in ('entry.c','allocation.c','files.c','library.c',*native_units)]
    sources += [qed/name for name in qed_units]
    definitions={str(p):['--char-is-unsigned','-DQED_BANKED_MALLOC=1','-DQED_INITIAL_SCOPE=1',
        *selected()['compiler_options'],*[f'-D{a}={b}' for a,b in (calls or {}).get(p.name,{}).items()]] for p in sources}
    supervisor=out/'probe.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    supervisor.write_text(prefix+'''
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
                         runtime_attributes={'printf':'nofloat'},minimum_stack=minimum_stack,
                         probes=[(ROOT/'tests/programs'/name,layout) for name,layout in probes]),
        fixture_source=supervisor,expected_completed=2,native_optimize=True,
        release_compiler=True,loader_failures=loader_failures,interaction=interaction,
        writable=writable,ram=ram,
        media_files=media_files,filesystem=filesystem,
        stack_observation_index=1 if interactive_lifetimes else 0,profile_all=interactive_lifetimes)
