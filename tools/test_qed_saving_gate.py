#!/usr/bin/env python3
"""Combined current saving/editor development gate, with closed-image bytes."""
import argparse,hashlib,json
from pathlib import Path
from native_program import ROOT,require,sha256
from test_qed_selection import run
from test_qed_cleanup_stop import media
from qed_combined_observe import interact,expected


def audit(out):
    from filesystem_audit import Audit
    oracle=Audit((out/'system.atr').read_bytes());allocation=oracle.sdfs()
    original,one,two,three=expected()
    expected_files={'COMBO.TXT':b'\n'.join(one),'COMBO.BAK':b'\n'.join(original),
        'FRESH.TXT':b'\n'.join(three),'FRESH.BAK':b'\n'.join(two),
        'CRLF.TXT':b'aone\r\nlast','CRLF.BAK':b'one\r\nlast',
        'LONGNAME.LNG/'*16+'DEEP.TXT':b'adeep','LONGNAME.LNG/'*16+'DEEP.BAK':b'deep'}
    for name,payload in expected_files.items():require(oracle.files.get(name)==payload,'Combined ATR differs: '+name)
    temporary={n:v for n,v in oracle.files.items() if n.startswith('Q') and n.endswith(('.TMP','.OLD'))}
    require(len(temporary)==1 and list(temporary.values())==[b'\n'.join(two)],'Uncertain recovery T was altered/lost')
    data=dict(status='pass',image_sha256=sha256(out/'system.atr'),allocation=allocation,
        files={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in {**expected_files,**temporary}.items()})
    (out/'saving-gate-audit.json').write_text(json.dumps(data,indent=2)+'\n');return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path,required=True);p.add_argument('--reuse-app',action='store_true');a=p.parse_args()
    observers=[*ROOT.glob('tools/qed*observe.py'),ROOT/'tools/qed_form_oracle.py',Path(__file__),
        ROOT/'tools/qed_stack_observer.py',ROOT/'tests/programs/qed_cleanup_stop.act',
        ROOT/'tests/programs/qed_saving_cleanup_faults.c',ROOT/'tests/programs/qed_saving_faults.c',
        ROOT/'tests/programs/qed_editing_faults.c']
    source_hashes={str(v.relative_to(ROOT)):sha256(v) for v in observers}
    r=run(a.output,native_from=a.native_from,reuse_app=a.reuse_app,
        fixture_source=ROOT/'tests/programs/qed_cleanup_stop.act',media_files=media(),
        saving=True,long_cleanup=True,writable=True,interaction=interact)
    r['observer_inputs']=source_hashes
    (a.output/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    audit(a.output.resolve());print(r['status'],r['completed'])
