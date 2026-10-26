#!/usr/bin/env python3
"""Bounded emitted probes for shared physical guest/ROM stack ownership."""
import argparse
from sdx_test_firmware import select as select_firmware, configure as configure_firmware
import json
from pathlib import Path

from native_program import ROOT, build, compiler, require, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def fixture(out, anchor, deep=False, lease_case=False):
    source=out/'resident-stack.act'
    source.write_text('''MODULE RESIDENTSTACKTEST
USE EXEC
USE EXECTASKS
USE EXECOS
USE SDXABI
USE HEAPCORE

CARD checks
BYTE ARRAY message=[83 68 88 155]

PROC Require(BYTE okay)

  IF okay=0 THEN
    HEAPCORE.Abort($fa00+checks)
  FI
  checks==+1

RETURN

PROC Word(BYTE POINTER bytes CARD value)

  bytes(0)=BYTE(value)
  bytes(1)=BYTE(value RSH 8)

RETURN

PROC Main()
  CARD index

  LET page=BYTE POINTER(ADDRESS($100))
  LET gate=BYTE POINTER(ADDRESS(SDXABI.STATE_GATE))
  LET lease=BYTE POINTER(ADDRESS(SDXABI.STATE_LEASE))
  LET saved=BYTE POINTER(ADDRESS(SDXABI.STATE_ANCHOR))
  EXEC.Forbid()
  gate(0)=1
  Word(saved,STACK_ANCHOR_VALUE)
  Word(lease,1)
  FOR index=STACK_ANCHOR_VALUE-$100+1 TO $ef DO
    page(index)=BYTE(index XOR $5a)
  OD
  gate(0)=0
  EXEC.Permit()
  Require(EXECOS.Write(@message,4)=1)
  Require(EXECTASKS.Sleep(4)=0)
  FOR index=STACK_ANCHOR_VALUE-$100+1 TO $ef DO
    Require(page(index)=BYTE(index XOR $5a))
  OD
  FOR index=0 TO 15 DO
    Require(page(index)=$a5)
  OD
  EXEC.Forbid()
  gate(0)=1
  Word(lease,0)
  Word(saved,0)
  gate(0)=0
  EXEC.Permit()

RETURN

ENDMODULE
'''.replace('STACK_ANCHOR_VALUE',f'${anchor:x}'))
    if lease_case:
        text=source.read_text().replace('USE HEAPCORE','USE HEAPCORE\nUSE SDXRUNTIME')
        start=text.index('  EXEC.Forbid()')
        finish=text.index('  Require(EXECOS.Write')
        text=text[:start]+'  LET context=BYTE POINTER(ADDRESS(SDXABI.CONTEXT_BASE))\n  Word(context+SDXABI.FIELDS_BANK,$30)\n  Word(context+SDXABI.FIELDS_ENTRY,$3000)\n  Word(context+SDXABI.FIELDS_DP,$7e00)\n  Require(SDXRUNTIME.Acquire(0)=1)\n  Require(SDXRUNTIME.Acquire(1)=0)\n  SDXRUNTIME.Enter(0)\n  Require(page($e1)=$30)\n  Require(page($e2)=0 AND page($e3)=$7e)\n  Require(page($ec)=0 AND page($ed)=$30)\n  SDXRUNTIME.MoveFrame(0,$1c0)\n  Require(page($c1)=$30)\n  Require(page($c2)=0 AND page($c3)=$7e)\n  Require(page($cc)=0 AND page($cd)=$30)\n  SDXRUNTIME.Release()\n  Require(SDXRUNTIME.Acquire(1)=1)\n  SDXRUNTIME.Release()\n'+text[finish:]
        start=text.index('  FOR index=STACK_ANCHOR_VALUE') if '  FOR index=STACK_ANCHOR_VALUE' in text else text.index('  FOR index=$d0') if '  FOR index=$d0' in text else text.index('  FOR index=',text.index('  Require(EXECOS.Write'))
        finish=text.index('  FOR index=0 TO 15 DO',start)
        text=text[:start]+text[finish:]
        source.write_text(text)
    if deep:
        text=source.read_text().replace('BYTE ARRAY message=[83 68 88 155]',
            'BYTE ARRAY message=['+' '.join(map(str,[83,68,88,155]*30))+']')
        text=text.replace('  Require(EXECOS.Write(@message,4)=1)',
            '  LET fine=BYTE POINTER(ADDRESS($26e))\n  LET cursor=BYTE POINTER(ADDRESS($54))\n'
            '  fine(0)=1\n  cursor(0)=23\n  Require(EXECOS.Write(@message,120)=1)\n  fine(0)=0')
        source.write_text(text)
    return source


def probe(out, mode, anchor, expected=0, phase=0, deep=False, lease_case=False, rom=None):
    out.mkdir(parents=True,exist_ok=True)
    source=fixture(out,anchor,deep,lease_case)
    p=build(compiler(ROOT/'build/actionc',release=True),source,out,
            optimize=mode=='opt',tasks=True,task_capacity=12,console=False,
            sio_enabled=False,sdx=True,sdx_stack_probe=phase)
    firmware,pin=select_firmware(rom,PIN)
    with emulator(ROOT/'build/shell-paced-bridge',firmware,out,pin=pin) as b:
        configure_firmware(b,firmware)
        machine=verify_machine(b,firmware,pin)
        try:
            runtime,_=execute(b,p,expected_status=expected,timeout=180,frame_limit=9000)
        except Exception:
            print('Checks:',data(b,p['image'],'checks'),flush=True)
            raise
        if expected==0:ownership(b,p,out)
        pool=p['build']['memory']['sdx_storage']['dp_reservation']
        require(b.memdump(pool['address'],16)==bytes([0xa5])*16,'Lower DP guard changed')
        require(b.memdump(pool['address']+pool['size']-16,16)==bytes([0xa5])*16,'Upper DP guard changed')
        checks=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
        state=json.loads((ROOT/'abi/sdx.json').read_text())['runtime']['state']
        rom_nmis=int.from_bytes(b.memdump(state['rom_nmis'],2),'little')
        if phase:require(rom_nmis>0,'No real NMI interrupted the selected borrow boundary')
    require(runtime['status']==expected,'Wrong domain result')
    return dict(status='pass',tier='development',qualification=False,case=mode,
                anchor=anchor,checks=checks,phase=phase,rom_nmis=rom_nmis,
                runtime=runtime,machine=machine,build=p['build'],
                bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--group',choices=('rom','bounds','transition','lease'),required=True)
    parser.add_argument('--rom',type=Path)
    parser.add_argument('--deep',action='store_true',help='ROM fine scroll with real nested VBI at minimum borrow anchor')
    parser.add_argument('--phase',type=int,choices=range(1,8),default=0)
    parser.add_argument('--case',choices=('raw','opt'),default='opt')
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running',tier='development',qualification=False)
    try:
        if args.group=='rom':
            result=probe(out,args.case,0x190 if args.deep else 0x1d0,deep=args.deep,rom=args.rom)
        elif args.group=='bounds':
            abi=json.loads((ROOT/'abi/sdx.json').read_text())['runtime']
            boundary=abi['stack_floor']+abi['rom_reserve']
            result=dict(status='pass',tier='development',qualification=False,
                        accepted=probe(out/'accepted',args.case,boundary,rom=args.rom),
                        rejected=probe(out/'rejected',args.case,boundary-1,1,rom=args.rom))
        elif args.group=='lease':
            phases=[args.phase] if args.phase else range(5,8)
            result=dict(status='pass',tier='development',qualification=False,
                        cases=[probe(out/str(phase),args.case,0x1d0,phase=phase,lease_case=True,rom=args.rom) for phase in phases])
        else:
            phases=[args.phase] if args.phase else range(1,5)
            result=dict(status='pass',tier='development',qualification=False,
                        cases=[probe(out/str(phase),args.case,0x1d0,phase=phase,rom=args.rom) for phase in phases])
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Resident stack:',args.group,args.case,'passed',flush=True)


if __name__=='__main__':main()
