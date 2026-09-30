"""Independent ABI oracle and emitted field writes, reads and array-stride probes."""
from generate_dos import ABI
# name, native type, offset, value (or bytes). Independent of abi/dos.json.
DATE=[('ds_Days','LONGINT',0,0xffffffff),('ds_Minute','LONGINT',4,70000),('ds_Tick','LONGINT',8,0x80000000)]
INFO=[('fib_DiskKey','LONGINT',0,0x87654321),('fib_DirEntryType','LONGINT',4,0xfffffffd),
      ('fib_FileName','ARRAY',8,bytes(range(108))),('fib_Protection','LONGINT',116,5),
      ('fib_EntryType','LONGINT',120,2),('fib_Size','LONGINT',124,70001),('fib_NumBlocks','LONGINT',128,65535)]+[
      ('fib_Date.'+f,k,132+o,v) for f,k,o,v in DATE]+[
      ('fib_Comment','ARRAY',144,bytes(range(80))),('fib_OwnerUID','CARD',224,65535),('fib_OwnerGID','CARD',226,32768),('fib_Reserved','ARRAY',228,bytes(range(32)))]
PACKET=[('dp_Link','EXEC.Message POINTER',0,0x070000),('dp_Port','EXEC.MsgPort POINTER',3,0x090000),
        ('dp_Type','LONGINT',6,1008),('dp_Res1','LONGINT',10,0xffffffff),('dp_Res2','LONGINT',14,70002)]+[
        (f'dp_Arg{i}','LONGINT',14+i*4,v) for i,v in enumerate([0,0xffffff,0x1000000,0xffff0000,0x80000000,0x7fffffff,0x12345678],1)]
MSG=[('mn_Node.ln_Succ','EXECLISTS.Node POINTER',0,0x050000),('mn_Node.ln_Pred','EXECLISTS.Node POINTER',3,0x0dffff),('mn_Node.ln_Type','BYTE',6,5),('mn_Node.ln_Pri','BYTE',7,255),('mn_Node.ln_Name','BYTE POINTER',8,0x0c0000),('mn_ReplyPort','EXEC.MsgPort POINTER',11,0x090000),('mn_Length','CARD',14,62)]
STANDARD=[('sp_Msg.'+f,k,o,v) for f,k,o,v in MSG]+[('sp_Pkt.'+f,k,16+o,v) for f,k,o,v in PACKET]
FIXTURES=[('DateStamp',0x8fff8,12,DATE),('FileInfoBlock',0x6fff0,260,INFO),('DosPacket',0x9fff8,46,PACKET),('StandardPacket',0xbfff0,62,STANDARD)]
WIDTH={'LONGINT':4,'CARD':2,'BYTE':1}

def generate(output):
    declarations=[];routines=[];calls=[];facts=[];fact_index=0
    for number,(name,address,size,fields) in enumerate(FIXTURES):
        kind='DOS.'+name if number<2 else name
        array='records'+str(number);declarations.append(f'{kind} ARRAY {array}(2)')
        layout=[(f'ADDRESS(@{array}(1))-ADDRESS(@{array}(0))',size)]+[(f'ADDRESS(@{array}(0).{f})-ADDRESS(@{array}(0))',o) for f,_,o in ABI['records'][name]['fields']]
        for part in range(0,len(layout),4):
            label=f'Layout{number}Part{part}';calls.append(label+'(0)');lines=['PROC '+label+'(BYTE unused)']
            for expr,value in layout[part:part+4]:
                lines.append(f'  facts({fact_index})=CARD({expr})');facts.append(value);fact_index+=1
            routines.append('\n'.join(lines+['RETURN']))
        for part in range(0,len(fields),3):
            label=f'Field{number}Part{part}';calls.append(label+'(0)')
            lines=['PROC '+label+'(BYTE unused)',f'  {kind} POINTER item','  CARD i',f'  item={kind} POINTER(${address:x})']
            for field,typ,offset,value in fields[part:part+3]:
                if typ=='ARRAY':
                    lines+=[f'  FOR i=0 TO {len(value)-1} DO item.{field}(i)=BYTE(i) OD',f'  FOR i=0 TO {len(value)-1} DO Require(item.{field}(i)=BYTE(i)) OD']
                else:
                    literal=f'{typ}(${value:x})'
                    lines += [f'  item.{field}={literal}',f'  Require(item.{field}={literal})']
            routines.append('\n'.join(lines+['RETURN']))
    declarations.append(f'CARD ARRAY facts({len(facts)})')
    text='\n'.join(declarations+routines)+ '\nPROC Fields()\n  '+'\n  '.join(calls)+'\nRETURN\n'
    (output/'dos-abi-fields.inc').write_text(text)
    return facts

def buffers():
    result=[]
    for name,address,size,fields in FIXTURES:
        buf=bytearray([0xa5]*(size+32))
        for _,kind,offset,value in fields:
            raw=value if kind=='ARRAY' else value.to_bytes(3 if 'POINTER' in kind else WIDTH[kind],'little')
            buf[16+offset:16+offset+len(raw)]=raw
        result.append((address-16,bytes(buf)))
    return result
