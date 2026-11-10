#!/usr/bin/env python3
"""Current phased APP relocation/instance checks; native ABI probes use test_calypsi."""
import argparse
from pathlib import Path
from test_c_runtime import run as runtime


def run(out,optimize,reuse=False):
    return runtime(out,'relocation','opt' if optimize else 'raw',reuse)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true')
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),not args.raw,args.from_build)
