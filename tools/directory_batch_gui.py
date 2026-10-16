"""Narrow packaged Files/selector walkthrough; physical input, observed state."""
import json
from gem_applications import instances
from native_program import require
from browser_model import FIELDS as B,listing,wait_listing
from colour_desktop_model import FIELDS as D
from file_selector_model import FIELDS as F,FORM_SELECTOR
from generate_aes_server import expected_layout,ABI
from text_model import FIELDS as T
from test_shell_core import KEYS
from sio_transaction_trace import BASE_HZ


def exercise(s,menus,move,click,apps='C:',batch=True,standalone=True):
    b=s.b;out=s.p['output'];directory=out/'bitmap-console'
    shared=json.loads((directory/'c-image.json').read_text())['symbols']
    fields=dict(F)
    if not batch:
        for name in fields:
            if fields[name]>fields['scan']:fields[name]-=18
    s.saved.setdefault('desktop_menu',{})
    def app(name):
        for _ in range(80):
            found=[a for a in instances(b,s.p,directory) if a['name']==name]
            if found:return found[0]
            s.frames(10)
        raise RuntimeError('Missing '+name)
    def text(address,length=128):return b.memdump(address,length).split(b'\0')[0].decode('ascii')
    def type_key(key,shift=False):
        if shift:b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+key+' down');s.frames(3);b._cmd_ok('KEY '+key+' up')
        if shift:b._cmd_ok('KEY SHIFT up')
        s.frames(5)
    def launch(name):
        # App loading is setup, not a measured directory/UI interval. Keep the
        # expensive host instruction profiler off during serial transfers.
        b.profile_stop()
        menus.select('Shell');old=s.begin('RUN '+apps+name.upper()+'.APP');s.ready(old);s.result()
        result=app(name);b.profile_start()
        return result
    def retired(name):
        for _ in range(100):
            if not any(a['name']==name for a in instances(b,s.p,directory)):return
            s.frames(10)
        raise RuntimeError('Application did not retire: '+name)
    desk=app('desktop')['symbols']['GEMDesk']
    previous=s.number(desk+D['active'],4)
    click(296,8);start=b.eval_expr('@clk');click(304,28)
    current=s.number(desk+D['active'],4)
    require(current and current!=previous,'New Window did not create a folder')
    wait_listing(s,current)
    new_window=dict(start=start,end=b.eval_expr('@clk'),input_to_settled_upper_ms=((b.eval_expr('@clk')-start)&0xffffffff)*1000/BASE_HZ,
                    count=s.number(current+B['count'],2))
    print('Batch UI: New Window ready',flush=True)
    menus.close();s.frames(60)
    if standalone:
        files=launch('files');model=files['symbols']['GEMBrowser']
        s.rendezvous('dw($%x)=1'%(model+B['ready']));wait_listing(s,model)
        names=listing(s,model)
        menus.key('L',ctrl=True);wait_listing(s,model)
        require(listing(s,model)==names,'Standalone Files refresh changed entries')
        print('Batch UI: standalone Files refreshed',flush=True)
        menus.close();retired('files')
    viewer=launch('text');model=viewer['symbols']['GEMText']
    s.rendezvous('dw($%x)=1'%(model+T['ready']));s.frames(40)
    context=next(c for i in range(ABI['constants']['CONTEXTS'])
                 if (c:=s.number(shared['contexts']+i*4,4)) and s.number(c+32,3)==viewer['task'])
    form=context+dict(expected_layout())['C context form']
    start=b.eval_expr('@clk');menus.key('O')
    session=s.number(form,4);require(session,'Open did not create a form')
    selector=s.number(session+FORM_SELECTOR,4);require(selector,'Missing file selector')
    s.rendezvous('(dw($%x)=1)&(dw($%x)=0)'%(selector+fields['valid'],selector+fields['loading']))
    opened=dict(start=start,end=b.eval_expr('@clk'),input_to_ready_upper_ms=((b.eval_expr('@clk')-start)&0xffffffff)*1000/BASE_HZ,
                count=s.number(selector+fields['count'],2))
    print('Batch UI: selector ready',flush=True)
    progress=dict(new_window=new_window,standalone_files_refresh=True if standalone else None,
                  text_task=viewer['task'],selector_open=opened)
    (out/'directory-batch-ui-progress.json').write_text(json.dumps(progress,indent=2)+'\n')
    # Edit the path normally, then queue Escape during the live scan. This
    # preserves event checks between local records and synchronous DOS waits.
    obj=selector+3*24
    click(s.number(selector+16,2)+s.number(obj+16,2)+16,
          s.number(selector+18,2)+s.number(obj+18,2)+4)
    for _ in text(selector+fields['path']):type_key('BACKSPACE')
    for ch in 'SYS:C/*.*':
        key,shift=KEYS[ch];type_key(key,shift=shift)
    b._cmd_ok('KEY RETURN down');s.frames(3);b._cmd_ok('KEY RETURN up')
    lock=selector+fields['scan']
    s.rendezvous('(dw($%x)=1)&((dw($%x)!=0)|(dw($%x)!=0))'%(selector+fields['loading'],lock,lock+2))
    start=b.eval_expr('@clk');b._cmd_ok('KEY ESC down');s.frames(3);b._cmd_ok('KEY ESC up')
    s.rendezvous('(dw($%x)=0)&(dw($%x)=0)'%(form,form+2))
    canceled=dict(start=start,end=b.eval_expr('@clk'),input_to_retired_ms=((b.eval_expr('@clk')-start)&0xffffffff)*1000/BASE_HZ,
                  observed_mid_scan=True)
    print('Batch UI: selector canceled during scan',flush=True)
    b.profile_stop()
    s.frames(60);menus.close();retired('text')
    result=dict(**progress,selector_cancel=canceled,
                scope='Physical input and IRQ-sampled UI completion; upper bounds include helper settling waits.')
    (out/'directory-batch-ui.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
