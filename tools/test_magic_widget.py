#!/usr/bin/env python3
"""Functional shared Widget/Counter checks on emitted 68000 code, without timings."""
import json
import time
from prepare_magic_widget import CASES,controlled,descriptors
from prepare_magic_text import wait_for
from prepare_magic_counters import digit_pixels
from prepare_st_reference import sha256
from widget_model import FIELDS,SIZE
from widget_observe import widget_state


def mono_region(frame,rect):
    if len(frame)!=32000:raise ValueError('Incomplete ST monochrome framebuffer')
    x,y,w,h=rect
    if x<0 or y<0 or w<=0 or h<=0 or x+w>640 or y+h>400:
        raise ValueError('Region outside ST framebuffer')
    return bytes((frame[row*80+col//8]>>(7-col%8))&1
                 for row in range(y,y+h) for col in range(x,x+w))


def capture(out,record):
    result=dict(status='running',tier='development',qualification=False,cases=[])
    try:
        for mode in CASES:
            directory=out/mode;directory.mkdir(exist_ok=True)
            with controlled(out,record,mode,mode+'/hatari.log') as (process,control):
                def command(text):control.sendall((text+'\n').encode('ascii'))
                serial=0
                def memory(address,size):
                    nonlocal serial
                    serial+=1
                    path=directory/('memory-%d.bin'%serial)
                    command(f'hatari-debug savebin {path} ${address:x} #{size}')
                    wait_for(process,lambda:path.exists() and path.stat().st_size==size,'guest memory')
                    raw=path.read_bytes();path.unlink()
                    return raw
                def shot(name):
                    path=directory/(name+'.bin');path.unlink(missing_ok=True)
                    command('hatari-debug screenshot '+str(directory/(name+'.png')))
                    command('hatari-debug savebin '+str(path)+' "($44e)" #32000')
                    wait_for(process,lambda:path.exists() and path.stat().st_size==32000,name+' pixels')
                    return path.read_bytes()
                wait_for(process,lambda:descriptors(out,'widget') and
                    (mode=='solo' or descriptors(out,'pulse')),'shared apps',timeout=40)
                widget=descriptors(out,'widget');pulse=descriptors(out,'pulse')
                base=widget['ready']-FIELDS['ready']
                def state():return widget_state(memory(base,SIZE),'big')
                def counter():
                    raw=memory(pulse['ready']-12,46)
                    return dict(count=int.from_bytes(raw[14:18],'big'),
                        paints=int.from_bytes(raw[18:22],'big'),
                        work=[int.from_bytes(raw[i:i+2],'big',signed=True) for i in (38,40,42,44)])
                first=wait_for(process,lambda:(row if row['ready'] and row['paints'] else None)
                    if (row:=state()) else None,'first Widget paint')
                if first['work']!=[32,56,304,128] or first['actions'] or first['selected']:
                    raise ValueError('Incorrect initial Widget state or canvas')
                if mode!='solo':
                    if pulse['id']==widget['id'] or pulse['window']==widget['window'] or \
                            pulse['period']!=100 or pulse['silent']!=int(mode=='silent'):
                        raise ValueError('Incorrect independent Counter setup')
                    wait_for(process,lambda:counter()['paints']>0,'initial Counter exposure')
                command('hatari-option --fast-forward false')
                time.sleep(.2)
                start=state();before=shot('initial')
                count_before=counter() if pulse else None
                reports_before={name:(out/'drive-c'/name).read_bytes() for name in
                    (('WIDGET.LOG','PULSE.LOG') if pulse else ('WIDGET.LOG',))}
                time.sleep(.8)
                idle=state();count_idle=counter() if pulse else None
                if (idle['actions'],idle['paints'])!=(start['actions'],start['paints']):
                    raise ValueError('Foreground Widget polled or repainted while idle')
                if pulse and count_idle['count']<=count_before['count']:
                    raise ValueError('Background timer did not progress')
                if mode=='silent' and count_idle['paints']!=count_before['paints']:
                    raise ValueError('Silent Counter painted on a timer')
                if mode=='paint' and count_idle['paints']<=count_before['paints']:
                    raise ValueError('Painting Counter did not redraw')
                # Real keyboard delivery exercises the same activation as Toggle.
                # Poll completion fields through the debugger, outside guest drawing.
                for action in (1,2,3):
                    previous=state()['paints']
                    command('hatari-event keypress 0x39')
                    wait_for(process,lambda:(row if row['actions']==action and
                        row['paints']>previous else None) if (row:=state()) else None,
                        'Widget activation')
                changed=state();after=shot('toggled')
                if changed['label']!='Clicks: 000003' or changed['selected']!=1:
                    raise ValueError('Activation did not update label and button')
                x,y,_,_=first['work']
                for region in ((x+16,y+12,112,16),(x+16,y+44,128,24)):
                    if mono_region(before,region)==mono_region(after,region):
                        raise ValueError('Changed Widget model did not reach the screen')
                if mode=='paint' and digit_pixels(before,count_before['work'])==digit_pixels(after,count_idle['work']):
                    raise ValueError('Counter model advanced without visible digit changes')
                if mode=='silent' and digit_pixels(before,count_before['work'])!=digit_pixels(after,count_idle['work']):
                    raise ValueError('Silent Counter changed its visible digits')
                if any((out/'drive-c'/name).read_bytes()!=raw for name,raw in reports_before.items()):
                    raise ValueError('Observation performed guest file I/O during interaction')
                command('hatari-event keypress 0x10')
                wait_for(process,lambda:'exit=0 ready=0 opened=0 window=-1' in
                    (out/'drive-c/WIDGET.LOG').read_text(),'normal Widget retirement')
                # The process memory can be reused after exit; only use the exit
                # report as the retirement oracle. Counter's memory remains live.
                if pulse:
                    last=counter()['count'];time.sleep(.4)
                    if counter()['count']<=last:raise ValueError('Counter stopped when Widget exited')
                for name in ('LAUNCH.LOG','WIDGET.LOG',*(['PULSE.LOG'] if pulse else [])):
                    (directory/name).write_bytes((out/'drive-c'/name).read_bytes())
                result['cases'].append(dict(mode=mode,initial=first,idle=idle,activated=changed,
                    counter_before=count_before,counter_idle=count_idle,widget_exit=True,
                    periodic_guest_log_writes=0,physical_input='keyboard Space and Q',
                    counter_continues_after_widget_exit=bool(pulse)))
                command('hatari-debug quit');process.wait(timeout=10)
                print('MagiC Widget:',mode,'passed',flush=True)
        result.update(status='pass',artifacts={str(p.relative_to(out)):sha256(p)
            for mode in CASES for p in sorted((out/mode).iterdir()) if p.suffix in ('.bin','.png','.LOG')})
    except Exception as error:
        result.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
