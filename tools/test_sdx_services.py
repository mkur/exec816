#!/usr/bin/env python3
"""Guest-call probes for the fourteen MD5 SDX symbols (P4 development)."""
import argparse
import hashlib
import json
from pathlib import Path
import time

from native_program import ROOT, build, compiler, verify_machine
from os_boundary import emulator
from sdx_fixtures import assemble
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_patches import PIN


def fixture(out, close_error):
    origin=0x240000
    payload=bytearray()
    modules={}
    for name in ('services','fail','options','console','rethrow'):
        item=assemble(out,name)
        modules[name]=(origin+len(payload),len(item['bytes']))
        payload+=item['bytes']
    calls=[]
    def launch(name,args,primary,secondary,inspect=''):
        at,size=modules[name]
        calls.append(f'''  image=PROGRAM.Load(BYTE POINTER(ADDRESS(${at:x})),{size})
  Require(image<>NULL)
  identity=PROCESS.StartLoaded(BYTE POINTER(image),BYTE POINTER(c"{args}"),{len(args)},0)
  Require(identity<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  Require(result.primary={primary} AND result.secondary={secondary})
  state=SDXSTATE.Session POINTER(image.extension)
  Require(state.handles(0)=NULL AND state.handles(1)=NULL AND state.trapCount=0)
{inspect}
  PROGRAM.Unload(image)''')
    if close_error:
        launch('services','/CC A:>ONE.BIN A:>TWO.BIN',20,221)
    else:
        launch('services','/CC A:>ONE.BIN A:>TWO.BIN',0,0,'''  bank=state.bank
  Require(bank($500)='Q AND bank($501)=$5a AND bank($502)=$a6)
  Require((bank($503) & $82)=0)
  Require(bank($504)='C AND bank($505)=$fe AND bank($506)=0)
  Require(bank($507)=10 AND bank($508)=1 AND bank($509)=2)
  Require(bank($50a)=0 AND bank($50b)=0 AND bank($526)=$a6)
  Require(bank($50c)=$ff AND (bank($50d) & $80)<>0 AND bank($50e)=3)
  Require(bank($3800)='x AND bank($3801)='y AND bank($3802)='z)
  Require(bank($782)=0 AND bank($783)=$38)
  Require(bank($51c)=$9b AND bank($51d)=$ff)
  Require(bank($50f)=0 AND bank($510)=170 AND (bank($51e) & $80)<>0)
  Require(bank($511)=$80 AND bank($51f)=0 AND (bank($520) & $80)=0)
  Require(bank($512)=$35 AND bank($513)=$5a AND bank($514)=$a6)
  Require((bank($515) & $83)=$81)
  Require(bank($516)=$35 AND bank($517)=$5a AND bank($518)=$a6)
  Require(bank($519)=$ab AND bank($51a)=0)
  Require(bank($524)=$21 AND bank($525)=$10)
  Require(bank($527)=0 AND bank($528)=161)
  Require(bank($529)=0 AND bank($52a)=156)
  Require(bank($80)=7 AND state.dp($80)=5)''')
    launch('fail','A:>ONE.BIN A:>TWO.BIN',20,170,'  Require(state.bank($500)=0)')
    launch('fail','A:>MISSING.BIN',20,205)
    launch('fail','B:>ONE.BIN',20,160)
    for tail,secondary in [('S',205),('DD',171),('RRR A:>ONE.BIN',170)]:
        launch('rethrow','A:>MISSING.BIN '+tail,20,secondary,
               '  Require(state.bank($500)=170)')
    launch('options','/H A:>ONE.BIN',20,156)
    launch('options','/Z A:>ONE.BIN',20,156)
    launch('options','A:>HASH.BIN',0,0,'  Require(state.bank($500)=0 AND state.bank($502)=$a0)')
    launch('options','+P -H A:>ONE.BIN',0,0,'  Require((state.bank($501) & 2)=0 AND state.bank($502)=$21)')
    launch('options','+H',0,0,'  Require((state.bank($501) & 2)<>0 AND state.bank($502)=2)')
    launch('options','-Q A:>ONE.BIN',20,156)
    launch('options','X'*64,20,156)
    # The same guest stream must be adapted only at the interactive boundary.
    saved_calls=calls
    calls=[]
    launch('console','',0,0)
    console_calls='\n'.join(calls)
    calls=saved_calls
    source=out/'probe.act'
    source.write_text('''MODULE SDXSERVICEPROBE
USE EXEC
USE DOS
USE DOSCLIENT
USE PROCESS
USE PROGRAM
USE PROGRAMIMAGE
USE SDXSTATE
USE HEAPCORE
USE FSBOOT
USE CONSOLEDRIVER
USE CONSOLECORE
USE CONSOLETYPES

CARD checks
LONGINT reason,primary,secondary
BYTE ARRAY first=[0 $80 $ff 65]
BYTE ARRAY second=[120 121 122]
BYTE ARRAY outputBytes(64)

PROC Require(BYTE okay)

  IF okay=0 THEN
    reason=DOS.IoErr()
    HEAPCORE.Abort($fb00+checks)
  FI
  checks==+1

RETURN

PROC Main()
  PROGRAMIMAGE.Image POINTER image
  SDXSTATE.Session POINTER state
  CONSOLETYPES.Instance POINTER terminal
  DOS.FileHandle POINTER file,output,previous
  PROCESS.Result result
  LONGCARD identity,baseline
  BYTE POINTER bank
  CARD index

  baseline=EXEC.AvailMem(0)
  file=DOS.Open(BYTE POINTER(c"RAM:ONE.BIN"),DOS.MODE_NEWFILE)
  Require(file<>NULL)
  Require(DOS.Write(file,first,4)=4 AND DOS.Close(file)<>0)
  file=DOS.Open(BYTE POINTER(c"RAM:TWO.BIN"),DOS.MODE_NEWFILE)
  Require(file<>NULL)
  Require(DOS.Write(file,second,3)=3 AND DOS.Close(file)<>0)
  output=DOS.Open(BYTE POINTER(c"RAM:RESULT.TXT"),DOS.MODE_NEWFILE)
  Require(output<>NULL)
  previous=DOS.SelectOutput(output)
'''+ '\n'.join(calls)+'''
  DOS.SelectOutput(previous)
  Require(DOS.Close(output)<>0)
  file=DOS.Open(BYTE POINTER(c"RAM:RESULT.TXT"),DOS.MODE_OLDFILE)
  Require(file<>NULL)
  Require(DOS.Read(file,@outputBytes,64)=OUTPUT_BYTES)
  Require(DOS.Close(file)<>0)
  output=DOS.Open(BYTE POINTER(c"CON:"),DOS.MODE_READWRITE)
  Require(output<>NULL AND DOS.IsInteractive(output)<>0)
  previous=DOS.SelectOutput(output)
CONSOLE_CALLS
  terminal=CONSOLEDRIVER.GetInstance()
  Require(terminal.row=1 AND terminal.column=0)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,0))='A)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,1))='C)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,8))='Z)
  DOS.SelectOutput(previous)
  Require(DOS.Close(output)<>0)
  ; Both handles were closed even after uncaught errors and terminal Close failures.
  file=DOS.Open(BYTE POINTER(c"RAM:ONE.BIN"),DOS.MODE_NEWFILE)
  Require(file<>NULL AND DOS.Close(file)<>0)
  file=DOS.Open(BYTE POINTER(c"RAM:TWO.BIN"),DOS.MODE_NEWFILE)
  Require(file<>NULL AND DOS.Close(file)<>0)
  Require(DOS.ReleaseContext()<>0)
  Require(FSBOOT.Stop()<>0)
  Require(EXEC.AvailMem(0)=baseline)
  SDXSTATE.Guards()

RETURN

ENDMODULE
'''.replace('OUTPUT_BYTES','0' if close_error else '21').replace('CONSOLE_CALLS',console_calls))
    # Preserve the failing guest result before a native assertion terminates.
    text=source.read_text().replace('  Require(result.primary=',
        '  primary=result.primary\n  secondary=result.secondary\n  Require(result.primary=')
    source.write_text(text)
    return source,[(origin,bytes(payload))]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--close-error',action='store_true')
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running');started=time.monotonic()
    try:
        source,payload=fixture(out,args.close_error)
        if args.close_error:
            text=(ROOT/'lib/dos/sdxfiles.act').read_text()
            needle='  IF DOS.Close(file)=0 THEN\n'
            assert text.count(needle)==1
            text=text.replace(needle,'  DOS.Close(file)\n  DOS.SetIoErr(221)\n  IF 1 THEN\n')
            (out/'sdxfiles.act').write_text(text)
        else:
            (out/'sdxfiles.act').unlink(missing_ok=True)
        program=build(compiler(ROOT/'build/actionc',release=True),source,out,
            tasks=True,task_capacity=8,console=True,console_test=True,sdx=True,
            image_data=payload,dos_mounts=[dict(alias='RAM',format=3)])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:
                runtime,_=execute(b,program,timeout=180,frame_limit=9000)
            except Exception:
                print({k:data(b,program['image'],k) for k in ('checks','reason','primary','secondary')},flush=True)
                context=b.memdump(0x287a00,512)
                bank=context[0x108]*65536
                print('Guest records:',hex(bank),b.memdump(bank+0x500,48).hex(),flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
            output=bytes(data(b,program['image'],'outputBytes'))
            expected=b'' if args.close_error else b'MD5 05 ok DONE 258 %\x9b'
            assert output[:len(expected)]==expected,output.hex()
        result=dict(status='pass',tier='development',checks=checks,runtime=runtime,
                    machine=machine,build=program['build'],close_error=args.close_error,
                    output=output[:len(expected)].hex(),
                    close_error_override_sha256=hashlib.sha256((out/'sdxfiles.act').read_bytes()).hexdigest() if args.close_error else None)
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:
        result['seconds']=round(time.monotonic()-started,3)
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('SDX services:',checks,'checks passed',flush=True)


if __name__=='__main__':
    main()
