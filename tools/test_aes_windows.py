"""Physical GEM control requests before the application acknowledges them."""
from desktop_mouse import schedule
from generate_aes_server import layout
from generate_desktop import layout as desktop_layout
from generate_layers import layout as layers_layout
from native_program import require
from os_boundary import run_to
from pathlib import Path
import adapter_state as adapter
import struct


def physical(b, p, foreign, report):
    sy = foreign['symbols']
    at = lambda mod, n: next(d['address'] for d in p['image']['data']
                            if '_'+mod+'_'+n.upper()+'_' in d['name'])
    get = lambda address, size=2: int.from_bytes(b.memdump(address, size), 'little')
    def reach(condition):
        b.bp_clear_all()
        b.bp_set(p['labels']['native_irq'], condition=condition)
        b.bp_set(p['labels']['done'], condition=adapter.STOPPED)
        original = b.regs
        def registers():
            r = original()
            if int(r['PC'].lstrip('$'),16) == p['labels']['done']:
                require(b.peek16(adapter.STATE) == 65535, 'Guest stopped: '+hex(b.peek16(adapter.STATE)))
            return r
        b.regs = registers
        try:
            run_to(b, p['labels']['native_irq'], condition=condition,
                   timeout=120, frame_limit=6000)
        finally: b.regs = original
    def phase(value):
        print('Await physical phase', value, flush=True)
        reach('dw($%x)=%d' % (sy['AESPhysical'], value))
    def frames(n=4):
        reach('@frame>=%d' % (b.eval_expr('@frame')+n))
    def scan():
        path = Path(p['output']).parent/'outline-scan.bgra'
        image = b.rawscreen(str(path)); raw = path.read_bytes()
        return b''.join(raw[y*image.stride+16*4:y*image.stride+(16+640)*4] for y in range(240))
    position = [320, 120]
    def move(x, y):
        nonlocal position
        position = schedule(b, p, position, (x, y))
        reach('(dw($%x)=%d)&(dw($%x)=%d)' %
              (at('DESKINPUT', 'cursorX'), position[0], at('DESKINPUT', 'cursorY'), position[1]))
    def edge(down):
        b._cmd_ok('MOUSE AT 2000 0 0 '+str(down)); frames()
    b._cmd_ok('MOUSE ST'); b._cmd_ok('KEY ALL up')
    phase(1); frames(100)
    vf = layout()['WindowView']['fields']
    view = get(sy['AESView'], 4)
    service = get(at('DESKSTATE', 'service'), 3)
    df = desktop_layout()['Service']['fields']
    scene = service+df['scene']
    busy = scene+layers_layout()['Scene']['fields']['busy']
    wf = desktop_layout()['Window']['fields']; ws = desktop_layout()['Window']['size']
    windows = [service+df['windows']+i*ws for i in range(4)]
    window = min((w for w in windows if get(w+wf['kind'],1) == 4 and get(w+wf['id'],4)),
                 key=lambda w: get(w+wf['id'],4))
    title = window+wf['title']
    require(b.memdump(title,65) == b'T'*64+b'\0', 'Title was not copied at admission')
    old_focus = get(service+df['focus'], 4)
    old_bounds = b.memdump(view+vf['bounds'], 8)
    # The inactive root title remains visible above the overlapping peer.
    move(17, 20); edge(1); edge(0); phase(2)
    require(get(service+df['focus'], 4) == old_focus, 'Top committed before WM_TOPPED acknowledgment')
    require(get(busy, 1) == 0, 'Scene token survives application wait')
    b.poke16(sy['AESPhysicalGo'], 2); phase(3); frames(100)
    require(get(service+df['focus'], 4) != old_focus, 'Top acknowledgment did not focus application')
    # The left closer of an inactive window topped it without closing. Once
    # focused, release outside and Escape must leave the waiter untouched.
    move(17,20); edge(1); move(60,30); edge(0); frames(10)
    require(get(sy['AESPhysical'])==3, 'Outside closer release delivered a command')
    move(17,20); edge(1); b._cmd_ok('KEY ESC down'); frames(3)
    b._cmd_ok('KEY ESC up'); edge(0); frames(10)
    require(get(sy['AESPhysical'])==3, 'Escape closer cancellation delivered a command')
    # The old right closer is now part of the draggable title.
    move(201, 20); frames(); before_outline = scan()
    edge(1); move(218, 31); edge(0); phase(4)
    move(201, 20); frames()
    require(scan() == before_outline, 'Odd-coordinate outline did not restore exact pixels')
    require(b.memdump(view+vf['bounds'], 8) == old_bounds, 'Move committed before WM_MOVED acknowledgment')
    words = struct.unpack('<8h', b.memdump(sy['AESControl'], 16))
    require(words[4:8] == (26, 20, 200, 120), 'Drag lost pixel coordinates: '+str(words))
    b.poke16(sy['AESPhysicalGo'], 4); phase(5); frames(100)
    require(struct.unpack('<4h', b.memdump(view+vf['bounds'], 8)) == (26, 20, 226, 140),
            'Move acknowledgment did not change geometry')
    move(34, 26); edge(1); edge(0); phase(6)
    require(get(view+vf['shown']) == 1, 'Close committed before WM_CLOSED acknowledgment')
    require(get(busy, 1) == 0, 'Close request retains scene token')
    b.poke16(sy['AESPhysicalGo'], 6); phase(7)
    report['physical_requests'] = dict(top='deferred', move=list(words[4:8]), close='deferred', scene_token=0, outline_pixels='exact', copied_title_bytes=65)
    # New gadgets retain the same application-acknowledged transaction.
    phase(10); frames(100)
    view=get(sy['AESView'],4)
    initial=(32,32,272,192)
    def bounds():return struct.unpack('<4h',b.memdump(view+vf['bounds'],8))
    def message():return struct.unpack('<8h',b.memdump(sy['AESControl'],16))
    require(bounds()==initial,'Initial resizable geometry')
    move(264,184);frames(20);before_size=scan()
    edge(1);move(288,200)
    b._cmd_ok('KEY ESC down');frames(3);b._cmd_ok('KEY ESC up');edge(0);frames(15)
    require(get(sy['AESPhysical'])==10 and bounds()==initial,'Resize Escape failed')
    move(264,184);frames(20)
    require(scan()==before_size,'Cancelled size outline changed pixels')
    move(264,184);edge(1);move(304,208);edge(0);phase(11)
    require(bounds()==initial,'Resize committed before WM_SIZED acknowledgment')
    require(message()[0]==27 and message()[4:8]==(32,32,280,184),'Size request geometry')
    require(get(busy,1)==0,'Resize retains a scene token')
    b.poke16(sy['AESPhysicalGo'],11);phase(12);frames(100)
    require(bounds()==(32,32,312,216),'Resize acceptance')
    # Compare the complete gadget strip with an independent raster. Logical
    # slider size 250/position 1000 gives a 30-pixel thumb at absolute Y=154.
    from gem_render_oracle import Raster, font_bytes, PENS, PALETTE
    from test_desktop_presentation import frame
    raster=Raster(font_bytes(Path(p['output']).parent/'selected/src/vdi/font8x8.c'))
    frame(raster,(32,32,312,216),b'',True,close=True,kind=491,slider=(122,30))
    move(600,220);frames(40);actual=scan()
    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
    hardware={v:rgb[i*3:i*3+3][::-1] for i,v in enumerate(PENS)}
    for y in range(48,216):
        for x in range(296,312):
            offset=y*640+x
            require(actual[offset*4:offset*4+3]==hardware[raster.pixels[offset]],
                'Gadget frame pixel differs at '+str((x,y)))
    observations=[]
    for start,x,y,expected in ((12,304,56,2),(14,304,192,3),(16,304,80,0)):
        phase(start);move(x,y);edge(1);edge(0);phase(start+1)
        words=message();require(words[0]==24 and words[4]==expected,'Arrow/page request '+str(words))
        observations.append(list(words));b.poke16(sy['AESPhysicalGo'],start+1)
    phase(18);move(304,166);edge(1);move(304,50);edge(0);phase(19)
    require(message()[0]==26 and message()[4]==0,'Thumb top endpoint')
    require(get(view+vf['vslide'])==1000,'Thumb changed client value before acknowledgment')
    b.poke16(sy['AESPhysicalGo'],19);phase(20);frames(100)
    require(get(view+vf['vslide'])==0,'Thumb acknowledgment')
    move(304,130);edge(1);edge(0);phase(21)
    require(message()[0]==24 and message()[4]==1,'Page down request')
    b.poke16(sy['AESPhysicalGo'],21);phase(22)
    move(304,78);edge(1);move(304,230);edge(0);phase(23)
    require(message()[0]==26 and message()[4]==1000,'Thumb bottom endpoint')
    b.poke16(sy['AESPhysicalGo'],23);phase(24)
    report['gadgets']=dict(resize=[32,32,280,184],escape_cancel=True,
        deferred_geometry=True,arrow_pages=[2,3,0,1],slider_endpoints=[0,1000],
        deferred_slider=True,scene_token=0,frame_pixels=2688,outline_pixels="exact")
    b.bp_clear_all()
