"""Independent bounded ARC fixture writer/reader; never executes guest code."""
import struct

DATE=(46<<9)|(10<<5)|18
TIME=(14<<11)|(32<<5)|7


def crc16(raw):
    crc=0
    for value in raw:
        crc^=value
        for _ in range(8):crc=(crc>>1)^(0xa001 if crc&1 else 0)
    return crc


def member(name,raw,method=2,packed=None,checksum=None):
    if packed is None:packed=raw
    if checksum is None:checksum=sum(raw)&65535 if method==15 else crc16(raw)
    header=b'\x1a'+bytes([method])+name.encode().ljust(13,b'\0')
    header+=struct.pack('<IHHH',len(packed),DATE,TIME,checksum)
    if method!=1:header+=struct.pack('<I',len(raw))
    return header+packed


def bits(codes,width=9,msb=False):
    bitlist=[]
    for code in codes:
        bitlist.extend((code>>i)&1 for i in (range(width-1,-1,-1) if msb else range(width)))
    bitlist += [0]*(-len(bitlist)%8)
    return bytes(sum(bitlist[n+i]<<(7-i if msb else i) for i in range(8)) for n in range(0,len(bitlist),8))


def codec_corpus():
    files={'OLD.BIN':b'old','EMPTY.BIN':b'','BINARY.BIN':bytes(range(256)),
           'RLE.BIN':b'A'*8,'HUFF.BIN':b'A'*8,'LZW.BIN':b'abc','SDX.BIN':b'abc'}
    tree=struct.pack('<Hhhhhhh',3,1,2,-66,-145,-9,-257)+bits([0,0,0,1,1,0,1,1],1)
    packed=[member('OLD.BIN',files['OLD.BIN'],1),member('EMPTY.BIN',b''),member('BINARY.BIN',files['BINARY.BIN']),
            member('RLE.BIN',files['RLE.BIN'],3,b'A\x90\x08'),member('HUFF.BIN',files['HUFF.BIN'],4,tree),
            member('LZW.BIN',b'abc',8,b'\x0c'+bits(b'abc')),
            member('SDX.BIN',b'abc',15,bits([256,97,98,99,257],msb=True))]
    return b''.join(packed)+b'\x1a\0',files


def rle(raw,limit):
    result=bytearray();escape=False
    for value in raw:
        if escape:
            if value==0:result.append(0x90)
            else:
                if not result:raise ValueError('RLE without prior byte')
                result.extend(result[-1:]*(value-1))
            escape=False
        elif value==0x90:escape=True
        else:result.append(value)
        if len(result)>limit:raise ValueError('Expanded beyond header size')
    if escape:raise ValueError('Truncated RLE')
    return bytes(result)


def huffman(raw,limit):
    nodes=struct.unpack_from('<H',raw)[0]
    if not 0<nodes<=256:raise ValueError('Invalid tree size')
    tree=[struct.unpack_from('<hh',raw,2+4*i) for i in range(nodes)]
    data=raw[2+4*nodes:];result=bytearray();node=0
    for value in data:
        for shift in range(8):
            node=tree[node][(value>>shift)&1]
            if node<0:
                symbol=-node-1
                if symbol==256:return rle(result,limit)
                if symbol>255:raise ValueError('Invalid leaf')
                result.append(symbol);node=0
            elif node>=nodes:raise ValueError('Invalid branch')
    raise ValueError('Missing tree terminator')


def lzw(raw,limit,sdx=False):
    if not sdx:
        if raw[:1]!=b'\x0c':raise ValueError('Unsupported width')
        raw=raw[1:]
    # ARC groups eight codes at a fixed width, padding at width changes/clear.
    # SDX method 15 packs an uninterrupted MSB-first stream with explicit EOF.
    pos=0;width=9;group_start=0;next_code=258 if sdx else 257;previous=None
    table={i:bytes([i]) for i in range(256)};result=bytearray()
    def take(n):
        nonlocal pos
        if pos+n>len(raw)*8:return None
        value=0
        for shift in range(n):
            bit=(raw[pos//8]>>(7-pos%8 if sdx else pos%8))&1
            value=(value<<1)|bit if sdx else value|(bit<<shift)
            pos+=1
        return value
    while True:
        if next_code>=(1<<width) and width<12:
            if not sdx:pos=group_start+((pos-group_start+width*8-1)//(width*8))*(width*8)
            width+=1;group_start=pos
        code=take(width)
        if code is None:
            if sdx:raise ValueError('Missing SDX terminator')
            break
        if code==256:
            if not sdx:pos=group_start+((pos-group_start+width*8-1)//(width*8))*(width*8)
            width=9;group_start=pos;table={i:bytes([i]) for i in range(256)}
            next_code=258 if sdx else 257;previous=None;continue
        if sdx and code==257:break
        if code in table:entry=table[code]
        elif code==next_code and previous is not None:entry=previous+previous[:1]
        else:raise ValueError('Invalid dictionary reference')
        result.extend(entry)
        if len(result)>limit*2+16:raise ValueError('LZW expansion limit')
        if previous is not None and next_code<4096:
            table[next_code]=previous+entry[:1];next_code+=1
        previous=entry
    return bytes(result) if sdx else rle(result,limit)


def read(raw):
    at=0;files={};entries=[]
    while True:
        if raw[at:at+1]!=b'\x1a' or at+2>len(raw):raise ValueError('Missing ARC marker')
        method=raw[at+1];at+=2
        if method==0:
            if at!=len(raw):raise ValueError('Trailing archive data')
            return files,entries
        header=23 if method==1 else 27
        if at+header>len(raw):raise ValueError('Truncated header')
        name=raw[at:at+13].split(b'\0')[0].decode('ascii')
        packed,date,time,check=struct.unpack_from('<IHHH',raw,at+13)
        size=packed if method==1 else struct.unpack_from('<I',raw,at+23)[0]
        at+=header;data=raw[at:at+packed];at+=packed
        if len(data)!=packed:raise ValueError('Truncated payload')
        if method in [1,2]:value=data
        elif method==3:value=rle(data,size)
        elif method==4:value=huffman(data,size)
        elif method in [8,15]:value=lzw(data,size,method==15)
        else:raise ValueError('Unsupported method '+str(method))
        if len(value)!=size or (sum(value)&65535 if method==15 else crc16(value))!=check:raise ValueError('Size/checksum mismatch')
        if name in files:raise ValueError('Duplicate member')
        files[name]=value;entries.append(dict(name=name,method=method,packed=packed,size=size,date=date,time=time,checksum=check))


def creation_corpus():
    import random
    rng=random.Random(816)
    return {'EMPTY.BIN':b'', 'BINARY.BIN':bytes(range(256)), 'REPEAT.BIN':b'A'*600,
            'TEXT.BIN':b'Exec816 private banks and preemptive tasks. '*160,
            'SKEW.BIN':bytes(rng.choices(range(16),weights=[40]+[1]*15,k=4096))}
