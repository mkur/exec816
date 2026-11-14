#!/usr/bin/env python3
"""Loaded GEMDOS source subset on the pinned native Process/DOS provider."""
import argparse
import json
from pathlib import Path
from native_program import ROOT,require
from generate_gemdos_compat import expected_layout
from c_program import ABI
from test_c_runtime import fixture
from test_c_process import run as process_run


def run(out,mode,abi=False,reuse=False,filesystem='sdfs',metadata=False,stat=False,document=False):
    out.mkdir(parents=True,exist_ok=True)
    metadata=metadata or stat or document
    definitions={} if metadata and not (stat or document) else {name:['-DEXEC_CRT_TEST'] for name in ('allocation.c','files.c')}
    if stat:
        definitions[str(ROOT/'c/runtime/files.c')]=['-DEXEC_CRT_TEST','-DExamineFH=ExecCRTTestExamineFH']
    source='gemdos_document.c' if document else 'gemdos_stat.c' if stat else 'dos_examine_fh.c' if metadata else 'gemdos_compat.c'
    if abi:definitions[source]=['-DGEMDOS_ABI_ONLY']
    native=fixture(out,'abi' if abi and not metadata else 'files')
    if metadata:
        text=native.read_text().replace('DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)',
            'DOS.Open(BYTE POINTER(c"SYS:FHDATA.DAT"),DOS.MODE_OLDFILE)')
        text=text.replace('  LET oldInput=',
            '  Require(DOS.Seek(input,11,DOS.OFFSET_BEGINNING)=0)\n  LET oldInput=')
        text=text.replace('  DOS.SelectInput(oldInput)',
            '  Require(DOS.Seek(input,0,DOS.OFFSET_CURRENT)=11)\n  DOS.SelectInput(oldInput)')
        native.write_text(text)
    media={'FHDATA.DAT':bytes(n&255 for n in range(513)),'EMPTY.DAT':b''} if metadata else {}
    if document:
        media.update({'SMALL.TXT':b'one\r\ntwo\nthree\rfour\tend','MAX.TXT':b'x'*65519,
            'TOOBIG.TXT':b'x'*65520,'MAXLINES.TXT':b'\n'*16380,'TALL.TXT':b'\n'*16381})
    record=process_run(out,mode=='opt',reuse=reuse,rebuild_app=reuse,
        app_sources=[ROOT/'tests/programs'/source],
        app_options=dict(gemdos=True,minimum_stack=ABI['stack_floor_bytes'],
            includes=[ROOT/'c/runtime',ROOT/'c/compat/gemdos'],definitions=definitions,
            probes=[(ROOT/'c/compat/gemdos/layout.c',expected_layout())]),
        fixture_source=native,expected_completed=2 if abi and not metadata else 4,
        media_files=media,
        native_optimize=True,release_compiler=True,writable=True,ram=True,
        observe_stacks=not abi,filesystem=filesystem,loader_failures=False)
    if document:
        import hashlib
        from filesystem_audit import Audit
        oracle=Audit((out/'system.atr').read_bytes())
        allocation=getattr(oracle,filesystem)()
        persisted={name:data for name,data in oracle.files.items() if name.startswith('DOC') and name.endswith('.DAT')}
        require(len(persisted)>=2 and all(data==media['SMALL.TXT'] for data in persisted.values()),
            'Incorrect independently decoded document bytes')
        record['persisted_documents']=dict(allocation=allocation,files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest()) for name,data in persisted.items()})
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print('GEMDOS',mode,'ABI' if abi else filesystem,'passed',flush=True)
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--case',choices=('raw','opt'),default='opt')
    p.add_argument('--abi',action='store_true')
    p.add_argument('--metadata',action='store_true')
    p.add_argument('--stat',action='store_true')
    p.add_argument('--document',action='store_true')
    p.add_argument('--from-build',action='store_true')
    p.add_argument('--variant-from',type=Path,help='Reuse native emission with a rebuilt APP')
    p.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    a=p.parse_args()
    if a.variant_from:
        from test_c_process import variant
        variant(a.variant_from.resolve(),a.output.resolve(),a.filesystem)
    run(a.output.resolve(),a.case,a.abi,a.from_build or bool(a.variant_from),a.filesystem,a.metadata,a.stat,a.document)
