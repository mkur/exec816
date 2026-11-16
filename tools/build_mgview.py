#!/usr/bin/env python3
"""Build the original-source, disk-loaded MagiC text viewer."""
import argparse
from pathlib import Path
from build_c_program import build as application
from native_program import ROOT
from prepare_mgview import PORT,prepare


def build(output,optimize=True,**options):
    output=Path(output).resolve();source=output/'source';prepare(source)
    sources=[source/name for name in ('mgview.c','mgwind.c','windows.c')]
    sources += [PORT/'native/support.c',ROOT/'c/compat/gem/rect.c']
    definitions={str(p):['--char-is-unsigned','--no-inline','-Werror=implicit-function-declaration'] for p in sources}
    definitions.update(options.pop('definitions',{}))
    return application(output,sources,optimize,includes=[source,PORT/'native'],
        definitions=definitions,main_signature='args',gemdos=True,
        # Caller-side frame drawing exceeds the small pool's ordinary stack.
        # Admit this APP to an existing large pool; reserve no new bank zero.
        minimum_stack=2560,extra_inputs=[PORT/'inputs.json',PORT/'native.patch'],**options)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    args=parser.parse_args();build(args.output,not args.raw)
