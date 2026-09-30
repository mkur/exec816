"""Target-executed far transfers for tests with the pinned 16-bit bridge API.

Only call at a paused bank-zero E=1 bootstrap/probe entry. The helper preserves
the live OS stack and registers and returns to that exact entry. $8100-$86FF
and $9000-$AFFF are scratch in these isolated cold-launch fixtures, never part
of a production loader or an application-visible memory API.
"""
from pathlib import Path
import struct
from native_program import command, require
from os_boundary import run_to


def transfer(bridge, source, destination, size, output):
    pc = int(bridge.regs()['PC'].lstrip('$'),16)
    require(pc < 65536 and not 0x8100 <= pc < 0x8700,'Far test helper needs a bank-zero caller')
    require(0 < size <= 8192,'Invalid test transfer size')
    require(int.from_bytes(bridge.memdump(0x02e5,2),'little') >= 0xb000,'Test scratch unavailable')
    output = Path(output)/'memory-helper';output.mkdir(parents=True,exist_ok=True)
    source_text = f'''.setcpu "65816"
.segment "CODE"
.export start,done
start:
    php
    pha
    phx
    phy
    phb
    phk
    plb
loop:
read:
    lda f:${source:06x}
write:
    sta f:${destination:06x}
    inc read+1
    bne :+
    inc read+2
    bne :+
    inc read+3
:
    inc write+1
    bne :+
    inc write+2
    bne :+
    inc write+3
:
    lda count
    bne :+
    dec count+1
:
    dec count
    lda count
    ora count+1
    bne loop
    plb
    ply
    plx
    pla
    plp
done:
    jmp done
count: .word {size}
'''
    (output/'helper.s').write_text(source_text)
    (output/'helper.cfg').write_text('MEMORY { RAM: start=$8100,size=$600,file=%O; } '
                                   'SEGMENTS { CODE: load=RAM,type=ro; }\n')
    command(['ca65','-o',output/'helper.o',output/'helper.s'])
    command(['ld65','-C',output/'helper.cfg','-o',output/'helper.bin','-Ln',output/'helper.lbl',output/'helper.o'])
    labels = {s.split()[2].lstrip('.'):int(s.split()[1],16) for s in (output/'helper.lbl').read_text().splitlines()}
    old = bridge.memdump(pc,3)
    bridge.memload(labels['start'],(output/'helper.bin').read_bytes())
    bridge.memload(pc,b'\x4c'+struct.pack('<H',labels['start']))
    bridge.bp_clear_all();bridge.bp_set(labels['done']);run_to(bridge,labels['done'])
    bridge.memload(pc,old)
    bridge.memload(labels['done'],b'\x4c'+struct.pack('<H',pc))
    bridge.bp_clear_all();bridge.bp_set(pc);run_to(bridge,pc)


def write(bridge, address, data, output):
    if address + len(data) <= 65536:
        bridge.memload(address,data)
        return
    for offset in range(0,len(data),8192):
        chunk = data[offset:offset+8192]
        bridge.memload(0x9000,chunk)
        transfer(bridge,0x9000,address+offset,len(chunk),output)


def read(bridge, address, size, output):
    if address + size <= 65536:
        return bridge.memdump(address,size)
    result = bytearray()
    for offset in range(0,size,8192):
        n = min(size-offset,8192)
        transfer(bridge,address+offset,0x9000,n,output)
        result += bridge.memdump(0x9000,n)
    return bytes(result)
