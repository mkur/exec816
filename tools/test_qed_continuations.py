#!/usr/bin/env python3
"""Loaded QED Save/Discard/Cancel and post-save rereading development checks."""
import argparse,hashlib,json
from pathlib import Path
from native_program import ROOT,require,sha256
from test_qed_selection import run
from test_qed_documents import fixtures
from qed_continuations_observe import interact


def audit(out,filesystem):
    from filesystem_audit import Audit
    oracle=Audit((out/'system.atr').read_bytes());allocation=getattr(oracle,filesystem)()
    expected={'SAVED.TXT':b'cbaxyz','SAVED.BAK':b'baxyz','REREAD.TXT':b'abc',
        'FRESH.TXT':b'abcde','FRESH.BAK':b'abcd','CRLF.TXT':b'aone\r\nlast','CRLF.BAK':b'one\r\nlast',
        'LONGNAME.LNG/'*16+'DEEP.TXT':b'deep'}
    for n,v in expected.items():require(oracle.files.get(n)==v,'Continuation ATR differs: '+n)
    require(not any(n.startswith('Q') and n.endswith(('.TMP','.OLD')) for n in oracle.files),
            'Continuation fixture retained temporary files')
    result=dict(status='pass',allocation=allocation,image_sha256=sha256(out/'system.atr'),
        files={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in expected.items()})
    (out/'continuation-audit.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path);p.add_argument('--provider-from',type=Path)
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--from-build',action='store_true');p.add_argument('--reuse-app',action='store_true')
    p.add_argument('--short-launch',action='store_true')
    a=p.parse_args()
    media=fixtures()
    if a.short_launch:media['LONG.TXT']=b'd'
    r=run(a.output,reuse=a.from_build,reuse_app=a.reuse_app,native_from=a.native_from,
        fixture_source=ROOT/'tests/programs/qed_continuations.act',media_files=media,filesystem=a.filesystem,
        provider_from=a.provider_from,saving=True,writable=True,interaction=lambda *args:interact(*args,short_launch=a.short_launch))
    audit(a.output.resolve(),a.filesystem);print(r['status'],r['completed'])
