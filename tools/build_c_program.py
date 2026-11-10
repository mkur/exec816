#!/usr/bin/env python3
"""Compile a disk C application and verify relocation at every permitted bank."""
import argparse
import json
import re
from pathlib import Path

from calypsi_build import emit
from calypsi_image import read_image
from c_program import ABI, fixups, import_assembly, pack, shape, verify
from native_program import ROOT, command, sha256,require
from c_runtime_build import prepare as runtime_sources,audit as audit_runtime,COMPILER_OPTIONS


def build(output,sources,optimize=True,probes=(),includes=(),definitions=None,runtime_attributes=None,
          extra_assembly=(),minimum_stack=None,extra_inputs=(),main_signature='void'):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    sources,runtime=runtime_sources(output,sources,main_signature)
    require(not runtime_attributes or runtime_attributes.get('printf','nofloat')=='nofloat','APP printf uses the integer formatter')
    runtime_attributes={'printf':'nofloat',**(runtime_attributes or {})}
    assembly=output/'imports.s'
    assembly.write_text(import_assembly())
    image=emit(output,sources,[assembly,ROOT/'c/calypsi/image-info.s',*extra_assembly],(),optimize=optimize,
               probes=probes,includes=includes,definitions=definitions,runtime_attributes=runtime_attributes,
               compiler_options=COMPILER_OPTIONS,entry_name=ABI['entry'])
    runtime['owners']=audit_runtime(output,image,sources)
    relocations,banks=verify_relocations(output,image)
    payload,record=pack(image,relocations,minimum_stack)
    path=output/'program.app';path.write_bytes(payload)
    record.update(abi=ABI,bytes=len(payload),sha256=sha256(path),verified_banks=banks,
                  image=image,c_runtime=runtime,inputs={str(p):sha256(p) for p in (*sources,*extra_assembly,*extra_inputs)})
    (output/'app.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


def verify_relocations(output,image,roots=()):
    """The same independent relocation proof for executable and analysis images."""
    output=Path(output)
    original=(ROOT/'c/calypsi/layout.scm').read_text()
    span=max(s['offset']+s['size'] for s in shape(image,ABI['link_bank']))
    last=ABI['max_banks']-(span+65535)//65536
    def link(bank):
        layout=re.sub(r'#x([0-9a-f]+)',lambda m:'#x'+format(int(m[1],16)+(bank-ABI['link_bank'])*65536,'x')
                      if int(m[1],16)>=ABI['link_bank']*65536 else m[0],original)
        config=output/'relocated.scm';config.write_text(layout)
        elf=output/'relocated.elf'
        attributes=[part for name,value in image['provenance']['runtime_attributes'].items()
                    for part in ('--rtattr',name+'='+value)]
        overrides=[part for name in image['provenance'].get('runtime_source_overrides',{}).get('symbol_overrides',[]) for part in ('--override',name)]
        command([image['provenance']['tools']['ln65816']['path'],'--hosted','--program-root',ABI['entry'],
                 '--program-start',ABI['entry'],'--root-symbol','__exec_image_info',
                 *[part for name in roots for part in ('--root-symbol',name)],*attributes,*overrides,
                 '--no-data-init-table-section','--no-automatic-placement-rules','-o',elf,
                 *image['provenance']['link_objects'],config])
        return read_image(elf,base_bank=bank,entry_name=ABI['entry'])
    relocations=fixups(image,link(ABI['link_bank']+1))
    # Exhaust the bounded 4 MiB profile, including negative displacements.
    # This detects address arithmetic that a single +1 comparison cannot prove.
    for bank in range(1,last+1):
        verify(image,link(bank),bank,relocations)
    return relocations,list(range(1,last+1))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,action='append',required=True)
    parser.add_argument('--main-signature',choices=('void','args'),default='void')
    parser.add_argument('--raw',action='store_true')
    parser.add_argument('--minimum-stack',type=int,help='Total pool bytes including interrupt reserve')
    args=parser.parse_args()
    build(args.output,[p.resolve() for p in args.source],not args.raw,minimum_stack=args.minimum_stack,main_signature=args.main_signature)
