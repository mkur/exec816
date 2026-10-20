#!/usr/bin/env python3
"""QE4 actual-source transactions and the loaded editor's clipboard commands."""
import argparse
import struct
from pathlib import Path
from test_qed_selection import logical
from test_qed_editing import run
from qed_clipboard_observe import interact

def core_heap(bridge,program,app,record,owner):
    from os_boundary import run_to
    delta=owner['image_base']-(app['abi']['link_bank']<<16)
    symbols={n:v+delta for n,v in app['image']['symbols'].items()}
    condition='dw($%x)=1'%symbols['QedClipboardFinished']
    bridge.bp_clear_all();bridge.bp_set(program['labels']['native_cop'],condition=condition)
    run_to(bridge,program['labels']['native_cop'],condition=condition,timeout=120,frame_limit=30000)
    values=struct.unpack('<4I',bridge.memdump(symbols['QedClipboardHeap'],16))
    record['clipboard_core']=dict(zip(('blocks','payload','backing','peak_backing'),values))

if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--native-from',type=Path)
    parser.add_argument('--group',choices=['core','editor'],default='core')
    parser.add_argument('--from-build',action='store_true')
    parser.add_argument('--reuse-app',action='store_true')
    args=parser.parse_args()
    result=logical(args.output,native_from=args.native_from,clipboard=True,interaction=core_heap) if args.group=='core' else run(
        args.output,reuse=args.from_build,reuse_app=args.reuse_app,interaction=interact)
    print(result['status'],result['completed'])
