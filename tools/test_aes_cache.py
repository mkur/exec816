"""AES snapshot eligibility, exact restored client pixels and exposure delivery."""
import struct

import adapter_state as adapter
from generate_desktop import layout,ABI
from generate_layers import layout as layers_layout
from gem_render_oracle import DESKTOP_PALETTE
from native_program import require
from os_boundary import run_to


def physical(b,p,foreign,report):
    sy=foreign['symbols'];out=p['output'].parent
    at=lambda mod,n:next(d['address'] for d in p['image']['data']
                        if '_'+mod+'_'+n.upper()+'_' in d['name'])
    get=lambda address,size=4:int.from_bytes(b.memdump(address,size),'little')
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
    slot=layers_layout()['CacheSlot'];cache=layout()['Service']['fields']['cache']
    previous=None;report['aes_cache']=[]
    for phase in range(1,17):
        reach('dw($%x)=%d'%(sy['AESCachePhase'],phase))
        reach('@frame>=%d'%(b.eval_expr('@frame')+100))
        service=get(at('DESKSTATE','service'),3)
        # Find the actual source identity through its native content kind.
        records=layout()
        windows=records['Service']['fields']['windows'];window=records['Window']
        address=next(service+windows+i*window['size']
                    for i in range(ABI['constants']['WINDOWS'])
                    if get(service+windows+i*window['size']+window['fields']['kind'],1)==4)
        source=b.memdump(address,window['size'])
        identity=int.from_bytes(source[window['fields']['id']:window['fields']['id']+4],'little')
        slots=[]
        raw=b.memdump(service+cache,2*slot['size'])
        for index in range(2):
            start=index*slot['size']
            slots.append({name:int.from_bytes(raw[start+offset:start+offset+size],'little')
                          for name,offset,size in [(n,slot['fields'][n],sz) for n,sz in
                              [('identity',4),('revision',4),('valid',1),('pinned',1)]]})
        valid=[s for s in slots if s['identity']==identity and s['valid']]
        row=dict(phase=phase,slots=slots,captures=get(at('DESKCACHE','captures')),
                 restores=get(at('DESKCACHE','restores')),
                 patches=get(at('DESKCACHE','patches')),
                 patched_bytes=get(at('DESKCACHE','patchedBytes')))
        require(not any(s['pinned'] for s in slots),'Settled AES cache is pinned')
        if phase in (1,2,3,4,6,7,9,10,11,12,14,15):require(valid,'Missing eligible AES image at phase '+str(phase))
        if phase in (5,8,13,16):require(not valid,'Ambiguous update/resize retained a usable image')
        if phase==15:require(row['captures']==previous['captures'],'Sibling update recaptured our image')
        if phase==2:require(row['captures']==previous['captures'],'Title-only change recaptured pixels')
        if phase in (3,12):require(row['restores']>previous['restores'],'Aligned AES move missed its client image')
        if phase==7:require(row['restores']==previous['restores'],'Normalized no-op move restored its client')
        if phase in (10,11):
            require(row['captures']==previous['captures'],'Small update recaptured whole client')
            require(row['patches']==previous['patches']+1 and
                    row['patched_bytes']==previous['patched_bytes']+64,'Small repair did not copy 16 by 8 pixels')
        if phase in (1,2,3,4,6,9,10,11,12,14):
            x,y,w,h=struct.unpack('<4h',b.memdump(sy['AESCacheWork'],8))
            require((w,h)==((216,100) if phase<8 else (224,108)),
                    'INFO/scroll/size work bounds changed: '+str((x,y,w,h)))
            path=out/('aes-cache-%d.bgra'%phase);frame=b.rawscreen(str(path));pixels=path.read_bytes()
            for yy in range(y,y+h):
                for xx in range(x,x+w):
                    pen=3
                    if phase in (10,11,12) and y+8<=yy<y+16:
                        if x+8<=xx<x+24:pen=4
                        elif phase in (11,12) and x+32<=xx<x+48:pen=5
                    color=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
                    offset=yy*frame.stride+(xx+16)*4
                    require(pixels[offset:offset+3]==color,'AES cache pixels %d at %d,%d'%(phase,xx,yy))
            row['work_pixels']='exact'
        report['aes_cache'].append(row);previous=row
        b.poke16(sy['AESCacheGo'],phase)
    require(get(sy['AESCacheRedraws'],2)>0,'Cached restoration suppressed WM_REDRAW')
    b.bp_clear_all()
