"""Reachable-instruction audit of the pinned 6502 MD5, including inline data/SMC.

This is a static decoder, not a CPU emulator. Unknown instructions or indirect
control transfers fail closed. Offsets are relative to MD5 block one.
"""
import argparse
import hashlib
import json
from pathlib import Path

from sdx_file import parse, place
from sdx_patch import manifests, select, validate_patches

ROOT=Path(__file__).resolve().parents[1]
OPCODES={}
for mode, groups in {
    'imp': 'PHP:08 PLP:28 PHA:48 PLA:68 RTS:60 CLC:18 SEC:38 CLI:58 SEI:78 CLV:b8 CLD:d8 SED:f8 TAX:aa TXA:8a TAY:a8 TYA:98 TSX:ba TXS:9a INX:e8 DEX:ca INY:c8 DEY:88 ASL:0a LSR:4a ROL:2a ROR:6a NOP:ea',
    'imm': 'LDA:a9 LDX:a2 LDY:a0 ADC:69 SBC:e9 CMP:c9 CPX:e0 CPY:c0 AND:29 ORA:09 EOR:49',
    'dp': 'LDA:a5 LDX:a6 LDY:a4 STA:85 STX:86 STY:84 ADC:65 SBC:e5 CMP:c5 CPX:e4 CPY:c4 AND:25 ORA:05 EOR:45 BIT:24 INC:e6 DEC:c6 ASL:06 LSR:46 ROL:26 ROR:66',
    'dpx': 'LDA:b5 LDY:b4 STA:95 STY:94 ADC:75 SBC:f5 CMP:d5 AND:35 ORA:15 EOR:55 INC:f6 DEC:d6 ASL:16 LSR:56 ROL:36 ROR:76',
    'dpy': 'LDX:b6 STX:96',
    'abs': 'LDA:ad LDX:ae LDY:ac STA:8d STX:8e STY:8c ADC:6d SBC:ed CMP:cd CPX:ec CPY:cc AND:2d ORA:0d EOR:4d BIT:2c INC:ee DEC:ce ASL:0e LSR:4e ROL:2e ROR:6e JMP:4c JSR:20',
    'absx': 'LDA:bd LDY:bc STA:9d ADC:7d SBC:fd CMP:dd AND:3d ORA:1d EOR:5d INC:fe DEC:de ASL:1e LSR:5e ROL:3e ROR:7e',
    'absy': 'LDA:b9 LDX:be STA:99 ADC:79 SBC:f9 CMP:d9 AND:39 ORA:19 EOR:59',
    'indy': 'LDA:b1 STA:91 ADC:71 SBC:f1 CMP:d1 AND:31 ORA:11 EOR:51',
    'indx': 'LDA:a1 STA:81 ADC:61 SBC:e1 CMP:c1 AND:21 ORA:01 EOR:41',
    'rel': 'BPL:10 BMI:30 BVC:50 BVS:70 BCC:90 BCS:b0 BNE:d0 BEQ:f0',
}.items():
    for group in groups.split():
        mnemonic,opcode=group.split(':')
        OPCODES[int(opcode,16)]=(mnemonic,mode,1 if mode=='imp' else 3 if mode.startswith('abs') else 2)


def audit(raw):
    manifest,module=select(raw,manifests(ROOT/'compat/sdx'))
    assert manifest['id']=='md5-450'
    program=parse(raw)
    validate_patches(program,module)
    abi=json.loads((ROOT/'abi/sdx.json').read_text())
    symbols={name:item['address'] for name,item in abi['guest_services'].items()}
    memory,layout=place(program,0x3000,0xe000,symbols)
    base=layout['blocks'][1]
    end=base+program.blocks[0].size
    imported={value:name for name,value in symbols.items() if name not in ('COMTAB','FILE_P')}
    # Each compression round loads a branch displacement from sixteen entries
    # in block two. Walk every resulting target, not the initial FE placeholder.
    branches={site:list(program.blocks[1].data[0x100+16*i:0x110+16*i])
              for i,site in enumerate((0x49d,0x5c6,0x6f8,0x819))}
    pending=[base,base+0xc0]  # U_SFAIL's cleanup continuation is a data pointer.
    code={}; inline={}; calls=[]; occupied=set(); accesses=[]
    while pending:
        pc=pending.pop()
        if pc in code:continue
        assert base<=pc<end,hex(pc)
        opcode=memory[pc]
        assert opcode in OPCODES,('unknown opcode',hex(pc),hex(opcode))
        name,mode,size=OPCODES[opcode]
        assert not occupied.intersection(range(pc,pc+size)),('overlapping decode',hex(pc))
        occupied.update(range(pc,pc+size))
        code[pc]=(name,mode,size)
        arg=int.from_bytes(memory[pc+1:pc+size],'little')
        after=pc+size
        if name in ('JSR','JMP'):
            if arg in imported:
                symbol=imported[arg]
                calls.append(dict(offset=pc-base,symbol=symbol,tail=name=='JMP'))
                if symbol=='PRINTF':
                    stop=memory.index(0,after,end)
                    text=bytes(memory[after:stop])
                    count=0;i=0
                    while i<len(text):
                        if text[i]==37:
                            i+=1
                            if text[i]!=37:
                                count+=1
                                while chr(text[i]) in '0123456789*':
                                    if text[i]==42:count+=1
                                    i+=1
                        i+=1
                    inline[pc-base]=dict(format_hex=text.hex(),arguments=list(range(stop+1-base,stop+1-base+2*count,2)))
                    after=stop+1+2*count
                if symbol=='U_FAIL':continue
            else:
                pending.append(arg)
            if name=='JMP':continue
        elif name=='RTS':continue
        elif mode=='rel':
            for delta in branches.get(pc-base,[arg]):
                pending.append(after+(delta if delta<128 else delta-256))
        elif mode.startswith('abs') or mode in ('dp','dpx','dpy','indy','indx'):
            accesses.append(dict(offset=pc-base,instruction=name,mode=mode,operand=arg))
        pending.append(after)
    for at,record in inline.items():
        lo=base+at+3
        hi=lo+len(bytes.fromhex(record['format_hex']))+1+2*len(record['arguments'])
        assert not occupied.intersection(range(lo,hi)),('inline data executed',hex(at))
    # All mutable executable bytes are operand bytes, never opcodes.
    mutations=sorted({a['operand']-base for a in accesses
        if a['instruction'] in ('STA','STX','STY','INC','DEC') and a['mode']=='abs'
        and base<=a['operand']<end})
    for at in mutations:
        if at==0x2f2:continue  # PRINTF's first argument word
        assert any(pc<base+at<pc+size for pc,(_,_,size) in code.items()),('opcode write',hex(at))
    assert sorted(r['arguments'][0] for r in inline.values() if r['arguments'] and r['format_hex'] in ('25703a20','25303278'))==[0x1f8,0x2f2]
    # Absolute FFFF reads are precisely the sixteen self-modified message
    # operands. No other instruction accesses an upper hardware/ROM window.
    hardware=[a for a in accesses if a['mode'].startswith('abs') and a['operand']>=0xd000]
    assert len(hardware)==16 and all(a['instruction']=='LDA' and a['operand']==0xffff for a in hardware)
    return dict(status='pass',sha256=hashlib.sha256(raw).hexdigest(),layout=layout,
        instructions=len(code),opcode_bytes=len(occupied),opcodes=sorted({memory[pc] for pc in code}),
        calls=sorted(calls,key=lambda x:x['offset']),inline=inline,
        self_modifying_operands=mutations,dynamic_branches=branches,
        accesses=accesses,
        instruction_offsets=sorted(pc-base for pc in code),
        direct_page_arguments=[0x1f8,0x2f2],
        notes=['No indirect control transfers or undocumented opcodes.',
               'MEMLO/MEMTOP and SDMCTL use private guest-bank storage.',
               'Direct-page indexed accesses wrap in E=1; indirect buffer pointer is B8.',
               'The /H path reads private RTCLOK and is rejected by parsed U_SLASH before entry.',
               'The only SEI is compression offset 041A, patched to NOP.',
               'Cleanup handler at 00C0 preserves error in X across FCLOSEAL and tail-calls U_FAIL.'])


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('binary',type=Path)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    result=audit(args.binary.read_bytes())
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+'\n')
    print('MD5 audit:',result['instructions'],'reachable instructions')
