#!/usr/bin/env python3
"""Focused original MGVIEW disk, drawing, interaction and Process lifetime check."""
import argparse
import hashlib
import json
import math
from pathlib import Path
from build_mgview import build as viewer
from build_gem_desktop import build_desktop
from c_program import ABI
from desktop_mouse import schedule,slow_schedule
from sio_transaction_trace import BASE_HZ
from gem_render_oracle import Raster,DESKTOP_PALETTE,PENS,font_bytes
from make_data_disk import make
from native_program import ROOT,read_build,require,verify_machine,sha256
from os_boundary import emulator,run_to
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM

LAYOUT=[('WORD',2),('huge pointer',4),('WINDOW',338),('outer',260),('work',268),
        ('vertical',276),('horizontal',300),('file',328),('index',332),('tabs',336)]
DOCUMENT=b''.join((f'Row {i:03d}\t'+''.join(chr(65+(i+j)%26) for j in range(100))+'\r\n').encode() for i in range(50))


def run(out,reuse=False,scroll=False,failures=False,interactions=False,document=None,vertical_only=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    content=Path(document).read_bytes() if document else DOCUMENT
    if not reuse:
        viewer(out/'apps/mgview',probes=[(ROOT/'tests/programs/mgview_layout.c',LAYOUT)])
        program=build_desktop(out,source=ROOT/'tests/programs/c_mgview.act',build_applications=False,
            program_output=out/'program',release_compiler=True,system_mount='D1',
            dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)])
    else:program=read_build(out/'program')
    apps={name:json.loads((out/'apps'/name/'app.json').read_text()) for name in ('mgview',)}
    media=out/'media';media.mkdir(exist_ok=True)
    for name in apps:(media/(name.upper()+'.APP')).write_bytes((out/'apps'/name/'program.app').read_bytes())
    (media/'VIEW.TXT').write_bytes(content);(media/'EMPTY.TXT').write_bytes(b'')
    if failures:
        (media/'BIG.TXT').write_bytes(b'x'*65520)
        (media/'TALL.TXT').write_bytes(b'\n'*16381)
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,binary_names={p.name for p in media.iterdir()})
    at=lambda name:next(d['address'] for d in program['image']['data'] if '_CMGVIEWTEST_'+name.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,cases=[],bank_zero_delta=dict(fixed=0,root=0,kernel=0,private_idle=0,per_public_task=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.mount(0,str(out/'system.atr'));report['machine']=verify_machine(b,ROM,PIN)
            number=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
            def reach(condition):
                marker=program['labels']['native_cop'];condition=f'(@xpc=${marker:x})&({condition})'
                b.bp_clear_all();b.bp_set(marker,condition=condition)
                faults=[program['labels'][key] for key in ('heap_fault','stack_overflow','arithmetic_fault','done')]
                for fault in faults:b.bp_set(fault)
                original=b.regs
                def regs():
                    state=original();pc=b.eval_expr('@xpc')
                    if pc in faults:report['guest_fault']=dict(pc=pc,stack=b.eval_expr('@s'),state=state)
                    require(pc not in faults,'Guest fault/stopped: '+str(state));return state
                b.regs=regs
                try:run_to(b,marker,condition=condition,timeout=120,frame_limit=12000)
                finally:b.regs=original
            def frames(count):reach('@frame>=%d'%(b.eval_expr('@frame')+count))
            def symbols(name,base):return {key:base+value-(ABI['link_bank']<<16) for key,value in apps[name]['image']['symbols'].items()}
            paint_context=[0]
            def context_for(identity):
                from generate_aes_server import layout,ABI as AES_ABI
                resident=json.loads((out/'c-image.json').read_text())['symbols']
                raw=b.memdump(resident['contexts'],AES_ABI['constants']['CONTEXTS']*4)
                contexts=[int.from_bytes(raw[i:i+4],'little') for i in range(0,len(raw),4)]
                return next(c for c in contexts if c and number(c+layout()['Request']['fields']['global']+4)==identity)
            def picture(window,label,payload):
                from generate_aes_server import expected_layout
                depth=paint_context[0]+dict(expected_layout())['C context updateDepth']
                reach(f'dw(${depth:x})=0');frames(1)
                x,y,w,h=[number(window+268+i*2) for i in range(4)]
                vshift=number(window+280,4);hshift=number(window+304,4);tabs=number(window+336)
                font=font_bytes(out/'selected/src/vdi/font8x8.c');model=Raster(font)
                model.clip=(x,y,x+w-1,y+h-1);model.fill=0;model.apply(11,[x,y,x+w-1,y+h-1]);model.text=1
                lines=payload.replace(b'\r\n',b'\n').replace(b'\r',b'\n').splitlines()
                for row in range(h//8):
                    if row+vshift>=len(lines):break
                    line=lines[row+vshift].replace(b'\0',b' ')
                    if tabs:line=line.expandtabs(tabs)
                    line=line[:272]
                    model.apply(8,[x-hshift*8,y+row*8+6],list(line))
                colours=[None]*16
                for pen,hardware in enumerate(PENS):colours[hardware]=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
                path=out/(label+'.bgra');frame=b.rawscreen(str(path));raw=path.read_bytes()
                actual=b''.join(raw[yy*frame.stride+(xx+16)*4:yy*frame.stride+(xx+16)*4+3] for yy in range(y,y+h) for xx in range(x,x+w))
                expected=b''.join(colours[model.pixels[yy*640+xx]] for yy in range(y,y+h) for xx in range(x,x+w))
                if actual!=expected:
                    report['pixel_failure']=dict(label=label,work=[x,y,w,h],shift=[hshift,vshift],window=b.memdump(window,338).hex(),first=next(i for i,(a,c) in enumerate(zip(actual,expected)) if a!=c));b.screenshot(str(out/'failure.png'))
                require(actual==expected,'MGVIEW exact pixels differ: '+label)
                report.setdefault('pixels',[]).append(dict(label=label,pixels=w*h,shift=[hshift,vshift],sha256=hashlib.sha256(actual).hexdigest()))
                print('MGVIEW pixels:',label,flush=True)
                return actual
            def before(b):
                position=[320,120];b._cmd_ok('MOUSE ST')
                def move(x,y,held=False):
                    nonlocal position
                    cursor=lambda name:next(d['address'] for d in program['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
                    if held:
                        # Use isolated physical phases during a gesture. Coarse
                        # bursts can cause raw input loss, which cancels a drag.
                        position=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        distance=max(abs(a-c) for a,c in zip((x,y),position))
                        target=slow_schedule(b,program,position,(x,y))
                        frames(30+math.ceil((70000+math.ceil(distance/2)*130000)*50/BASE_HZ))
                        position=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        require(position==target,'Held pointer did not settle: '+str((target,position)))
                        return
                    # Schedule from observed coordinates after earlier packets
                    # settle; a transient exact coordinate is not completion.
                    for _ in range(3):
                        position=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        target=schedule(b,program,position,(x,y))
                        frames(40)
                        position=[number(cursor(n)) for n in ('cursorX','cursorY')]
                        if position==target:return
                    require(False,'Physical pointer did not settle: '+str((target,position)))
                def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(15 if down else 60)
                def drag(start,end):move(*start);edge(1);move(*end,held=True);edge(0)
                arguments=(b'SYS:BIG.TXT',b'SYS:TALL.TXT',b'') if failures else (b'"SYS:VIEW.TXT"',b'SYS:EMPTY.TXT',b'')
                for round,argument in enumerate(arguments):
                    phase=round*2+1;reach(f'dw(${at("phase"):x})={phase}')
                    base=number(at('bases'),4);sy=symbols('mgview',base)
                    b.memload(at('argument'),argument+b'\0');b.poke16(at('argBytes'),len(argument));b.poke16(at('go'),phase)
                    reach(f'dw(${at("phase"):x})={phase+1}')
                    if failures and argument:
                        from generate_aes_server import layout,expected_layout,ABI as AES_ABI
                        reach(f'dw(${sy["ap_id"]:x})>0')
                        resident=json.loads((out/'c-image.json').read_text())['symbols']
                        contexts=b.memdump(resident['contexts'],AES_ABI['constants']['CONTEXTS']*4)
                        candidates=[int.from_bytes(contexts[i:i+4],'little') for i in range(0,len(contexts),4)]
                        context=next(c for c in candidates if c and number(c+layout()['Request']['fields']['global']+4)==number(sy['ap_id']))
                        form=context+dict(expected_layout())['C context form']
                        reach(f'dw(${form:x})!=0');frames(20)
                        b._cmd_ok('KEY RETURN down');frames(3);b._cmd_ok('KEY RETURN up')
                        reach(f'dw(${form:x})=0');frames(10)
                        require(number(sy['nwindows'])==0 and number(sy['windows'],4)==0,'Rejected loader published a document')
                        report['cases'].append(dict(arguments=argument.decode(),rejected=True))
                    elif argument:
                        count=1
                        reach(f'dw(${sy["nwindows"]:x})={count}');frames(80)
                        window=number(sy['windows'],4);require(window,'Missing original window record')
                        paint_context[0]=context_for(number(sy['ap_id']))
                        move(632,0)
                        picture(window,f'round-{round}',content if round==0 else b'')
                        if scroll and round==0:
                            # Atari physical cursor keys use Ctrl with -, = and *.
                            actions=(('EQUALS',(0,1)),('MINUS',(0,0))) if vertical_only else (('EQUALS',(0,1)),('ASTERISK',(1,1)),('MINUS',(1,0)))
                            for key,expected_shift in actions:
                                b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY '+key+' down');frames(3)
                                b._cmd_ok('KEY '+key+' up');b._cmd_ok('KEY CTRL up');frames(50)
                                require((number(window+304,4),number(window+280,4))==expected_shift,'Scroll key did not change the original model: '+key)
                                picture(window,'scroll-'+key,content)
                            if not vertical_only:
                                # This pinned bridge has no raw PLUS key name; use GEM's left-arrow gadget.
                                ox,oy,ow,oh=[number(window+260+i*2) for i in range(4)]
                                move(ox+8,oy+oh-5)
                                b._cmd_ok('MOUSE AT 2000 0 0 1');frames(3)
                                b._cmd_ok('MOUSE AT 2000 0 0 0');frames(50)
                                require(number(window+304,4)==0,'Horizontal left gadget did not restore the model')
                                picture(window,'scroll-left-gadget',content)
                        if interactions and round==0:
                            outer=lambda:tuple(number(window+260+i*2) for i in range(4))
                            ox,oy,ow,oh=outer()
                            drag((ox+ow-5,oy+oh-5),(ox+ow-133,oy+oh-53))
                            report['resize']=dict(before=[ox,oy,ow,oh],after=outer())
                            require(outer()[2]<ow and outer()[3]<oh,'Size message did not resize the viewer')
                            move(632,0);picture(window,'resized',content)
                            ox,oy,ow,oh=outer()
                            drag((ox+80,oy+5),(ox+104,oy+13))
                            require(outer()[:2]==(ox+24,oy+8),'Move message did not move the viewer')
                            move(632,0);picture(window,'moved',content)
                            # Both drags use the stored track/thumb rectangles. They
                            # verify the manager's object-based WM_*SLID path.
                            for axis,object_id,offset in (('vertical',10,280),('horizontal',14,304)):
                                from generate_desktop import layout as dl
                                from generate_gem_objects import layout as gl
                                desktop=next(d['address'] for d in program['image']['data'] if '_DESKSTATE_SERVICE_' in d['name'])
                                service=number(desktop,3);fields=dl()['Window']['fields']
                                record=0
                                for slot in range(6):
                                    candidate=number(service+dl()['Service']['fields']['windows']+slot*3,3)
                                    if candidate and number(candidate+fields['gui'])==number(window):record=candidate;break
                                require(record,'Missing canonical viewer frame')
                                tree=record+fields['frame']+gl()['Frame']['fields']['tree']
                                def object_rect(obj):
                                    import struct
                                    raw=b.memdump(tree+obj*24,24)
                                    x,y,w,h=struct.unpack_from('<4h',raw,16)
                                    root=b.memdump(tree,24);rx,ry=struct.unpack_from('<2h',root,16)
                                    if obj in (10,14):
                                        parent=b.memdump(tree+(obj-1)*24,24);px,py=struct.unpack_from('<2h',parent,16);x+=px;y+=py
                                    return rx+x,ry+y,w,h
                                x,y,w,h=object_rect(object_id)
                                start=(x+w//2,y+h//2)
                                end=(start[0],start[1]+16) if axis=='vertical' else (start[0]+16,start[1])
                                before_shift=number(window+offset,4)
                                drag(start,end)
                                after_shift=number(window+offset,4)
                                require(after_shift>before_shift,'Thumb did not scroll: '+axis)
                                report.setdefault('thumbs',[]).append(dict(axis=axis,before=before_shift,after=after_shift))
                                move(632,0);picture(window,'thumb-'+axis,content)
                        frames(4)
                        report['cases'].append(dict(arguments=argument.decode(),documents=number(sy['nwindows'])))
                        if round==0:
                            b._cmd_ok('KEY CTRL down');b._cmd_ok('KEY U down');frames(3)
                            b._cmd_ok('KEY U up');b._cmd_ok('KEY CTRL up')
                            reach(f'dw(${sy["nwindows"]:x})=0')
                    else:frames(20);require(number(sy['nwindows'])==0,'No-argument viewer opened a document')
                    b.poke16(at('go'),phase+1)
                b.bp_clear_all()
            report['runtime'],_=execute(b,program,before_run=before,timeout=300,frame_limit=30000)
            ownership(b,program,program['output'])
            require(number(at('completed'))==3,'Viewer lifetimes incomplete')
            report.update(status='pass',completed=3,checks=number(at('checks')),app_sha256={name:sha256(out/'apps'/name/'program.app') for name in apps})
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:
        payload=json.dumps(report,indent=2)+'\n'
        (out/'results.json').write_text(payload)
        (out/('results-'+('reference' if document else 'failures' if failures else 'interactions' if interactions else 'scroll' if scroll else 'smoke')+'.json')).write_text(payload)
    print('MGVIEW development check passed: three lifetimes, exact pixels and guards',flush=True)
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True);parser.add_argument('--reuse',action='store_true');parser.add_argument('--scroll',action='store_true');parser.add_argument('--failures',action='store_true');parser.add_argument('--interactions',action='store_true')
    parser.add_argument('--document',type=Path);parser.add_argument('--vertical-only',action='store_true')
    args=parser.parse_args();run(args.output,args.reuse,args.scroll,args.failures,args.interactions,args.document,args.vertical_only)
