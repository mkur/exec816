"""Physical SEROUT write guard for bounded IDE-only development sessions."""
from native_program import require


def install(bridge):
    clear=bridge.bp_clear_all
    registers=bridge.regs
    observation=dict(address=0xd20d,writes=0,scope='boot entry through kernel EXIT')

    def reset():
        result=clear()
        bridge.watch_set(0xd20d,'w')
        return result

    def checked_registers():
        result=registers()
        pc=bridge.eval_expr('@xpc')
        # Access breakpoints stop after the store. The firmware uses absolute
        # stores; native platform accesses also allow absolute-long stores.
        code=bridge.memdump((pc-4)&0xffffff,4)
        store=code[1:] in (b'\x8d\x0d\xd2',b'\x8c\x0d\xd2',
                           b'\x8e\x0d\xd2',b'\x9c\x0d\xd2')
        store=store or code==b'\x8f\x0d\xd2\x00'
        if store:
            observation['writes']+=1
            require(False,'Physical SIO SEROUT write during IDE-only session')
        return result

    bridge.bp_clear_all=reset
    bridge.regs=checked_registers
    reset()
    return observation
