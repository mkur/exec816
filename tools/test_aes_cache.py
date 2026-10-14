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
    for phase in range(1,32):
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
                              [('identity',4),('revision',4),('width',2),('height',2),('valid',1),('pinned',1)]]})
        valid=[s for s in slots if s['identity']==identity and s['valid']]
        row=dict(phase=phase,slots=slots,captures=get(at('DESKCACHE','captures')),
                 restores=get(at('DESKCACHE','restores')),
                 patches=get(at('DESKCACHE','patches')),
                 patched_bytes=get(at('DESKCACHE','patchedBytes')))
        require(not any(s['pinned'] for s in slots),'Settled AES cache is pinned')
        if phase in (1,2,3,4,6,7,9,10,11,12,14,15):require(valid,'Missing eligible AES image at phase '+str(phase))
        if phase in (5,8,13,16):require(not valid,'Ambiguous update/resize retained a usable image')
        if phase in (17,18,19,21,24,25,26):require(valid,'Missing preserved source at phase '+str(phase))
        if phase in (20,23):require(not valid,'Hidden change/eviction retained preserved source')
        if valid:
            require((valid[0]['width'],valid[0]['height'])==((240,144) if phase<8 else (248,152)),
                    'Snapshot does not use outer geometry')
        if phase>=27:
            require(valid,'Frame update did not produce a usable image')
        if phase in (27,29):
            require(row['captures']==previous['captures']+1,'Changed frame was not recaptured')
        if phase in (28,30,31):
            require(row['captures']==previous['captures'],'Unchanged frame/exposure recaptured pixels')
        if phase==31:
            require(row['restores']==previous['restores']+1,
                    'Whole-window exposure did not retire exactly one body copy')
        if phase in (19,31):
            require(row['restores']>previous['restores'],'Preserved exposure missed its image')
            require(row['captures']==previous['captures'] and row['patches']==previous['patches'],
                    'Preserved exposure caused cache maintenance')
        if phase==15:require(row['captures']==previous['captures'],'Sibling update recaptured our image')
        if phase==2:require(row['captures']==previous['captures'],'Title-only change recaptured pixels')
        if phase in (3,12):require(row['restores']==previous['restores'],'Copied AES move replayed its client image')
        if phase==7:require(row['restores']==previous['restores'],'Normalized no-op move restored its client')
        if phase in (10,11):
            require(row['captures']==previous['captures'],'Small update recaptured whole client')
            require(row['patches']==previous['patches']+1 and
                    row['patched_bytes']==previous['patched_bytes']+64,'Small repair did not copy 16 by 8 pixels')
        if phase in (1,2,3,4,6,9,10,11,12,14,26):
            x,y,w,h=struct.unpack('<4h',b.memdump(sy['AESCacheWork'],8))
            require((w,h)==((216,112) if phase<8 else (224,120)),
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
        if phase in (27,29,31):
            from gem_render_oracle import Raster, font_bytes, PENS
            from test_desktop_presentation import frame as draw_frame
            raster=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
            slider=tuple(int.from_bytes(source[window['fields'][n]:window['fields'][n]+2],'little')
                         for n in ('sliderTop','sliderHeight'))
            draw_frame(raster,(360,48,608,200),b'Preserved source',True,3,True,
                       1|2|8|16|32|64|128|256,slider,b'Frame saved')
            path=out/('aes-cache-frame-%d.bgra'%phase)
            raw=b.rawscreen(str(path));pixels=path.read_bytes()
            for yy in range(48,200):
                for xx in range(360,608):
                    pen=PENS.index(raster.pixels[yy*640+xx])
                    color=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
                    offset=yy*raw.stride+(xx+16)*4
                    require(pixels[offset:offset+3]==color,'Frame pixels %d at %d,%d'%(phase,xx,yy))
            row['frame_pixels']='exact'
        if phase==25:
            menu_restores=get(at('DESKMENUCACHE','restores'))
            def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY ESC down');frames(3)
            b._cmd_ok('KEY ESC up');b._cmd_ok('KEY CTRL up');frames(100)
            require(get(at('DESKMENU','menu'),1)==2,'Mixed-owner menu did not open')
            b._cmd_ok('KEY ESC down');frames(3);b._cmd_ok('KEY ESC up');frames(100)
            require(get(at('DESKMENUCACHE','restores'))==menu_restores+1,
                    'Mixed-owner menu missed its saved background')
            row['mixed_policy_menu_restore']=True
        report['aes_cache'].append(row);previous=row
        b.poke16(sy['AESCacheGo'],phase)
    # The emitted fixture checks genuine exposure after the final phase.
    b.bp_clear_all()
