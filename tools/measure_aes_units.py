#!/usr/bin/env python3
"""Measure the 32-row AES-object boundary without changing production sources."""
import argparse
from pathlib import Path
from unittest.mock import patch

import build_bitmap_console as builder
import measure_magic_aes as corpus
import measure_aes_drawing as detail
from native_program import ROOT,require


def run(out,from_build=None):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'c/calypsi/aes-objects.c'
    text=source.read_text()
    old='rows=b-t<=32 ? 32:16;'
    current='rows=32;'
    require(text.count(old)==1 or text.count(current)==1,'Changed object boundary selection')
    text=text.replace(old,current)
    for header in ('aes-private.h','vdi-private.h','aes-paint-private.h'):
        text=text.replace('#include "'+header+'"',
            '#include "'+str(ROOT/'c/calypsi'/header)+'"')
    generated=out/'aes-objects-rows32.c';generated.write_text(text)
    original=builder.emit
    def emit(output,sources,*args,**kwargs):
        return original(output,[generated if p==source else p for p in sources],*args,**kwargs)
    with patch.object(builder,'emit',emit),patch.object(corpus,'trace_definition',detail.definition):
        corpus.run(out,from_build)
    return detail.analyze(out)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',type=Path)
    a=parser.parse_args();run(a.output.resolve(),a.from_build.resolve() if a.from_build else None)
