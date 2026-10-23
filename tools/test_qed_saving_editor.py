#!/usr/bin/env python3
"""Loaded QED Save/Save As physical-input development cohort."""
import argparse
from pathlib import Path
from native_program import ROOT
from test_qed_selection import run
from test_qed_documents import fixtures
from qed_saving_observe import interact
from native_program import require,sha256
import hashlib,json

def audit_editor(out,filesystem,cleanup=False):
    from filesystem_audit import Audit
    oracle=Audit((out/'system.atr').read_bytes());allocation=getattr(oracle,filesystem)()
    expected={'SAVED.TXT':b'abcdefg','SAVED.BAK':b'abcdefg','CRLF.TXT':b'one\r\nlast',
              'LONGNAME.LNG/'*16+'DEEP.TXT':b'deep'}
    for name,payload in ({} if cleanup else expected).items():
        require(oracle.files.get(name)==payload,'Closed editor ATR differs: '+name)
    if cleanup:
        expected={'CLEAN.TXT':b'abcd','CLEAN.BAK':b'abd','RECOVER.TXT':b'abcd',
            'CRLF.TXT':b'one\r\nlast','LONGNAME.LNG/'*16+'DEEP.TXT':b'deep'}
        for name,payload in expected.items():require(oracle.files.get(name)==payload,'Cleanup ATR differs: '+name)
    temporary={n:v for n,v in oracle.files.items() if n.startswith('Q') and n.endswith(('.TMP','.OLD'))}
    require(len(temporary)==1 and next(iter(temporary.values()))==(b'ad' if cleanup else b'abcdefg'),
            'Uncertain Close must retain its possible T, with exact bytes')
    data=dict(status='pass',allocation=allocation,image_sha256=sha256(out/'system.atr'),
        scope='Independent closed ATR, including explicitly forgotten recovery T; no cache-only byte assertion',
        files={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in {**expected,**temporary}.items()})
    (out/'saving-audit.json').write_text(json.dumps(data,indent=2)+'\n');return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path);p.add_argument('--provider-from',type=Path)
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--from-build',action='store_true');p.add_argument('--reuse-app',action='store_true')
    p.add_argument('--cleanup',action='store_true')
    a=p.parse_args()
    interaction=__import__('qed_saving_cleanup_observe').interact if a.cleanup else interact
    media=fixtures()
    if a.cleanup:media['LONG.TXT']=b'd'
    r=run(a.output,reuse=a.from_build,reuse_app=a.reuse_app,native_from=a.native_from,
        fixture_source=ROOT/'tests/programs/qed_saving.act',media_files=media,filesystem=a.filesystem,
        provider_from=a.provider_from,saving=True,writable=True,interaction=interaction)
    audit_editor(a.output.resolve(),a.filesystem,a.cleanup)
    print(r['status'],r['completed'])
