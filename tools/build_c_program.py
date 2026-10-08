#!/usr/bin/env python3
"""Compile a disk C application and verify relocation at every permitted bank."""
import argparse
import json
import re
from pathlib import Path

from calypsi_build import emit
from calypsi_image import read_image
from c_program import ABI, fixups, import_assembly, pack, shape, verify
from native_program import ROOT, command, sha256


def build(output,sources,optimize=True):
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    assembly=output/'imports.s'
    assembly.write_text(import_assembly())
    image=emit(output,sources,[assembly,ROOT/'c/calypsi/image-info.s'],(),optimize=optimize)
    original=(ROOT/'c/calypsi/layout.scm').read_text()
    span=max(s['offset']+s['size'] for s in shape(image,ABI['link_bank']))
    last=ABI['max_banks']-(span+65535)//65536
    def link(bank):
        layout=re.sub(r'#x([0-9a-f]+)',lambda m:'#x'+format(int(m[1],16)+(bank-ABI['link_bank'])*65536,'x')
                      if int(m[1],16)>=ABI['link_bank']*65536 else m[0],original)
        config=output/'relocated.scm';config.write_text(layout)
        elf=output/'relocated.elf'
        command([image['provenance']['tools']['ln65816']['path'],'--hosted','--program-root','main',
                 '--program-start','main','--root-symbol','__exec_image_info',
                 '--no-data-init-table-section','--no-automatic-placement-rules','-o',elf,
                 *image['provenance']['link_objects'],config])
        return read_image(elf,base_bank=bank)
    relocations=fixups(image,link(ABI['link_bank']+1))
    # Exhaust the bounded 4 MiB profile, including negative displacements.
    # This detects address arithmetic that a single +1 comparison cannot prove.
    for bank in range(1,last+1):
        verify(image,link(bank),bank,relocations)
    payload,record=pack(image,relocations)
    path=output/'program.app';path.write_bytes(payload)
    record.update(abi=ABI,bytes=len(payload),sha256=sha256(path),verified_banks=list(range(1,last+1)),
                  image=image,inputs={str(p):sha256(p) for p in sources})
    (output/'app.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--source',type=Path,action='append',required=True)
    parser.add_argument('--raw',action='store_true')
    args=parser.parse_args()
    build(args.output,[p.resolve() for p in args.source],not args.raw)
