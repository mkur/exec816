#!/usr/bin/env python3
"""Development comparison build; production keeps the scanner's default eight."""
import argparse
from pathlib import Path
import calypsi_build


def build(output,capacity):
    original=calypsi_build.emit
    def emit(*args,**kwargs):
        definitions=dict(kwargs.get('definitions') or {})
        definitions['file-list.c']=[*definitions.get('file-list.c',()),
                                     '-DFILE_SCAN_BATCH='+str(capacity)]
        kwargs['definitions']=definitions
        return original(*args,**kwargs)
    calypsi_build.emit=emit
    # Import after installing the diagnostic compile option in both the
    # resident selector and loaded clients; provenance records the define.
    from build_demo import bundle
    from native_program import ROOT
    try:
        return bundle(output,ROOT/'build/actionc',gem_desktop=True,release_compiler=True)
    finally:
        calypsi_build.emit=original


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--capacity',type=int,choices=(8,16),required=True)
    a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();build(args.output.resolve(),args.capacity)
