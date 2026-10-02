"""Read-only event/serial/scanout observations for the interactive workload."""
import hashlib
import json
from pathlib import Path
import adapter_state as adapter
from native_program import require
from os_boundary import run_to
from gem_render_oracle import PENS, PALETTE
from test_gem_interactive import scene


def latency(b,p,foreign,folder,wrap=False,source=None):
    sy=foreign['symbols']; samples=[]
    read=lambda k,n=2:int.from_bytes(b.memdump(sy[k],n),'little')
    ex=lambda k:f'dw(${sy[k]:x})'
    phase=p['labels']['SD_PHASE']; posts=p['labels']['SD_POSTS']
    capture=p['build']['memory']['input_storage']['CAPTURE']
    active=f'(db(${phase:x})>0)&(db(${phase:x})<13)'
    def reach(condition,label='native_irq'):
        b.bp_clear_all(); b.bp_set(p['labels'][label],condition=condition)
        run_to(b,p['labels'][label],condition=condition,frame_limit=5000,timeout=75)
    def point():
        return dict(tick=b.peek16(adapter.VBI_COUNT),frame=b.eval_expr('@frame'),
                    phase=b.peek(phase)[0],terminal_posts=b.peek16(posts))
    reach(f'{ex("initialReady")}=1','native_nmi')
    for index,key in enumerate(('A','B','C')):
        reach(active)
        if wrap and index==0: b.poke16(adapter.VBI_COUNT,65534)
        item=dict(key=key,stimulus=point())
        before=b.peek(capture+1)[0]; received=read('received'); submitted=read('submitted')
        require(b._cmd_ok(f'KEY {key} down')['raw_scan'],'Physical matrix stimulus required')
        reach(f'db(${capture+1:x})!={before}')
        raw=b.memdump(capture+48+(before&63)*8,8)
        item['capture']=dict(**point(),record=raw.hex(),event_tick=int.from_bytes(raw[2:4],'little'))
        b._cmd_ok(f'KEY {key} up')
        reach(f'{ex("received")}>{received}','native_nmi')
        item['consumption']=dict(**point(),capture_tick=read('lastCapture'),consume_tick=read('lastConsume'))
        event=b.memdump(sy['event'],24)
        item['consumption']['event']=event.hex()
        require(event[10:12]==bytes((1,1)),'Latency requires native timestamped KEY, not injected input')
        require(item['consumption']['capture_tick']==item['capture']['event_tick'],'Wrong captured event')
        reach(f'({ex("submitted")}>{submitted})&({ex("renderTile")}=1)','native_nmi')
        packet_count=read('submitted')
        item['submission']=dict(**point(),submit_tick=read('lastSubmit'),packet=packet_count)
        # Only the first text tile is compared: unrelated disk progress can
        # legitimately repaint elsewhere while a physical transfer continues.
        packed=scene(source or folder,bytes(range(97,98+index)))
        rgb=bytes((v&254)+(v>>7) for v in PALETTE); hardware=[None]*16
        for pen,hw in enumerate(PENS):hardware[hw]=rgb[pen*3:pen*3+3][::-1]
        expected=b''.join(hardware[v>>4]+hardware[v&15] for y in range(58,66) for v in packed[y*320+16:y*320+48])
        scans=[]
        for attempt in range(18):
            path=folder/f'latency-{index}-{attempt}.bgra'; frame=b.rawscreen(str(path)); raw_pixels=path.read_bytes()
            actual=b''.join(raw_pixels[y*frame.stride+(x+16)*4:y*frame.stride+(x+16)*4+3] for y in range(58,66) for x in range(32,96))
            scan=dict(**point(),matches=actual==expected,sha256=hashlib.sha256(actual).hexdigest()); scans.append(scan)
            if scan['matches']:break
            reach(f'@frame>{b.eval_expr("@frame")}','native_nmi')
        item['scanouts']=scans
        item['latency_ticks']=(scans[-1]['tick']-item['capture']['event_tick'])&65535
        reach(f'{ex("collected")}>={packet_count}','native_nmi')
        item['completion']=dict(**point(),complete_tick=read('lastComplete'))
        item['wire_overlap']=(all(0<v['phase']<13 for v in (item['capture'],item['submission'],scans[-1])) and
                              len({v['terminal_posts'] for v in (item['capture'],item['submission'],scans[-1])})==1)
        samples.append(item)
        (folder/'latency.json').write_text(json.dumps(samples,indent=2)+'\n')
        require(scans[-1]['matches'],'No visible text update')
        require(item['latency_ticks']<=16,'Keyboard latency exceeded sixteen PAL ticks')
    require(any(s['wire_overlap'] for s in samples),'No input/render progress within an active serial transaction')
    if wrap:require(any(s['capture']['event_tick']>s['scanouts'][-1]['tick'] for s in samples),'Tick wrap not exercised')
    b._cmd_ok('KEY ESC down'); b.bp_clear_all()
    return dict(samples=samples,maximum_ticks=max(s['latency_ticks'] for s in samples),wrap=wrap)
