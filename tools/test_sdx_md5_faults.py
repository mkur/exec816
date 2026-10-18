#!/usr/bin/env python3
"""Real MD5 after settled native read/write/close failures and short writes."""
import argparse
import hashlib
import json
from pathlib import Path

from native_program import ROOT,build,compiler,verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute,ownership
from test_sdx_md5 import PIN
from test_sdx_md5_exec import fixture


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--case',choices=('close','read-close','write','partial'),required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    result=dict(status='running')
    try:
        source,payload,cases=fixture(out,quick=True)
        files=(ROOT/'lib/dos/sdxfiles.act').read_text()
        printing=(ROOT/'lib/dos/sdxprint.act').read_text()
        if args.case in ('close','read-close'):
            files=files.replace('  IF DOS.Close(file)=0 THEN',
                '  DOS.Close(file)\n  DOS.SetIoErr(221)\n  IF 1 THEN')
        if args.case=='read-close':
            files=files.replace('    IF got<0 THEN',
                '    DOS.SetIoErr(219)\n    got=-1\n    IF got<0 THEN')
        if args.case=='write':
            printing=printing.replace('    IF sent<=0 THEN',
                '    DOS.SetIoErr(223)\n    sent=-1\n    IF sent<=0 THEN')
        if args.case=='partial':
            files=files.replace('target+SIZE(total),LONGINT(count)-total)',
                'target+SIZE(total),1)')
            printing=printing.replace('LONGINT(state.outputUsed)-done)', '1)')
        else:
            want={'close':221,'read-close':219,'write':223}[args.case]
            text=source.read_text().replace('Require(primary=0 AND secondary=0)',
                f'Require(primary=20 AND secondary={want})')
            # Output may have a committed prefix before an error. A settled
            # read/close failure emits nothing; write injection consumes the
            # first real PRINTF call before reporting its error.
            text=text.replace('  Require(DOS.Read(file,@actual,128)=LONGINT(expectedBytes))',
                '  Require(DOS.Read(file,@actual,128)=20)' if args.case=='write' else
                '  Require(DOS.Read(file,@actual,128)=0)')
            begin=text.index('  FOR index=0 TO expectedBytes-1 DO')
            end=text.index('  Require(DOS.Close(file)',begin)
            text=text[:begin]+text[end:]
            source.write_text(text)
        (out/'sdxfiles.act').write_text(files);(out/'sdxprint.act').write_text(printing)
        program=build(compiler(ROOT/'build/actionc',release=True),source,out,
            tasks=True,task_capacity=8,console=False,console_test=True,sdx=True,
            image_data=payload,dos_mounts=[dict(alias='RAM',format=3)])
        with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            for key,value in PIN['configuration'].items():
                b.config(key,str(value).lower() if isinstance(value,bool) else value)
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            try:runtime,_=execute(b,program,timeout=180,frame_limit=9000)
            except Exception:
                print({k:data(b,program['image'],k) for k in ('checks','currentCase','primary','secondary','reason','actual')},flush=True)
                raise
            ownership(b,program,out)
            checks=int.from_bytes(bytes(data(b,program['image'],'checks')),'little')
        result=dict(status='pass',tier='development',case=args.case,checks=checks,
            runtime=runtime,machine=machine,build=program['build'],
            overrides={name:hashlib.sha256((out/name).read_bytes()).hexdigest()
                       for name in ('sdxfiles.act','sdxprint.act')})
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MD5 fault:',args.case,checks,'checks passed',flush=True)


if __name__=='__main__':main()
