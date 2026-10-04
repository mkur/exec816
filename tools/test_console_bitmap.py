#!/usr/bin/env python3
"""Exact bitmap CON: presentation and worker-owned ordinary C calls."""
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
from bitmap_console_oracle import Terminal
from bitmap_console_trace import observation,intervals
from generate_console import constants


def run(out,mode,replay=False,observe=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    p=read_build(out/'program') if replay else build_bitmap(ROOT/'tests/programs/console_bitmap.act',out,mode=='opt',probe=True)
    foreign=json.loads((out/'c-image.json').read_text());sy=foreign['symbols']
    require(p['build']['optimize']==(mode=='opt') and sha256(p['xex'])==p['build']['xex_sha256'],'Changed replay image')
    result=dict(status='running',tier='development',mode=mode,build=p['build'],pin=PIN,
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),observations=[])
    address=lambda name:next(d['address'] for d in p['image']['data'] if '_BITMAPTEST_'+name+'_' in d['name'])
    try:
        with observation(foreign,p,observe,module='BITMAPTEST') as marks, emulator(BRIDGE,ROM,out,pin=PIN) as b:
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
                terminal=Terminal(80,30)
                edits={5:b'AB',6:b'\x08',7:b'\rZ',8:b'C',9:b' abd\n'}
                for stage in range(1,10):
                    if stage==9:
                        instance=p['build']['memory']['console_storage']['INSTANCE']
                        ready=instance+constants()['INSTANCE_READREADY']
                        reach(f'db(${ready:x})=2')
                        for key in ('A','B','C','BACKSPACE','D','RETURN'):
                            require(b._cmd_ok(f'KEY {key} down')['raw_scan'],'Physical key required')
                            reach(f'@frame>={b.eval_expr("@frame")+4}')
                            b._cmd_ok(f'KEY {key} up')
                            reach(f'@frame>={b.eval_expr("@frame")+2}')
                    reach(f'dw(${address("CHECKPOINT"):x})={stage}')
                    if stage==1 and 'ConsoleProbeResults' in sy:
                        raw=b.memdump(sy['ConsoleProbeResults'],80)
                        records=[]
                        for n in range(2):
                            row=raw[n*40:(n+1)*40];w=lambda i:int.from_bytes(row[i:i+2],'little')
                            require([w(0),w(2),w(4)]==[(p['labels']['console_bitmap_call']-1)&65535,0x5678,0x9abc],'Bridge lost full registers: '+row.hex())
                            require(w(6)==w(32) and w(8)==w(34),'Bridge lost S/D')
                            require(row[10:12]==bytes([0,0]),'Bridge lost P/DBR: '+row.hex())
                            require([w(12+i*2) for i in range(10)]==list(range(0x5a00,0x5a0a)),'Bridge lost lower DP')
                            records.append(dict(stack=w(6),dp=w(8),registers=row.hex()))
                        require((records[0]['stack']^records[1]['stack'])&1,'Missing odd/even bridge entry')
                        result['bridge_context']=records
                    reach(f'@frame>={b.eval_expr("@frame")+2}')
                    model=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
                    if stage in (1,3):
                        for row in range(30):
                            for col in range(79 if row==29 else 80):
                                ch=33+(row*7+col)%90
                                for y in range(8):
                                    for x in range(8):
                                        if model.font[y*256+ch]&(128>>x):model.pixel(col*8+x,row*8+y,1)
                    if stage in (1,3,4):
                        x,y=(632,239) if stage in (1,3) else (0,7)
                        for column in range(8):model.pixel(x+column,y,1)
                    if stage in edits:
                        terminal.feed(edits[stage])
                        terminal.paint(model,0,0,True)
                    folder=out/f'stage-{stage}';folder.mkdir(exist_ok=True)
                    result['observations'].append(dict(stage=stage,pixels=pixels(b,folder,model.packed())))
                    b.memload(address('GATE'),stage.to_bytes(2,'little'))
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timer_irq=False,timeout=180,frame_limit=10000)
            require(b.memdump(saved['screen'],960)==saved['bytes'] and b.memdump(0x22f,3)==saved['dma'],'OS screen not restored')
            require(b.memdump(0x2f0,1)==saved['cursor'] and b.memdump(0x208,2)==saved['input'],'OS input not restored')
            ownership(b,p,p['output'])
            if observe:b.profile_stop()
            result.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True))
        if observe:
            result['operations']=intervals(out/'emulator.log',marks,9)
            for sample in result['operations']:
                if sample['kind']=='idle':
                    require(not sample['calls'],'Settled caret submitted work: '+str(sample))
                elif sample['stage'] in (5,6,7,8):
                    expected=2 if sample['stage']==7 else 1
                    require(sample['calls'].get('GemDrawingText',0)==expected,
                            'Unexpected caret/text redraws: '+str(sample))
                    require(sample['calls'].get('GemDrawingFill',0)==1,
                            'Missing new caret: '+str(sample))
    except Exception as error:result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('Bitmap console passed',mode,flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True);p.add_argument('--mode',choices=('raw','opt'),default='opt');p.add_argument('--replay',action='store_true');p.add_argument('--observe',action='store_true');a=p.parse_args();run(a.output,a.mode,a.replay,a.observe)
