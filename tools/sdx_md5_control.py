"""Build the malformed-record patch control for original SDX, without Exec calls.

Only disposable control files are rewritten. Native admission always checks the
unaltered pinned file, then patches after relocation. The control must remove
the overwritten FCLOSE relocation from its wire records before SDX loads it.
"""
import copy
import json
import struct

from sdx_file import parse,place
from sdx_patch import manifests,select,validate_patches,apply
from sdx_md5_audit import ROOT


def patched_control(raw):
    _,original=select(raw,manifests(ROOT/'compat/sdx'))
    module=copy.deepcopy(original)
    module['patches']=[p for p in module['patches'] if p['id']!='md5-break-checkpoint']
    program=parse(raw)
    data={b.number:bytearray(b.data) for b in program.blocks}
    removed=set()
    for patch,expected,replacement in validate_patches(program,module):
        assert not patch['fixups']
        start=patch['offset'];data[patch['block']][start:start+len(expected)]=replacement
        removed.update((f['base'],patch['block'],f['offset']) for f in patch['intersections'])
    result=bytearray()
    for block in program.blocks:
        result+=struct.pack('<HBBHH',0xfffe,block.number,block.control,block.offset,block.size)
        result+=data[block.number]
    for fix in program.fixups:
        sites=[(b,at) for b,at in fix.sites if (fix.base,b,at) not in removed]
        if not sites:continue
        payload=bytearray()
        for block,offset in sites:
            payload+=bytes((0xfe,block))
            while offset>=250:
                payload.append(0xff);offset-=250
            payload.append(offset)
        payload.append(0xfc)
        if isinstance(fix.base,int):result+=struct.pack('<HB',0xfffd,fix.base)
        else:result+=struct.pack('<H8s',0xfffb,fix.base.encode().ljust(8,b' '))
        result+=struct.pack('<H',len(payload))+payload
    for export in program.exports:
        result+=struct.pack('<HBH8s',0xfffc,export.block,export.offset,export.name.encode().ljust(8,b' '))
    encoded=parse(bytes(result))
    symbols={name:item['address'] for name,item in json.loads((ROOT/'abi/sdx.json').read_text())['guest_services'].items()}
    for start in (0x2000,0x4100):
        expected,layout=place(program,start,0xe000,symbols)
        expected,_=apply(program,module,expected,layout,symbols)
        actual,_=place(encoded,start,0xe000,symbols)
        assert actual==expected,'Control rewrite changed bytes outside approved patches'
    return bytes(result)
