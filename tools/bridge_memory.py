"""24-bit test memory access over the pinned bridge's 16-bit transfer API.

Reads use the debugger expression evaluator. Far writes are test stimuli at a
paused bank-zero bootstrap or IRQ-masked rendezvous, never a production API.
A short target trampoline borrows profile-defined test scratch and leaves A/P, the
stack pointer, D, DBR and X/Y unchanged. It uses up to three stack bytes. NMI is
masked for the transfer, so these writes are not interrupt qualification runs.
"""
import struct
import adapter_state as adapter


def install(bridge):
    base = adapter.TEST_FAR_WRITE
    capacity = adapter.TEST_FAR_WRITE_BYTES
    near_dump, near_load = bridge.memdump, bridge.memload
    near_peek, near_peek16 = bridge.peek, bridge.peek16
    near_poke, near_poke16 = bridge.poke, bridge.poke16

    def read(address, size):
        if not 0 <= address <= address+size <= 0x1000000:
            raise ValueError('Invalid 24-bit test read')
        if address+size <= 65536:
            return near_dump(address,size) if size else b''
        return b''.join((bridge.eval_expr(f'dw(${address+i:x})') & 65535).to_bytes(2,'little')
                        for i in range(0,size-1,2)) + (
            bytes([bridge.eval_expr(f'db(${address+size-1:x})') & 255]) if size%2 else b'')

    def write(address, payload):
        from os_boundary import run_to, require
        payload = bytes(payload)
        require(0 <= address <= address+len(payload) <= 0x1000000, 'Invalid 24-bit test write')
        if address+len(payload) <= 65536:
            return near_load(address,payload)
        regs = bridge.regs()
        pc = bridge.eval_expr('@xpc')
        flags = int(regs['P'].lstrip('$'),16)
        require(regs['mode'] == '65C816' and adapter.RESIDENT_BASE <= pc < 0x8000 and
                (pc+3 <= base or pc >= base+capacity),
                'Far write requires a paused bank-zero bootstrap/adapter rendezvous')
        require(flags & 4 or flags & 0x30 == 0x30,
                'Far write requires masked IRQs or an emulation bootstrap')
        nmien = int(bridge.antic()['NMIEN'].lstrip('$'),16)
        original_entry = near_dump(pc,3)
        scratch = near_dump(base,capacity)
        bridge.hwpoke(0xd40e,0)
        try:
            for offset in range(0,len(payload),32):
                # REP is harmless in E=1; in E=0 it preserves the full B:A.
                code = bytearray([0x08,0x78,0xc2,0x20,0x48,0xe2,0x20])
                for i,value in enumerate(payload[offset:offset+32]):
                    code += bytes([0xa9,value,0x8f])+(address+offset+i).to_bytes(3,'little')
                code += bytes([0xc2,0x20,0x68,0x28])
                done = base+len(code)
                code += b'\x4c'+struct.pack('<H',done)
                require(len(code) <= capacity, 'Far-write trampoline exceeds scratch')
                near_load(base,code)
                near_load(pc,b'\x4c'+struct.pack('<H',base))
                stop = bridge.bp_set(done)
                try:
                    run_to(bridge,done,frame_limit=10,timeout=5)
                finally:
                    bridge.bp_clear(stop)
                near_load(pc,original_entry)
                near_load(done,b'\x4c'+struct.pack('<H',pc))
                back = bridge.bp_set(pc)
                try:
                    run_to(bridge,pc,frame_limit=10,timeout=5)
                finally:
                    bridge.bp_clear(back)
        finally:
            near_load(pc,original_entry)
            near_load(base,scratch)
            bridge.hwpoke(0xd40e,nmien)
        return dict(ok=True,addr=f'${address:x}',length=len(payload))

    bridge.memdump = read
    bridge.memload = write
    bridge.peek = lambda a,n=1: near_peek(a,n) if a+n <= 65536 else read(a,n)
    bridge.peek16 = lambda a: near_peek16(a) if a+2 <= 65536 else int.from_bytes(read(a,2),'little')
    bridge.poke = lambda a,v: near_poke(a,v) if a < 65536 else write(a,bytes([v & 255]))
    bridge.poke16 = lambda a,v: near_poke16(a,v) if a+2 <= 65536 else write(a,struct.pack('<H',v & 65535))
