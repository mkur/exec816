"""Small physical-input/scanout comparison across two loaded panel lifetimes."""
from statistics import median
from gem_render_oracle import Raster, font_bytes, PALETTE, PENS
from gem_desktop_oracle import paint
from native_program import require
from sio_transaction_trace import BASE_HZ
from test_gem_cursor import overlay


def measure(s, panel, move, label, count=6):
    b=s.b
    font=font_bytes(s.p['output']/s.manifest['font_source'])
    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    x,y,w,h=[s.number(panel+34+2*i,2) for i in range(4)]
    move(x+32,y+40);s.frames(5)
    region=(x+5,y+29,x+91,y+51)
    def visible():
        raster=Raster(font)
        paint(b,{'GEMPanel':panel},raster,b'GEM Control Panel',(x-8,y-16,x+w+8,y+h+8))
        packed=overlay(raster,s.saved['pointer'])
        want=b''.join(colors[(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
                      for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
        path=s.p['output']/'button-scanout.bgra'
        frame=b.rawscreen(str(path));raw=path.read_bytes()
        actual=b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]
                        for yy in range(region[1],region[3]) for xx in range(region[0],region[2]))
        return actual==want
    samples=[]
    for _ in range(count):
        target=1-s.number(panel+178+2*24+10,2)
        start=b.eval_expr('@clk')&0xffffffff
        b._cmd_ok('MOUSE AT 2000 0 0 1')
        s.rendezvous('dw($%x)=%d'%(panel+178+2*24+10,target))
        for attempt in range(30):
            if visible():break
            s.frames(1)
        else:raise RuntimeError('Loaded panel feedback did not reach scanout')
        elapsed=((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000
        require(elapsed<500,'Loaded panel press exceeded the bounded smoke limit')
        samples.append(elapsed)
        s.frames(1);b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(15)
    record=dict(model_address=panel,samples_ms=samples,median_ms=median(samples),max_ms=max(samples),
                scope=f'{count} press edges, submission to matching button scanout, frame-granular polling; not a p95 benchmark.')
    if count>=30:
        from measure_desktop import distribution
        record.update(distribution(samples))
        record['scope']=f'{count} press edges, submission to matching button scanout, frame-granular polling; limited appearance comparison.'
    s.saved.setdefault('loaded_panel_feedback',{})[label]=record
    print('Loaded panel feedback:',label,record['median_ms'],record['max_ms'],flush=True)
