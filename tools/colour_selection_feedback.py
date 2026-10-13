"""Completed-release to matching folder scanout; reuses the GEM pixel oracle."""
from browser_model import FIELDS as F, CONTENT_TOP
from gem_desktop_oracle import paint
from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
from measure_desktop import distribution
from native_program import require
from sio_transaction_trace import BASE_HZ
from test_gem_cursor import overlay


def exercise(s,base,click,key,path,move,count=40):
    b=s.b;path(base,'WORK:');font=font_bytes(s.p['output']/s.manifest['font_source'])
    colors={hw:bytes((v&254)+(v>>7) for v in PALETTE[pen*3:pen*3+3])[::-1] for pen,hw in enumerate(PENS)}
    n=lambda name:s.number(base+F[name],2)
    clock=lambda:b.eval_expr('@clk')&0xffffffff
    result={};models={}
    def expected(mode,mask):
        x,y,w,h=[s.number(base+F['work']+i*2,2) for i in range(4)]
        if (mode,mask) not in models:
            raster=Raster(font);paint(b,{'GEMBrowser':base},raster,b'WORK:',(x-8,y-16,x+w+16,y+h+16))
            models[mode,mask]=raster
        raster=models[mode,mask]
        packed=overlay(raster,s.saved['pointer'])
        region=(x,y,x+w,y+h)
        want=b''.join(colors[(packed[(yy*640+xx)//2]>>(0 if xx&1 else 4))&15]
            for yy in range(y,y+h) for xx in range(x,x+w))
        return region,want
    def visible(region,want):
        file=s.p['output']/'selection-scanout.bgra';frame=b.rawscreen(str(file));raw=file.read_bytes()
        x,y,r,bt=region
        actual=b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]
            for yy in range(y,bt) for xx in range(x,r))
        return actual==want
    def point(index):
        x,y,w,h=[s.number(base+F['work']+i*2,2) for i in range(4)]
        return (x+48+index*104,y+CONTENT_TOP+12) if n('iconView') else (x+40,y+CONTENT_TOP+4+index*12)
    def arrow(name,shift=False):
        b._cmd_ok('KEY ALL up');s.frames(3)
        b._cmd_ok('KEY CTRL down')
        if shift:b._cmd_ok('KEY SHIFT down')
        s.frames(3);b._cmd_ok('KEY '+name+' down');s.frames(8)
        b._cmd_ok('KEY '+name+' up');s.frames(3)
        b._cmd_ok('KEY ALL up');s.frames(35)
    for mode,row in [('icons',0),('list',1)]:
        click(216,8);click(224,24+row*16);click(216,8);click(224,88)
        arrow('ASTERISK');require(n('selected')==0 and n('selectionCount')==1,'Arrow without lead')
        # Ctrl+Shift+asterisk/plus conflict in the Atari keyboard matrix.
        # Vertical cursor chords remain physically representable.
        arrow('EQUALS',True);require(n('selected')==n('columns') and n('selectionCount')==2,'Shift-arrow add')
        arrow('MINUS');require(n('selected')==0 and n('selectionCount')==1,'Plain arrow replace')
        for modified in (False,True):
            label=mode+('-shift' if modified else '-plain');samples=[];paint_counts=[]
            for i in range(count):
                index=1 if modified else 1-(i%2);mask=(1 if i%2 else 3) if modified else 1<<index
                move(*point(index));s.frames(3)
                before=s.number(base+F['paints'],4)
                if modified:
                    b._cmd_ok('KEY SHIFT down');s.frames(3)  # Let POKEY latch Shift before the press.
                b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(3)
                # Membership commits on completed release. Keep the press hold
                # and settling interval identical in all four cases.
                start=clock();b._cmd_ok('MOUSE AT 2000 0 0 0')
                # Read the oracle after the application has published every
                # changed OBJECT and the status. Bitmap mutation comes first.
                s.rendezvous('(db($%x)=%d)&(dw($%x)>%d)'%
                    (base+F['selection'],mask,base+F['paints'],before&65535))
                if modified:b._cmd_ok('KEY SHIFT up')
                region,want=expected(mode,mask)
                for _ in range(50):
                    if visible(region,want):break
                    s.frames(1)
                else:raise RuntimeError('Selection did not reach matching scanout: '+label)
                samples.append(((clock()-start)&0xffffffff)/BASE_HZ*1000)
                paint_counts.append(s.number(base+F['paints'],4)-before)
                s.frames(15)
            result[label]=dict(samples_ms=samples,**distribution(samples),paint_counts=paint_counts)
            print('Selection feedback',label,distribution(samples),flush=True)
        before=s.number(base+F['paints'],4);click(*point(0));s.frames(30)
        require(s.number(base+F['paints'],4)==before,'Repeated sole selection repainted')
        before=s.number(base+F['paints'],4)
        b._cmd_ok('KEY CTRL down');key('A');b._cmd_ok('KEY CTRL up')
        require(n('selectionCount')==n('count') and s.number(base+F['paints'],4)==before+1,'Select All rebuilt the folder')
        click(216,8);click(224,88)
    result['scope']='40 completed release edges per case to matching whole work-area scanout, including status; PAL frame polling, fixed 3-frame hold and 15-frame settling interval. No disk I/O. Not HY4 qualification.'
    result['keyboard_arrows']=True;result['repeat_no_paint']=True;result['select_all_one_transaction']=True
    s.saved['selection_feedback']=result


def standalone(s,desk,click,key,path,move,menus,shot):
    """Exercise the shared folder code in a separate loadable Files Process."""
    from browser_model import select,listing,wait_listing
    from colour_desktop_model import FIELDS as D
    from gem_applications import instances
    import re
    menus.select('Shell')
    def memory():
        text=s.command('MEM').decode('ascii')
        values=[int(n) for n in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',text)]
        require(len(values)>=4,'Missing MEM totals');return values[-4:]
    before=memory();ledger=s.ledger();previous=s.begin('RUN C:FILES.APP')
    for _ in range(200):
        found=[app for app in instances(s.b,s.p,s.p['output']/'bitmap-console') if app['name']=='files']
        if found:break
        s.frames(40)
    require(found,'Standalone Files did not load');base=found[0]['symbols']['GEMBrowser']
    s.rendezvous('dw($%x)=1'%(base+F['ready']));wait_listing(s,base);path(base,'WORK:')
    select(s,base,'ALPHA.TXT',click);s.b._cmd_ok('KEY SHIFT down')
    select(s,base,'BETA.TXT',click);s.b._cmd_ok('KEY SHIFT up')
    require(s.number(base+F['selectionCount'],2)==2,'Standalone multiple selection')
    peer=s.number(desk+D['folders'],4)
    require(not s.number(peer+F['selectionCount'],2),'Standalone selection changed desktop')
    click(216,8);click(224,40);key('R')
    require(not s.number(base+F['dialog'],2),'Standalone multi-Rename acted')
    x,y,w,h=[s.number(base+F['work']+2*i,2) for i in range(4)]
    move(x+w+8,y+h+8);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
    move(x+w-56,y+h-24);s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(180)
    require(s.number(base+F['selectionCount'],2)==2,'Resize lost membership')
    shot('standalone-multiple-selection')
    x,y=[s.number(base+F['work']+2*i,2) for i in range(2)]
    click(x,y-8);s.ready(previous);menus.select('Shell')
    after=memory();require(after==before and s.ledger()==ledger,'Standalone Files retained heap/ownership')
    s.saved['standalone_selection']=dict(multiple=True,list=True,resize=True,independent=True,
        command_gate=True,collected=True,heap_before=before,heap_after=after)
