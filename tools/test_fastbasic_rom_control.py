#!/usr/bin/env python3
"""Run unmodified FastBasic arithmetic with the actual pinned AltirraOS ROM.

This original XEX runs in the OS environment, without Exec or a math patch.
It controls numeric behavior only, not Exec scheduling or resource ownership.
"""
import argparse
import json
from pathlib import Path
import re

from build_fastbasic import ROOT, PIN, command, sha256, prepare
from native_program import require, verify_machine
from os_boundary import emulator, run_to
from test_sdx_md5 import PIN as MACHINE_PIN
from make_sdfs_fixtures import CAR_SHA
from sdfs_reference import make

SOURCE = '''? "ROM FP CONTROL"
? 1.25+2.5
? SQR(81.0)
DEG
? SIN(90.0)
? INT(ATN(1.0))
? 0.0+VAL("-12.25")
? "CONTROL DONE"
DO
LOOP
'''


def run(output):
    output.mkdir(parents=True,exist_ok=True)
    for name in ('failure.json','failure.png','results.json'):
        (output/name).unlink(missing_ok=True)
    _,source,_,_=prepare(ROOT/'build/fastbasic')
    basic=output/'control.bas'
    basic.write_text(SOURCE)
    assembly=output/'control.asm'
    obj=output/'control.o'
    xex=output/'control.xex'
    with (output/'build.log').open('w') as log:
        command(['make','-j4','build/compiler/fastbasic-fp.lib'],source,log)
        command([source/'build/bin/fastbasic','-target-path:compiler',
            '-syntax-path:src/syntax','-t:atari-fp','-c','-o',assembly,basic],source,log)
        command([source/'build/bin/ca65','-tatari','-I',source/'cc65/asminc',
            '-I',source/'src','-o',obj,assembly],source,log)
        command([source/'build/bin/ld65','-S','0x6000','-C',source/'compiler/fastbasic.cfg',
            '-Ln',output/'control.lbl','-o',xex,obj,
            source/'build/compiler/fastbasic-fp.lib'],source,log)
    rom=ROOT/'build/firmware/altirraos-816.rom'
    cartridge=ROOT/'build/sdx-inputs/md5/SDX450_maxflash1.car'
    require(sha256(cartridge)==CAR_SHA,'Changed original SDX control cartridge')
    media=output/'media'
    media.mkdir(exist_ok=True)
    (media/'CONTROL.COM').write_bytes(xex.read_bytes())
    (media/'AUTOEXEC.BAT').write_bytes(b'D1:CONTROL.COM\x9b')
    (media/'CONFIG.SYS').write_bytes(b'USE OSRAM\x9bDEVICE SPARTA\x9bDEVICE SIO\x9b')
    make(output/'control.atr',media)
    labels={name:int(address,16) for address,name in re.findall(
        r'al ([0-9A-Fa-f]+) \.(\S+)',(output/'control.lbl').read_text())}
    with emulator(ROOT/'build/shell-paced-bridge',rom,output,pin=MACHINE_PIN) as b:
        machine=verify_machine(b,rom,MACHINE_PIN)
        require(not machine['fppatch'],'Original ROM math must run without emulator FP patch')
        # The source's final DO/LOOP is its only bytecode jump. Stop there,
        # after all output, without a marker in cartridge-mapped memory.
        b.bp_set(labels['EXE_JUMP'])
        b.mount(0,str(output/'control.atr'))
        b.boot(str(cartridge))
        try:
            run_to(b,labels['EXE_JUMP'],frame_limit=3000,timeout=60)
        except RuntimeError:
            b.screenshot(str(output/'failure.png'))
            (output/'failure.json').write_text(json.dumps(dict(
                registers=b.regs(),
                screen=b.memdump(b.peek16(88),960).hex(),
                direct_page=b.memdump(0x80,128).hex()),indent=2)+'\n')
            raise
        registers=b.regs()
        cpu={key:registers[key] for key in ('mode','clock_multiplier','shadow_rom')}
        require(cpu==dict(mode=MACHINE_PIN['machine']['cpu'],
            clock_multiplier=MACHINE_PIN['machine']['clock_multiplier'],
            shadow_rom=MACHINE_PIN['machine']['shadow_rom']),
            'Changed original control CPU configuration')
        raw=b.memdump(b.peek16(88),960)
        text=''.join(chr((c&127)+32 if (c&127)<64 else c&127) for c in raw)
        # The OS text device retains its default two-column left margin.
        rows=[text[i:i+40].strip() for i in range(0,960,40)]
        expected=['ROM FP CONTROL','3.75','9','1','45','-12.25','CONTROL DONE']
        start=next((i for i,row in enumerate(rows) if row=='ROM FP CONTROL'),None)
        require(start is not None and rows[start:start+len(expected)]==expected,
                'Original ROM numeric control differs: '+repr(rows))
        b.screenshot(str(output/'screen.png'))
    result=dict(status='pass',tier='development',qualification=False,
        scope='Unmodified FastBasic runtime, real pinned AltirraOS ROM math, no emulator FP patch; no Exec context or physical hardware qualification',
        upstream_revision=PIN['revision'],machine=machine,cpu=cpu,pin=MACHINE_PIN,
        rom_sha256=sha256(rom),xex_sha256=sha256(xex),source_sha256=sha256(basic),
        cartridge_sha256=CAR_SHA,disk_sha256=sha256(output/'control.atr'),
        expected=expected,rows=rows,
        host_compiler_sha256=sha256(source/'build/bin/fastbasic'))
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/fastbasic/fp-rom-control')
    args=parser.parse_args()
    run(args.output.resolve())
    print('Original pinned-ROM FastBasic numeric control passed')
