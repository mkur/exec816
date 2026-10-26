#!/usr/bin/env python3
"""Pinned 6502 MD5 through native DOS, Images and ordinary Processes."""
import argparse
from sdx_test_firmware import select as select_firmware, configure as configure_firmware
import hashlib
import json
from pathlib import Path
import time

from native_program import ROOT, build, compiler, read_build, verify_machine
from os_boundary import emulator
from sdx_md5_audit import audit
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN
from sdfs_reference import make


def fixture(out, quick=False, disk=False, shell=False):
    binary=(ROOT/'build/sdx-inputs/md5/MD5.COM').read_bytes()
    audited=audit(binary)
    (out/'audit.json').write_text(json.dumps(audited,indent=2)+'\n')
    payload=bytearray(binary)
    blob=bytes((i*37+i//251)&255 for i in range(131073))
    corpus=[('empty',b''),('abc',b'abc')]
    if disk:
        corpus += [('65537',blob[:65537])]
    elif not quick:
        corpus.append(('all-bytes',bytes(range(256))))
        corpus += [(str(n),blob[:n]) for n in (55,56,63,64,65,256,39935,39936,39937,65535,65536,65537,131073)]
    cases=[]; calls=[]
    files=out/'files';files.mkdir(exist_ok=True)
    for i,(name,raw) in enumerate(corpus):
        leaf=f'F{i:02}.BIN' if disk else 'DATA.BIN'
        if disk:(files/leaf).write_bytes(raw)
        at=0x300000+len(payload);payload+=raw
        expected=f'MD5 (A:>{leaf}) = '.encode()+hashlib.md5(raw).hexdigest().upper().encode()+b'\x9b'
        expected_at=0x300000+len(payload);payload+=expected
        calls.append(f'  Run({i},BYTE POINTER(c"A:>{leaf}"),{3+len(leaf)},BYTE POINTER(ADDRESS(${at:x})),LONGINT(${len(raw):x}),BYTE POINTER(ADDRESS(${expected_at:x})),{len(expected)})')
        cases.append(dict(name=name,bytes=len(raw),md5=hashlib.md5(raw).hexdigest(),expected=expected.hex()))
    source=out/'probe.act'
    source.write_text('''MODULE SDXMD5EXEC
USE EXEC
USE DOS
USE PROCESS
USE PROGRAM
USE PROGRAMFILE
USE PROGRAMIMAGE
USE SDXSTATE
USE HEAPCORE
USE FSBOOT

CARD checks,currentCase
LONGINT primary,secondary,reason
LONGCARD guestBank
BYTE ARRAY actual(128)

PROC Require(BYTE okay)

  IF okay=0 THEN
    reason=DOS.IoErr()
    HEAPCORE.Abort($fd00+checks)
  FI
  checks==+1

RETURN

PROC Run(CARD number BYTE POINTER args CARD argBytes BYTE POINTER bytes LONGINT count
    BYTE POINTER expected CARD expectedBytes)
  DOS.FileHandle POINTER file,output,previous
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  PROCESS.Result result
  LONGCARD identity
  CARD index

  currentCase=number
  file=DOS.Open(BYTE POINTER(c"RAM:DATA.BIN"),DOS.MODE_NEWFILE)
  Require(file<>NULL)
  Require(DOS.Write(file,bytes,count)=count AND DOS.Close(file)<>0)
  output=DOS.Open(BYTE POINTER(c"RAM:RESULT.TXT"),DOS.MODE_NEWFILE)
  Require(output<>NULL)
  previous=DOS.SelectOutput(output)
  image=PROGRAMFILE.Load(BYTE POINTER(c"RAM:MD5"))
  Require(image<>NULL)
  state=SDXSTATE.Session POINTER(image.extension)
  guestBank=LONGCARD(ADDRESS(state.bank))
  identity=PROCESS.StartLoaded(BYTE POINTER(image),args,argBytes,0)
  Require(identity<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  primary=result.primary
  secondary=result.secondary
  Require(primary=0 AND secondary=0)
  Require(state.handles(0)=NULL AND state.handles(1)=NULL AND state.trapCount=0)
  PROGRAM.Unload(image)
  DOS.SelectOutput(previous)
  Require(DOS.Close(output)<>0)
  file=DOS.Open(BYTE POINTER(c"RAM:RESULT.TXT"),DOS.MODE_OLDFILE)
  Require(file<>NULL)
  Require(DOS.Read(file,@actual,128)=LONGINT(expectedBytes))
  FOR index=0 TO expectedBytes-1 DO
    Require(actual(index)=expected(index))
  OD
  Require(DOS.Close(file)<>0)
  SDXSTATE.Guards()

RETURN

PROC Main()
  DOS.FileHandle POINTER file
  LONGCARD baseline

  baseline=EXEC.AvailMem(0)
  file=DOS.Open(BYTE POINTER(c"RAM:MD5"),DOS.MODE_NEWFILE)
  Require(file<>NULL)
  Require(DOS.Write(file,BYTE POINTER(ADDRESS($300000)),BINARY_BYTES)=BINARY_BYTES)
  Require(DOS.Close(file)<>0)
CALLS
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)

RETURN

ENDMODULE
'''.replace('BINARY_BYTES',str(len(binary))).replace('CALLS','\n'.join(calls)))
    if disk:
        text=source.read_text()
        begin=text.index('  file=DOS.Open(BYTE POINTER(c"RAM:DATA.BIN")')
        end=text.index('  output=DOS.Open',begin)
        source.write_text(text[:begin]+text[end:])
        make(out/'input.atr',files,1024,256,'MD5DATA')
    if shell:
        text=source.read_text().replace('CARD checks,currentCase',
            'INCLUDE "'+str(ROOT/'examples/shell/shell-session.inc')+'"\n\nShellContext context\nCARD checks,currentCase')
        tail='''  Require(ShellStart(@context,BYTE POINTER(c"RAM:"))<>0)
  LET line=ShellLine(@context)
  LET command=BYTE POINTER(c"RAM:MD5 DATA.BIN >RAM:SHELL.OUT")
  index=0
  WHILE command(index)<>0 DO
    line(index)=command(index)
    index==+1
  OD
  line(index)=0
  context.shell.length=index
  ShellCommand(@context)
  Require(context.shell.lastStatus=0 AND context.shell.lastError=0
      AND context.shell.done=0)
  Require(ShellFinish(@context)=0 AND context.shell=NULL)
  file=DOS.Open(BYTE POINTER(c"RAM:SHELL.OUT"),DOS.MODE_OLDFILE)
  Require(file<>NULL)
  Require(DOS.Read(file,@actual,128)=SHELL_BYTES)
  Require(DOS.Close(file)<>0)
'''
        expected=b'MD5 (DATA.BIN) = '+hashlib.md5(corpus[-1][1]).hexdigest().upper().encode()+b'\x9b'
        # The host independently checks the complete shell-produced byte stream.
        cases.append(dict(name='shell',expected=expected.hex()))
        text=text.replace('  LONGCARD baseline\n','  LONGCARD baseline\n  CARD index\n')
        text=text.replace('  Require(DOS.ReleaseContext()<>0)',tail.replace('SHELL_BYTES',str(len(expected)))+'  Require(DOS.ReleaseContext()<>0)')
        source.write_text(text)
    (out/'cases.json').write_text(json.dumps(cases,indent=2)+'\n')
    return source,[(0x300000,bytes(payload))],cases


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--rom',type=Path)
    parser.add_argument('--quick',action='store_true')
    parser.add_argument('--replay',action='store_true')
    parser.add_argument('--disk',action='store_true')
    parser.add_argument('--shell',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running');started=time.monotonic()
    try:
        assert not (args.disk and args.shell),'Run RAM shell and SDFS cases separately'
        if args.replay:
            cases=json.loads((out/'cases.json').read_text())
        else:
            source,payload,cases=fixture(out,args.quick,args.disk,args.shell)
        mounts=[dict(alias='RAM',format=3)]
        if args.disk:
            # Physical D1 is the emulator's XLOS XEX Disk Boot transport.
            mounts.append(dict(alias='DATA',unit=50,sectors=1024,sector_bytes=256,profile=4,format=2))
        profile=None
        if args.shell:
            memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
            memory['image_data_bytes']=8192
            profile=out/'memory-profile.json';profile.write_text(json.dumps(memory,indent=2)+'\n')
        program=read_build(out) if args.replay else build(compiler(ROOT/'build/actionc',release=True),source,out,
            tasks=True,task_capacity=8,console=args.shell,console_test=True,sdx=True,
            image_data=payload,dos_mounts=mounts,memory_profile=profile,
            sdx_drive_a='DATA:' if args.disk else 'RAM:')
        firmware,pin=select_firmware(args.rom,PIN)
        with emulator(ROOT/'build/shell-paced-bridge',firmware,out,pin=pin) as b:
            configure_firmware(b,firmware)
            for key,value in pin['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            if args.disk:b.config('diskemu','generic56k')
            machine=verify_machine(b,firmware,pin)
            if args.disk:b.mount(1,str(out/'input.atr'))
            try:
                runtime,_=execute(b,program,timeout=240,frame_limit=12000)
            except Exception:
                print({k:data(b,program['image'],k) for k in ('checks','currentCase','primary','secondary','reason','guestBank','actual')},flush=True)
                abi=json.loads((ROOT/'abi/sdx.json').read_text())['runtime']
                context=b.memdump(abi['context_base'],abi['context_bytes'])
                print('Frame:',b.memdump(int.from_bytes(context[abi['fields']['guest_s']:abi['fields']['guest_s']+2],'little')+1,13).hex(),'guest S',context[abi['fields']['guest_s']:abi['fields']['guest_s']+2].hex(),flush=True)
                print('DP:',b.memdump(program['build']['memory']['sdx_storage']['dp_base'],256).hex(),flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
            if args.shell:
                expected=bytes.fromhex(cases[-1]['expected'])
                actual=bytes(data(b,program['image'],'actual'))
                assert actual[:len(expected)]==expected,actual.hex()
        result=dict(status='pass',tier='development',checks=checks,cases=cases,
                    runtime=runtime,machine=machine,build=program['build'])
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MD5 Exec:',checks,'checks passed',flush=True)


if __name__=='__main__':
    main()
