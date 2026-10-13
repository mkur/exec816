"""Physical file drops on unchanged distribution media; inspect saved bytes."""
import json
import tempfile
from pathlib import Path
from browser_model import FIELDS as F, CONTENT_TOP, ICON_PITCH, listing, select, wait_listing
from colour_desktop_model import FIELDS as D, DRAG_FIELDS as G
from native_program import require
from sio_transaction_trace import BASE_HZ
from measure_desktop import distribution


def exercise(s,desk,source,click,key,fill,path,desk_menu,shot,move,menus):
    b=s.b;drag=desk+D['drag'];result={}
    n=lambda base,name:s.number(base+(4 if name=='window' else F[name]),2)
    g=lambda name:s.number(drag+G[name],2)
    clock=lambda:b.eval_expr('@clk')&0xffffffff
    def work(base):return [s.number(base+F['work']+i*2,2) for i in range(4)]
    def edge(down,frames=8):
        b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(frames)
    def place(base,left):
        x,y,w,h=work(base)
        move(x+w+8,y+h+8);edge(1)
        move(x+w+8+(304-(w+24)),y+h+8+(208-(h+32)));edge(0,150)
        x,y,w,h=work(base)
        move(x+120,y-8);edge(1)
        move(left+128,24);edge(0,150)
        require(work(base)==[left+8,32,280,176],'Folder placement: '+repr(work(base)))
    def ready():s.rendezvous('dw($%x)=0'%(drag+G['phase']));s.frames(40)
    def pick(name,shift=False):
        point=[]
        def chosen(x,y):point[:]=[x,y];click(x,y)
        if shift:b._cmd_ok('KEY SHIFT down')
        select(s,source,name,chosen)
        if shift:b._cmd_ok('KEY SHIFT up')
        return point
    def begin(point,threshold=True):
        move(*point);start=clock();edge(1,1)
        s.rendezvous('dw($%x)=1'%(drag+G['phase']))
        result.setdefault('press_to_armed_ms',[]).append(((clock()-start)&0xffffffff)/BASE_HZ*1000)
        if not threshold:return start
        move(point[0]+8,point[1]);s.rendezvous('dw($%x)=2'%(drag+G['phase']))
        s.rendezvous('db($%x)=1'%outline)
    def cancel():
        key('ESC');edge(0,60);ready()
        require(not g('held') and not s.number(outline,1),'Cancelled visual/hold survived')
        require(not s.number(desk+D['job'],4),'Cancellation admitted a copy')
    def hover(point,target):
        move(*point);s.rendezvous('dw($%x)=%d'%(drag+G['target'],n(target,'window')))
    def finish(prefix='Copy complete'):
        started=clock();edge(0,1)
        from colour_drag_timing import admission
        result.setdefault('release_to_visible_copy_ms',[]).append(admission(s,source,desk,started))
        s.rendezvous('dw($%x)=0'%(drag+G['phase']))
        s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2))
        s.rendezvous('dw($%x)=0'%(source+F['dialog']));s.frames(180)
        status=b.memdump(source+F['status'],128).split(b'\0')[0].decode()
        require(status.startswith(prefix),'Drop outcome: '+status)
        require(not g('held') and not s.number(outline,1),'Finished drop retained visual')
        return status
    # File gestures use the same physical pointer as existing window gestures.
    outline=next(d['address'] for d in s.p['image']['data'] if '_DESKSTATE_OUTLINEVISIBLE_' in d['name'])
    print("Drag: arrange folders",flush=True)
    place(source,8)
    desk_menu(0);s.frames(180)
    target=s.number(desk+D['folders']+4,4);require(target,'Second folder missing')
    wait_listing(s,target);path(target,'WORK:')
    key('N');fill(target,'DROP');key('RETURN');wait_listing(s,target)
    path(target,'WORK:DROP');key('N');fill(target,'SUB');key('RETURN');wait_listing(s,target)
    place(target,328)
    tx,ty,tw,th=work(target);background=(tx+190,ty+100)
    print('Drag: clicks, outline timing and cancellation',flush=True)
    menus.select('SYS:');point=pick('README.TXT')
    before=s.number(source+F['paints'],4)
    # Clicks and below-threshold motion stay ordinary selection, with no copy.
    move(*point);edge(1);move(point[0]+2,point[1]);edge(0,60);ready()
    require(n(source,'selectionCount')==1 and not s.number(desk+D['job'],4),'Small motion became a drag')
    from colour_drag_timing import exercise as timing
    result['idle_timing']=timing(s,point,begin,cancel,move)
    begin(point);hover(background,target);cancel()
    require(b.memdump(source+F['path'],128).split(b'\0')[0]==b'SYS:','Drag Escape navigated')
    begin(point);move(tx+48,ty+CONTENT_TOP+12);s.frames(30)
    require(not g('target'),'Parent accepted a drop or fell through to background')
    edge(0,60);ready();require(not s.number(desk+D['job'],4),'Parent drop admitted a copy')
    result['parent_drop_rejected']=True
    result['escape_and_rearm']=True
    begin(point);move(639,235);s.frames(30)
    require(not g('target'),'Desktop edge accepted as folder')
    edge(0,60);ready();require(not s.number(desk+D['job'],4),'Invalid target copied')
    begin(point);hover(background,target)
    # Stationary and in-folder motion only paint feedback when target changes.
    painted=s.number(target+F['paints'],4)
    for dx in (2,-2,4,-4):move(background[0]+dx,background[1])
    require(s.number(target+F['paints'],4)==painted,'Motion repainted a stable target')
    print('Drag: copy single file',flush=True)
    result['single']=finish();result['stable_hover_no_repaint']=True
    require('README.TXT' in listing(s,target),'Destination did not refresh')
    # Both views, an offscreen member, and a directory object as destination.
    menus.select('SYS:');click(216,8);click(224,40)
    key('ESC');pick('LONG.TXT');point=pick('VIEW.TXT',True)
    require(n(source,'selectionCount')==2,'Multi-selection setup')
    begin(point)
    names=listing(s,target);index=names.index('SUB')+n(target,'parent')-n(target,'first');columns=n(target,'columns')
    sub=(tx+48+index%columns*104,ty+CONTENT_TOP+12+index//columns*ICON_PITCH)
    hover(sub,target)
    require(b.memdump(drag+G['destination'],128).split(b'\0')[0]==b'WORK:DROP/SUB','Subdirectory targeting')
    print('Drag: copy selected files into subdirectory',flush=True)
    result['multiple']=finish();require('2 done' in result['multiple'],'Incomplete dragged batch')
    # Existing overwrite UI uses default Cancel; a repeated drop stays safe.
    menus.select('SYS:');key('ESC');point=pick('README.TXT');begin(point);hover(background,target);edge(0,1)
    s.rendezvous('dw($%x)=7'%(source+F['dialog']));s.frames(60)
    require(not g('held') and not s.number(outline,1),'Overwrite prompt holds drag')
    key('RETURN');s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(desk+D['job'],desk+D['job']+2));s.frames(100)
    result['default_cancel']=True
    result['release_to_visible_copy']=distribution(result['release_to_visible_copy_ms'])
    result['source_paints']=s.number(source+F['paints'],4)-before
    result['press_to_armed']=distribution(result['press_to_armed_ms'])
    result['timing_scope']='Physical press submission to application armed state at IRQ checkpoints; no visual feedback is promised before threshold movement.'
    # Source-side virtual mapping and Escape consumption in a subdirectory.
    menus.select('SYS:');path(source,'SYS:C')
    point=pick('..');move(*point);edge(1);move(point[0]+8,point[1]);s.frames(20)
    require(not g('phase'),'Parent started a file drag');edge(0,60)
    point=pick('HELLO');begin(point);cancel()
    require(b.memdump(source+F['path'],128).split(b'\0')[0]==b'SYS:C','Drag Escape navigated out of subdirectory')
    key('ESC');wait_listing(s,source)
    require(b.memdump(source+F['path'],128).split(b'\0')[0]==b'SYS:','Ordinary Escape did not resume navigation')
    result['parent_source_rejected']=True;result['subdirectory_cancel_consumed']=True
    # A separate ticking AES client exercises an ineligible peer UPDATE while
    # MCTRL is held, then prompt painting progress after every release.
    print('Drag: counter coexistence',flush=True)
    # Cold affected-folder refresh may still be doing DOS work after job=NULL.
    # Wait for the desktop to arm its next event call, after menu publication.
    from generate_aes_server import layout
    wire=layout();resident=json.loads((s.p['output']/'bitmap-console/c-image.json').read_text())['symbols']
    inbox=0
    for i in range(8):
        context=s.number(resident['contexts']+i*4,4)
        if context:
            # Private C context prefix: 112-byte request and five pointers.
            endpoint=s.number(context+132,4)
            if endpoint and s.number(endpoint+wire['Endpoint']['fields']['gemId'],2)==s.number(desk,2):
                inbox=s.number(endpoint+wire['Endpoint']['fields']['input'],3);break
    require(inbox,'Missing desktop input endpoint')
    s.rendezvous('dw($%x)!=0'%(inbox+wire['InputInbox']['fields']['interest']))
    desk_menu(4)
    s.rendezvous('(dw($%x)|dw($%x))!=0'%(desk+D['children'],desk+D['children']+2))
    from gem_applications import symbols
    child=s.number(desk+D['children'],4);require(child,'Counter did not start')
    counter=symbols(b,s.p,s.p['output']/'bitmap-console','counter',child)['GEMCounter']
    s.rendezvous('dw($%x)=1'%(counter+12));before=s.number(counter+18,4)
    menus.select('SYS:');point=pick('README.TXT')
    result['counter_timing']=timing(s,point,begin,cancel,move)
    s.frames(60);require(s.number(counter+18,4)>before,'Peer UPDATE did not resume')
    result['peer_update_resumed']=True
    menus.select('Counter');click(200,38);s.frames(160)
    shot('desktop-drag-complete')
    return result


def readback(out):
    from sdfs_reference import extract
    manifest=json.loads((out/'demo-manifest.json').read_text())
    with tempfile.TemporaryDirectory(prefix='exec816-drop-readback-') as temp:
        root=Path(temp);source=root/'source';target=root/'target';source.mkdir();target.mkdir()
        extract(out/manifest['media'],source);extract(out/'work-walkthrough.atr',target)
        for name,directory in [('README.TXT','DROP'),('LONG.TXT','DROP/SUB'),('VIEW.TXT','DROP/SUB')]:
            require((source/name).read_bytes()==(target/directory/name).read_bytes(),'Dropped bytes differ: '+name)
        require(not list(target.rglob('EXECCOPY.TMP')),'Drop retained a temporary file')
