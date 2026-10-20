#!/usr/bin/env python3
"""Generate the caller-owned combined AES/Exec wait record."""
import argparse,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]


def files():
    abi=json.loads((ROOT/'abi/aes-wait.json').read_text());at=0;fields=[]
    for name,kind,offset in abi['fields']:
        if at!=offset:raise ValueError('Invalid AES wait field: '+name)
        fields.append('    WORD '+name+'[8];' if kind=='WORD[8]' else '    '+kind+' '+name+';')
        at+=16 if kind=='WORD[8]' else 4 if kind=='ULONG' else 2
    if at!=abi['bytes']:raise ValueError('Invalid AES wait size')
    return {ROOT/'c/include/exec816/aes-wait.h':
        '/* Generated from abi/aes-wait.json; do not edit. */\n#ifndef EXEC816_AES_WAIT_H\n#define EXEC816_AES_WAIT_H\n#include <exec/types.h>\n'+
        '#define MU_EXEC 0x%04xU\n'%abi['exec_flag']+
        'struct ExecAESWaitSpec {\n'+'\n'.join(fields)+'\n};\nWORD ExecAESWait(struct ExecAESWaitSpec *spec);\n#endif\n'}


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--check',action='store_true');args=p.parse_args()
    for path,content in files().items():
        if args.check:
            if not path.exists() or path.read_text()!=content:raise SystemExit('Stale AES wait header: '+str(path))
        else:path.write_text(content)
