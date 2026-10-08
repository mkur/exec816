"""Development observers resolve private app symbols through retained Processes."""
import json
from native_program import ROOT,require

def symbols(bridge,program,directory,name,identity):
    app=json.loads((directory/'apps'/name/'app.json').read_text())
    abi=json.loads((ROOT/'abi/process.json').read_text())
    offsets={field[0]:field[2] for field in abi['record']}
    table=next(d for d in program['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
    raw=bridge.memdump(table['address'],table['size'])
    for offset in range(0,len(raw)-4,abi['record_bytes']):
        row=raw[offset:offset+abi['record_bytes']]
        if int.from_bytes(row[offsets['identity']:offsets['identity']+4],'little')==identity:
            at=int.from_bytes(row[offsets['image']:offsets['image']+3],'little')
            image=bridge.memdump(at,42)
            require(image[:4]==b'IMG1' and image[10]==1,'Expected a retained C image')
            # Private PROGRAMIMAGE layout; this is a host observer, not an app ABI.
            base=int.from_bytes(image[36:39],'little')
            return {key:base+address-(app['abi']['link_bank']<<16)
                    for key,address in app['image']['symbols'].items()
                    if (app['abi']['link_bank']<<16)<=address<(app['abi']['link_bank']<<16)+app['span']}
    raise RuntimeError('No retained Process for '+name)
