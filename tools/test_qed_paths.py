#!/usr/bin/env python3
"""Canonical path ownership using production QED helpers and public DOS."""
import argparse
from pathlib import Path
from native_program import ROOT,compiler
from build_command import compile_command
from qed_probe import run_probe

def run(out,native_from):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    target=out/'REASSIGN'
    compile_command(compiler(ROOT/'build/actionc',release=True),ROOT/'tests/programs/qed_reassign.act',target,True)
    return run_probe(out,'qed_paths.c',native_units=('path.c',),native_from=native_from,
        writable=True,ram=True,loader_failures=True,media_files={'REASSIGN':target.read_bytes()},minimum_stack=2048)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path,required=True);a=p.parse_args();run(a.output,a.native_from)
