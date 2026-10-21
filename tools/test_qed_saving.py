#!/usr/bin/env python3
"""Focused production saving helpers in ordinary loaded Processes."""
import argparse,struct,json,hashlib
from pathlib import Path
from native_program import ROOT,require
from qed_probe import run_probe

def heap(b,p,app,record,owner):
    from os_boundary import run_to
    import adapter_state as adapter
    from test_cooperative import data
    delta=owner['image_base']-(app['abi']['link_bank']<<16)
    symbols={n:v+delta for n,v in app['image']['symbols'].items()}
    condition='(dw($%x)=1)|(dw($%x)!=0)'%(symbols['QedSavingFinished'],symbols['QedProbeReturned'])
    b.bp_clear_all();b.bp_set(p['labels']['native_cop'],condition=condition)
    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
    original=b.regs
    def regs():
        values=original()
        require(not b.eval_expr(adapter.STOPPED),'Saving probe failed: '+str(data(b,p['image'],'lastPrimary',True)))
        return values
    b.regs=regs
    try:
        run_to(b,p['labels']['native_cop'],condition=condition,timeout=480,frame_limit=30000)
        require(b.peek16(symbols['QedSavingFinished'])==1,'Saving helper returned early: '+str(b.peek16(symbols['QedProbeReturned'])))
    except Exception:
        record['saving_failure']={n:int.from_bytes(b.memdump(symbols[n],2),'little')
            for n in ('QedProbeCheck','QedProbeReturned','mode','closes','deletes','writes') if n in symbols}
        record['saving_failure']['adapter_status']=b.peek16(adapter.STATE)
        raise
    finally:b.regs=original
    record['saving_core']=dict(zip(('blocks','payload','backing','peak_backing'),
        struct.unpack('<4I',b.memdump(symbols['QedSavingHeap'],16))))

def audit_stage(out,filesystem):
    from filesystem_audit import Audit
    out=out.resolve();oracle=Audit((out/'system.atr').read_bytes())
    allocation=getattr(oracle,filesystem)()
    expected=b''.join(b'\t'+bytes([97+i%26])*1021+bytes([255 if i%2 else 128])+b'\n' for i in range(80))
    files={n:v for n,v in oracle.files.items() if n.startswith('Q') and n.endswith('.TMP')}
    require(len(files)==2 and all(v==expected for v in files.values()),'Closed ATR staging bytes differ')
    result=dict(status='pass',scope='Closed staging T artifacts; no publication or Saved claim',
        allocation=allocation,files={n:dict(bytes=len(v),sha256=hashlib.sha256(v).hexdigest()) for n,v in files.items()},
        image_sha256=hashlib.sha256((out/'system.atr').read_bytes()).hexdigest())
    (out/'staging-audit.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

def core(out,native_from,filesystem='sdfs',group='stage'):
    result=run_probe(out,'qed_stage_edges.c' if group=='edges' else 'qed_stage.c',native_units=('path.c','stage.c'),qed_units=('memory.c','clipbrd.c'),
        native_from=native_from,filesystem=filesystem,writable=True,ram=True,
        interaction=heap,minimum_stack=2048,
        extra_inputs=[ROOT/'tests/programs/qed_stage.c'] if group=='edges' else (),
        calls={'stage.c':dict(malloc='QedStageAllocate',QedFileExclusive='QedStageExclusive',
            DeleteFile='QedStageDelete'),
            'files.c':dict(Write='QedStageNativeWrite',Close='QedStageNativeClose')})
    if group=='stage':audit_stage(out,filesystem)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path,required=True)
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--group',choices=('stage','edges'),default='stage');a=p.parse_args()
    r=core(a.output,a.native_from,a.filesystem,a.group);print(r['status'],r['completed'])
