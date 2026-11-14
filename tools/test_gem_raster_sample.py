#!/usr/bin/env python3
"""Check conventional raster scrolling and coexistence in the exact demo ZIP."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import zipfile
import adapter_state

from desktop_menu_check import Menus
from desktop_mouse import schedule
from console_turn_profile import analyze_events
from gem_applications import instances
from gem_render_oracle import Raster,DESKTOP_PALETTE,PENS,font_bytes
from native_program import read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from raster_model import SIZE,FIELDS
from shell_inspect import address
from sio_transaction_trace import BASE_HZ,read_events
from stack_budget import stack_usage
from test_dos_stack import execute,ownership
from test_gem_acceptance import Session,bootstrap
from test_mouse_observe import BRIDGE,PIN
from console_model import read_cells


def attribute_cpu(report,events,memory):
    marks=report['call_markers'];points=report['scheduler_markers'];clean=[];duplicates=0
    for tick,e in events:
        if clean and e[4:]==clean[-1][1][4:] and int(e[4],16) in marks.values():
            duplicates+=1;continue
        clean.append((tick,e))
    # @clk is 32-bit; the reader unfolds its epoch using earlier SIO events.
    epoch=round((clean[0][0]-report['timing'][0]['input_offered'])/(1<<32))*(1<<32)
    window=(report['timing'][0]['input_offered']+epoch,report['timing'][-1]['scanout_observed']+epoch+1)
    # PROFILE_STOP does not withdraw the passive history observer. Bound the
    # trace at the next balanced scheduler return after the measured scene.
    end=next(i for i,(tick,e) in enumerate(clean) if tick>=window[1]-1 and int(e[4],16)==points['selected'])
    clean=clean[:end+1]
    definition=dict(points={**points,'turn':marks['call']},
        spans=dict(raster=dict(entry=marks['call'],returns=[marks['returned']])),
        task_dps=[pool['dp'] for pool in memory['task_pools']])
    trace=analyze_events(clean,definition,window=window)
    spans=[span for span in trace['routine_spans'] if window[0]<=span['start']<=span['end']<=window[1]]
    require(len(spans)==4,'Incomplete raster call trace')
    for sample,span in zip(report['timing'],spans):
        require(sample['input_offered']+epoch<=span['start']<=span['end']<=sample['scanout_observed']+epoch,
                'Call trace outside its physical input/scanout observations')
        sample.update(cpu=span,call_elapsed_ms=span['elapsed_ms'],
            call_to_checked_scanout_ms=(sample['scanout_observed']+epoch-span['start'])*1000/BASE_HZ)
    report['cpu_trace']=dict(duplicates=duplicates,worker_dp=trace['worker_dp'],
        definition=definition,host_clock_epoch=epoch,
        scope='Conservative caller CPU charge including kernel and bus stalls; native IRQ/NMI and peer Task time separate')


class RasterSample:
    def exercise(self,s):
        b=s.b;out=s.out
        def loaded(name):return [a for a in instances(b,s.p,s.directory) if a['name']==name]
        def find(name):
            for _ in range(150):
                rows=loaded(name)
                if rows:return rows[0]
                s.frames(5)
            raise RuntimeError(name+' did not launch')
        def move(x,y):
            ax,ay=[s.native('DESKINPUT',name) for name in ('cursorX','cursorY')]
            schedule(b,s.p,[s.number(ax,2),s.number(ay,2)],(x,y))
            s.rendezvous(f'(dw(${ax:x})={x})&(dw(${ay:x})={y})');s.frames(3)
        def edge(down,frames=20):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));s.frames(frames)
        def click(x,y):move(x,y);edge(1);edge(0,60)
        def key(name,down):
            ctrl=name in ('UP','DOWN','RIGHT')
            physical=dict(UP='MINUS',DOWN='EQUALS',RIGHT='ASTERISK').get(name,name)
            if ctrl and down:b._cmd_ok('KEY CTRL down')
            b._cmd_ok('KEY '+physical+(' down' if down else ' up'))
            if ctrl and not down:b._cmd_ok('KEY CTRL up')
        def pulse(name):key(name,True);s.frames(3);key(name,False);s.frames(3)
        menus=Menus(s,click,move)
        s.command('RUN SYS:C/PULSE.APP paint')
        counter=find('pulse');cp=counter['symbols']['GEMCounter']
        s.rendezvous(f'dw(${cp+12:x})=1')
        # Each shell owns one background job. Give Raster a second shell;
        # the existing paired Widget launcher provides the other alternative.
        s.command('NEWSHELL')
        try:s.command('RUN SYS:C/RASTER.APP')
        except Exception:
            s.report['launch_diagnostic']=dict(windows=menus.windows(),
                apps=instances(b,s.p,s.directory),live_tasks=s.live(),
                cells=read_cells(s.far,s.source(s.index())).decode('latin1'))
            b.screenshot(str(out/'launch-failure.png'))
            raise
        app=find('raster');base=app['symbols']['GEMRaster']
        s.rendezvous(f'dw(${base+6:x})=1');s.frames(100)
        s.report['app']=app
        def state():
            raw=b.memdump(base,SIZE)
            result={name:int.from_bytes(raw[at:at+(4 if name in ('scrolls','shifts','roundtrips') else 2)],'little')
                    for name,at in FIELDS.items() if name!='work'}
            result['work']=[int.from_bytes(raw[26+i*2:28+i*2],'little',signed=True) for i in range(4)]
            return result
        font=font_bytes(s.directory/'selected/src/vdi/font8x8.c')
        colours=[None]*16
        for pen,hardware in enumerate(PENS):
            colours[hardware]=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
        def pixels(label):
            st=state();x,y,w,h=st['work'];model=Raster(font);model.clip=(x,y,x+w-1,y+h-1)
            require((w,h)==(304,96),'Raster work size changed')
            for i in range(12):
                row=(st['first']+i)&65535
                model.fill=row%14+2;model.apply(11,[x,y+i*8,x+w-1,y+i*8+7])
                model.text=1;model.apply(8,[x+2-st['left'],y+i*8+6],list(('Row %05d'%row).encode()))
            path=out/(label+'.bgra');frame=b.rawscreen(str(path));raw=path.read_bytes()
            require((frame.width,frame.height)==(672,240),'Unexpected scanout dimensions')
            actual=b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3]
                            for yy in range(y,y+h) for xx in range(x,x+w))
            want=b''.join(colours[model.pixels[yy*640+xx]] for yy in range(y,y+h) for xx in range(x,x+w))
            if actual!=want:
                s.report['pixel_failure']=dict(label=label,state=st,
                    first_difference=next(i for i,(a,c) in enumerate(zip(actual,want)) if a!=c))
                b.screenshot(str(out/(label+'-failure.png')))
            require(actual==want,'Raster scanout mismatch: '+label)
            s.report.setdefault('pixels',[]).append(dict(label=label,state=st,exact_pixels=w*h,
                sha256=hashlib.sha256(actual).hexdigest()))
            return actual
        menus.select('Raster:');move(632,232);s.frames(80)
        pixels('initial');idle=state();count=s.number(cp+14)
        s.frames(80)
        require(state()==idle,'Paused raster sample performed idle work')
        require(s.number(cp+14)>count,'Counter did not progress beside paused Raster')
        # Check the emitted JSL itself, then use its two instruction boundaries.
        listing=(s.directory/'apps/raster/0-main.lst').read_text()
        matches=re.findall(r'\\ ([0-9a-f]{6}) 22\.\.\.\.\.\.\s+jsl\s+long:vro_cpyfm',listing)
        require(len(matches)==1,'Raster call site changed')
        call=app['symbols']['transfer']+int(matches[0],16);returned=call+4
        stub=app['symbols']['vro_cpyfm']
        require(b.memdump(call,4)==bytes([0x22,stub&255,(stub>>8)&255,stub>>16]),'Raster call packing changed')
        s.report['call_markers']=dict(call=call,returned=returned)
        if 'trace_markers' in s.report:
            require(s.report['trace_markers']==s.report['call_markers'],'Loaded sample moved since trace setup')
        def reach(pc):
            require(pc<=65535,'Use passive trace for upper-bank call boundaries')
            condition=f'@xpc=${pc:x}'
            b.bp_clear_all();b.bp_set(pc&65535,condition=condition)
            b.bp_set(s.p['labels']['done'],condition=adapter_state.STOPPED)
            original=b.regs
            def regs():
                value=original()
                require(not b.eval_expr(adapter_state.STOPPED),'Guest stopped during raster call')
                return value
            b.regs=regs
            try:run_to(b,pc&65535,30000,180,condition=condition)
            finally:b.regs=original
        samples=[];s.report['timing']=samples
        if 'trace_markers' in s.report:
            reach(s.report['scheduler_markers']['selected']);b.profile_start()
        # The pinned bridge has no PLUS raw-key alias. Two rightward steps
        # exercise different-parity transfers without changing the observer;
        # lower-level snapshot probes cover leftward overlapping transfers.
        for index,(name,field) in enumerate((('DOWN','scrolls'),('UP','scrolls'),('RIGHT','shifts'),('RIGHT','shifts'))):
            old=state()[field];start=b.eval_expr('@clk')
            key(name,True);s.frames(3);key(name,False)
            s.rendezvous(f'dw(${base+FIELDS[field]:x})={old+1}')
            completed=b.eval_expr('@clk')
            # Observe a completed subsequent frame, rather than treating a
            # fenced drawing return as already scanned pixels.
            s.frames(1);pixels(name.lower()+'-'+str(index));scanout=b.eval_expr('@clk')
            samples.append(dict(operation=name,parity='different' if field=='shifts' else 'same',
                rectangle=[303,96] if field=='shifts' else [304,88],
                input_offered=start,completed_update_observed=completed,scanout_observed=scanout,
                offered_to_update_ms=((completed-start)&0xffffffff)*1000/BASE_HZ,
                offered_to_checked_scanout_ms=((scanout-start)&0xffffffff)*1000/BASE_HZ))
        if 'trace_markers' in s.report:
            reach(s.report['scheduler_markers']['selected']);b.profile_stop()
        before=state();before_pixels=pixels('before-memory');pulse('M')
        s.rendezvous(f'dw(${base+16:x})={before["roundtrips"]+1}');s.frames(2)
        require(pixels('memory-roundtrip')==before_pixels,'Memory round trip changed pixels')
        pulse('SPACE');s.frames(80);pulse('SPACE')
        s.rendezvous(f'dw(${base+20:x})=0');s.frames(30)
        require(state()['scrolls']>before['scrolls']+1,'Timed scrolling did not run')
        pixels('timed-scroll');after=state();s.frames(60)
        require(state()==after,'Paused sample kept scrolling')
        count=s.number(cp+14);menus.select('Terminal');s.frames(80)
        menus.select('Raster:');move(632,232);s.frames(80);pixels('uncovered')
        require(s.number(cp+14)>count,'Counter stalled during cover/uncover')
        x,y,_,_=state()['work'];move(x+120,y-10);edge(1)
        move(x+138,y+2);edge(0,100);move(632,232);s.frames(80)
        require(state()['work'][:2]==[x+18,y+12],'Raster physical move failed')
        pixels('moved');b.screenshot(str(out/'raster-and-counter.png'))
        pulse('Q');s.frames(100)
        require(all(a['state']==4 for a in loaded('raster')),'Raster did not retire')
        # RUN retains a retired Process/image until its shell collects JOBS.
        menus.select('Terminal');s.command('JOBS',b'finished')
        require(not loaded('raster'),'Raster image survived collection')
        s.close_extra_session()
        count=s.number(cp+14);s.frames(80);require(s.number(cp+14)>count,'Counter stopped with Raster')
        menus.select('Counter / paint');click(384,48);s.frames(100)
        require(all(a['state']==4 for a in loaded('pulse')),'Counter did not retire')
        s.report['coexistence']=dict(distinct_processes=counter['identity']!=app['identity'],
            paused_idle=True,timer_scroll=True,cover_uncover=True,physical_move=True,
            counter_progress=True,normal_app_exit=True)
        menus.select('Terminal');s.command('JOBS',b'finished')
        require(not loaded('pulse'),'Counter image survived collection')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def run(bundle,out,trace_from=None):
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(bundle);directory=bundle/'bitmap-console'
    report=dict(status='running',tier='development',qualification=False,
        zip_sha256=sha256(bundle/'exec816-demo.zip'),scope=__doc__,
        timing_scope='Four operations on the same 304x96 canvas; copy rectangles recorded separately. Checked scanout is an observation upper bound at frame resolution')
    if trace_from:
        previous=json.loads(trace_from.read_text());require(previous['zip_sha256']==report['zip_sha256'],'Trace package changed')
        report['trace_markers']=previous['call_markers']
        selected=p['labels']['context_restore']+4
        expected=bytes.fromhex('c230ab2b7afa6840');address_=p['labels']['context_restore']
        hosted=(p['output']/'hosted.bin').read_bytes()
        require(hosted[address_-adapter_state.RESIDENT_BASE:address_-adapter_state.RESIDENT_BASE+8]==expected,'Context restore marker changed')
        report['scheduler_markers']={name:p['labels'][name] for name in ('native_irq','native_nmi','interrupt_schedule')}
        report['scheduler_markers']['selected']=selected
        pcs=[*report['trace_markers'].values(),*report['scheduler_markers'].values()]
        os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in pcs))
    try:
        with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(out/'extracted')
        extracted=out/'extracted/exec816-demo';manifest=json.loads((bundle/'demo-manifest.json').read_text())
        shutil.copyfile(extracted/manifest['media'],out/'system.atr')
        with emulator(BRIDGE,extracted/'altirraos-816.rom',out,pin=PIN) as b:
            for name,value in PIN['configuration'].items():b.config(name,str(value).lower() if isinstance(value,bool) else value)
            report['machine']=verify_machine(b,extracted/'altirraos-816.rom',PIN);b.mount(0,str(out/'system.atr'))
            bootstrap(b,p,bundle,extracted,report)
            def before(b):
                b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE ST')
                selected=address(p['image'],'selectedSession');marker=p['labels']['native_nmi']
                condition=f'dw(${selected:x})=1';b.bp_clear_all();b.bp_set(marker,condition=condition)
                run_to(b,marker,12000,180,condition)
                session=Session(b,p,directory,out,report);session.ready();session.startup()
                RasterSample().exercise(session)
            report['runtime'],_=execute(b,{**p,'output':out},before_run=before,
                timeout=300,frame_limit=24000,preloaded=True)
            ownership(b,p,p['output']);report['stacks']=stack_usage(b,p['build']['memory'])
            require(all(row['remaining_above_floor']>=0 for row in report['stacks'].values()),'Sample exhausted its interrupt stack reserve')
            if trace_from:
                attribute_cpu(report,read_events(out/'emulator.log',kinds={'cpu'}),p['build']['memory'])
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def reanalyze(bundle,out):
    path=out/'results.json';report=json.loads(path.read_text())
    require(report['zip_sha256']==sha256(bundle/'exec816-demo.zip'),'Reanalysis package changed')
    require(report['runtime']['status']==0 and report['runtime']['guards']=='intact' and
            all(report['coexistence'].values()) and
            all(row['remaining_above_floor']>=0 for row in report['stacks'].values()),
            'Reanalysis requires completed guest, ownership, stack and cleanup checks')
    previous=dict(sha256=sha256(path),status=report['status'],error=report.get('error'))
    attribute_cpu(report,read_events(out/'emulator.log',kinds={'cpu'}),read_build(bundle)['build']['memory'])
    report.update(status='pass',reanalysis=previous);report.pop('error',None)
    path.write_text(json.dumps(report,indent=2)+'\n');return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--trace-from',type=Path,help='Recorded same-package run supplying verified relocated call markers')
    parser.add_argument('--analyze-only',action='store_true',help='Recompute CPU attribution from a completed guest run')
    args=parser.parse_args()
    report=reanalyze(args.bundle.resolve(),args.output.resolve()) if args.analyze_only else run(args.bundle.resolve(),args.output.resolve(),args.trace_from)
    print(report['status'])
