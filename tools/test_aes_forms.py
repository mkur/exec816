"""Focused synchronous-form lifetime faults and physical interaction checks."""
from native_program import ROOT, require, sha256


def instrument(out,alerts=False):
    """Replace only this fixture's form resource boundaries, never production."""
    import build_bitmap_console as builder
    original=builder.emit
    source=(ROOT/'c/calypsi/aes-form.c').read_text()
    prototypes='''
void *AESFormAlloc(ULONG,ULONG);
WORD AESFormCreate(WORD,WORD,WORD,WORD,WORD);
WORD AESFormOpen(WORD,WORD,WORD,WORD,WORD);
void AESFormVDIOpen(WORD *,WORD *,WORD *);
WORD AESFormClose(WORD);
WORD AESFormDelete(WORD);
BOOL AESFormVDIClose(struct ExecAESContext *);
'''
    source=source.replace('#include "aes-form-private.h"',
        '#include "'+str(ROOT/'c/calypsi/aes-form-private.h')+'"'+prototypes)
    source=source.replace('#include "vdi-private.h"',
        '#include "'+str(ROOT/'c/calypsi/vdi-private.h')+'"')
    source=source.replace('#include "aes-alert-private.h"',
        '#include "'+str(ROOT/'c/calypsi/aes-alert-private.h')+'"')
    for name,replacement in [('AllocMem','AESFormAlloc'),('wind_create','AESFormCreate'),
        ('wind_open','AESFormOpen'),('v_opnvwk','AESFormVDIOpen'),('wind_close','AESFormClose'),
        ('wind_delete','AESFormDelete'),('ExecVDIClose','AESFormVDIClose')]:
        source=source.replace(name+'(',replacement+'(')
    path=out/'aes-form-fault.c';path.write_text(source)
    if alerts:
        alert=(ROOT/'c/calypsi/aes-alert.c').read_text()
        for header in ('aes-alert-private.h','vdi-private.h'):
            alert=alert.replace('#include "'+header+'"','#include "'+str(ROOT/'c/calypsi'/header)+'"')
        alert=alert.replace('#include <string.h>', '#include <string.h>\nvoid *AESAlertAlloc(ULONG,ULONG);')
        alert=alert.replace('a=AllocMem(', 'a=AESAlertAlloc(')
        alert_path=out/'aes-alert-fault.c';alert_path.write_text(alert)
    def emit(output,sources,*args,**kwargs):
        if alerts:sources=[alert_path if p==ROOT/'c/calypsi/aes-alert.c' else p for p in sources]
        sources=[path if p==ROOT/'c/calypsi/aes-form.c' else p for p in sources]
        foreign=original(output,sources,*args,**kwargs)
        foreign['provenance']['form_fault_source_sha256']=sha256(path)
        if alerts:foreign['provenance']['alert_fault_source_sha256']=sha256(alert_path)
        return foreign
    builder.emit=emit
    return original


def physical(b,p,foreign,report):
    from os_boundary import run_to
    from desktop_mouse import schedule
    from generate_aes_server import expected_layout
    import adapter_state as adapter
    sy=foreign['symbols'];position=[320,120]
    def get(address,size=2):return int.from_bytes(b.memdump(address,size),'little')
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
    def frames(count=12):reach('@frame>=%d'%(b.eval_expr('@frame')+count))
    def phase(value):
        print('Form phase',value,flush=True)
        reach('dw($%x)=%d'%(sy['AESFormPhase'],value));frames(80)
        require(get(sy['AESFailures'])==0,'Target assertion at line/check '+str(get(sy['AESFirstFailure'])))
    at=lambda mod,name:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+name.upper()+'_' in d['name'])
    def move(x,y):
        nonlocal position
        position=schedule(b,p,position,(x,y))
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
    def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames()
    def click(x,y):move(x,y);edge(1);edge(0)
    def key(name):
        b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up');frames(8)
    def tree(who=0):
        context=get(sy['AESFormContext']+who*4,4)
        session=get(context+dict(expected_layout())['C context form'],4)
        require(session!=0,'Missing active form session')
        return get(session,4)
    def input_inbox():
        context=get(sy['AESFormContext'],4)
        endpoint=get(context+dict(expected_layout())['Request size']+20,4)
        return get(endpoint+36,3)
    def keyboard_counts():
        inbox=input_inbox()
        capture=p['build']['memory']['input_storage']['CAPTURE']
        return (get(capture+10),get(inbox+20,1),get(inbox+21,1))
    def typing(before,offered,inserted):
        after=keyboard_counts()
        counts=[(after[i]-before[i]) & (65535 if i==0 else 255) for i in range(3)]
        require(counts==[offered]*3,'Keyboard capture/route/consume mismatch: '+str(counts))
        return dict(offered=offered,captured=counts[0],routed=counts[1],consumed=counts[2],inserted=inserted)
    def xy(object,who=0):
        t=tree(who)
        return (get(t+16)+get(t+object*24+16)+get(t+object*24+20)//2,
                get(t+18)+get(t+object*24+18)+get(t+object*24+22)//2)
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    phase(1)
    require(get(sy['AESFormPhase']+2)==1,'Independent peer did not enter its form')
    # Independent full-tree pixels, including the editable-field border/caret.
    import struct
    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
    from control_panel_oracle import draw
    from test_desktop_presentation import rectangle
    move(620,220);frames(30)
    t=tree();objects=[list(struct.unpack('<hhhHHHIhhhh',b.memdump(t+i*24,24))) for i in range(7)]
    left,top=objects[0][7:9];width,height=objects[0][9:11]
    labels={}
    for i in range(2,7):
        labels[i]=b.memdump(objects[i][6],32).split(b'\0')[0].decode();objects[i][6]=i
    objects[1][3]=25;objects[1][6]=0;objects[0][7]=objects[0][8]=0
    raster=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
    draw(raster,objects,labels,(left,top,left+width,top+height))
    x,y=left+8,top+16
    rectangle(raster,(x-1,y-1,x+225,y+17),1);rectangle(raster,(x,y,x+224,y+16),0)
    raster.text=1;raster.apply(8,(x,y+10),b'seed')
    rectangle(raster,(x+32,y+4,x+33,y+12),1)
    path=p['output'].parent/'form-edit.bgra';capture=b.rawscreen(str(path));pixels=path.read_bytes()
    rgb=bytes((v&254)+(v>>7) for v in PALETTE)
    colours={hw:rgb[i*3:i*3+3][::-1] for i,hw in enumerate(PENS)}
    for yy in range(top,top+height):
        for xx in range(left,left+width):
            pixel=yy*capture.stride+(xx+16)*4
            require(pixels[pixel:pixel+3]==colours[raster.pixels[yy*640+xx]],f'Form pixels {xx},{yy}')
    report['form_pixels']=width*height
    before=keyboard_counts()
    for letter in ('A','B','C'):key(letter)
    report['paced_typing']=typing(before,3,3)
    click(*xy(3));click(*xy(4))
    require(get(sy['AESFormPhase'])==1,'Disabled button ended the form')
    move(*xy(5));edge(1);move(620,220);edge(0)
    require(get(sy['AESFormPhase'])==1,'Outside release ended the form')
    move(*xy(5));edge(1);key('ESC');edge(0)
    require(get(sy['AESFormPhase'])==1,'Cancelled press ended the form')
    # A key supplies the owner's wake after this durable-loss injection.
    move(*xy(5));edge(1);b.poke16(input_inbox()+14,2);key('A');edge(0);frames(30)
    require(get(sy['AESFormPhase'])==1,'Lost input accepted a held press')
    click(*xy(5))
    phase(2)
    # The temporary host can move without returning to application policy.
    t=tree();x,y=get(t+16),get(t+18)
    move(x+48,y-10);edge(1);move(x+56,y-2);edge(0);frames(60)
    require(get(t+16)==x+8 and get(t+18)==y+8,'Temporary move did not translate tree')
    click(*xy(6));phase(3);key('RETURN')
    phase(4)
    move(360,40);edge(1);move(372,52);edge(0)
    phase(5);click(324,52)
    phase(6)
    # Eight physical keys in a bounded burst. The field has three bytes left;
    # subsequent keys must be consumed but leave its terminator intact.
    before=keyboard_counts()
    for letter in 'ABCDEFGH':
        b._cmd_ok('KEY '+letter+' down');frames(1)
        b._cmd_ok('KEY '+letter+' up');frames(1)
    frames(60);report['bounded_burst']=typing(before,8,3)
    key('TAB');key('X');key('Y');key('RETURN')
    phase(7);key('TAB');key('SPACE')
    phase(8)
    t=tree();click(get(t+16),get(t+18)-8)
    phase(90)
    require(get(sy['AESFormPhase']+2)==1,'Peer form was changed by another caller')
    click(*xy(5,1))
    reach('dw($%x)=90'%(sy['AESFormPhase']+2))
    report['physical_forms']=dict(two_callers=True,ordinary_stacks=True,
        editing=True,radio=True,disabled=True,outside_release=True,escape_cancel=True,
        temporary_move=[8,8],repeated_form_do=True,aespb=True,
        borrowed_move='interrupted and preserved',borrowed_close='interrupted and preserved')
    b.bp_clear_all()
