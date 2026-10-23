#!/usr/bin/env python3
"""QE5 native dialog adapters and ordinary loaded-editor Find."""
import argparse
from pathlib import Path
from qed_probe import run_probe

def core(output,native_from=None):
    return run_probe(output,'qed_dialogs_core.c',native_units=('commands.c',),
        qed_units=('memory.c','find.c','block.c'),
        calls={'commands.c':dict(form_center='QedProbeCenter',form_do='QedProbeForm',
            set_state='QedProbeState',fsel_exinput='QedProbeSelector',ExecAESDiagnostic='QedProbeDiagnostic',
            form_alert='QedProbeAlert')},
        native_from=native_from)

def editor(output,native_from=None,reuse=False,reuse_app=False):
    from test_qed_selection import run
    from qed_dialogs_observe import interact
    return run(output,reuse=reuse,reuse_app=reuse_app,native_from=native_from,interaction=interact)

def selector(output,native_from=None):
    from qed_selector_observe import interact
    from file_selector_model import LAYOUT
    return run_probe(output,'qed_selector_native.c',native_units=('commands.c',),
        native_from=native_from,interaction=interact,interactive_lifetimes=True,
        probes=[('aes_fsel_layout.c',LAYOUT)],
        minimum_stack=2560,media_files={'DATA.TXT':b'Native QED selector reference.\n'})

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native-from',type=Path)
    parser.add_argument('--group',choices=['core','editor','selector'],default='core')
    parser.add_argument('--from-build',action='store_true')
    parser.add_argument('--reuse-app',action='store_true')
    args=parser.parse_args()
    result=(core(args.output,args.native_from) if args.group=='core' else
            selector(args.output,args.native_from) if args.group=='selector' else
            editor(args.output,args.native_from,args.from_build,args.reuse_app))
    print(result['status'],result['completed'])
