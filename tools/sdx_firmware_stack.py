"""Scoped XLOS GR.0 E: output stack walk, including native scrolling.

Both branch arms are explored except the reviewed DINDEX=0 mode admission.
Computed E: control dispatch admits the pinned 16 ordinary/four cursor entries.
Unknown code, stack effects and transfers fail closed. No third-party handlers.
"""
from pathlib import Path
from sdx_md5_audit import OPCODES as BASE
from generate_sdx_firmware import identify

DEC = {**BASE,
    0x80: ('BRA','rel',2), 0xda: ('PHX','imp',1),
    0x5a: ('PHY','imp',1), 0xfa: ('PLX','imp',1),
    0x7a: ('PLY','imp',1), 0x64: ('STZ','dp',2),
    0x9c: ('STZ','abs',3), 0x1a: ('INC','imp',1),
    0x3a: ('DEC','imp',1), 0x89: ('BIT','imm',2),
    0x6c: ('JMP','ind',3), 0xb2: ('LDA','inddp',2),
    0x92: ('STA','inddp',2), 0xfc: ('JSR','absix',3),
    0x8f: ('STA','long',4), 0xaf: ('LDA','long',4),
    0x9f: ('STA','longx',4), 0xbf: ('LDA','longx',4)}
DEC.update({147: ('STA', 'stacky', 2),
 179: ('LDA', 'stacky', 2),
 123: ('TDC', 'imp', 1),
 91: ('TCD', 'imp', 1),
 163: ('LDA', 'stack', 2),
 131: ('STA', 'stack', 2),
 59: ('TSC', 'imp', 1),
 27: ('TCS', 'imp', 1),
 18: ('ORA', 'inddp', 2),
 50: ('AND', 'inddp', 2),
 82: ('EOR', 'inddp', 2),
 114: ('ADC', 'inddp', 2),
 210: ('CMP', 'inddp', 2),
 242: ('SBC', 'inddp', 2),
 203: ('WAI', 'imp', 1),
 12: ('TSB', 'abs', 3),
 28: ('TRB', 'abs', 3),
 4: ('TSB', 'dp', 2),
 20: ('TRB', 'dp', 2),
 251: ('XCE', 'imp', 1),
 194: ('REP', 'imm8', 2),
 226: ('SEP', 'imm8', 2),
 235: ('XBA', 'imp', 1),
 139: ('PHB', 'imp', 1),
 171: ('PLB', 'imp', 1),
 11: ('PHD', 'imp', 1),
 43: ('PLD', 'imp', 1),
 244: ('PEA', 'word', 3),
 84: ('MVN', 'banks', 3),
 68: ('MVP', 'banks', 3),
 124: ('JMP', 'absix', 3),
 116: ('STZ', 'dpx', 2),
 158: ('STZ', 'absx', 3)})

def editor_bound(path):
    profile=identify(path.read_bytes())
    if not profile["name"].startswith("xlos-"):raise ValueError("Use the AltirraOS source audit for this ROM")
    mem=bytes(0xc000)+path.read_bytes();root=int.from_bytes(mem[0xe406:0xe408],'little')+1
    q=[(root,((2,'r',-1),),(),1,1,1,None)];seen=set();peak=(0,());natives=0
    while q:
        pc,st,chain,m,x,e,c=q.pop()
        key=pc,st,m,x,e,c
        if key in seen:continue
        seen.add(key);depth=sum(v[0] for v in st)-2
        if depth>peak[0]:peak=(depth,chain+(pc,))
        if depth>70 or len(seen)>2000000:raise Exception('limit',depth,len(seen),[hex(x) for x in chain])
        if pc<0:continue
        if not 0xc000<=pc<=0xffff:raise Exception('out',hex(pc),st,[hex(x) for x in chain])
        if mem[pc] not in DEC:raise Exception('opcode',hex(pc),hex(mem[pc]),st,[hex(x) for x in chain])
        op,mode,size=DEC[mem[pc]]
        if mode=='imm' and ((op in ('LDX','LDY','CPX','CPY') and not x) or (op not in ('LDX','LDY','CPX','CPY') and not m)):size+=1
        arg=int.from_bytes(mem[pc+1:pc+size],'little');n=pc+size
        def queue(target,stack=st,path=chain):q.append((target,stack,path,m,x,e,c))
        if op in ('TXS','TCS','RTI','RTL','COP','BRK','JSL'):
            raise RuntimeError(('Unreviewed stack/control operation',hex(pc),op))
        if op=='RTS':
            if not st or st[-1][1]!='r':raise Exception('rts',hex(pc),st,[hex(x) for x in chain])
            if st[-1][2]>=0:queue(st[-1][2],st[:-1],chain[:-1])
            continue
        if op=='PHA':st+=((1 if m else 2,'v'),)
        if op in ('PHX','PHY'):st+=((1 if x else 2,'v'),)
        if op in ('PHB','PHD','PEA'):st+=((1 if op=='PHB' else 2,'v'),)
        if op=='PHP':st+=((1,'p',m,x,c),)
        if op in ('PLA','PLX','PLY','PLB','PLD','PLP'):
            if not st:raise Exception('pop',hex(pc))
            v=st[-1];st=st[:-1]
            want={'PLA':1 if m else 2,'PLX':1 if x else 2,'PLY':1 if x else 2,'PLB':1,'PLD':2,'PLP':1}[op]
            if v[0]==2 and want==1:
                st+=((1,'half',*v[2:]),)
            elif v[0]!=want:raise Exception('width',hex(pc),v,want)
            if op=='PLP':
                if v[1]!='p':raise Exception('plp',hex(pc),v)
                m,x,c=v[2:]
        if op in ('REP','SEP'):
            if arg&0x20:m=int(op=='SEP')
            if arg&0x10:x=int(op=='SEP')
            if arg&1:c=int(op=='SEP')
        if op=='CLC':c=0
        elif op=='SEC':c=1
        elif op=='XCE':
            if c is None:raise Exception('xce',hex(pc))
            e,c=c,e
            if e:m=x=1
            else:natives+=1
        elif op in ('ADC','SBC','CMP','CPX','CPY','ASL','LSR','ROL','ROR'):c=None
        if pc==0xf48a:queue(0xf48f,st);continue
        if op in ('JSR','JMP'):
            if mode=='absix' and pc==0xf1d1:
                # E: control table has 16 ordinary entries and four shifted cursor entries.
                for i in range(20):queue(int.from_bytes(mem[0xf898+i*3:0xf89a+i*3],'little'),st+((2,'r',n),),chain+(pc,))
                continue
            if mode!='abs':raise Exception('ind',hex(pc),hex(arg),[hex(x) for x in chain])
            if op=='JSR':st+=((2,'r',n),);chain+=(pc,)
            queue(arg,st,chain);continue
        if mode=='rel':
            queue(n+(arg if arg<128 else arg-256),st)
            if op=='BRA':continue
        queue(n,st)
    return dict(profile=profile['name'],body_bytes=peak[0],states=len(seen),native_transition_states=natives,peak_path=[hex(x) for x in peak[1]])

def support_bound(path):
    """Compose the reviewed stock-ROM chain, excluding third-party callbacks.

    Public CIO saves DBR/D (3), calls its dispatcher (2), then E75A (2)
    and E766 (2). PEI/RTS synthesizes a handler call (temporary 2). The
    maximum retained dispatch prefix is 9; the admitted 13 allows four more
    bytes for non-handler bookkeeping/error paths. Caller saved S plus the
    bank-zero JSR cost 4. The editor walk excludes its already-counted RTS.

    Native XLOS IRQ adds 11 below its synthetic frame. The shared outer
    IRQ frame (19) plus stock dispatcher/leaf saves (at most 9) is 39;
    the existing 48-byte IRQ envelope covers both this and owned native IRQs.
    Emulation NMI saves A/X/Y (3), with one stock nested call/save (3).
    The bridge's complete frame (13) and synthetic emulation return (3)
    give the existing 22-byte nested-VBI envelope. Deeper NMI only acknowledges.
    """
    profile = identify(path.read_bytes())
    editor = editor_bound(path)
    mem = bytes(0xc000)+path.read_bytes()
    if mem[0xe4d5:0xe4e2] != bytes.fromhex('8b0b2028c62022e52babc00060'):
        raise ValueError('Unreviewed CIO public wrapper')
    if mem[0xe75a:0xe769] != bytes.fromhex('a092a62e2066e78423c00060d42c60'):
        raise ValueError('Unreviewed CIO handler trampoline')
    if mem[0xc018:0xc029] != bytes.fromhex('2c0fd410036c000248da5a8d0fd46c2202'):
        raise ValueError('Unreviewed emulation NMI prefix')
    parts = profile['stack']
    if parts['editor_body'] != editor['body_bytes']:
        raise ValueError('Editor depth differs from the firmware contract')
    total = sum(parts.values())
    if total > 128:
        raise ValueError('Firmware exceeds shared ROM reserve')
    return dict(status='pass', profile=profile['name'], editor=editor,
                components=parts, peak_bytes=total, reserve=128,
                minimum_anchor=0x190, headroom=128-total,
                assumptions=['IOCB0 PUT CHARACTERS to the stock GR.0 E: handler',
                             'DINDEX=0, stock ROM/Exec vectors, no third-party handlers',
                             'Native SIO excludes ROM serial service while owned',
                             'One nested ROM VBI; deeper NMI acknowledges only'])
