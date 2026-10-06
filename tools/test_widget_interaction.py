#!/usr/bin/env python3
"""Physical ST/key input, bounded deferred intake and retained widget recovery."""
import argparse
import json
from pathlib import Path
import adapter_state as adapter
import generate_tasks
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from desktop_mouse import schedule
from generate_desktop import layout
from generate_widgets import layout as widgets
from stack_budget import stack_usage
from desktop_budget import delta


def build_fixture(out,mode):
    from generate_memory import PROFILE
    out.mkdir(parents=True,exist_ok=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    (out/'widgetinputprobe.act').write_text('MODULE WIDGETINPUTPROBE\nPUBLIC BYTE holdPaint\nPUBLIC CARD heldIndex\nENDMODULE\n')
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        text=(ROOT/'lib/desktop/deskpaint.act').read_text().replace('USE EXEC\n','USE EXEC\nUSE WIDGETINPUTPROBE\n',1)
        needle='  LET region=LAYERS.PaintRegion(@service.scene,paintToken)'
        require(text.count(needle)==1,'Paint continuation boundary moved')
        text=text.replace(needle,'  IF WIDGETINPUTPROBE.holdPaint=2 THEN\n    RETURN(0)\n  FI\n\n'+needle)
        needle='  IF done=2 THEN\n'
        require(text.count(needle)==1,'Paint step return moved')
        text=text.replace(needle,needle+'''    IF WIDGETINPUTPROBE.holdPaint=1 AND window<>NULL
        AND window.kind=DESKTYPES.CONTENT_WIDGETS AND started=1 AND commandIndex<>0 THEN
      WIDGETINPUTPROBE.heldIndex=commandIndex
      WIDGETINPUTPROBE.holdPaint=2
    FI
''')
        (directory/'deskpaint.act').write_text(text)
        return directory
    generate_tasks.policy_modules=instrument
    try:return build_bitmap(ROOT/'tests/programs/widgets_interaction.act',out,mode=='opt',desktop=True,memory_profile=memory)
    finally:generate_tasks.policy_modules=original


def run(out,mode,replay=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build_fixture(out,mode)
    report=dict(slice='AW4',tier='development',qualification=False,mode=mode,status='running',cases=[])
    at=lambda mod,n:next(d['address'] for d in p['image']['data'] if '_'+mod+'_'+n.upper()+'_' in d['name'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
            report['machine']=verify_machine(b,ROM,PIN)
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
            read=lambda name,size=2:get(at('WIDGETINPUTTEST',name),size)
            write=lambda name,value,size=2:b.memload(at('WIDGETINPUTTEST',name),value.to_bytes(size,'little'))
            def reach(condition):
                marker=p['labels']['native_irq'];b.bp_clear_all();b.bp_set(marker,condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def registers():
                    r=original()
                    if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Guest stopped: '+hex(b.peek16(adapter.STATE)))
                    return r
                b.regs=registers
                try:run_to(b,marker,condition=condition,frame_limit=8000,timeout=120)
                finally:b.regs=original
            def frames(n=2):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            turn=1;position=[320,120]
            def begin_command(op,arg=0):
                nonlocal turn
                write('argument',arg);write('command',op);turn+=1
            def finish_command():
                reach('dw($%x)=%d'%(at('WIDGETINPUTTEST','checkpoint'),turn))
            def command(op,arg=0):
                begin_command(op,arg);finish_command()
            def key(name,shift=False):
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok('KEY '+name+' down');frames(3)
                b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                frames(3)
            def move(x,y):
                nonlocal position
                position=schedule(b,p,position,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),position[0],at('DESKINPUT','cursorY'),position[1]))
                frames(2)
            def button(down):
                b._cmd_ok('MOUSE AT 2000 0 0 '+str(down))
                reach('dw($%x)=%d'%(at('DESKINPUT','buttons'),down));frames(4)
            def click(x,y):move(x,y);button(1);button(0)
            def snapshot():
                command(1);base=at('WIDGETINPUTTEST','snapshot')
                return dict(epoch=get(base,4),revision=get(base+4,4),focus=get(base+10),states=[get(base+12+4*i) for i in range(9)])
            def event(kind,obj=None):
                base=at('WIDGETINPUTTEST','observed');fields=layout()['Event']['fields']
                while True:
                    command(2)
                    e={k:get(base+v,4 if k in ('window','route','epoch','revision') else 2) for k,v in fields.items()}
                    if e['window']==read('panel',4) or e['kind']==4:break
                    require(e['window']==1 and e['kind'] in (1,2,3),'Unexpected other-window event')
                require(e['kind']==kind and (obj is None or e['object']==obj),'Wrong widget event: '+str(e))
                if kind in (8,9):require(e['epoch'] and e['revision'],'Missing model metadata')
                if kind==8:require(e['flags']&1,'Lost capture tick-valid flag')
                report['cases'].append(e);return e
            def patch(index,mask,state=0,hidden=0):
                data=bytearray(widgets()['Update']['size']);data[8:10]=(1).to_bytes(2,'little')
                for offset,value in ((12,index),(14,mask),(16,state),(18,hidden)):data[offset:offset+2]=value.to_bytes(2,'little')
                b.memload(at('WIDGETINPUTTEST','patch'),bytes(data));command(6);frames(4)
            def before(bridge):
                reach('dw($%x)=1'%at('WIDGETINPUTTEST','checkpoint'));frames(3)
                service=get(at('DESKSTATE','service'),3);sf=layout()['Service']['fields'];wf=layout()['Window']['fields']
                window=service+sf['windows']+layout()['Window']['size']
                context=get(window+wf['widgets'],4)
                armed=lambda:get(context+20)
                start=snapshot();require(start['focus']==1,'Initial keyboard focus')
                move(164,134);button(1);require(armed()==1,'Mouse did not arm')
                move(420,190);require(get(context+22)==0,'Drag-out feedback')
                move(164,134);require(get(context+22)==1,'Drag-in feedback')
                button(0);event(8,1);s=snapshot();require(s['states'][1]==1 and s['revision']==2,'Toggle commit')
                button(1);move(420,190);button(0);require(armed()==65535,'Outside release did not cancel')
                require(snapshot()['revision']==2,'Outside release changed selection')
                click(304,134);event(8,3);s=snapshot();require(s['states'][2]==0 and s['states'][3]==1,'Radio group')
                key('TAB');require(snapshot()['focus']==7,'Tab traversal')
                key('TAB',True);require(snapshot()['focus']==3,'Shift-Tab traversal')
                key('SPACE');event(8,3)
                key('RETURN');event(8,7)
                key('ESC');event(9)
                key('BREAK');event(9)
                key('A');event(1)
                patch(1,1,8);click(164,134);require(armed()==65535 and snapshot()['states'][1]==8,'Disabled button activated')
                patch(5,4,hidden=1);key('RETURN');s=snapshot();require(s['focus']!=7,'Hidden default focused')
                patch(5,4);patch(1,1)
                move(164,134);button(1);command(5,0);frames(4);require(armed()==65535,'Focus loss retained gesture');button(0)
                command(5,1);frames(4)
                move(164,134);button(1);old=snapshot()['epoch'];command(3);button(0)
                require(snapshot()['epoch']!=old and snapshot()['states'][1]==0,'Replacement reused gesture')
                from generate_layers import layout as layer_layout
                ll=layer_layout();scene=service+sf['scene']
                busy=scene+ll['Scene']['fields']['busy']
                quiet='(dw($%x)=0)&(dw($%x)=0)'%(busy,busy+2)
                def settled():
                    # Covered damage intentionally survives without runnable paint work.
                    for _ in range(100):
                        reach(quiet)
                        data=b.memdump(scene,ll['Scene']['size'])
                        word=lambda offset:int.from_bytes(data[offset:offset+2],'little',signed=True)
                        rect=lambda offset:tuple(word(offset+2*i) for i in range(4))
                        pending=False
                        for slot in range(5):
                            base=ll['Scene']['fields']['items']+slot*ll['Layer']['size']
                            lf=ll['Layer']['fields']
                            if not data[base+lf['dirty']]:continue
                            damages=base+lf['damage'];region=base+lf['visible']
                            for d in range(data[damages+ll['Damage']['fields']['count']]):
                                damage=rect(damages+ll['Damage']['fields']['rects']+d*8)
                                for i in range(word(region)):
                                    visible=rect(region+ll['Region']['fields']['rects']+i*8)
                                    pending|=(visible[0]<damage[2] and visible[2]>damage[0]
                                        and visible[1]<damage[3] and visible[3]>damage[1])
                        if not pending:return
                        frames(20)
                    raise RuntimeError('Visible widget damage did not settle')
                # Hold after a real object step, with live scratch and token.
                settled();move(164,134)
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\1');command(3);frames(3)
                require(get(at('WIDGETINPUTPROBE','holdPaint'),1)==2 and
                    get(at('WIDGETINPUTPROBE','heldIndex'))>0,'No held object continuation')
                old=get(context+4,4)
                button(1);move(170,134);button(0)
                require(get(service+sf['widgetCount'],1)>0 and get(context+4,4)==old,
                    'Physical input edited live paint snapshot')
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\0');frames(30);event(8,1)
                require(snapshot()['states'][1]==1,'Lost or doubled held press/release')
                # Hide and patch requests cannot invalidate the live C context.
                for op in (4,6):
                    settled()
                    b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\1');command(3);frames(3)
                    token=get(busy,4);old=get(context+4,4)
                    if op==6:
                        data=bytearray(widgets()['Update']['size'])
                        for offset,value in ((8,1),(12,1),(14,1),(16,8)):
                            data[offset:offset+2]=value.to_bytes(2,'little')
                        b.memload(at('WIDGETINPUTTEST','patch'),bytes(data))
                    begin_command(op);frames(10)
                    require(read('checkpoint')!=turn and get(busy,4)==token and
                        get(window+wf['widgets'],4)==context and get(context+4,4)==old,
                        'Control crossed an unfinished object strip')
                    b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\0');finish_command();frames(30)
                    if op==4:
                        command(4,1);command(5,1)
                    else:require(snapshot()['states'][1]==8,'Deferred patch lost')
                report['continuation_cases']=['physical motion/press/release','hide','patch']
                settled()
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\1');command(3);frames(3)
                require(get(service+sf['scene']+__import__('generate_layers').layout()['Scene']['fields']['busy'],4)!=0,'No held paint token')
                old=get(context+4,4);key('SPACE')
                require(get(service+sf['widgetCount'],1)>0 and get(context+4,4)==old,'Input edited live paint snapshot')
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\0');frames(30);event(8,1)
                # Deferred overflow: preserve the snapshot, cancel, and require recovery.
                settled()
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\1');command(3);frames(3)
                for _ in range(18):key('SPACE')
                require(get(service+sf['widgetCount'],1)<=16,'Unbounded deferred queue')
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\0');frames(30);event(4)
                require(snapshot()['states'][1]==0 and armed()==65535,'Deferred overflow activated controls')
                # Event-lane overflow with the client deliberately stalled.
                settled()
                for _ in range(17):
                    revision=get(context+4,4)
                    key('SPACE')
                    reach('dw($%x)=%d'%(context+4,revision+1))
                event(4);s=snapshot();require(s['states'][1]==1,'Loss readback differs from committed model')
                key('SPACE');event(8,1);require(snapshot()['states'][1]==0,'Recovery synthesized/doubled action')
                # Chrome keeps priority; a captured client click cannot start a drag.
                layer=scene+ll['Scene']['fields']['items']+ll['Layer']['size']
                bounds=layer+ll['Layer']['fields']['bounds']
                left=get(bounds);top=get(bounds+2)
                move(250,90);button(1);move(266,98);button(0)
                target_x=(left+16+4)&~7;target_y=(top+8+4)&~7
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(bounds,target_x,bounds+2,target_y))
                require(armed()==65535,'Title gesture armed a widget')
                settled();move(target_x+51,target_y+49);button(1)
                reach('dw($%x)=1'%(context+20))
                # Retire while an object strip is incomplete. No free/reply may
                # happen before that paint token retires; cleanup checks follow.
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\1');command(3);frames(3)
                token=get(busy,4)
                require(token and get(at('WIDGETINPUTPROBE','holdPaint'),1)==2,'No close continuation')
                write('command',255);frames(10)
                require(get(busy,4)==token and get(window+wf['widgets'],4)==context,
                    'Close freed an unfinished widget context')
                report['continuation_cases'].append('close')
                b.memload(at('WIDGETINPUTPROBE','holdPaint'),b'\0');b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,frame_limit=40000,timeout=300)
            ownership(b,p,p['output']);report['checks']=read('checks');report['stack_usage']=stack_usage(b,p['build']['memory'])
            require(all(v['remaining_above_floor']>0 for v in report['stack_usage'].values()),'Stack floor')
        report.update(status='pass',bank_zero_delta=delta(p['build']['memory']),xex_sha256=sha256(p['xex']),build_sha256=sha256(out/'program/build.json'))
    except Exception as e:report.update(status='fail',error=str(e));raise
    finally:(out/'interaction-results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Widget interaction passed',mode,report['checks'],flush=True)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--mode',choices=('raw','opt'),default='opt');a.add_argument('--replay',action='store_true')
    args=a.parse_args();run(args.output,args.mode,args.replay)
