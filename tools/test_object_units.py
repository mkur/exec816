"""Caller-local object unit boundaries, builder budgets and donor pixel oracle."""
import sys
from native_program import ROOT, require


def instrument(out):
    source=(ROOT/'ports/gem4xe/adapter/gem-vbxe.c').read_text()
    source=source.replace('#include "gem-drawing.h"', '#include "gem-drawing.h"\n'
        'extern void ObjectBorrowProbe(UWORD);\nextern void ObjectListProbe(const UBYTE *,UWORD);')
    needle='    status=DisplayEnter(grant);'
    require(source.count(needle)==1,'Borrow admission changed')
    source=source.replace(needle,'    ObjectBorrowProbe(bottom-top);\n'+needle)
    needle='    if (commandCount && !fault) latch(VbxeOwnerSubmit(&display,commands,commandCount));'
    require(source.count(needle)==1,'Builder publication changed')
    source=source.replace(needle,'    if (commandCount && !fault) ObjectListProbe(commands,commandCount);\n'+needle)
    path=out/'gem-vbxe.c';path.write_text(source)
    return path


def physical(b,p,foreign,report,reach):
    from desktop_mouse import schedule
    from gem_render_oracle import PALETTE,PENS
    from test_gem_cursor import overlay
    from types import SimpleNamespace
    sys.path.insert(0,str(ROOT/'build/gem-vdi/upstream/tools'))
    import aesref as a
    import vdiref as v
    sy=foreign['symbols'];out=p['output'].parent
    rgb=bytes((c&254)+(c>>7) for c in PALETTE)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    position=[320,120];observations=[]
    for i,height in enumerate((16,17,31,32,33,14,16,16,26,33,12)):
        reach('dw($%x)=%d'%(sy['ObjectPhase'],i+1))
        # Intersect subsequent draws, then verify both overlay and restoration.
        position=schedule(b,p,position,(280,60) if i%2==0 else (620,220))
        reach('@frame>=%d'%(b.eval_expr('@frame')+40))
        device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
        button=5<=i<=8
        obj=a.Obj(-1,-1,-1,a.G_BUTTON if button else a.G_BOX,
                  a.LASTOB|(a.EXIT if 6<=i<=8 else 0)|(a.DEFAULT if i in (7,8) else 0),
                  a.SELECTED|a.DISABLED if i==8 else a.SELECTED if i==10 else 0,
                  0 if button else 0x1178,17,49,608,height)
        aes=a.AES(device,[obj],{0:a.Text('Wide')});aes.gsx_start()
        aes.gsx_sclip(a.Rect(19,52,603,24) if i==9 else a.Rect(8,40,624,184))
        aes.ob_draw(0,0)
        packed=device.dev.s.mem[:76800]
        model=SimpleNamespace(pixels=[(value>>shift)&15 for value in packed for shift in (4,0)])
        expected=overlay(model,position)
        path=out/f'object-{i+1}.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
        for y in range(40,224):
            for x in range(8,632):
                want=colors[(expected[(y*640+x)//2]>>(0 if x&1 else 4))&15]
                at=y*frame.stride+(x+16)*4
                require(raw[at:at+3]==want,f'Object unit {i+1} pixel {x},{y}')
        observations.append(dict(case=i+1,borrows=b.peek16(sy['ObjectBorrows']),
            rows=[b.peek16(sy['ObjectRows']+n*2) for n in range(4)],lists=b.peek16(sy['ObjectLists']),pixels=624*184))
        b.poke16(sy['ObjectGo'],i+1)
    report['object_units']=observations
    # The same extracted routine serves caller-owned and retained trees. Keep
    # this oracle on the pinned, unmodified donor algorithm, including borders.
    cases=((20,1,41,25,0x1178,0,0),(20,3,41,25,0x2173,0,0),
        (20,-1,41,25,0x0172,0,0),(20,-3,41,25,0x4170,0,0),
        (20,0,41,25,0x1189,0,0),(20,0,41,25,0x1170,0,0),
        (20,2,5,5,0x0172,0,0),(20,3,6,6,0x1178,0,0),
        (20,3,5,5,0x1178,0,0),(25,2,41,25,0x1178,0,0),
        (20,2,41,25,0x2173,a.SELECTED|a.DISABLED,0),
        (20,-2,41,25,0x1178,a.SELECTED,0),
        (20,-3,41,25,0x2173,0,1),(20,-3,41,25,0x2173,0,2),
        (20,-3,41,25,0x2173,0,3),(20,-3,41,25,0x2173,0,4),
        (20,3,41,33,0x2173,0,0),(20,-2,41,33,0x1178,a.DISABLED,0),
        (20,2,41,25,0x1140,0,0),(20,1,90,42,0x1178,0,0),
        (20,-3,41,25,0x2173,0,5))
    report['box_pixels']=[]
    for i,(kind,th,width,height,color,state,edge) in enumerate(cases):
        reach('dw($%x)=%d'%(sy['ObjectPhase'],12+i))
        position=schedule(b,p,position,(68,87) if i%2==0 else (620,220))
        reach('@frame>=%d'%(b.eval_expr('@frame')+40))
        device=v.VDI();device.call(v.V_OPNWK,(),v.WORK_IN)
        device.dev.fill_rect(8,40,631,223,5)
        # Hosted WidgetFill rejects empty/negative interiors. The donor VDI
        # instead orders their reversed endpoints; use its frame-only oracle
        # for those pre-existing degenerate cases.
        tree=[a.Obj(-1,1 if i==19 else -1,2 if i==19 else -1,
                    a.G_IBOX if i in (7,8,18) else kind,0 if i==19 else a.LASTOB,
                    state,((th&255)<<16)|color,57,81,width,height)]
        if i==19:
            tree.extend((a.Obj(2,-1,-1,a.G_BOX,0,0,0xff1172,10,8,30,16),
                a.Obj(0,-1,-1,a.G_BUTTON,a.SELECTABLE|a.EXIT|a.DEFAULT|a.LASTOB,
                      a.SELECTED|a.DISABLED,0,25,12,48,16)))
        aes=a.AES(device,tree,{0:a.Text('Wide')});aes.gsx_start()
        l,t,r,bottom=(58 if edge==1 else 8,82 if edge==3 else 40,
                      97 if edge==2 else 632,105 if edge==4 else 224)
        clips=((8,40,73,224),(79,40,632,224)) if edge==5 else ((l,t,r,bottom),)
        for l,t,r,bottom in clips:
            aes.gsx_sclip(a.Rect(l,t,r-l,bottom-t));aes.ob_draw(0,8)
        if i==18:
            # Existing hosted patterned-box fallback is the white stipple,
            # not a claim of general GEM pattern support. Preserve its pixels.
            for y in range(83,104):
                for x in range(59,96):
                    if (x+y)%2==0:device.dev.fill_rect(x,y,x,y,0)
        model=SimpleNamespace(pixels=[(value>>shift)&15 for value in device.dev.s.mem[:76800] for shift in (4,0)])
        expected=overlay(model,position)
        path=out/f'box-{i}.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
        for y in range(40,224):
            for x in range(8,632):
                at=y*frame.stride+(x+16)*4
                want=colors[(expected[(y*640+x)//2]>>(0 if x&1 else 4))&15]
                require(raw[at:at+3]==want,f'Box case {i} pixel {x},{y}')
        report['box_pixels'].append(dict(case=i,borrows=b.peek16(sy['ObjectBorrows']),
            lists=b.peek16(sy['ObjectLists']),pixels=624*184))
        b.poke16(sy['ObjectGo'],12+i)
