#!/usr/bin/env python3
"""QE6 checked reading, single-document replacement and loaded editor sessions."""
import argparse
import struct
from pathlib import Path
from native_program import ROOT

def core_heap(b,p,app,record,owner):
    from os_boundary import run_to
    import adapter_state as adapter
    from test_cooperative import data
    delta=owner['image_base']-(app['abi']['link_bank']<<16)
    sy={n:v+delta for n,v in app['image']['symbols'].items()}
    condition='dw($%x)=1'%sy['QedDocumentFinished']
    b.bp_clear_all();b.bp_set(p['labels']['native_cop'],condition=condition)
    b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
    original=b.regs
    def regs():
        values=original()
        if b.eval_expr(adapter.STOPPED):
            primary=data(b,p['image'],'lastPrimary',True)[0]
            record['document_failure']=dict(primary=primary,
                cause=int.from_bytes(b.memdump(sy['cause'],4),'little'))
            raise RuntimeError('Document core stopped: '+str(record['document_failure']))
        return values
    b.regs=regs
    try:run_to(b,p['labels']['native_cop'],condition=condition,timeout=120,frame_limit=30000)
    finally:b.regs=original
    values=struct.unpack('<4I',b.memdump(sy['QedDocumentHeap'],16))
    record['document_core']=dict(zip(('blocks','payload','backing','peak_backing'),values))

def core(output,native_from,filesystem='sdfs'):
    from qed_probe import run_probe
    return run_probe(output,'qed_documents_core.c',native_units=('document.c',),
        qed_units=('memory.c','clipbrd.c','block.c','tasten.c'),native_from=native_from,
        filesystem=filesystem,interaction=core_heap,media_files=fixtures(),
        calls={'document.c':dict(malloc='QedDocAllocate',new_col='QedDocLine',
            Fread='QedDocRead',Fclose='QedDocClose'),
            'tasten.c':dict(form_alert='QedDocAlert'),'clipbrd.c':dict(form_alert='QedDocAlert')})

def title(output,native_from):
    from qed_probe import run_probe
    return run_probe(output,'qed_title.c',qed_units=('window.c',),native_from=native_from,
        calls={'window.c':dict(wind_set_str='QedTitle')})

def fixtures():
    prefix=b'head\tneedle a*b a*b'
    suffix=b'tail\tneedle a*b a*b'
    return {'EMPTY.TXT':b'', 'SMALL.TXT':b'alpha\tbeta\nsecond\n',
        'CRLF.TXT':b'one\r\nlast', 'NOLAST.TXT':b'a\tb',
        'BOUNDARY.TXT':(b'a'*1023+b'\r\n')*3+b'b'*1020+b'\r\nlast',
        'LONG.TXT':prefix+b'a'*(1023-len(prefix))+b'\n'+(b'a'*1023+b'\n')*78+
            suffix+b'z'*(1023-len(suffix))+b'\n',
        'NUL.TXT':b'ab\x00c', 'MIXED.TXT':b'a\nb\r\n', 'MIXED2.TXT':b'a\r\nb\n',
        'CR.TXT':b'a\rb', 'ENDCR.TXT':b'a\r', 'WIDE.TXT':b'a'*1024}

def editor(output,native_from=None,reuse=False,reuse_app=False,filesystem='sdfs'):
    from test_qed_selection import run
    return run(output,reuse=reuse,reuse_app=reuse_app,native_from=native_from,
        fixture_source=ROOT/'tests/programs/qed_documents.act',media_files=fixtures(),
        filesystem=filesystem,provider_from=ROOT/'build/qed-editing/qe5-core/c-image.json',
        interaction=__import__('qed_documents_observe').interact)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--native-from',type=Path);p.add_argument('--from-build',action='store_true')
    p.add_argument('--reuse-app',action='store_true')
    p.add_argument('--filesystem',choices=['sdfs','mydos'],default='sdfs')
    p.add_argument('--group',choices=['editor','core','title'],default='editor')
    a=p.parse_args();r=(title(a.output,a.native_from) if a.group=='title' else
        core(a.output,a.native_from,a.filesystem) if a.group=='core' else
        editor(a.output,a.native_from,a.from_build,a.reuse_app,a.filesystem))
    print(r['status'],r['completed'])
