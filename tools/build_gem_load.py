#!/usr/bin/env python3
"""Build the matched GF0 Counter configurations and native disk command."""
import argparse
import json
import shutil
from pathlib import Path

from build_command import compile_command
from build_c_program import build as application
from make_data_disk import make
from native_program import ROOT,compiler,sha256


def build(out):
    out.mkdir(parents=True,exist_ok=True)
    media=out/'media';media.mkdir(exist_ok=True)
    command=compile_command(compiler(ROOT/'build/actionc',release=True),
        ROOT/'tests/programs/gem_load.act',out/'GFLOAD')
    shutil.copyfile(out/'GFLOAD',media/'GFLOAD')
    app=application(out/'apps/gfcount',[ROOT/'tests/programs/gem_first_counter.c',
        ROOT/'examples/gem-counter/counter.c'],minimum_stack=1312)
    shutil.copyfile(out/'apps/gfcount/program.app',media/'GFCOUNT.APP')
    payload=bytes((i^(i>>8)^0x5a)&255 for i in range(16384))
    (media/'LOAD.BIN').write_bytes(payload)
    (media/'CANCEL.BIN').write_bytes(payload)
    make(out/'seed.atr',media,binary_names={'GFLOAD','GFCOUNT.APP','LOAD.BIN','CANCEL.BIN'},
        sector_bytes=256,sectors=2880,filesystem='sdfs')
    record=dict(status='pass',tier='development',qualification=False,command=command,
        app_sha256=app['sha256'],seed_sha256=sha256(out/'seed.atr'),
        payload_sha256=sha256(media/'LOAD.BIN'),
        counter_body_sha256=sha256(ROOT/'examples/gem-counter/counter.c'),
        native_buffer_bytes=16384,passes=4,cancellation='cold read-only CANCEL.BIN',
        bank_zero_reserved_delta=0)
    (out/'fixture.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args().output.resolve())
