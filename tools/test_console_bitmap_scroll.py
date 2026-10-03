#!/usr/bin/env python3
"""Independent scanout oracle for scrolls, narrow/hidden tiles and caret."""
import argparse,json
from pathlib import Path
import adapter_state as adapter
from build_bitmap_console import build_bitmap
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from test_dos_stack import execute,ownership
from test_cooperative import data
from gem_render_oracle import Raster,font_bytes
from test_gem_interactive import pixels
from bitmap_console_trace import observation,intervals


def run(out,mode,replay=False,observe=False,performance=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/console_bitmap_scroll.act',out,mode=='opt',probe=False)
    foreign=json.loads((out/'c-image.json').read_text());sy=foreign['symbols']
    require(p['build']['optimize']==(mode=='opt') and sha256(p['xex'])==p['build']['xex_sha256'],'Changed replay image')
    result=dict(observed=observe,status='running',tier='development',mode=mode,build=p['build'],pin=PIN,
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
                if observe:b.profile_start()
                saved.update(screen=b.peek16(88),dma=b.memdump(0x22f,3),cursor=b.memdump(0x2f0,1),input=b.memdump(0x208,2))
                saved['bytes']=b.memdump(saved['screen'],960)
                from bitmap_console_oracle import scroll_scenes
                scenes=scroll_scenes(font_bytes(out/'selected/src/vdi/font8x8.c'))
                for stage,expected in enumerate(scenes,1):
                    reach(f'dw(${address("CHECKPOINT"):x})={stage}')
                    reach(f'@frame>={b.eval_expr("@frame")+2}')
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    result['observations'].append(dict(stage=stage,pixels=pixels(b,folder,expected)))
                    reach(f'@frame>={b.eval_expr("@frame")+2}')
                    b.memload(address('GATE'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timer_irq=True,timeout=180,frame_limit=10000)
            require(b.memdump(saved['screen'],960)==saved['bytes'] and b.memdump(0x22f,3)==saved['dma'],'OS screen not restored')
            require(b.memdump(0x2f0,1)==saved['cursor'] and b.memdump(0x208,2)==saved['input'],'OS input not restored')
            if observe:b.profile_stop()
            ownership(b,p,p['output'])
            result.update(runtime=runtime,checks=data(b,p['image'],'checks',True))
        if observe:
            result['operations']=intervals(out/'emulator.log',marks,len(result['observations']))
            for sample in result['operations']:
                if sample['kind']=='idle':require(not sample['calls'],'Clean console submitted work: '+str(sample))
                elif sample['stage'] in (2,3,7):
                    require(sample['calls'].get('GemDrawingCopy',0)+sample['calls'].get('GemDrawingScrollStart',0)>0,'Eligible scroll did not copy')
                    require(sample['calls'].get('blit_glyph',0)<=4,'Eligible scroll redrew unchanged glyphs')
                elif sample['stage']==8:require(sample['calls'].get('GemDrawingCopy',0)==0,'Height-one copy is not empty')
        if performance and observe:result['performance']=summarize(out/'emulator.log',timing,result['operations'])
        result['status']='pass'
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/('results-replay.json' if replay and not observe else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap scrolling passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--observe',action='store_true');p.add_argument('--performance',action='store_true');a=p.parse_args();run(a.output,a.mode,a.replay,a.observe,a.performance)
