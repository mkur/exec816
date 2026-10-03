"""Independent snapshot-copy oracle and fixed emitted-code inputs for B3."""
import struct


def corpus():
    cases=[]
    def add(name,base=0x3f000,ss=None,ds=None,xy=(0,0,0,0,64,20),status=0,fault=0):
        ss=ss or (base+32,80,128,60);ds=ds or ss
        before=bytes((i*37+(i>>8)*11)&255 for i in range(8192));after=bytearray(before)
        sx,sy,dx,dy,width,height=xy
        if status==0 or fault:
            rows=range(height)
            if fault:
                down=ds[0]+dy*ds[1]+dx//2>ss[0]+sy*ss[1]+sx//2
                rows=range(height-16,height) if down else range(16)
            for row in rows:
                source=ss[0]-base+(sy+row)*ss[1]+sx//2
                dest=ds[0]-base+(dy+row)*ds[1]+dx//2
                after[dest:dest+width//2]=before[source:source+width//2]
        h=2166136261
        for byte in after:h=((h^byte)*16777619)&0xffffffff
        packet=struct.pack('<IHHHIHHH6H',*ss,*ds,*xy)
        cases.append(dict(name=name,base=base,packet=packet.hex(),status=status,fault=fault,hash=h))
    add('up',xy=(0,8,0,0,128,50));add('down',xy=(0,0,0,8,128,50))
    add('left',xy=(8,0,0,0,120,40));add('right',xy=(0,0,8,0,120,40))
    add('down-right',xy=(0,0,8,3,120,40));add('up-left',xy=(8,3,0,0,120,40))
    add('same');add('height-one',xy=(0,0,2,0,126,1))
    add('page-crossing',base=0xfe0);add('bank-crossing',base=0xffe0)
    add('last-vram-byte',base=0x7e000,ss=(0x7e000,128,256,64),xy=(0,62,0,63,256,1))
    add('distinct-pitches',ss=(0x3f020,64,120,30),ds=(0x40000,80,128,30))
    add('shifted-overlapping-views',ss=(0x3f020,80,128,50),ds=(0x3f033,80,128,50))
    add('zero-width',xy=(0,0,0,0,0,20));add('zero-height',xy=(0,0,0,0,64,0))
    for name,xy in [('odd-source',(1,0,0,0,64,20)),('odd-dest',(0,0,1,0,64,20)),
                    ('odd-width',(0,0,0,0,63,20)),('bad-right',(64,0,0,0,66,20)),
                    ('bad-bottom',(0,50,0,0,64,20)),('overflow',(65534,65535,0,0,64,20))]:
        add(name,xy=xy,status=6)
    for name,s in [('zero-pitch',(0x3f020,0,128,60)),('large-pitch',(0x3f020,4096,128,1)),
                   ('narrow-pitch',(0x3f020,32,128,60)),('vram-wrap',(0x7ffff,80,128,60)),
                   ('arena',(0x38000,80,128,60)),('address-overflow',(0xffffffff,80,128,60))]:
        add(name,ss=s,status=6)
    add('overlapping-different-pitches',ds=(0x3f020,81,128,60),status=6)
    add('fault-after-up-chunk',xy=(0,8,0,0,128,50),status=5,fault=1)
    add('fault-after-down-chunk',xy=(0,0,0,8,128,50),status=5,fault=1)
    return cases


def header():
    out='/* Generated test inputs and snapshot-model FNV hashes. */\n'
    out+='struct CopyCase { ULONG base; UBYTE packet[32]; UWORD status,fault; ULONG hash; };\n'
    out+='static const struct CopyCase copyCases[]={\n'
    for c in corpus():
        packet=','.join(str(b) for b in bytes.fromhex(c['packet']))
        out+=f'    {{{c["base"]}UL,{{{packet}}},{c["status"]},{c["fault"]},{c["hash"]}UL}}, /* {c["name"]} */\n'
    return out+'};\n'
