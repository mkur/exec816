#!/usr/bin/env python3
"""Retained interpreter state and explicit restart in the actual OF816 ZIP."""
import argparse,json
from pathlib import Path
from native_program import sha256
from test_fastbasic_interpreter_demo import SourceInterpreter,physical_keys
from test_twelve_task_demo import check


class PersistentInterpreter(SourceInterpreter):
    def source_shell(self):
        self.command('FB WORK:CALC.BAS',b'3.75')
        self.command('FBI WORK:HELLO.BAS',b'42')



if __name__=='__main__':
    physical_keys()
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--bundle',type=Path,required=True)
    a.add_argument('--native-snapshot',type=Path,help='Replay a verified pre-native boot checkpoint')
    args=a.parse_args();bundle=args.bundle.resolve()
    bootstrap=None
    if args.native_snapshot:
        from test_bootable_atr import DiskBoot
        bootstrap=DiskBoot(bundle,native_snapshot=args.native_snapshot.resolve())
    result=check(bundle,PersistentInterpreter,bootstrap)
    result.update(feature='persistent-interpreter',runner_sha256=sha256(Path(__file__)))
    if args.native_snapshot:result['replay_snapshot_sha256']=sha256(args.native_snapshot)
    (bundle/'persistent-interpreter-results.json').write_text(json.dumps(result,indent=2)+'\n')
