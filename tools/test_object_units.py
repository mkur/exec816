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
