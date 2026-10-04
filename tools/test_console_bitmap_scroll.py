#!/usr/bin/env python3
"""Independent scanout oracle for scrolls, narrow/hidden tiles and caret."""
import argparse,json,shutil
import generate_tasks
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from stack_budget import stack_usage
from gem_render_oracle import Raster,font_bytes
from test_gem_interactive import pixels
from bitmap_console_trace import observation,intervals


def run(out,mode,replay=False,observe=False,performance=False,batch=False,phase=0,action=0):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    original=generate_tasks.policy_modules
    def instrument(*args,**kwargs):
        directory=original(*args,**kwargs)
        source=ROOT/'lib/console/console-bitmap-display.inc'
        text=source.read_text();needle='      view.scrollState=3'
        require(text.count(needle)==1,'Batch launch boundary changed')
        target=directory/'batch-launch.inc'
        target.write_text(text.replace(needle,needle+'\n      BATCHPROBE.Launched(rows)'))
        path=directory/'consoledisplay.act'
        path.write_text(path.read_text().replace('USE A816MEMORY\n','USE A816MEMORY\nUSE BATCHPROBE\n',1).replace(str(source),str(target)))
        text=target.read_text().replace('PUBLIC PROC Poll(BYTE notified)\n',
            'PUBLIC PROC Poll(BYTE notified)\n'
            '  IF notified<>0 THEN\n    BATCHPROBE.notice=1\n  FI\n'
            '  notified=BATCHPROBE.notice\n').replace('    CONSOLEBITMAP.Poll()',
            '    IF BATCHPROBE.Blocked()<>0 THEN\n      RETURN\n    FI\n'
            '    CONSOLEBITMAP.Poll()\n    BATCHPROBE.notice=0')
        target.write_text(text)
        path=directory/'consoledriver.act';text=path.read_text().replace('USE EXEC\n','USE EXEC\nUSE BATCHPROBE\n',1)
        text=text.replace('IF CONSOLEBITMAP.Pending()=0 AND', 'IF CONSOLEBITMAP.Pending()=0 AND BATCHPROBE.Blocked()=0 AND')
        text=text.replace('          CONSOLEDISPLAY.Present(view,instance)',
            '          IF BATCHPROBE.Blocked()=0 THEN\n            CONSOLEDISPLAY.Present(view,instance)\n          FI')
        text=text.replace('IF batch.phase=CONSOLETYPES.BATCH_GATHER THEN\n          again=0',
            'IF batch.phase=CONSOLETYPES.BATCH_GATHER OR BATCHPROBE.Blocked()<>0 THEN\n          again=0')
        path.write_text(text)
        return directory
    if batch:
        (out/'batchprobe.act').write_bytes((ROOT/'tests/programs/batchprobe.act').read_bytes())
        generate_tasks.policy_modules=instrument
    try:
        source=ROOT/'tests/programs'/('console_batch_bitmap.act' if batch else 'console_bitmap_scroll.act')
        p=read_build(out/'program') if replay else build_bitmap(source,out,mode=='opt',probe=False)
    finally:generate_tasks.policy_modules=original
    foreign=json.loads((out/'c-image.json').read_text());sy=foreign['symbols']
    require(p['build']['optimize']==(mode=='opt') and sha256(p['xex'])==p['build']['xex_sha256'],'Changed replay image')
    result=dict(observed=observe,batch=batch,phase=phase,action=action,status='running',tier='development',mode=mode,build=p['build'],pin=PIN,
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),observations=[])
    address=lambda name:next(d['address'] for d in p['image']['data'] if '_BITMAPSCROLL_'+name+'_' in d['name'])
    from bitmap_console_performance import markers,summarize
    timing=markers(p,foreign,out/'drawing') if performance else None
    try:
        with observation(foreign,p,observe,timing) as marks, emulator(BRIDGE,ROM,out,pin=PIN) as b:
            require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
            result['machine']=verify_machine(b,ROM,PIN);saved={}
            def reach(condition):
                b.bp_clear_all();marker=p['labels']['native_nmi'];b.bp_set(marker,condition=condition)
                b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
                original=b.regs
                def regs():
                    value=original()
                    if int(value['PC'].lstrip('$'),16)==p['labels']['done']:
                        require(b.peek16(adapter.STATE)==65535,'Bitmap stopped: '+str(b.peek16(adapter.STATE)))
                    return value
                b.regs=regs
                try:run_to(b,marker,frame_limit=15000,timeout=60,condition=condition)
                except Exception:
                    print('Status/checks/regs',b.peek16(adapter.STATE),data(b,p['image'],'checks',True),b.regs(),flush=True);raise
                finally:b.regs=original
            def before(b):
                if batch:
                    b.memload(address('TARGETPHASE'),bytes([phase]))
                    b.memload(address('ACTION'),bytes([action]))
                if observe:b.profile_start()
                saved.update(screen=b.peek16(88),dma=b.memdump(0x22f,3),cursor=b.memdump(0x2f0,1),input=b.memdump(0x208,2))
                saved['bytes']=b.memdump(saved['screen'],960)
                from bitmap_console_oracle import scroll_scenes,batch_scenes
                scenes=(batch_scenes if batch else scroll_scenes)(font_bytes(out/'selected/src/vdi/font8x8.c'))
                for stage,expected in enumerate(scenes,1):
                    reach(f'dw(${address("CHECKPOINT"):x})={stage}')
                    reach(f'@frame>={b.eval_expr("@frame")+2}')
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    result['observations'].append(dict(stage=stage,pixels=pixels(b,folder,expected)))
                    reach(f'@frame>={b.eval_expr("@frame")+2}')
                    b.memload(address('GATE'),stage.to_bytes(2,'little'))
                if batch:
                    reach(f'dw(${address("CHECKPOINT"):x})=6')
                    accepted=data(b,p['image'],'cutBytes',True)[0]
                    expected=batch_scenes(font_bytes(out/'selected/src/vdi/font8x8.c'),accepted)[-1]
                    folder=out/'stage-6';folder.mkdir(exist_ok=True)
                    result['observations'].append(dict(stage=6,accepted=accepted,
                        pixels=pixels(b,folder,expected) if action<4 else 'stopped'))
                    b.memload(address('GATE'),b'\6\0')
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timer_irq=False,timeout=180,frame_limit=10000)
            require(b.memdump(saved['screen'],960)==saved['bytes'] and b.memdump(0x22f,3)==saved['dma'],'OS screen not restored')
            require(b.memdump(0x2f0,1)==saved['cursor'] and b.memdump(0x208,2)==saved['input'],'OS input not restored')
            if observe:b.profile_stop()
            ownership(b,p,p['output'])
            result.update(runtime=runtime,checks=data(b,p['image'],'checks',True),
                          stack_usage=stack_usage(b,p['build']['memory']))
            if batch:
                result['batch_launches']={name:data(b,p['image'],name,True)[0]
                    for name in ('batchLaunches','multiLaunches','maxRows')}
                require(result['batch_launches']['multiLaunches']>0 and
                        1<result['batch_launches']['maxRows']<=4,'No bounded multi-row hardware launch')
        if observe:
            result['operations']=intervals(out/'emulator.log',marks,len(result['observations']))
            for sample in result['operations']:
                if sample['kind']=='idle':require(not sample['calls'],'Clean console submitted work: '+str(sample))
                elif not batch and sample['stage'] in (2,3,7):
                    require(sample['calls'].get('GemDrawingCopy',0)+sample['calls'].get('GemDrawingScrollStart',0)>0,'Eligible scroll did not copy')
                    glyphs=sum(sample['calls'].get(name,0) for name in ('blit_glyph','_text_record'))
                    require(glyphs<=4,'Eligible scroll redrew unchanged glyphs')
                elif not batch and sample['stage']==8:require(sample['calls'].get('GemDrawingCopy',0)==0,'Height-one copy is not empty')
        if performance and observe:
            result['performance']=summarize(out/'emulator.log',timing,result['operations'])
            from blitter_completion_trace import analyze
            result['completion_timing']=analyze(out/'emulator.log',timing)
            rows=result['completion_timing']['scrolls']
            require('async_launch' not in timing or (rows and all(row['polls']==1 and row['waits']>=1 and row['yields']==0
                    and row['irq'] is not None and row['expired'] is None for row in rows)),
                    'Scroll worker did not wait for one completion notification')
        if observe:shutil.copyfile(out/'emulator.log',out/'observed-emulator.log')
        result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/('results-replay.json' if replay and not observe else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap scrolling passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--observe',action='store_true');p.add_argument('--performance',action='store_true');p.add_argument('--batch',action='store_true');a=p.parse_args();run(a.output,a.mode,a.replay,a.observe,a.performance,a.batch)
