"""Real scanout for shared mouse hide/show and an UPDATE-held scroll repair."""
from types import SimpleNamespace
from native_program import require
from os_boundary import run_to
from gem_render_oracle import DESKTOP_PALETTE,PENS
from test_gem_interactive import pixels
from test_gem_cursor import overlay
from generate_aes_server import layout


def form_overlay(background,point,words):
    result=bytearray(background)
    x,y=point;x-=words[0];y-=words[1]
    for row in range(16):
        for col in range(16):
            bit=0x8000>>col
            if 0<=x+col<640 and 0<=y+row<240:
                if words[21+row]&bit: pen=words[4]
                elif words[5+row]&bit: pen=words[3]
                else: continue
                result[(y+row)*640+x+col]=PENS[pen]
    return bytes((a<<4)|b for a,b in zip(result[::2],result[1::2]))


def physical(bridge,program,foreign,report):
    sy=foreign['symbols'];out=program['output'].parent
    records=[];report['cursor_pixels']=records
    state=layout()['MouseState']['fields']
    marker=program['labels']['native_nmi']
    rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
    colors={rgb[p*3:p*3+3][::-1]:PENS[p] for p in range(16)}
    def reach(phase):
        # The caller publishes a phase after physical completion, then yields.
        # A computing peer can own every NMI entry while that caller is ready.
        condition=f'dw(${sy["AESPhysical"]:x})={phase}'
        bridge.bp_clear_all();bridge.bp_set(marker,condition=condition)
        run_to(bridge,marker,condition=condition,frame_limit=3000,timeout=60)
        frame=bridge.eval_expr('@frame')
        condition=f'@frame>={frame+2}'
        bridge.bp_clear_all();bridge.bp_set(marker,condition=condition)
        run_to(bridge,marker,condition=condition,frame_limit=20,timeout=10)
    def capture(folder):
        folder.mkdir(exist_ok=True)
        frame=bridge.rawscreen(str(folder/'sample.bgra'))
        raw=(folder/'sample.bgra').read_bytes()
        require((frame.width,frame.height)==(672,240),'Unexpected scanout geometry')
        cropped=b''.join(raw[y*frame.stride+64:y*frame.stride+2624] for y in range(240))
        return bytearray(colors[cropped[i:i+3]] for i in range(0,len(cropped),4))
    previous=None
    for phase in range(1,138):
        reach(phase)
        address=int.from_bytes(bridge.memdump(sy['AESMouse'],4),'little')
        raw=bridge.memdump(address,layout()['MouseState']['size'])
        word=lambda n:int.from_bytes(raw[state[n]:state[n]+2],'little')
        point=(word('x'),word('y'))
        visible=phase in (2,4) or 6<=phase<=136
        require(bool(word('visible'))==visible,'Wrong logical visibility')
        folder=out/f'cursor-phase-{phase}'
        actual=capture(folder)
        if not visible:
            if phase==3:
                for y in range(64,120):
                    pen=2 if y<72 else 3 if y<80 else 4
                    require(all(actual[y*640+x]==PENS[pen] for x in range(80,200)),
                            'Hidden scroll/copy/exposed-strip pixels differ')
            if phase==137:
                require(actual==previous,'Custom forms did not restore the exact background')
            else: previous=actual
        else:
            if 6<=phase<=133:
                pen,pos=divmod(phase-6,8)
                words=[(pen+pos)&15,(15-pen+pos)&15,1,pen,(pen+5)&15]
                words += [0xaaaa if row&1 else 0x5555 for row in range(16)]
                words += [0xcccc if pos&1 else 0x3333]*16
                expected=form_overlay(previous,point,words)
            elif phase in (134,135):
                expected=form_overlay(previous,point,[0,0,1,9,1]+[65535]*16+[0]*16)
            else: expected=overlay(SimpleNamespace(pixels=previous),point)
            digest=pixels(bridge,folder,expected,palette=DESKTOP_PALETTE)
            records.append(dict(phase=phase,position=point,sha256=digest))
        require(int.from_bytes(bridge.memdump(sy['cursorDrawn'],2),'little')==visible,
                'Physical pointer disagrees with requested visibility')
        bridge.memload(sy['AESPhysicalGo'],phase.to_bytes(2,'little'))
    bridge.bp_clear_all()
