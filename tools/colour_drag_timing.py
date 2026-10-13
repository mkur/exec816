"""Physical motion submission to independently checked outline scanout."""
import json
from gem_render_oracle import DESKTOP_PALETTE, PENS
from measure_desktop import distribution
from native_program import require
from sio_transaction_trace import BASE_HZ


def exercise(s,point,begin,cancel,move,count=12):
    b=s.b
    sy=json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
    at=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    clock=lambda:b.eval_expr('@clk')&0xffffffff
    def scan():
        path=s.p['output']/'drag-scanout.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
        return b''.join(raw[y*frame.stride+64:y*frame.stride+64+2560] for y in range(240))
    colors={hw:bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1] for pen,hw in enumerate(PENS)}
    inverse={rgb:colors[hw^15] for hw,rgb in colors.items()}
    def visible(background,left,top,width):
        actual=scan()
        for x in range(left,left+width):
            p=(top*640+x)*4
            if actual[p:p+3]!=inverse[background[p:p+3]]:return False
        return True
    samples={'press_to_outline':[],'threshold_packet_to_outline':[],'motion_packet_to_outline':[]}
    for i in range(count):
        move(*point);s.frames(8);background=scan()
        # Begin uses physical press only; no positioning-helper delay belongs
        # to the measurement. A four-phase packet crosses the 4-pixel threshold.
        pressed=begin(point,threshold=False)
        start=clock();b._cmd_ok('MOUSE AT 2000 64 0 -1')
        for _ in range(80):
            s.frames(1)
            left=s.number(sy['outlineLeft'],2);top=s.number(sy['outlineTop'],2)
            right=s.number(sy['outlineRight'],2)
            if s.number(sy['outlineDrawn'],2) and left>=point[0]-4 and visible(background,left,top,right-left):break
        else:raise RuntimeError('Threshold outline never reached scanout')
        samples['press_to_outline'].append(((clock()-pressed)&0xffffffff)/BASE_HZ*1000)
        samples['threshold_packet_to_outline'].append(((clock()-start)&0xffffffff)/BASE_HZ*1000)
        previous=s.number(at('cursorX'),2);s.frames(8)
        start=clock();b._cmd_ok('MOUSE AT 2000 64 0 -1')
        for _ in range(80):
            s.frames(1)
            left=s.number(sy['outlineLeft'],2);top=s.number(sy['outlineTop'],2)
            right=s.number(sy['outlineRight'],2)
            if left>previous-8 and s.number(sy['outlineDrawn'],2) and visible(background,left,top,right-left):break
        else:raise RuntimeError('Moving outline never reached scanout')
        samples['motion_packet_to_outline'].append(((clock()-start)&0xffffffff)/BASE_HZ*1000)
        cancel();move(*point);s.frames(8)
        print('Drag timing sample',i+1,flush=True)
        actual=scan()
        # The source listing above its status strip must be restored exactly.
        # Comparing the entire screen would include legitimate status updates.
        x,y=point
        region=lambda raw:b''.join(raw[(yy*640+x-8)*4:(yy*640+x+104)*4] for yy in range(y-4,y+28))
        require(region(actual)==region(background),'Cancelled application outline changed pixels')
    return {**{name:dict(samples_ms=values,**distribution(values)) for name,values in samples.items()},
        'restoration':'Exact 112x32 source patch including icon/label after every cancellation',
        'scope':'12 physical four-phase packets per case, 2000-cycle electrical submission delay; submission to XOR top-edge scanout, PAL one-frame polling. Includes capture and rendering, excludes positioning-helper delays. Not capture-to-visible or HY4 qualification.'}


def admission(s,source,desk,started):
    """Observe the stable copying caption, excluding transfer progress text."""
    from browser_model import FIELDS as F
    from colour_desktop_model import FIELDS as D
    from gem_desktop_oracle import paint
    from gem_render_oracle import Raster,font_bytes
    b=s.b
    s.rendezvous('(dw($%x)|dw($%x))!=0'%(desk+D['job'],desk+D['job']+2))
    colors={hw:bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1] for pen,hw in enumerate(PENS)}
    x,y,w,h=[s.number(source+F['work']+i*2,2) for i in range(4)]
    font=font_bytes(s.p['output']/s.manifest['font_source'])
    # Existing copy admission opens/examines paths before constructing its UI.
    # Directory I/O can take seconds; do not mistake it for a drawing timeout.
    s.rendezvous('(dw($%x)=28)|((dw($%x)|dw($%x))=0)'%
        (source+F['dialogTree']+54,desk+D['job'],desk+D['job']+2))
    for _ in range(100):
        if s.number(source+F['dialog'],2)==5 and s.number(source+F['dialogTree']+54,2)==28:
            raster=Raster(font)
            title=b.memdump(source+178,65).split(b'\0')[0][:64]
            paint(b,{'GEMBrowser':source,'objc_edit':1},raster,title,(x-8,y-16,x+w+16,y+h+16))
            path=s.p['output']/'drag-admission.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            if all(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]==colors[raster.pixels[yy*640+xx]]
                for yy in range(y+2,y+10) for xx in range(x+8,x+w-8)):
                return ((b.eval_expr('@clk')-started)&0xffffffff)/BASE_HZ*1000
        s.frames(1)
    raise RuntimeError('Copy admission caption never reached scanout: '+repr((x,y,w,h,s.number(source+F['dialog'],2),b.memdump(source+F['status'],128))))
