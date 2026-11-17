#!/usr/bin/env python3
"""Small raw/optimized AES record layout and actual C/native pointer bridge."""
import argparse,json
from pathlib import Path
from calypsi_build import emit
from generate_aes_server import expected_layout
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN


def run(out,mode):
    out.mkdir(parents=True,exist_ok=True)
    source=out/'wire.c'
    source.write_text('''#include "aes-private.h"
#include <exec816/runtime.h>
volatile UWORD WireSeen;
LONG EXEC_CALL WireProbe(ULONG value) {
    struct AESRequest *q=(struct AESRequest *)value;
    WireSeen=q[0].bytes;
    struct AESWindowView *v=q[1].view;
    if (q[0].bytes!=sizeof(*q) || q[0].status!=55 || q[1].operation!=107 ||
        q[1].intin[0]!=3 || v->handle!=7 || v->epoch!=0x12345678UL ||
        v->work.left!=-3 || !q[1].displayGrant || *q[1].displayGrant!=91) return 1;
    q[1].intout[0]=-7;v->revision=0x87654321UL;
    return 0;
}
int main(void) {return 0;}
''')
    f=emit(out/'c',[source],[ROOT/'c/calypsi/image-info.s'],[],optimize=mode=='opt',
           includes=[ROOT/'c/calypsi'],roots=['WireProbe','WireSeen'],probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout())])
    launcher=out/'wire.act';launcher.write_text('''MODULE AESWIRETEST
USE EXEC
USE HEAPCORE
USE AESTYPES
USE CALYPSICALL
AESTYPES.Request ARRAY requests(2)
AESTYPES.WindowView view
BYTE token
PROC Main()
  requests(0).bytes=SIZEOF(AESTYPES.Request)
  requests(0).status=55
  requests(1).operation=107
  requests(1).intin(0)=3
  requests(1).view=@view
  requests(1).displayGrant=@token
  view.handle=7
  view.epoch=$12345678
  view.work.left=-3
  token=91
  IF CALYPSICALL.Invoke(ADDRESS($'''+format(f['symbols']['WireProbe'],'x')+'''),LONGCARD(ADDRESS(@requests)))<>0
      OR requests(1).intout(0)<>-7 OR view.revision<>$87654321 THEN
    HEAPCORE.Abort($fc99)
  FI
RETURN
ENDMODULE
''')
    p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',tasks=True,optimize=mode=='opt',foreign_image=f)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN);runtime,_=execute(b,p,frame_limit=600,timeout=90)
        ownership(b,p,p['output'])
    r=dict(status='pass',tier='development',qualification=False,mode=mode,layout_checks=len(expected_layout()),
           request_bytes=dict(expected_layout())['Request size'],view_bytes=dict(expected_layout())['WindowView size'],
           native_sha256=sha256(p['xex']),machine=machine,runtime=runtime)
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('AES wire',mode,'passed')

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');x=a.parse_args();run(x.output.resolve(),x.mode)
