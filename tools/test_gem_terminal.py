#!/usr/bin/env python3
"""Focused real-shell, loaded GEM terminal and physical keyboard checks."""
import argparse,hashlib,json,os,shutil
from pathlib import Path
from unittest.mock import patch
import adapter_state as adapter
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from test_shell_core import KEYS
from generate_console import constants
from console_model import read_cells
from shell_inspect import address
from gem_applications import instances
from desktop_mouse import schedule
from generate_desktop import layout as scene_layout
from generate_aes_server import expected_layout,layout as aes_layout
from terminal_model import FIELDS as TF,SESSION_FIELDS as SF,SESSION_SIZE
from gem_render_oracle import font_bytes,DESKTOP_PALETTE


def _run(directory,out,observer=None,checkpoint=None):
    p=read_build(directory/'program');c=constants();out.mkdir(parents=True,exist_ok=True)
    original=p['output'];p={**p,'output':out}
    report=dict(status='running',tier='development',qualification=False,build=p['build'],commands=[])
    from gem_applications import MODELS
    MODELS['terminal']=('GEMTerminal',0,18)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(directory/'system.atr'))
        def number(at,size=4):return int.from_bytes(b.memdump(at,size),'little')
        selected=address(p['image'],'selectedSession');live=address(p['image'],'controllerLive')
        windows=p['build']['memory']['console_storage']['WINDOWS']
        def source(index):return number(windows+c['WINDOWS_ITEMS']+index*c['WINDOW_SIZE']+c['WINDOW_INSTANCE'],3)
        def route(index):return number(windows+c['WINDOWS_ITEMS']+index*c['WINDOW_SIZE']+c['WINDOW_ROUTE'])
        def reach(condition,frames=12000,timeout=180):
            b.bp_clear_all();marker=p['labels']['native_nmi']
            b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
            original=b.regs
            def regs():
                result=original()
                if int(result['PC'].lstrip('$'),16)==p['labels']['done']:
                    require(b.peek16(adapter.STATE)==65535,'Terminal guest stopped: '+hex(b.peek16(adapter.STATE)))
                return result
            b.regs=regs
            try:run_to(b,marker,frames,timeout,condition)
            finally:b.regs=original
        def frames(count=5):reach('@frame>='+str(b.eval_expr('@frame')+count),count+300,60)
        def press(char):
            name,shift=KEYS[char]
            if shift:b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down');frames(3)
            b._cmd_ok('KEY '+name+' up')
            if shift:b._cmd_ok('KEY SHIFT up')
            frames(3)
        def move(x,y):
            ax=address(p['image'],'cursorX','DESKINPUT');ay=address(p['image'],'cursorY','DESKINPUT')
            schedule(b,p,[number(ax,2),number(ay,2)],(x,y))
            reach(f'(dw(${ax:x})={x})&(dw(${ay:x})={y})');frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');frames(40)
        def scene_windows():
            records=scene_layout();service=number(address(p['image'],'service','DESKSTATE'),3)
            base=service+records['Service']['fields']['windows'];w=records['Window']
            result=[]
            for slot in range(6):
                at=base+slot*w['size']
                if number(at,4):result.append((at,b.memdump(at+w['fields']['title'],65).split(b'\0')[0]))
            return result
        def alert(at,shown):
            for _ in range(80):
                form=number(at+dict(expected_layout())['C context form'])
                if bool(form)==shown:
                    if shown:frames(20)
                    return form
                frames(5)
            raise RuntimeError('Terminal confirmation did not '+('open' if shown else 'close'))
        def pixels(at,index,label):
            work=[number(at+TF['work']+i*2,2) for i in range(4)]
            session=at+TF['sessions']+index*SESSION_SIZE
            width=number(session+SF['width'],2);height=number(session+SF['width']+2,2)
            cells=read_cells(b.memdump,source(index))
            require(width==64 and height==20 and work[2]==512,'Terminal viewport clips its cells')
            require(b.memdump(session+SF['cells'],len(cells))==cells,'Terminal copy differs from backend')
            provider=json.loads((directory/'c-image.json').read_text())['provenance']
            path,digest=next((k,v) for k,v in provider['source_inputs'].items() if k.endswith('/vdi/font8x8.c'))
            require(sha256(ROOT/path)==digest,'Changed terminal pixel oracle font')
            font=font_bytes(ROOT/path);rom=b.memdump(0xe000,1024)
            mode=number(session+SF['mode'],2);column=number(session+SF['column'],2);row=number(session+SF['column']+2,2)
            cursor=number(at+12,2) and not mode&32
            rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
            colours=[rgb[i*3:i*3+3][::-1] for i in (0,1)]
            want=bytearray()
            for y in range(height*8):
                for x in range(width*8):
                    ch=cells[(y//8)*width+x//8]
                    if mode&64:
                        code=ch&127;code=code+64 if code<32 else code-32 if code<96 else code
                        bits=rom[code*8+y%8] ^ (255 if ch&128 else 0)
                    else:bits=font[(y%8)*256+ch]
                    ink=bool(bits&(128>>(x%8))) or (cursor and y==row*8+7 and column*8<=x<column*8+8)
                    want.extend(colours[int(ink)])
            frame=b.rawscreen(str(out/(label+'.bgra')));raw=(out/(label+'.bgra')).read_bytes()
            actual=b''.join(raw[(work[1]+16+y)*frame.stride+(work[0]+16+x)*4:
                               (work[1]+16+y)*frame.stride+(work[0]+16+x)*4+3]
                            for y in range(height*8) for x in range(width*8))
            mismatch=next((i//3 for i,(a,c) in enumerate(zip(actual,want)) if a!=c),None)
            (out/(label+'-model.json')).write_text(json.dumps(dict(work=work,cells=cells.hex(),mode=mode,column=column,row=row,cursor=bool(cursor)),indent=2)+'\n')
            (out/(label+'-expected.bgr')).write_bytes(want)
            require(actual==want,'Terminal pixel mismatch at '+str((mismatch%512,mismatch//512) if mismatch is not None else None))
            report.setdefault('pixels',{})[label]=hashlib.sha256(actual).hexdigest()
        def ready(index):
            at=source(index);require(at!=0,'Missing console source')
            reach(f'db(${at+c["INSTANCE_READREADY"]:x})=2')
        def command(index,text,expected=None):
            previous=route(index)
            for char in text:press(char)
            press('\n')
            at=source(index);r=windows+c['WINDOWS_ITEMS']+index*c['WINDOW_SIZE']+c['WINDOW_ROUTE']
            reach(f'(dw(${r:x})!={previous&65535})&(db(${at+c["INSTANCE_READREADY"]:x})=2)')
            cells=read_cells(b.memdump,at)
            if expected:require(expected in cells,'Missing shell result: '+repr(expected))
            report['commands'].append(dict(command=text,index=index,route=route(index)))
            print('Terminal command completed:',index,text,flush=True)
        def before(b):
            b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE ST')
            reach(f'dw(${selected:x})=1')
            ready(0)
            provider=json.loads((directory/'c-image.json').read_text())['symbols']
            children=provider['GEMDesktopChildren']
            reach(f'dw(${children+8:x})!=0')
            apps=instances(b,p,directory)
            terminal=next(a for a in apps if a['name']=='terminal')
            pointer=terminal['symbols']['GEMTerminal']
            reach(f'(dw(${pointer:x})|db(${pointer+2:x}))!=0')
            at=number(terminal['symbols']['GEMTerminal'])
            reach(f'(dw(${at+6:x})=1)&(dw(${at+8:x})=0)&(dw(${at+14:x})!=0)')
            require(at!=0 and number(at+6,2)==1,'Terminal window not opened')
            report['terminal']=dict(identity=terminal['identity'],state=at,window=number(at+2,2))
            table=next(d['address'] for d in p['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
            abi=json.loads((ROOT/'abi/process.json').read_text())
            task=next(row[2] for row in abi['record'] if row[0]=='task')
            report['terminal']['slot']=(terminal['task']-table-task)//abi['record_bytes']
            owner=aes_layout()['Request']['fields']['owner']
            contexts=[number(provider['contexts']+i*4) for i in range(4)]
            context=next(c for c in contexts if c and number(c+owner,3)==terminal['task'])
            if observer:observer(b,p,terminal,report)
            report['live_tasks']=number(p['build']['task_storage']['LIVE'],1)
            report['aes_clients']=sum(bool(c) for c in contexts)
            report['aes_windows']=len(scene_windows())
            frames(80)
            if checkpoint:checkpoint('quiet-start',b,p,report)
            frames(120)
            if checkpoint:checkpoint('quiet-end',b,p,report)
            command(0,'ECHO gem-terminal',b'gem-terminal')
            frames(120)
            require(number(at+14)>0,'Terminal did not paint')
            if checkpoint:checkpoint('output',b,p,report)
            report['paints']=number(at+14)
            move(620,44)
            b.screenshot(str(out/'terminal.png'))
            pixels(at,0,'terminal-front')
            from generate_layers import layout as layer_layout
            ll=layer_layout();sl=scene_layout()['Service']['fields']
            service=number(address(p['image'],'service','DESKSTATE'),3)
            layers=service+sl['scene']+ll['Scene']['fields']['items']
            alternatives=[]
            for w,title in scene_windows():
                if title==b'Terminal':continue
                layer_id=number(w+scene_layout()['Window']['fields']['layer'])
                for slot in range(9):
                    layer=layers+slot*ll['Layer']['size']
                    if number(layer)==layer_id and number(layer+ll['Layer']['fields']['shown'],1):
                        bounds=layer+ll['Layer']['fields']['bounds']
                        alternatives.append((number(bounds+2,2),number(bounds,2)))
            require(alternatives,'Missing focus peer')
            peer_y,peer_x=min(alternatives)
            report['focus_peer']=[peer_x+40,peer_y+4]
            click(peer_x+40,peer_y+4);reach(f'dw(${at+12:x})=0')
            click(620,44);reach(f'dw(${at+12:x})=1');frames(40)
            pixels(at,0,'terminal-exposed')
            command(0,'ECHO editx\b',b'edit')
            edge='0123456789'*6+'EDGE'
            command(0,'ECHO '+edge,edge.encode());frames(80)
            pixels(at,0,'terminal-edge')
            command(0,'NEWSHELL')
            reach(f'dw(${selected:x})=2');ready(1);frames(120)
            report['peak_observed_tasks']=number(p['build']['task_storage']['LIVE'],1)
            if checkpoint:checkpoint('created',b,p,report)
            command(1,'ECHO second-session',b'second-session')
            command(1,'SESSION 1');reach(f'dw(${selected:x})=1');frames(80)
            if checkpoint:checkpoint('selected-first',b,p,report)
            command(0,'ECHO first-again',b'first-again')
            command(0,'SESSION 2');reach(f'dw(${selected:x})=2');frames(80)
            if checkpoint:checkpoint('selected-second',b,p,report)
            click(116,44);alert(context,True)
            press('\n');alert(context,False)
            require(number(live,1)==2,'Cancelled close retired a session')
            click(116,44);form=alert(context,True)
            area=[number(form+4+i*2,2) for i in range(4)]
            click(area[0]+area[2]//2+36,area[1]+area[3]-24);alert(context,False)
            report['commands'].append(dict(command='confirmed window close',index=1))
            reach(f'dw(${selected:x})=1');ready(0);frames(80)
            if checkpoint:checkpoint('fallback',b,p,report)
            for char in 'EXIT':press(char)
            press('\n');b.bp_clear_all()
        try:
            report['runtime'],_=execute(b,p,before_run=before,timeout=180,frame_limit=12000)
            ownership(b,p,original);report['status']='pass'
        except Exception as error:
            report.update(status='fail',error=str(error),native_status=b.peek16(adapter.STATE))
            report['fault_required']=number(adapter.STATE+24,2)
            report['failure_clock']=dict(frame=b.eval_expr('@frame'),clock=b.eval_expr('@clk'),adapter=b.memdump(adapter.STATE,64).hex(),nmien=number(0xd40e,1),nmist=number(0xd40f,1))
            ts=p['build']['task_storage']
            report['failure_task_contexts']=b.memdump(ts['BASE'],ts['SIZE']*len(p['build']['memory']['task_pools'])).hex()
            if any(d['name']=='G_DIRECTORYCHECKS' or 'DIRECTORYCHECKS_' in d['name'] for d in p['image']['data']):
                report['directory_failure']={name:number(address(p['image'],name),size) for name,size in [('directoryChecks',2),('directoryReady',1),('directoryDone',1),('directoryOldUnit',4),('directoryNewUnit',4)]}
            report['controller']={name:number(address(p['image'],name),size) for name,size in [('selectedSession',4),('controllerLive',1),('controllerStatus',4),('bootPrimary',4),('bootSecondary',4),('nextSession',4),('shellPublished',1)]}
            report['applications']=instances(b,p,directory)
            provider=json.loads((directory/'c-image.json').read_text())['symbols']
            report['desktop_children']=[number(provider['GEMDesktopChildren']+i*4) for i in range(3)]
            report['desktop_failure']=number(provider['GEMDesktopFailure'],2)
            for name in ('systemContext','sessions'):
                at=address(p['image'],name)
                record=next(d for d in p['image']['data'] if d['address']==at)
                report[name]=b.memdump(at,record['size']).hex()
            print('Terminal failure',report['native_status'],report['fault_required'],report.get('directory_failure'),report['controller'],flush=True)
            raise
        finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def run(directory,out,observe_wakes=False):
    if not observe_wakes:return _run(directory,out)
    from text_performance_trace import sites
    from sio_transaction_trace import read_events
    from g4bench_trace import native_calls
    from measure_gui_baseline import save_cpu_trace
    p=read_build(directory/'program');folder=directory/'apps/terminal'
    app=json.loads((folder/'app.json').read_text())
    local={pc:s for pc,s in sites(folder,app['image'],{'ExecAESWait':'wake'}).items() if s['category']=='wake'}
    require(local,'Missing Terminal wait call sites')
    pcs={bank*65536+(pc&65535) for pc,s in local.items() for pc in (pc,s['end'])
         for bank in p['build']['memory']['usable_banks']}
    def begin(b,p,terminal,report):
        t=p['build']['task_storage']
        number=lambda at,size=4:int.from_bytes(b.memdump(at,size),'little')
        slot=next(i for i,pool in enumerate(p['build']['memory']['task_pools'])
            if number(t['BASE']+i*t['SIZE']+t['TCB_ITEM'],3)==terminal['task'])
        at=number(terminal['symbols']['GEMTerminal']);port=number(at+TF['replies'])
        notification=number(at+TF['wake']);reply=1<<number(port+12,1)
        require(notification and not(notification&reply),'Terminal wake aliases replies')
        report['wake_observer']=dict(dp=p['build']['memory']['task_pools'][slot]['dp'],
            delta=terminal['base']-(app['abi']['link_bank']<<16),notification_mask=notification,reply_mask=reply)
        b.profile_start()
    with patch.dict(os.environ,EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(pcs))):
        report=_run(directory,out,begin)
    save_cpu_trace(out)
    observed=report['wake_observer'];delta=observed['delta']
    marks={str(pc):dict(entry=pc+delta,returns=[s['end']+delta]) for pc,s in local.items()}
    calls=[s for s in native_calls(read_events(out/'cpu-trace.log',kinds={'cpu'}),marks) if s['dp']==observed['dp']]
    observed.update(completed_calls=len(calls),view_wakes=sum(bool(s['return_a']&0x8000) for s in calls),
        timer_wakes=sum(bool(s['return_a']&0x20) for s in calls),trace_sha256=sha256(out/'cpu-trace.log'))
    require(observed['view_wakes']>0,'Missing real view wakes')
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

def missing_terminal(directory,out):
    from make_data_disk import make
    out.mkdir(parents=True,exist_ok=True)
    media=out/'media';shutil.copytree(directory/'media',media,dirs_exist_ok=True)
    (media/'C/TERMINAL.APP').unlink(missing_ok=True)
    disk=out/'system.atr'
    make(disk,media,filesystem='sdfs',sector_bytes=256,sectors=2880,
         binary_names={str(p.relative_to(media)) for p in media.rglob('*') if p.is_file() and p.suffix in ('.APP','.RSC')})
    p=read_build(directory/'program');original=p['output'];p={**p,'output':out}
    report=dict(status='running',tier='development',qualification=False,build=p['build'],scenario='missing-terminal')
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():
            b.config(key,str(value).lower() if isinstance(value,bool) else value)
        report['machine']=verify_machine(b,ROM,PIN);b.mount(0,str(disk))
        report['runtime'],_=execute(b,p,timeout=180,frame_limit=12000)
        report['controller_status']=int.from_bytes(b.memdump(address(p['image'],'controllerStatus'),4),'little')
        require(report['controller_status']==20,'Missing terminal did not fail supervised startup')
        require(b.memdump(address(p['image'],'controllerLive'),1)[0]==0,'Failed startup retained a shell')
        require(b.memdump(address(p['image'],'shellPublished'),1)[0]==0,'Failed startup retained its named port')
        ownership(b,p,original);report['status']='pass'
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--scenario',choices=('normal','missing-terminal'),default='normal')
    a.add_argument('--observe-wakes',action='store_true');args=a.parse_args()
    if args.scenario=='normal':run(args.build.resolve(),args.output.resolve(),args.observe_wakes)
    else:
        require(not args.observe_wakes,'Wake observation requires the normal scenario')
        missing_terminal(args.build.resolve(),args.output.resolve())
    print('GEM terminal development checks passed',args.scenario,flush=True)
