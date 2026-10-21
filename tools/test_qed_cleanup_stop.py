#!/usr/bin/env python3
"""Real-editor Stop while a 256 KiB older backup awaits native deletion."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from test_qed_selection import run
from test_qed_documents import fixtures
from qed_cleanup_stop_observe import interact


def media():
    files=fixtures();files.update({'LONG.TXT':b'd','CRLF.BAK':b'Y'*262144});return files


def audit(out):
    from filesystem_audit import Audit
    oracle=Audit((out/'system.atr').read_bytes());allocation=oracle.sdfs()
    require(oracle.files.get('CRLF.TXT')==b'aone\r\nlast' and oracle.files.get('CRLF.BAK')==b'one\r\nlast',
            'Stop interrupted publication or retained the wrong backup')
    require(not any(n.startswith('Q') and n.endswith(('.TMP','.OLD')) for n in oracle.files),'Cleanup Stop retained T/E')
    result=dict(status='pass',allocation=allocation,image_sha256=sha256(out/'system.atr'),
        older_backup_bytes=262144,saved_hex=oracle.files['CRLF.TXT'].hex(),backup_hex=oracle.files['CRLF.BAK'].hex())
    (out/'cleanup-stop-audit.json').write_text(json.dumps(result,indent=2)+'\n');return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path);p.add_argument('--provider-from',type=Path)
    p.add_argument('--reuse-app',action='store_true');a=p.parse_args()
    r=run(a.output,native_from=a.native_from,reuse_app=a.reuse_app,
        fixture_source=ROOT/'tests/programs/qed_cleanup_stop.act',media_files=media(),
        provider_from=a.provider_from,saving=True,long_cleanup=True,writable=True,interaction=interact)
    audit(a.output.resolve());print(r['status'],r['completed'])
