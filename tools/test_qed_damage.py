#!/usr/bin/env python3
"""Focused emitted actual-source row damage and viewport-clamp regressions."""
import argparse
from pathlib import Path

from build_qed import selected
from native_program import ROOT
from prepare_qed import PORT, prepare
from test_c_process import variant
from test_qed_native import process_run


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--native-from', type=Path, default=ROOT/'build/qed-coexist/core-opt')
    a = p.parse_args(); out = a.output.resolve()
    variant(a.native_from.resolve(), out, 'sdfs'); prepare(out/'inputs')
    qed = out/'inputs/source/qed/src'; native = PORT/'native'
    sources = [ROOT/'tests/programs/qed_damage_core.c', qed/'edit.c', qed/'set.c']
    sources += [native/name for name in ('entry.c', 'allocation.c', 'files.c', 'library.c')]
    options = dict(includes=[native, qed, out/'inputs/source/cflib'],
        definitions={str(source): ['--char-is-unsigned', '-DQED_BANKED_MALLOC=1',
                                  *selected()['compiler_options']] for source in sources})
    fixture = a.native_from.resolve()/'logical.act'
    result = process_run(out, True, reuse=True, rebuild_app=True,
        app_sources=sources, app_options=options, fixture_source=fixture,
        expected_completed=2, native_optimize=True, release_compiler=True,
        loader_failures=False)
    print('QED damage policy passed', result['completed'])
