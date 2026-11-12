"""Account shared code/table placement against the existing provider layout."""
import re
from native_program import ROOT, require


def budget(resident, allowances):
    text=(ROOT/'c/calypsi/layout.scm').read_text()
    regions={name:(int(low,16),int(high,16)+1) for name,low,high in re.findall(
        r'\(memory (\w+) \(address \(#x([0-9a-f]+) \. #x([0-9a-f]+)\)\)',text)}
    readonly=[regions[n] for n in ('Code','ExtraCode','GemTables','MoreCode')]
    data=regions['Data']
    occupied=0
    for s in resident['segments']:
        extent=(s['address'],s['address']+len(s['bytes']))
        if not s['executable'] and not s['writable'] and not any(
                a<=extent[0]<extent[1]<=b for a,b in readonly):
            # Serialized RAM desktop boot assets are outside the C provider.
            continue
        allowed=[data] if s['writable'] else readonly
        require(any(a<=extent[0]<extent[1]<=b for a,b in allowed),
                'Provider segment outside its existing layout')
        if not s['writable']:occupied+=len(s['bytes'])
    mutable=sum(len(s['bytes']) for s in resident['segments'] if s['writable'])
    for s in resident['zero_fill']:
        require(data[0]<=s['address']<s['address']+s['size']<=data[1],
                'Provider zero fill outside its existing data bank')
        mutable+=s['size']
    capacity=sum(b-a for a,b in readonly)
    reserve=allowances['code_bytes']+allowances['table_bytes']
    require(occupied+reserve<=capacity and
            mutable+allowances['data_bss_bytes']<=data[1]-data[0],
            'Provider and explicit allowances exceed its layout')
    return dict(readonly_bytes=occupied,readonly_capacity=capacity,
                readonly_allowance=reserve,mutable_bytes=mutable,
                mutable_capacity=data[1]-data[0],
                shared_code_table_banks=True)
