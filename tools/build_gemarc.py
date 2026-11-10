#!/usr/bin/env python3
"""Build GemARC as one ordinary APP using the common C runtime."""
import argparse,json
from pathlib import Path
from native_program import ROOT,sha256
from prepare_gemarc import prepare,PORT
from build_c_program import build as application


def build(output):
    output=Path(output).resolve();prepared=prepare(output)
    source=output/'source/src/apps'
    sources=[source/name for name in ['gemarc.c','arcfile.c','arccodec.c']]
    sources += [PORT/'native'/name for name in ['io.c','path.c','metadata.c']]+[ROOT/'c/calypsi/file-list.c']
    app=application(output,sources,main_signature='args',minimum_stack=2560,
        includes=[source,PORT/'native',ROOT/'c/calypsi'],
        extra_inputs=[output/'GEMARC.RSC',source/'gemarcrsc.h',source/'arcfile.h',source/'arccodec.h',
            PORT/'native/platform.h',PORT/'inputs.json',*sorted((PORT/'patches').glob('*.patch'))])
    app['gemarc']=prepared
    (output/'app.json').write_text(json.dumps(app,indent=2)+'\n')
    return app


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args().output)
