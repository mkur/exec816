#!/usr/bin/env python3
"""Build the normal QED demo (convenience entry point)."""
import argparse
from pathlib import Path
from build_demo import bundle
from native_program import ROOT

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/qed-delivery/separate-disk')
    parser.add_argument('--compiler-dir', type=Path, default=ROOT/'build/actionc')
    args = parser.parse_args()
    bundle(args.output,args.compiler_dir,gem_desktop=True,qed=True,mouse_profile='mild',release_compiler=True)
