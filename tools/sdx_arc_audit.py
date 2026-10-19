"""Static reachable-code and inline-operand inventory of the four pinned ARC modules.

This is a decoder and input audit, not an emulator or a qualification claim.
Audited main jump-table entries and trap continuations are explicit roots.
"""
import argparse
import hashlib
import json
from pathlib import Path

from sdx_file import parse,place
from sdx_md5_audit import OPCODES,ROOT
from sdx_patch import manifests,select,validate_patches


def audit(directory):
    abi=json.loads((ROOT/'abi/sdx.json').read_text())
    symbols={name:entry['address'] for name,entry in abi['guest_services'].items()}
    symbols['_ARC']=0x3959
    imports={v:k for k,v in symbols.items() if abi['guest_services'].get(k,{}).get('event',0)}
    printers=[symbols[k] for k in ['PRINTF','VPRINTF']]+[0x31a8,0x31b0,0x3959,0x395c]
    result={}
    for leaf in ['ARC.COM','ARCLST.OVL','ARCEXT.OVL','ARCADD.OVL']:
        raw=(directory/leaf).read_bytes();manifest,module=select(raw,manifests(ROOT/'compat/sdx'))
        assert manifest['id']=='arc-450' and module['file']==leaf
        program=parse(raw);validate_patches(program,module)
        memory,layout=place(program,0x3000 if leaf=='ARC.COM' else 0x4a6c,0xe000,symbols)
        lo=layout['blocks'][1];hi=lo+program.blocks[0].size
        pending=[lo]+([0x321a,0x35c6]+list(range(0x3959,0x399b,3)) if leaf=='ARC.COM' else [])
        if leaf=='ARCEXT.OVL':
            pending += [int.from_bytes(memory[a:a+2],'little') for a in range(0x4fc7,0x4fcf,2)]
        code={};inline={};external=[]
        while pending:
            pc=pending.pop()
            if pc in code or not lo<=pc<hi:continue
            op=memory[pc]
            assert op in OPCODES,(leaf,hex(pc),hex(op))
            name,mode,size=OPCODES[op]
            operand=int.from_bytes(memory[pc+1:pc+size],'little');after=pc+size
            code[pc]=dict(instruction=name,mode=mode,operand=operand,bytes=size)
            if name in ['JSR','JMP']:
                if operand in printers:
                    if name=='JMP':continue
                    end=memory.index(0,after,hi);text=memory[after:end];count=0;index=0
                    while index<len(text):
                        if text[index]==37:
                            index+=1
                            if text[index]!=37:
                                count+=1
                                while chr(text[index]) in '0123456789*':
                                    if text[index]==42:count+=1
                                    index+=1
                        index+=1
                    sites=list(range(end+1,end+1+count*2,2))
                    inline[pc-lo]=dict(text_hex=text.hex(),sites=[at-lo for at in sites],
                        values=[int.from_bytes(memory[at:at+2],'little') for at in sites])
                    after=end+1+count*2
                elif operand==0x34fe and name=='JSR':after+=6
                if not lo<=operand<hi:
                    external.append(dict(offset=pc-lo,target=operand,symbol=imports.get(operand)))
                else:pending.append(operand)
                if name=='JMP':continue
            if name=='RTS':continue
            if mode=='rel':pending.append(after+(operand if operand<128 else operand-256))
            pending.append(after)
        assert not any(x['instruction']=='SEI' for x in code.values())
        result[leaf]=dict(sha256=hashlib.sha256(raw).hexdigest(),layout=layout,
            instructions=len(code),external=external,inline=inline,
            memory_accesses=[dict(offset=pc-lo,**x) for pc,x in sorted(code.items()) if x['mode'] not in ['imp','imm','rel'] and x['instruction'] not in ['JSR','JMP']],
            instruction_offsets=[pc-lo for pc in sorted(code)],
            direct_page_arguments=[site for x in inline.values() for site,value in zip(x['sites'],x['values']) if value<256])
    return dict(status='pass',scope='Pinned original static inventory; self-modifying operand targets and execution paths require slice-specific checks',modules=result)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs',type=Path,default=ROOT/'build/sdx-inputs/arc')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=audit(args.inputs)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print({name:module['instructions'] for name,module in result['modules'].items()})
