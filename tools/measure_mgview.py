#!/usr/bin/env python3
"""Two-action passive MGVIEW audit using cached APPs/provider, without builds."""
import argparse,hashlib,json,os,re,shutil
from collections import Counter
from pathlib import Path

import adapter_state as adapter
from console_turn_profile import analyze_events,Timeline
from c_program import ABI
from dos_concurrent_trace import call_marker
from filesystem_audit import Audit
from g4bench_trace import listing_returns,calls
from gem_render_oracle import Raster,DESKTOP_PALETTE,PENS,font_bytes
from generate_aes_server import layout,expected_layout,ABI as AES
from native_program import ROOT,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from sio_transaction_trace import BASE_HZ,read_events
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from desktop_mouse import schedule

APP=('set_shift','_my_draw','_my_keyed','redraw_window','update_window',
     'arrowed','window_calc_slider','_my_arrange')
RESIDENT=('vro_cpyfm','v_gtext','vr_recfl','ExecAESBeginUpdate','wind_update',
    'ExecAESUpdate','ExecAESSubmit','ExecGemRasterCopy','ExecAESPainted',
    'GemDrawingRasterBorrow','GemDrawingBorrow','GemDrawingSolidBorrow',
    'GemDrawingMouseBorrow','VbxeOwnerSubmit','VbxeOwnerFence','VbxeOwnerCopy',
    'VbxeOwnerWrite','VbxeOwnerRead','GemVdiPaint','DisplayEnter','DisplayLeave')


def definition(cache,p,foreign,app):
    entries={foreign['symbols'][n]:n for n in RESIDENT if n in foreign['symbols']}
    app_entries={app['image']['symbols'][n]:n for n in APP}
    app_returns=set();app_exits=set();sites={}
    for path in (cache/'apps/mgview').glob('*.lst'):
        if path.name=='link.lst':continue
        for section in path.read_text().split('.section ')[1:]:
            if not section.startswith('farcode,text'):continue
            name=next((n for n in APP if re.search(r'\\ 000000\s+'+re.escape(n)+':',section)),None)
            if not name:continue
            base=app['image']['symbols'][name]
            for m in re.finditer(r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:([^\s]+)',section):
                pc=base+int(m[1],16);app_returns.add(pc+4)
                sites[pc]=name+'/'+m[2]+'/call';sites[pc+4]=name+'/'+m[2]+'/returned'
            for m in re.finditer(r'\\ ([0-9a-f]{6}) 6b\s+(?:`[^`]+`: *)?rtl',section):
                app_exits.add(base+int(m[1],16))
    require(app_returns and app_exits,'Missing emitted application call boundaries')
    collect=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_AESSYSTEM_COLLECT_'))
    turn=call_marker({**p,'labels':{**p['labels'],'collect':collect}},'M_AESSYSTEM_RUN_','collect')
    restore=p['labels']['context_restore']
    require((p['output']/'hosted.bin').read_bytes()[restore-adapter.RESIDENT_BASE:restore-adapter.RESIDENT_BASE+8]==bytes.fromhex('c230ab2b7afa6840'),'Changed scheduler marker')
    clock={name:p['labels'][name] for name in ('native_irq','native_nmi','interrupt_schedule')}
    clock.update(turn=turn,selected=restore+4)
    points={pc:name for name,pc in clock.items()}
    points.update({p['labels'][n]:n for n in ('input_capture','blitter_irq_complete','blitter_irq_posted') if n in p['labels']})
    returns=listing_returns(foreign,cache/'drawing')
    exits=listing_returns(foreign,cache/'drawing',exits=True)
    copy_returns=[]
    for path in (cache/'drawing').glob('*gem-vbxe.lst'):
        for section in path.read_text().split('.section ')[1:]:
            if not re.search(r'\\ 000000\s+GemDrawingCopyBorrow:',section):continue
            for m in re.finditer(r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:VbxeOwnerCopyRect',section):
                pc=foreign['symbols']['GemDrawingCopyBorrow']+int(m[1],16)
                segment=next(s for s in foreign['segments'] if s['address']<=pc< s['address']+len(s['bytes']))
                raw=bytes(segment['bytes'][pc-segment['address']:pc-segment['address']+4])
                require(raw==b'\x22'+foreign['symbols']['VbxeOwnerCopyRect'].to_bytes(3,'little'),'Changed owned copy call')
                require(pc+4 in returns,'Owned copy return was not selected')
                copy_returns.append(pc+4)
    require(len(copy_returns)==1,'Missing unique owned copy return')
    pcs=set(entries)|set(returns)|set(exits)|set(points)
    link=ABI['link_bank']<<16
    # Legal placements are selected before normal disk loading. No fixed base
    # or guest instrumentation is needed; analysis uses only the loaded image.
    for bank in app['verified_banks']:
        delta=(bank<<16)-link
        pcs.update(pc+delta for pc in set(app_entries)|app_returns|app_exits|set(sites))
    return dict(entries=entries,returns=returns,exits=exits,app_entries=app_entries,
        app_returns=sorted(app_returns),app_exits=sorted(app_exits),sites=sites,points=points,
        pcs=sorted(pcs),copy_returns=copy_returns,
        timeline=dict(points=clock,spans={},task_dps=[r['dp'] for r in p['build']['memory']['task_pools']]))


def expected(font,work,content,shift):
    x,y,w,h=work;model=Raster(font);model.clip=(x,y,x+w-1,y+h-1)
    model.fill=0;model.apply(11,[x,y,x+w-1,y+h-1]);model.text=1
    text=content.replace(b'\r\n',b'\n').replace(b'\r',b'\n')
    lines=text.split(b'\n') if text else []
    if text.endswith(b'\n'):lines.pop()
    for row,line in enumerate(lines[shift:shift+h//8]):
        model.apply(8,[x,y+row*8+6],list(line.replace(b'\0',b' ').expandtabs(8)[:272]))
    colours=[None]*16
    for pen,hardware in enumerate(PENS):colours[hardware]=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
    return b''.join(colours[model.pixels[yy*640+xx]] for yy in range(y,y+h) for xx in range(x,x+w))


def analyze(out,d,base,samples):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={d['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,d['timeline'],include_segments=True)
    delta=base-(ABI['link_bank']<<16)
    entries={**d['entries'],**{pc+delta:name for pc,name in d['app_entries'].items()}}
    returns=set(d['returns'])|{pc+delta for pc in d['app_returns']}
    exits=set(d['exits'])|{pc+delta for pc in d['app_exits']}
    shift_pc=next(pc for pc,name in entries.items() if name=='set_shift')
    dps={int(e[9],16) for _,e in events if int(e[4],16)==shift_pc}
    require(len(dps)==1,'No unique scrolling Task')
    dp=dps.pop();timeline=Timeline(profile['segments'],dp)
    spans,unfinished=calls(events,entries,returns,dp,exits)
    points={**d['points'],**entries,**{pc+delta:name for pc,name in d['sites'].items()}}
    result=[]
    for sample in samples:
        start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        end=start+(sample['end']-sample['start'])%(1<<32)
        pixels_end=start+(sample['complete_tick']-sample['start'])%(1<<32)
        selected=[dict(s,**timeline.measure(s['start'],s['end'])) for s in spans if start<=s['start']<s['end']<=end]
        shifts=[s for s in selected if s['kind']=='set_shift']
        require(len(shifts)==1,'Expected exactly one set_shift per key')
        shift=shifts[0];counts=Counter(s['kind'] for s in selected)
        copy_spans=[s for s in selected if s['kind']=='vro_cpyfm']
        require(len(copy_spans)==1 and counts['_my_draw']==1 and counts['v_gtext']==1,
                'Expected one copy and one text-row draw')
        require(not counts['redraw_window'] and not counts['update_window'],'Unexpected repaint fallback')
        copy=copy_spans[0]
        physical=[dict(tick=t,status=int(e[5],16)) for t,e in events
            if copy['start']<=t<=copy['end'] and int(e[9],16)==dp and int(e[4],16) in d['copy_returns']]
        require(len(physical)==12 and all(row['status']==0 for row in physical),'Owned hardware copy did not complete twelve strips')
        physical_irqs=sum(copy['start']<=t<=copy['end'] and d['points'].get(int(e[4],16))=='blitter_irq_complete' for t,e in events)
        boundaries=[dict(name=points[int(e[4],16)],ms=(t-start)*1000/BASE_HZ,
            dp=int(e[9],16),a=int(e[5],16),x=int(e[6],16),s=int(e[8],16))
            for t,e in events if start<=t<=end and int(e[4],16) in points]
        input_tick=next((t for t,e in events if start<=t<=end and points.get(int(e[4],16))=='input_capture'),None)
        phases={}
        for name in ('_my_keyed','set_shift','ExecAESBeginUpdate','vro_cpyfm','_my_draw','GemDrawingMouseBorrow','wind_update'):
            rows=[s for s in selected if s['kind']==name]
            phases[name]=dict(calls=len(rows),**{k:sum(s[k] for s in rows) for k in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms')})
        scope_charges={str(other):Timeline(profile['segments'],other).measure(shift['start'],shift['end']) for other in d['timeline']['task_dps']}
        def last_wrong(field):
            values=[(poll['tick']-sample['start'])%(1<<32)*1000/BASE_HZ for poll in sample['polls'] if not poll[field]]
            return max(values) if values else None
        result.append(dict(sample,start=start,end=end,viewer_dp=dp,call_counts=dict(counts),phases=phases,
            set_shift_start_ms=(shift['start']-start)*1000/BASE_HZ,set_shift_end_ms=(shift['end']-start)*1000/BASE_HZ,
            capture_ms=(input_tick-start)*1000/BASE_HZ if input_tick is not None else None,
            cpu_to_complete=timeline.measure(start,pixels_end),spans=selected,boundaries=boundaries,
            scope_task_charges=scope_charges,owned_copy_completions=physical,copy_completion_irqs=physical_irqs,
            copy_display_enters=sum(s['kind']=='DisplayEnter' and copy['start']<=s['start']<s['end']<=copy['end'] for s in selected),
            copy_display_leaves=sum(s['kind']=='DisplayLeave' and copy['start']<=s['start']<s['end']<=copy['end'] for s in selected),
            copy_fences=sum(s['kind']=='VbxeOwnerFence' and copy['start']<=s['start']<s['end']<=copy['end'] for s in selected),
            first_row_bracket_ms=[last_wrong('top'),sample['offered_to_first_row_ms']],
            complete_bracket_ms=[last_wrong('complete'),sample['offered_to_complete_ms']],
            task_charges={str(other):Timeline(profile['segments'],other).measure(start,pixels_end) for other in d['timeline']['task_dps']}))
    return dict(samples=result,unfinished_calls=unfinished,trace_events=len(events),
        presenter_dp=profile['worker_dp'],supervisor_dp=d['timeline']['task_dps'][0],
        cpu_scope='Conservative Task CPU charge includes gateway and bus stalls; native interrupts and other Tasks are separate.',
        visible_scope='PAL-frame polling at native COP boundaries: observed top-row and complete-viewport matches are upper bounds, bracketed by prior mismatches.')


def run(cache,out,presenter=False):
    cache=cache.resolve();out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(cache/'program');foreign=json.loads((cache/'c-image.json').read_text())
    apps={n:json.loads((cache/'apps'/n/'app.json').read_text()) for n in ('mgview','counter')}
    require('desktop_mouse' in p['build'],'Cached MGVIEW fixture is missing mouse-profile metadata')
    require(p['build']['foreign_image']['c_program_provider']['abi']==ABI['version'],'Cached provider ABI changed')
    require(sha256(p['xex'])==p['build']['xex_sha256'],'Cached native image changed')
    shutil.copyfile(cache/'system.atr',out/'system.atr')
    disk=Audit((out/'system.atr').read_bytes());disk.sdfs();content=disk.files['VIEW.TXT']
    for name,app in apps.items():require(hashlib.sha256(disk.files[name.upper()+'.APP']).hexdigest()==app['sha256'],'Cached disk APP differs: '+name)
    d=definition(cache,p,foreign,apps['mgview'])
    if presenter:
        import mgview_presenter_trace
        d['presenter']=mgview_presenter_trace.definition(p)
        d['pcs']=sorted(set(d['pcs'])|set(d['presenter']['pcs']))
    (out/'definition.json').write_text(json.dumps(d,indent=2)+'\n')
    at=lambda name:next(r['address'] for r in p['image']['data'] if '_CMGVIEWTEST_'+name.upper()+'_' in r['name'])
    report=dict(status='running',tier='development',qualification=False,builds_run=0,samples=[],
        source_cache=str(cache),native_sha256=sha256(p['xex']),app_sha256={n:a['sha256'] for n,a in apps.items()},
        rom_sha256=sha256(ROM),emulator_sha256=sha256(BRIDGE/'AltirraBridgeServer'),
        app_abi=ABI['version'],aes_abi=AES['version'],base_clock_hz=BASE_HZ,
        document_bytes=len(content),document_sha256=hashlib.sha256(content).hexdigest(),
        bank_zero_delta=dict(fixed=0,root=0,kernel=0,idle=0,per_public_task=0))
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE');saved={k:os.environ.get(k) for k in keys}
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in d['pcs'])
    for k in ('EXEC816_LATENCY_TRACE','EXEC816_MASK_TRACE'):os.environ.pop(k,None)
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Changed observer binary')
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.mount(0,str(out/'system.atr'));report['machine']=verify_machine(b,ROM,PIN)
            number=lambda a,n=2:int.from_bytes(b.memdump(a,n),'little')
            def reach(condition):
                marker=p['labels']['native_cop'];condition=f'(@xpc=${marker:x})&({condition})'
                b.bp_clear_all();b.bp_set(marker,condition=condition)
                faults=[p['labels'][n] for n in ('heap_fault','stack_overflow','arithmetic_fault','done')]
                for pc in faults:b.bp_set(pc)
                original=b.regs
                def regs():
                    state=original();require(b.eval_expr('@xpc') not in faults,'Guest fault: '+str(state));return state
                b.regs=regs
                try:run_to(b,marker,condition=condition,timeout=180,frame_limit=18000)
                finally:b.regs=original
            def frames(count):reach('@frame>=%d'%(b.eval_expr('@frame')+count))
            def screen(work):
                x,y,w,h=work;path=out/'current.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
                return b''.join(raw[yy*frame.stride+(x+16)*4+i:yy*frame.stride+(x+16)*4+i+3]
                    for yy in range(y,y+h) for i in range(0,w*4,4))
            def before(b):
                b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE ST');base=0
                for execution_index in range(3):
                    stage=execution_index*2+1;reach(f'dw(${at("phase"):x})={stage}')
                    base=number(at('bases'),4)
                    sy={n:base+v-(ABI['link_bank']<<16) for n,v in apps['mgview']['image']['symbols'].items()}
                    argument=b'SYS:VIEW.TXT' if not execution_index else b''
                    b.memload(at('argument'),argument+b'\0');b.poke16(at('argBytes'),len(argument));b.poke16(at('go'),stage)
                    reach(f'dw(${at("phase"):x})={stage+1}')
                    if not execution_index:
                        report['loaded_base']=base
                        reach(f'dw(${sy["nwindows"]:x})=1')
                        window=number(sy['windows'],4)
                        contexts=[number(foreign['symbols']['contexts']+i*4,4) for i in range(AES['constants']['CONTEXTS'])]
                        context=next(c for c in contexts if c and number(c+layout()['Request']['fields']['global']+4)==number(sy['ap_id']))
                        depth=context+dict(expected_layout())['C context updateDepth']
                        frames(80);reach(f'dw(${depth:x})=0')
                        position=schedule(b,p,[320,120],(632,0))
                        cursor=lambda name:next(row['address'] for row in p['image']['data']
                            if '_DESKINPUT_'+name.upper()+'_' in row['name'])
                        reach(f'(dw(${cursor("cursorX"):x})={position[0]})&(dw(${cursor("cursorY"):x})={position[1]})')
                        frames(40)
                        report['pointer_start']=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        require(report['pointer_start']==position,'Pointer did not settle at the requested position')
                        work=[number(window+268+i*2) for i in range(4)];report['work']=work
                        font=font_bytes(cache/'selected/src/vdi/font8x8.c')
                        require(screen(work)==expected(font,work,content,0),'Initial pixels differ')
                        counter_base=number(at('bases')+4,4)
                        counter=counter_base+apps['counter']['image']['symbols']['GEMCounter']-(ABI['link_bank']<<16)
                        before_count=number(counter+14,4)
                        b._cmd_ok('KEY CTRL down');frames(3);b.profile_start();frames(2)
                        for label,key,shift in (('down','EQUALS',1),('up','MINUS',0)):
                            want=expected(font,work,content,shift);row_bytes=work[2]*8*3
                            sample=dict(action=label,start=b.eval_expr('@clk')&0xffffffff,rpc_before=number(context+layout()['Request']['fields']['sequence'],4),polls=[])
                            b._cmd_ok('KEY '+key+' down')
                            first=None;full=None
                            for index in range(150):
                                frames(1)
                                if index==2:b._cmd_ok('KEY '+key+' up')
                                got=screen(work);tick=b.eval_expr('@clk')&0xffffffff
                                top=got[:row_bytes]==want[:row_bytes];complete=got==want
                                sample['polls'].append(dict(tick=tick,top=top,complete=complete))
                                if top and first is None:first=tick
                                if complete:
                                    full=tick;b._cmd_ok('KEY '+key+' up');break
                            require(full is not None,'Viewport did not settle: '+label)
                            reach(f'dw(${depth:x})=0');frames(2)
                            require(number(window+280,4)==shift,'Wrong scroll position')
                            sample.update(first_row_tick=first,complete_tick=full,end=b.eval_expr('@clk')&0xffffffff,
                                offered_to_first_row_ms=((first-sample['start'])&0xffffffff)*1000/BASE_HZ,
                                offered_to_complete_ms=((full-sample['start'])&0xffffffff)*1000/BASE_HZ,
                                rpc_delta=number(context+layout()['Request']['fields']['sequence'],4)-sample['rpc_before'],
                                pixel_sha256=hashlib.sha256(got).hexdigest())
                            require(sample['rpc_delta']==0,'Scroll unexpectedly used AES RPC')
                            report['samples'].append(sample)
                            (out/'samples.json').write_text(json.dumps(report['samples'],indent=2)+'\n')
                            print('MGVIEW',label,'complete pixels:',round(sample['offered_to_complete_ms'],2),'ms',flush=True)
                            frames(5)
                        frames(3);b.profile_stop();b._cmd_ok('KEY CTRL up');frames(60)
                        report['counter_progress']=number(counter+14,4)-before_count
                        require(report['counter_progress']>0,'Counter did not progress')
                        report['pointer_end']=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        require(report['pointer_start']==report['pointer_end'],'Pointer moved during scroll capture')
                    else:frames(20);require(number(sy['nwindows'])==0,'No-argument viewer opened a window')
                    b.poke16(at('go'),stage+1)
                b.bp_clear_all()
            report['runtime'],_=execute(b,p,before_run=before,timeout=300,frame_limit=30000)
            ownership(b,p,p['output']);require(number(at('completed'))==4,'Incomplete cleanup')
        report['audit']=analyze(out,d,report['loaded_base'],report['samples'])
        if presenter:
            report['presenter']=mgview_presenter_trace.analyze(out,d,report['audit'],foreign,cache/'drawing')
        report['status']='pass'
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:
        for k,v in saved.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def reanalyze(cache,out):
    """Reuse a completed capture; changes to reporting do not rerun the guest."""
    cache=cache.resolve();out=out.resolve();r=json.loads((out/'results.json').read_text())
    require(r['runtime']['status']==0 and r['runtime']['guards']=='intact','Incomplete guest capture')
    p=read_build(cache/'program');foreign=json.loads((cache/'c-image.json').read_text())
    app=json.loads((cache/'apps/mgview/app.json').read_text())
    require(sha256(p['xex'])==r['native_sha256'] and app['sha256']==r['app_sha256']['mgview'],'Captured binaries changed')
    d=definition(cache,p,foreign,app)
    recorded=json.loads((out/'definition.json').read_text())
    if 'presenter' in recorded:
        import mgview_presenter_trace
        d['presenter']=mgview_presenter_trace.definition(p)
        d['pcs']=sorted(set(d['pcs'])|set(d['presenter']['pcs']))
    require(json.loads(json.dumps(d))==json.loads((out/'definition.json').read_text()),'Captured markers changed')
    r['audit']=analyze(out,d,r['loaded_base'],r['samples'])
    if 'presenter' in d:
        r['presenter']=mgview_presenter_trace.analyze(out,d,r['audit'],foreign,cache/'drawing')
    r.update(status='pass');r.pop('error',None)
    (out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    return r


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--cache',type=Path,default=ROOT/'build/mgview-dev/smoke')
    parser.add_argument('--output',type=Path,default=ROOT/'build/mgview-audit')
    parser.add_argument('--analyze-only',action='store_true')
    parser.add_argument('--presenter',action='store_true',help='Trace presenter phases and signal sites')
    args=parser.parse_args()
    r=reanalyze(args.cache,args.output) if args.analyze_only else run(args.cache,args.output,args.presenter)
    for row in r['audit']['samples']:print(row['action'],row['call_counts'],row['phases']['set_shift'])
    if 'presenter' in r:
        for row in r['presenter']['samples']:
            held=row['windows']['owned_core']
            print('presenter',row['action'],'UPDATE-held CPU ms',round(held['measured']['charged_cpu_ms'],2),
                'Present CPU ms',round(held['routine_costs']['DESKINPUT_PRESENT']['cpu_ms'],2),
                'signal posts',held['presenter_signal_counts'])
