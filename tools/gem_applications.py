"""Development observers resolve private app symbols through retained Processes."""
import json
from native_program import ROOT,require

MODELS={'panel':('GEMPanel',8,34),'counter':('GEMCounter',12,38),'files':('GEMBrowser',8,26),'calc':('Calculator',4,22)}

def instances(bridge,program,directory):
    apps={name:json.loads((directory/'apps'/name/'app.json').read_text())
          for name in MODELS if (directory/'apps'/name/'app.json').exists()}
    abi=json.loads((ROOT/'abi/process.json').read_text())
    offsets={field[0]:field[2] for field in abi['record']}
    table=next(d for d in program['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
    raw=bridge.memdump(table['address'],table['size']);result=[]
    for offset in range(0,len(raw)-4,abi['record_bytes']):
        row=raw[offset:offset+abi['record_bytes']]
        at=int.from_bytes(row[offsets['image']:offsets['image']+3],'little')
        if not row[offsets['state']] or not at:continue
        image=bridge.memdump(at,42)
        if image[:4]!=b'IMG1' or image[10]!=1:continue
        # Private PROGRAMIMAGE layout, used only by this development observer.
        base=int.from_bytes(image[36:39],'little')
        span=int.from_bytes(image[24:28],'little')
        entry=int.from_bytes(image[39:42],'little')-base
        matches=[name for name,app in apps.items() if app['span']==span and app['entry']==entry]
        require(len(matches)<=1,'Ambiguous application observer profile')
        if not matches:continue
        name=matches[0];app=apps[name];reference=app['abi']['link_bank']<<16
        sy={key:base+address-reference for key,address in app['image']['symbols'].items()
            if reference<=address<reference+app['span']}
        result.append(dict(name=name,identity=int.from_bytes(row[offsets['identity']:offsets['identity']+4],'little'),
                           symbols=sy,base=base,state=row[offsets['state']]))
    return result

def symbols(bridge,program,directory,name,identity):
    found=[item for item in instances(bridge,program,directory)
           if item['name']==name and item['identity']==identity]
    require(len(found)==1,'No retained Process for '+name)
    return found[0]['symbols']

def scene_symbols(bridge,program,directory,title,bounds):
    name={b'GEM Control Panel':'panel',b'Counter':'counter',b'Files':'files',b'Calculator':'calc'}[title]
    model,ready,work=MODELS[name];found=[]
    for item in instances(bridge,program,directory):
        if item['name']!=name:continue
        at=item['symbols'][model]
        xy=bridge.memdump(at+work,4)
        if int.from_bytes(xy[:2],'little')==bounds[0]+8 and int.from_bytes(xy[2:],'little')==bounds[1]+16:
            found.append(item['symbols'])
    require(len(found)==1,'No unique loaded window model for '+name)
    return found[0]
