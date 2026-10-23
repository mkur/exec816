#!/usr/bin/env python3
"""Boot a separately relinked, changed-library QED on diagnostic media."""
import argparse
import json
import shutil
import zipfile
from pathlib import Path

from filesystem_audit import Audit
from make_data_disk import make
from native_program import ROOT, require, sha256
from qed_demo import verify, SAMPLE
from test_demo import run
from test_qed_exec_setup import QedPreview


class RelinkedSetup(QedPreview):
    def exercise(self,session):
        super().exercise(session)
        session.saved['integration'].update(production_app=False,changed_library_diagnostic=True)


def check(output,bundle,relinked):
    require(not output.exists(),'Use a fresh relink boot directory')
    demo=json.loads((bundle/'demo-manifest.json').read_text());verify(demo,bundle)
    replacement=json.loads((relinked/'relink-results.json').read_text())
    require(replacement['status']=='pass' and replacement['replacement'] and
        replacement['app_sha256']==sha256(relinked/'program.app')!=demo['qed']['app_sha256'],
        'Use a verified changed-library diagnostic APP')
    def ignore(directory,names):
        return [n for n in names if n in {'altirra','extracted','emulator.log'} or
                n.endswith(('-results.json','.bgra')) or n=='work-walkthrough.atr']
    shutil.copytree(bundle,output,ignore=ignore)
    with zipfile.ZipFile(output/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    source=output/'diagnostic-source';shutil.copytree(output/'qed-media',source)
    shutil.copyfile(relinked/'program.app',source/'QED.APP')
    media=output/'diagnostic-qed.atr'
    make(media,source,binary_names={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()},
         filesystem='sdfs',sector_bytes=256,sectors=2880,label='QED')
    inputs={str(p.relative_to(ROOT)):sha256(p) for p in (Path(__file__),ROOT/'tools/test_qed_exec_setup.py',ROOT/'tools/test_demo.py')}
    result=run(output,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
        companion_overrides={'qed.atr':dict(path=str(media),sha256=sha256(media))},integration=RelinkedSetup(),profile_commands=False)
    work=Audit((output/'work-walkthrough.atr').read_bytes());allocation=work.sdfs()
    require(work.files['SAMPLE.TXT']==b'cab'+SAMPLE and work.files['SAMPLE.BAK']==b'ab'+SAMPLE,
            'Relinked editor saved/backup bytes differ')
    result.update(qualification=False,scope='Changed retained CF-Lib routine: relink, diagnostic boot, edit/save/reopen and normal return',
        relink_results_sha256=sha256(relinked/'relink-results.json'),modified_app_sha256=replacement['app_sha256'],
        zip_sha256=sha256(output/'exec816-demo.zip'),allocation=allocation,observer_inputs=inputs)
    (output/'relink-boot-results.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--relinked',type=Path,required=True)
    a=p.parse_args();check(a.output.resolve(),a.bundle.resolve(),a.relinked.resolve())
