#!/usr/bin/env python3
"""Boot the unchanged core package with the optional QED disk absent."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from native_program import require,sha256
from qed_demo import verify
from test_demo import run


def check(bundle,output):
    require(not output.exists(),'Use a fresh core-only check directory')
    demo=json.loads((bundle/'demo-manifest.json').read_text());verify(demo,bundle)
    def ignore(directory,names):
        return [n for n in names if n in {'altirra','extracted','emulator.log'} or
                n.endswith(('-results.json','.bgra')) or n.endswith('-walkthrough.atr')]
    shutil.copytree(bundle,output,ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    result=run(output,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
               omit_media=('qed.atr',),profile_commands=False)
    result.update(qualification=False,scope='Exact core SYS/OF816 boot with optional QED disk absent; ordinary commands, WORK writes and EXIT',
                  zip_sha256=sha256(bundle/'exec816-demo.zip'))
    (output/'core-only-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();check(args.bundle.resolve(),args.output.resolve())
