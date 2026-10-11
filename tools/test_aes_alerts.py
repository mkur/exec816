"""Physical alert acceptance and independent donor-mask/text pixels."""
import ast,struct
from native_program import ROOT,require


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from desktop_mouse import schedule
    from generate_aes_server import expected_layout
    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
    from control_panel_oracle import draw
    import adapter_state as adapter
    sy=foreign['symbols'];position=[320,120]
    def get(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
    def frames(n=20):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    def phase(n):
        print('Alert phase',n,flush=True)
        reach('(dw($%x)=%d)|(dw($%x)!=0)'%(sy['AESAlertPhase'],n,sy['AESFailures']));frames(80)
        require(get(sy['AESFailures'])==0,'Alert target assertion '+str(get(sy['AESFirstFailure'])))
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    def move(x,y):
        nonlocal position
        position=schedule(b,p,position,(x,y))
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),position[0],at('cursorY'),position[1]))
    def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames()
    def click(x,y):move(x,y);edge(1);edge(0)
    def key(name):b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up');frames(15)
    def tree(who=0):
        c=get(sy['AESAlertContext']+who*4,4)
        session=get(c+dict(expected_layout())['C context form'],4)
        require(session!=0,'No alert session')
        return get(session,4)
    def button(index,who=0):
        t=tree(who);o=t+index*24
        return get(t+16)+get(o+16)+get(o+20)//2,get(t+18)+get(o+18)+8
    donor=ast.parse((ROOT/'build/gem-vdi/upstream/tools/gemdata.py').read_text())
    masks=next(ast.literal_eval(n.value) for n in donor.body if isinstance(n,ast.Assign)
        and any(isinstance(t,ast.Name) and t.id=='ALERT_ICONS' for t in n.targets))
    report['alert_pixels']=[]
    def pixels(icon,name,covered=None):
        move(620,230);frames(30)
        t=tree();objects=[list(struct.unpack('<hhhHHHIhhhh',b.memdump(t+i*24,24))) for i in range(10)]
        x,y,w,h=objects[0][7:11];labels={}
        for i,o in enumerate(objects):
            if o[3] in (26,28):labels[i]=b.memdump(o[6],41).split(b'\0')[0].decode();o[6]=i
        objects[0][7]=objects[0][8]=0
        raster=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
        draw(raster,objects,labels,(x,y,x+w,y+h),7)
        if icon:
            words=masks[('NOTE','QUEST','STOP')[icon-1]]
            for yy in range(32):
                for xx in range(32):
                    if words[yy*2+xx//16] & (0x8000>>(xx%16)):
                        raster.pixels[(y+16+yy)*640+x+16+xx]=PENS[1]
        path=p['output'].parent/('alert-'+name+'.bgra');capture=b.rawscreen(str(path));actual=path.read_bytes()
        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
        colours={hw:rgb[i*3:i*3+3][::-1] for i,hw in enumerate(PENS)};count=0
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                if covered and covered[0]<=xx<covered[2] and covered[1]<=yy<covered[3]:continue
                offset=yy*capture.stride+(xx+16)*4
                require(actual[offset:offset+3]==colours[raster.pixels[yy*640+xx]],f'Alert {name} at {xx},{yy}')
                count+=1
        report['alert_pixels'].append(dict(name=name,icon=icon,pixels=count))
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    phase(1);require(get(sy['AESAlertPhase']+2)==1,'Concurrent peer missing')
    pixels(0,'plain');click(*button(7))
    phase(2);pixels(2,'question')
    # Move the front alert, expose the peer title and top it. Compare only the
    # independently computed uncovered rectangle, then verify exposure repair.
    t=tree();x,y,w=get(t+16),get(t+18),get(t+20)
    move(x+64,y-8);edge(1);move(x+128,y+8);edge(0);frames(60)
    peer=tree(1);px,py,pw,ph=[get(peer+o) for o in (16,18,20,22)]
    click(px+64,py-8);frames(60)
    pixels(2,'covered',(192,64,448,200))
    click(get(t+16)+w-24,get(t+18)-8);frames(60)
    pixels(2,'exposed');key('RETURN')
    phase(3);pixels(3,'stop');key('RETURN')
    require(get(sy['AESAlertPhase'])==3,'No-default Return accepted a button')
    key('TAB');key('SPACE')
    phase(4);pixels(1,'note');t=tree();click(get(t+16),get(t+18)-8)
    phase(90);require(get(sy['AESAlertPhase']+2)==1,'Peer alert was accepted by another caller')
    peer=tree(1);click(get(peer+16)+64,get(peer+18)-8);key('RETURN')
    reach('dw($%x)=90'%(sy['AESAlertPhase']+2))
    report['physical_alerts']=dict(two_ordinary_callers=True,pointer=True,default=True,
        no_default=True,space=True,temporary_close=True,movement=True,clipped_exposure=True)
    b.bp_clear_all()
