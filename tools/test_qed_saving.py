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
    if 'QedTransactionCases' in symbols:
        record['transaction_cases']=b.peek16(symbols['QedTransactionCases'])
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

def audit_transaction(out,filesystem):
    from filesystem_audit import Audit
    out=out.resolve();oracle=Audit((out/'system.atr').read_bytes());allocation=getattr(oracle,filesystem)()
    require(oracle.files.get('AUDIT.TXT')==b'\t\x80\n\t\xff' and
        oracle.files.get('AUDIT.BAK')==b'old','Published D/B bytes differ')
    require(not any(n.startswith('Q') and n.endswith(('.TMP','.OLD')) for n in oracle.files),
        'Core fixture retained an unexpected T/E')
    result=dict(status='pass',scope='Preauthorized core; injected uncertainty is not an offline transport claim',
        allocation=allocation,image_sha256=hashlib.sha256((out/'system.atr').read_bytes()).hexdigest(),
        files={n:dict(bytes=len(oracle.files[n]),sha256=hashlib.sha256(oracle.files[n]).hexdigest())
               for n in ('AUDIT.TXT','AUDIT.BAK')})
    (out/'transaction-audit.json').write_text(json.dumps(result,indent=2)+'\n');return result

def protected_media(path,filesystem):
    from mydos_fixtures import Image
    from test_filesystem_write_edges import entry
    from filesystem_audit import Audit
    image=Image(path.read_bytes())
    for name in ('PROTECT.TXT','BACKPROT.BAK'):
        positions,_,_=entry(image,filesystem,name)
        image.data[positions[0]]|=0x20 if filesystem=='mydos' else 1
    if filesystem=='sdfs':
        positions,_,_=entry(image,filesystem,'META.TXT');image.data[positions[0]]|=6
    getattr(Audit(image.data),filesystem)();path.write_bytes(image.data)

def core(out,native_from,filesystem='sdfs',group='stage'):
    transaction=group in ('transaction','transaction-edges')
    support=[]
    if group=='transaction-edges':
        generated=out.resolve()/'app/qed-transaction-support.inc';generated.parent.mkdir(parents=True,exist_ok=True)
        source=ROOT/'tests/programs/qed_transaction.c'
        prefix=source.read_text().split('static int body(int argc,char **argv)')[0]
        prefix=prefix.replace('#include "qed_stage.c"','#include "'+str(ROOT/'tests/programs/qed_stage.c')+'"')
        generated.write_text(prefix);support=[source,generated]
    result=run_probe(out,'qed_transaction_edges.c' if group=='transaction-edges' else ('qed_transaction.c' if group=='transaction' else ('qed_stage_edges.c' if group=='edges' else 'qed_stage.c')),native_units=('path.c','stage.c',*(['save.c'] if transaction else [])),qed_units=('memory.c','clipbrd.c'),
        native_from=native_from,filesystem=filesystem,writable=True,ram=True,
        interaction=heap,minimum_stack=2048,
        extra_inputs=[ROOT/'tests/programs/qed_stage.c',*support] if group!='stage' else (),
        prepare_media=protected_media if group=='transaction-edges' else None,
        media_files={'PROTECT.TXT':b'protected','BACKPROT.TXT':b'old','BACKPROT.BAK':b'protected','META.TXT':b'metadata'} if group=='transaction-edges' else None,
        calls={'stage.c':dict(malloc='QedStageAllocate',QedFileExclusive='QedStageExclusive',
            DeleteFile='QedStageDelete'),
            **({'path.c':dict(malloc='QedStageAllocate')} if group=='transaction-edges' else {}),
            'files.c':dict(Write='QedStageNativeWrite',Close='QedStageNativeClose'),
            **({'save.c':dict(Rename='QedTxnRename',DeleteFile='QedTxnDelete',**({'calloc':'QedTxnAllocate'} if group=='transaction-edges' else {}))} if transaction else {})})
    if group=='stage':audit_stage(out,filesystem)
    if group=='transaction':audit_transaction(out,filesystem)
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path,required=True)
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    p.add_argument('--group',choices=('stage','edges','transaction','transaction-edges'),default='stage');a=p.parse_args()
    r=core(a.output,a.native_from,a.filesystem,a.group);print(r['status'],r['completed'])
