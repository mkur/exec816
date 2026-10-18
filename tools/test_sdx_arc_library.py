#!/usr/bin/env python3
"""Original SDX controls for ARC's __MISC and partial MUL_32 entry."""
import argparse,json,struct,time
from pathlib import Path
from native_program import ROOT,verify_machine
from os_boundary import emulator
from sdfs_reference import make
from sdx_fixtures import stream
from test_sdx_md5 import PIN


def probe():
    code=bytearray();imports={}
    def emit(hex):code.extend(bytes.fromhex(hex))
    def ref(op,name,addend=0):
        code.append(op);imports.setdefault(name,[]).append(len(code));code.extend(struct.pack('<H',addend))
    emit('a901a25aa0a6');ref(0x20,'__MISC');emit('8d00058e01058c020508688d0305')
    cases=[(3,7),(25,0x010203),(255,0xffffff)]
    for index,(left,right) in enumerate(cases):
        for offset,value in enumerate(bytes([left,0x79,0x35,0x91])+right.to_bytes(4,'big')):
            emit(f'a9{value:02x}');ref(0x8d,'COMTAB',0xff+offset)
        emit('a008');ref(0x20,'MUL_32',2)
        for op,offset in [(0x8d,0),(0x8e,1),(0x8c,2)]:
            code.append(op);code.extend(struct.pack('<H',0x530+index*4+offset))
        emit('0868');code.append(0x8d);code.extend(struct.pack('<H',0x533+index*4))
        for offset in range(4):
            ref(0xad,'COMTAB',0x107+offset);code.append(0x8d);code.extend(struct.pack('<H',0x510+index*4+offset))
    emit('4c0060')
    wire=bytearray(struct.pack('<HBBHH',0xfffe,1,0,0,len(code))+code)
    for name,sites in imports.items():
        fix=stream(sites);wire+=struct.pack('<H8sH',0xfffb,name.encode().ljust(8,b' '),len(fix))+fix
    return bytes(wire),cases


def run(out):
    wire,cases=probe();source=out/'source';source.mkdir(exist_ok=True)
    (source/'PROBE.COM').write_bytes(wire)
    (source/'AUTOEXEC.BAT').write_bytes(b'PROBE.COM\x9b')
    (source/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
    make(out/'input.atr',source,1024,256,'ARCLIB')
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        b.config('diskemu','fastest');machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        b.mount(0,str(out/'input.atr'));b.bp_set(0x6000);b.boot(str(ROOT/'build/sdx-inputs/md5/SDX450_maxflash1.car'));b.resume()
        deadline=time.monotonic()+120
        while time.monotonic()<deadline:
            if int(b.regs()['PC'].lstrip('$'),16)==0x6000:break
            time.sleep(.05)
        else:raise RuntimeError('Original library probe timed out')
        b.pause();mem=b.memdump(0,65536);(out/'memory.bin').write_bytes(mem)
    misc=list(mem[0x500:0x504]);products=[int.from_bytes(mem[0x510+4*i:0x514+4*i],'big') for i in range(len(cases))]
    assert misc[:3]==[0x9a,0xfe,0x9b],misc
    assert products==[a*b for a,b in cases],products
    return dict(status='pass',tier='development',misc=misc,partial_multiply=[dict(left=a,right=b,product=c) for (a,b),c in zip(cases,products)],machine=machine,pin=PIN,multiply_registers=[list(mem[0x530+4*i:0x534+4*i]) for i in range(len(cases))])

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=run(out);(out/'results.json').write_text(json.dumps(result,indent=2)+'\n');print('ARC library controls pass')
