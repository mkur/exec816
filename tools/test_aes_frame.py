"""Private emitted frame policy, publication, pixels and call/feedback observer."""
import hashlib
from pathlib import Path

import adapter_state as adapter
from generate_aes_server import layout as aes_layout, ABI as AES_ABI
from generate_desktop import layout, ABI
from gem_render_oracle import Raster, font_bytes, PENS, DESKTOP_PALETTE
from library_paths import read_source
from native_program import ROOT, require
from os_boundary import run_to
from sio_transaction_trace import BASE_HZ
from desktop_raster import frame as draw_frame, menu_bar, tile

TEXT_FIELDS=tuple(AES_ABI['constants'][name] for name in ('WF_NAME','WF_INFO'))
SLIDER_FIELDS=tuple(AES_ABI['constants'][name] for name in
                    ('WF_VSLIDE','WF_VSLSIZE','WF_HSLIDE','WF_HSLSIZE'))
FRAME_FIELDS=TEXT_FIELDS+SLIDER_FIELDS

ROOTS = ['FrameNative','FrameBusy','FrameIcon','FrameIconBounds','FrameWaiting','FramePhase','FrameGo',
         'FramePoint','FrameHeld','FramePB','FrameField','FrameHandle',
         'FrameResult','FrameStatus','FrameSequence','FrameView',
         'FrameCallBegin','FrameCallEnd','FrameRelease']


def instrument(out):
    (out/'frameprobe.act').write_text('''MODULE FRAMEPROBE
USE EXEC
USE AESSTATE
USE AESGATE
USE HEAPCORE
USE AESTYPES
USE AESWINDOWSTATE
USE DESKSTATE
USE DESKCORE
USE LAYERTYPES
USE LAYERS
USE REGIONS
PUBLIC CARD ARRAY stats(2)
PUBLIC BYTE busy,icon
PUBLIC LAYERTYPES.Rect iconBounds
PUBLIC PROC Observe(AESSTATE.Client POINTER client AESTYPES.Request POINTER request)

  LET service=AESSTATE.Get()
  IF service.sceneOwner<>EXEC.FindTask(NULL) THEN
    HEAPCORE.Abort($fc62)
  FI
  IF icon<>0 THEN
    BEGIN
      LET desktop=DESKSTATE.Get()
      LET window=AESWINDOWSTATE.Handle(client,request.intin(0))
      IF icon=1 THEN
        DESKCORE.Iconify(desktop,window)
        BEGIN
          LET layer=LAYERS.Find(@desktop.scene,window.layer)
          REGIONS.Copy(@layer.bounds,@iconBounds)
        END
      ELSE
        IF DESKCORE.Top(desktop,window)<>LAYERTYPES.OK THEN
          HEAPCORE.Abort($fc63)
        FI
      FI
      icon=0
    END
  FI
  stats(IF AESGATE.SystemOwned()<>0 THEN BYTE(1) ELSE BYTE(0) FI)==+1

RETURN
ENDMODULE
''')
    text=read_source(ROOT/'lib/aes/aeswindow.act')
    text=text.replace('USE EXEC\n','USE EXEC\nUSE FRAMEPROBE\n',1)
    if 'PUBLIC CARD FUNC Frame(' in text:
        start=text.index('PUBLIC CARD FUNC Frame(')
        at=text.index('\n\n',start)+2
        text=text[:at]+('  FRAMEPROBE.Observe(client,request)\n'
            '  IF FRAMEPROBE.busy<>0 THEN\n    RETURN(AESTYPES.PENDING)\n  FI\n')+text[at:]
    else:
        # Freeze the GF4 parent with the same observation, before extraction.
        start=text.index('PUBLIC CARD FUNC Request(')
        at=text.index('\n\n',start)+2
        text=text[:at]+'''  IF request.operation=AESTYPES.OP_SET AND
      (request.intin(1)=AESTYPES.WF_NAME OR request.intin(1)=AESTYPES.WF_INFO
      OR request.intin(1)=AESTYPES.WF_VSLIDE OR request.intin(1)=AESTYPES.WF_VSLSIZE) THEN
    FRAMEPROBE.Observe(client,request)
  FI
'''+text[at:]
    (out/'aeswindow.act').write_text(text)


def setup(symbols):
    result=''
    for name,field in [('FrameNative','@FRAMEPROBE.stats(0)'),
                       ('FrameBusy','@FRAMEPROBE.busy'),
                       ('FrameIcon','@FRAMEPROBE.icon'),
                       ('FrameIconBounds','@FRAMEPROBE.iconBounds'),
                       ('FrameWaiting','@service.windowPending')]:
        result+=f'  BEGIN\n    LET target=LONGCARD POINTER(${symbols[name]:x})\n    target^=LONGCARD(ADDRESS({field}))\n  END\n'
    return result


def physical(b,p,foreign,report):
    b.profile_start()
    sy=foreign['symbols'];out=Path(p['output']).parent
    get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
    value=lambda name,size=2:get(sy[name],size)
    at=lambda module,name:next(d['address'] for d in p['image']['data']
                              if '_'+module+'_'+name.upper()+'_' in d['name'])
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        original=b.regs
        def registers():
            r=original()
            if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                raise RuntimeError('Frame fixture stopped: '+hex(get(adapter.STATE)))
            return r
        b.regs=registers
        try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        finally:b.regs=original
    def frames(n):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    def point(phase,step):
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(sy['FramePhase'],phase,sy['FramePoint'],step))
    records=layout();wf=records['Window']['fields'];df=records['Service']['fields']
    vf=aes_layout()['WindowView']['fields']
    font=font_bytes(out/'selected/src/vdi/font8x8.c')
    rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
    colors={v:rgb[i*3:i*3+3][::-1] for i,v in enumerate(PENS)}
    def state():
        desktop=get(at('DESKSTATE','service'),3);focus=get(desktop+df['focus'],4)
        view=value('FrameView',4)
        raw=b.memdump(view,aes_layout()['WindowView']['size'])
        view_state={n:int.from_bytes(raw[vf[n]:vf[n]+size],'little') for n,size in
                    [('vslide',2),('vsize',2),('hslide',2),('hsize',2),('shown',2),('kind',2),('revision',4)]}
        for n in ('bounds','work'):
            view_state[n]=[int.from_bytes(raw[vf[n]+2*i:vf[n]+2*i+2],'little',signed=True) for i in range(4)]
        windows=[]
        for index in range(ABI['constants']['WINDOWS']):
            address=desktop+df['windows']+index*records['Window']['size']
            raw=b.memdump(address,records['Window']['size'])
            number=lambda n,size=2:int.from_bytes(raw[wf[n]:wf[n]+size],'little')
            if number('id',4)==0:continue
            windows.append(dict(id=number('id',4),handle=number('gui'),kind=number('frameKind'),
                title=raw[wf['title']:wf['title']+65].split(b'\0')[0].decode(),
                info=raw[wf['info']:wf['info']+65].split(b'\0')[0].decode(),
                slider=[number('sliderTop'),number('sliderHeight')],
                hslider=[number('sliderLeft'),number('sliderWidth')],
                iconified=number('iconified',1),visual_revision=number('visualRevision',4),active=number('id',4)==focus))
        return dict(view=view_state,windows=windows)
    def scan(phase):
        path=out/f'frame-{phase:02d}.bgra';f=b.rawscreen(str(path));raw=path.read_bytes()
        return f,raw
    def crop(f,raw):
        return b''.join(raw[y*f.stride+(x+16)*4:y*f.stride+(x+17)*4]
                        for y in range(32,192) for x in range(32,320))
    def pixels(f,raw,s,phase,include_menu=True,changed=None):
        # The fixture never paints client work. Check every exposed frame pixel
        # against the independent frame raster, excluding application work.
        raster=Raster(font)
        area=[]
        for index,bounds in [(0,(32,32,272,192)),(2,(80,64,320,192))]:
            window=s['windows'][index]
            shown=index==0 or 23<=phase<=30
            if not shown:continue
            if window['iconified']:
                bounds=tuple(int.from_bytes(b.memdump(value('FrameIconBounds',4)+2*i,2),'little',signed=True) for i in range(4))
                tile(raster,bounds,window['title'].encode())
            else:
                draw_frame(raster,bounds,window['title'].encode(),window['active'],3,bool(window['kind']&2),
                           window['kind'],tuple(window['slider']),window['info'].encode(),tuple(window['hslider']))
            l,t,r,bt=bounds;work=(l+8,t+21,r-16,bt-(11 if window['kind']&(32|3584) else 2))
            if changed:
                handle,field=changed
                if window['handle']!=handle:continue
                if window['iconified'] and field==TEXT_FIELDS[1]:region=(0,0,0,0)
                elif field==TEXT_FIELDS[0]:region=(l,t,r,t+11)
                elif field==TEXT_FIELDS[1]:region=(l,t+11,r,t+21)
                elif field in (AES_ABI['constants']['WF_HSLIDE'],AES_ABI['constants']['WF_HSLSIZE']):region=(l,bt-11,r,bt)
                else:region=(r-16,t+11,r,bt)
            else:region=bounds
            if window['iconified']:work=(0,0,0,0)
            for y in range(t,bt):
                for x in range(l,r):
                    if (region[0]<=x<region[2] and region[1]<=y<region[3]
                        and not (work[0]<=x<work[2] and work[1]<=y<work[3])):area.append((x,y,index))
        digest=hashlib.sha256()
        for x,y,index in area:
            if index==0 and 23<=phase<=30 and 80<=x<320 and 64<=y<192:continue
            offset=y*f.stride+(x+16)*4;actual=raw[offset:offset+3]
            if actual!=colors[raster.pixels[y*640+x]]:return None
            digest.update(actual)
        if not include_menu:return digest.hexdigest()
        active=next((w for w in s['windows'] if w['active']),None)
        menu_bar(raster,((active['title'] or 'Exec816') if active else 'Exec816').encode())
        for y in range(11):
            for x in range(640):
                offset=y*f.stride+(x+16)*4
                if raw[offset:offset+3]!=colors[raster.pixels[y*640+x]]:return None
        return digest.hexdigest()
    report['frame_attributes']=[]
    for phase in range(1,37):
        print('Frame attribute phase',phase,flush=True)
        point(phase,0);frames(30)
        before_frame,before_pixels=scan(phase)
        before_stats=[get(value('FrameNative',4)+2*i) for i in range(2)]
        b.poke16(sy['FrameGo'],phase*3-2)
        point(phase,3)
        field=value('FrameField');sequence=value('FrameSequence',4)
        direct=field in (TEXT_FIELDS if report['frame_local']=='text' else
                         FRAME_FIELDS if report['frame_local']=='all' else ())
        expected_sequence=1 if phase in (1,27) else 0
        require(sequence==expected_sequence,f'Frame phase {phase}: unexpected RPC delta {sequence}')
        stats=[get(value('FrameNative',4)+2*i)-before_stats[i] for i in range(2)]
        if field in FRAME_FIELDS:
            require(stats[0]>0 if direct else stats[0]==0,f'Frame phase {phase}: wrong execution Task')
            if direct:require(stats[1]==0,f'Frame phase {phase}: direct setter reached RPC')
        s=state()
        if phase==5:require(s['windows'][0]['title']=='T'*64,'Title scratch was not copied')
        row=dict(phase=phase,field=field,handle=value('FrameHandle'),held=value('FrameHeld'),pb=value('FramePB'),
                 sequence_delta=sequence,helper_attempts=stats,status=value('FrameStatus'),
                 state=s,returned_clock=b.eval_expr('@clk'))
        if field in FRAME_FIELDS and row['status']==0:
            # Device drawing is fenced at return, but rawscreen is the last
            # scanout. Keep the caller parked (and outer UPDATE held) while
            # that image catches up, as in the frame-atlas fixture.
            frames(2)
            f,raw=scan(phase)
            require(pixels(f,raw,s,phase,include_menu=False,changed=(value('FrameHandle'),field)) is not None,
                    f'Frame phase {phase}: frame pixels incomplete at return')
            row['synchronous_frame_pixels']='exact'
            row['scanout_settle_frames']=2
        elif row['held']:
            f,raw=scan(phase)
            require(crop(f,raw)==crop(before_frame,before_pixels),
                    f'Frame phase {phase}: deferred field repainted before UPDATE release')
            row['held_pixels_unchanged']=True
        b.poke16(sy['FrameGo'],phase*3-1);point(phase,4)
        row['released_clock']=b.eval_expr('@clk')
        # Feedback is checked at one-PAL-frame intervals, after actual pixels
        # match the oracle. Keep deferred work inside the completion window.
        for attempt in range(120):
            f,raw=scan(phase);pixel_hash=pixels(f,raw,s,phase)
            if pixel_hash is not None:break
            frames(1)
        require(pixel_hash is not None,f'Frame phase {phase}: completed frame pixels differ')
        row.update(frame_pixels='exact',frame_sha256=pixel_hash,
                   feedback_clock=b.eval_expr('@clk'),feedback_sampling='one PAL frame upper bound')
        report['frame_attributes'].append(row)
        b.poke16(sy['FrameGo'],phase*3)
    b.bp_clear_all()


def timings(out,foreign,report):
    from sio_transaction_trace import read_events
    sy=foreign['symbols']
    names={sy[n]:n for n in ('FrameCallBegin','FrameCallEnd','FrameRelease')}
    events=[(t,names[int(e[4],16)]) for t,e in read_events(out/'emulator.log',{'cpu'})
            if int(e[4],16) in names]
    require(len(events)==36*3,'Incomplete exact setter brackets')
    draws=[t for t,e in read_events(out/'emulator.log',{'cpu'})
           if int(e[4],16)==sy['ExecAESFrameApply']]
    for row,index in zip(report['frame_attributes'],range(0,len(events),3)):
        (start,a),(end,z),(release,r)=events[index:index+3]
        require((a,z,r)==('FrameCallBegin','FrameCallEnd','FrameRelease'),'Setter marker order changed')
        row['caller_draw_calls']=sum(start<=t<=end for t in draws)
        if row['phase']==35:require(row['caller_draw_calls']>0,'Iconified title did not paint in caller')
        if row['phase']==36:require(row['caller_draw_calls']==0,'Unlinked iconified info drew pixels')
        row['call_ticks']=end-start;row['call_ms']=(end-start)/BASE_HZ*1000
        feedback=(row['feedback_clock']-start) % (1<<32)
        row['feedback_ms_upper']=feedback/BASE_HZ*1000
        row['held_observation_ticks']=release-end if row['held'] else 0
        # Check the menu title independently in the retained final scanout.
        raster=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
        active=next((w for w in row['state']['windows'] if w['active']),None)
        menu_bar(raster,((active['title'] or 'Exec816') if active else 'Exec816').encode())
        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
        colors={v:rgb[i*3:i*3+3][::-1] for i,v in enumerate(PENS)}
        raw=(out/f'frame-{row["phase"]:02d}.bgra').read_bytes()
        require(len(raw)==672*240*4,'Pinned frame scanout dimensions changed')
        menu=bytearray()
        for y in range(11):
            for x in range(640):
                offset=y*672*4+(x+16)*4
                pixel=raw[offset:offset+3]
                require(pixel==colors[raster.pixels[y*640+x]],
                        'Renamed menu pixels differ at phase '+str(row['phase']))
                menu.extend(pixel)
        row['menu_pixels']='exact';row['menu_sha256']=hashlib.sha256(menu).hexdigest()
    report['frame_timing_scope']='Exact external C call brackets; inclusive Task/preemption time. Pixel completion sampled at PAL frame boundaries. Functional UPDATE-held cases include the explicit hold; phases 31-34 are unheld setter-to-feedback observations. No percentile/hosted latency qualification.'
