#!/usr/bin/env python3
"""Build the ordinary loadable G4BENCH application."""
import argparse
from pathlib import Path
from build_c_program import build as application
from prepare_g4bench import prepare


def build(output):
    output=Path(output).resolve();prepare(output)
    source=output/'source/src/apps'
    return application(output,[source/'bench.c',source/'clock.c',source/'g4bench.c'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    build(parser.parse_args().output)
