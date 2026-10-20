#!/usr/bin/env python3
"""Inventory emitted integer runtime/compiler code and its native boundaries.

This traversal is not an emulator or a proof of dynamic pointer/stack safety.
It roots every linked bytecode handler, parser entry and port callback. Parser
action-table RTS transfers and writable operands still require source review.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re

from build_fastbasic import ABI, ROOT, profile, sha256
from sdx_md5_audit import OPCODES


def audit(source):
    prefix=source/'build/bin/fbci'
    raw=prefix.with_suffix('.xex').read_bytes()
    layout=profile(raw)
    labels={name:int(address,16) for address,name in re.findall(
        r'al ([0-9A-Fa-f]+) \.(\S+)',prefix.with_suffix('.lbl').read_text())}
    memory=bytearray(65536)
    memory[ABI['load']-16:layout['end']]=raw
    roots={name:address for name,address in labels.items() if name.startswith('EXE_')
           or name in ('COMPILE_BUFFER','FB_ARGUMENT','FB_ERROR','parser_start')}
    roots['container_entry']=layout['entry']
    dynamic={labels['dispatch_jump']:0xffff,labels['EXE_USR_CALL']:0xff00}
    services={ABI['checkpoint']:'checkpoint',**{
        ABI['service_base']+index*ABI['service_stride']:name
        for index,name in enumerate(ABI['services'])}}
    pending=list(roots.values())
    code,calls,accesses={},[],[]
    while pending:
        pc=pending.pop()
        if pc in code:continue
        if not ABI['load']<=pc<layout['end']:
            raise ValueError(f'Out-of-image control transfer: {pc:#x}')
        op=memory[pc]
        if op not in OPCODES:
            raise ValueError(f'Unreviewed opcode at {pc:#x}: {op:#x}')
        name,mode,size=OPCODES[op]
        if pc+size>layout['end']:raise ValueError('Truncated instruction')
        value=int.from_bytes(memory[pc+1:pc+size],'little')
        code[pc]=(name,mode,value)
        after=pc+size
        if pc in dynamic:
            if name!='JMP' or mode!='abs' or value!=dynamic[pc]:
                raise ValueError('Changed reviewed private JMP')
            continue
        if name in ('JMP','JSR'):
            if value in services:
                calls.append(dict(pc=pc,service=services[value],address=value))
            else:pending.append(value)
            if name=='JMP':continue
        elif mode.startswith('abs'):
            if value<256 or value>=0xc000:
                accesses.append(dict(pc=pc,instruction=name,mode=mode,address=value))
        if name=='RTS':continue
        if mode=='rel':pending.append(after+(value if value<128 else value-256))
        pending.append(after)
    return dict(format='exec816-fastbasic-code-inventory-v1',status='pass',
        scope='Static emitted-code inventory with selected roots; no dynamic-pointer, parser-table, stack or interrupt qualification',
        compiler_sha256=sha256(prefix.with_suffix('.xex')),
        map_sha256=sha256(prefix.with_suffix('.map')),profile=layout,
        heap_start=labels['__HEAP_RUN__'],
        direct_page=dict(start=0x80,used_end=0xb9,reserved_end=0xf0),
        roots=roots,instructions=len(code),modes=dict(Counter(v[1] for v in code.values())),
        services=sorted(calls,key=lambda item:item['pc']),
        private_mutable_jumps=dynamic,absolute_low_or_os_accesses=accesses,
        exclusions=['Unreachable donor IDE compile.asm and BRKKY ownership',
                    'User grammar excludes external USR and hardware statements',
                    'Parser action-table returns and data-dependent addresses reviewed at source level'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=ROOT/'build/fastbasic/source')
    parser.add_argument('--output',type=Path,default=ROOT/'build/fastbasic/audit.json')
    args=parser.parse_args()
    result=audit(args.source.resolve())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('FastBasic inventory:',result['instructions'],'instructions;',
          len(result['absolute_low_or_os_accesses']),'low/OS absolute data operands')
