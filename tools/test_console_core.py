#!/usr/bin/env python3
"""Execute retained console state and terminal controls without display access."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from test_dos_stack import execute,ownership
from test_sio_device import PIN
from os_boundary import emulator
from banked_test_memory import read
from test_cooperative import data

def run(t,out,optimize,bank,paced=False):
    pin=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text()) if paced else PIN
    bridge=ROOT/'build/shell-paced-bridge' if paced else ROOT/'build/altirra-sio-multi'
    require(sha256(bridge/'AltirraBridgeServer')==pin['emulator']['sha256'],'Unpinned console emulator')
    out.mkdir(parents=True,exist_ok=True)
    source=out/'native_console_core.act'
    source.write_bytes((ROOT/'tests/programs/native_console_core.act').read_bytes())
    p=build(t,source,out,optimize=optimize,tasks=True,
        task_capacity=8,kernel_bank=bank,console_test=True,
        image_data=[(0xd0000,bytes([0xa5])*1088),(0xafff8,bytes([0xa5])*32),
                    (0xbffe0,bytes([0xa5])*2432),(0xd0ff0,bytes([0xa5])*2432)])
    with emulator(bridge,ROOT/'build/firmware/altirraos-816.rom',out,pin=pin) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',pin)
        try:runtime,_=execute(b,p,timeout=120,frame_limit=6000)
        except Exception:
            print('Core checks',data(b,p['image'],'checks',True),flush=True);raise
        ownership(b,p,out)
        actual=read(b,0xd0000,1088,out)
        expected=bytearray([0xa5])*1088
        expected[16:40]=b'ABD     Z       Q?      '
        expected[48:58]=b'67        '
        cells=bytearray(v for row in range(1,24) for v in [65+row]*40)+bytearray(b' '*40)
        cells[919]=33;expected[80:1040]=cells
        require(actual==expected,'Independent terminal cell/guard oracle failed')
        bitmap=read(b,0xd0ff0,2432,out)
        expected=bytearray([0xa5])*2432
        expected[16:2416]=bytes(v for row in range(1,30) for v in [33+row]*80)+b' '*80
        expected[16+2319]=90
        require(bitmap==expected,'80x30 bank-crossing scroll/guard oracle failed')
        return dict(status='pass',build=p['build'],machine=machine,pin=pin,runtime=runtime,
            checks=data(b,p['image'],'checks',True)[0],quanta=data(b,p['image'],'quanta',True)[0],
            snapshots_sha256=__import__('hashlib').sha256(actual).hexdigest(),first=actual[16:40].decode(),second=actual[48:58].decode())

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),default='opt')
    a.add_argument('--bank',type=int,choices=(1,3),default=1);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--paced',action='store_true');args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);result={'status':'running'}
    try:result=run(compiler(ROOT/'build/actionc'),out,args.case=='opt',args.bank,args.paced)
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Console core passed',args.case,args.bank,flush=True)
