#!/usr/bin/env python3
"""Build the donor calculator as one ordinary private Exec C image."""
import argparse
from pathlib import Path
from build_c_program import build as application
from prepare_calculator import prepare


def build(output):
    output=Path(output).resolve();prepare(output)
    source=output/'source/src/apps'
    probe=output/'calculator-layout.c'
    probe.write_text('#include "'+str(source/'calculator.h')+'"\n#include <stddef.h>\n'
        '__attribute__((section("exec_layout")))\nconst UWORD CalculatorLayout[]={'
        'sizeof(struct Calculator),offsetof(struct Calculator,ready),'
        'offsetof(struct Calculator,actions),offsetof(struct Calculator,work),'
        'offsetof(struct Calculator,message)};\n')
    return application(output,[source/'calc.c',source/'calcapp.c'],probes=[(probe,[
        ('Calculator size',46),('Calculator ready',4),('Calculator actions',18),
        ('Calculator work',22),('Calculator message',30)])])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();build(args.output)
