#!/usr/bin/env python3
"""Fresh native services reopen an exact closed writer ATR without regeneration."""
import argparse,hashlib,json,shutil,struct
from pathlib import Path
from native_program import ROOT,require,sha256
from test_c_process import run,variant
from qed_saving_observe import SavingEditor


def reopen(out,writer,filesystem,native_from=None,combined=False):
    out=out.resolve();writer=writer.resolve();out.mkdir(parents=True,exist_ok=True)
    if native_from:
        variant(native_from.resolve(),out,filesystem)
        # The independent pixel oracle uses the exact selected native font.
        shutil.copytree(native_from.resolve()/'selected',out/'selected',dirs_exist_ok=True)
    original=sha256(writer/'system.atr')
    if combined:
        from qed_combined_observe import expected
        lines=expected()[3]
    else:lines=[b'abcde']
    wanted=b'\n'.join(lines)
    from filesystem_audit import Audit
    oracle=Audit((writer/'system.atr').read_bytes());allocation=getattr(oracle,filesystem)()
    require(oracle.files['FRESH.TXT']==wanted,'Writer ATR differs from the independent expected bytes')
    require(hashlib.sha256(oracle.files['PROBE.APP']).hexdigest()==sha256(writer/'app/program.app'),
            'Writer disk does not contain its recorded APP')
    def app(target):
        shutil.copytree(writer/'app',target,dirs_exist_ok=True)
        data=json.loads((target/'app.json').read_text())
        require(data['sha256']==sha256(target/'program.app'),'Changed copied APP')
        return data
    def media(path,fs):shutil.copyfile(writer/'system.atr',path)
    def interaction(b,p,a,record,owner):
        e=SavingEditor(b,p,a,record,owner);b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
        e.reach('dw($%x)=1'%e.at('phase'));e.frames(40)
        e.launched('fresh-service-reopen',lines,len(wanted),path=b'D1:FRESH.TXT')
        b.memload(e.at('control'),struct.pack('<H',1));return e.retire_key('Q',ctrl=True)
    r=run(out,True,reuse=bool(native_from),rebuild_app=bool(native_from),filesystem=filesystem,
        app_builder=app,fixture_source=ROOT/'tests/programs/qed_fresh_reopen.act',expected_completed=1,
        native_optimize=True,release_compiler=True,writable=False,ram=True,observe_stacks=True,
        loader_failures=False,prepare_media=media,interaction=interaction)
    require(sha256(out/'system.atr')==original==sha256(writer/'system.atr'),'Fresh read changed the exact closed image')
    proof=dict(status='pass',tier='development',fresh_native_services=True,readonly=True,
        image_sha256=original,app_sha256=sha256(out/'app/program.app'),allocation=allocation,
        payload_bytes=len(wanted),payload_sha256=hashlib.sha256(wanted).hexdigest(),
        writer_result_sha256=sha256(writer/'results.json'),reader_result_sha256=sha256(out/'results.json'))
    (out/'fresh-reopen-audit.json').write_text(json.dumps(proof,indent=2)+'\n');return r

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--writer',type=Path,required=True);p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--native-from',type=Path);p.add_argument('--combined',action='store_true');a=p.parse_args()
    r=reopen(a.output,a.writer,a.filesystem,a.native_from,a.combined);print(r['status'],r['completed'])
