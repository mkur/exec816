"""Focused execution checks for original MGVIEW and the shared viewer port."""
import json
import re
import time

from prepare_st_reference import sha256
from prepare_magic_text import controlled, reports, wait_for
from prepare_magic_scroll import ready
from test_magic_text import states


def pixels(frame,x,y,width,height):
    if len(frame)!=32000 or min(x,y)<0 or x+width>640 or y+height>400:
        raise ValueError('Invalid ST framebuffer crop')
    return bytes((frame[row*80+column//8]>>(7-column%8))&1
        for row in range(y,y+height) for column in range(x,x+width))


def capture(output,profiles):
    results=[]
    (output/'results.json').unlink(missing_ok=True)
    for name,profile in profiles.items():
        directory=output/name;capture_dir=directory/'capture';capture_dir.mkdir(exist_ok=True)
        with controlled(directory,profile,'capture/check.log') as (process,control):
            def command(value):control.sendall((value+'\n').encode('ascii'))
            wait_for(process,lambda:ready(directory,name),name+' initial document',timeout=40)
            command('hatari-option --fast-forward false')
            time.sleep(.2)
            def shot(label):
                image=capture_dir/(label+'.png');frame=capture_dir/(label+'.bin')
                image.unlink(missing_ok=True);frame.unlink(missing_ok=True)
                command('hatari-debug screenshot '+str(image))
                command('hatari-debug savebin '+str(frame)+' "($44e)" #32000')
                wait_for(process,lambda:frame.exists() and frame.stat().st_size==32000,label)
                return frame.read_bytes()
            launch=(directory/'drive-c/LAUNCH.LOG').read_text()
            match=re.search(r'counter=0 text=(\d+)',launch)
            if not launch.startswith('magic=1 ') or not match or int(match[1])<=0:
                raise ValueError('Missing independent viewer-only MagiC session')
            if name=='ported':
                row=states(reports(directory))[-1]
                if row['loads']!=1 or row['bytes']!=56746 or row['lines']!=901:
                    raise ValueError('The port did not load the comparison document')
                work=row['work'];x,y=work[0]+4,work[1]+4;cell=8;width=row['columns']*8
            else:
                match=re.search(r'ready viewer=(\d+) window=(\d+) work=(\d+),(\d+),(\d+),(\d+)',launch)
                if not match:raise ValueError('Original MGVIEW did not open its document window')
                work=list(map(int,match.groups()[2:]));x,y=work[:2];width=work[2];cell=16
            before=shot('initial')
            observer_before=reports(directory) if name=='ported' else ''
            command('hatari-event keypress 0x50')
            time.sleep(.5)
            after=shot('line-down')
            old_second=pixels(before,x,y+cell,width,cell)
            new_first=pixels(after,x,y,width,cell)
            if not any(new_first) or new_first!=old_second:
                raise ValueError(name+' did not scroll its text up by exactly one line')
            command('hatari-event keypress 0x48')
            time.sleep(.5)
            reverse=shot('line-up')
            if pixels(reverse,x,y,width,cell)!=pixels(before,x,y,width,cell):
                raise ValueError(name+' did not restore the first line')
            if name=='ported' and reports(directory)!=observer_before:
                raise ValueError('Diagnostic observation performed file I/O while scrolling')
            changed=sum(a!=b for a,b in zip(pixels(before,x,y,width,cell),new_first))
            if not changed:raise ValueError('Scrolling changed no visible glyphs')
            (capture_dir/'LAUNCH.LOG').write_text(launch)
            if name=='ported':(capture_dir/'TEXT.LOG').write_text(reports(directory))
            command('hatari-debug quit');process.wait(timeout=10)
        results.append(dict(viewer=name,status='pass',work=work,font_cell=[8,cell],
            first_row_changed_pixels=changed,normal_speed=True,background_counter=False,
            document_sha256=profile['document_sha256'],
            artifacts={str(p.relative_to(output)):sha256(p) for p in
                [*(capture_dir/(label+suffix) for label in ('initial','line-down','line-up')
                    for suffix in ('.png','.bin')),capture_dir/'LAUNCH.LOG']}))
    if results[0]['document_sha256']!=results[1]['document_sha256']:
        raise ValueError('The comparison uses different documents')
    result=dict(status='pass',tier='development',qualification=False,
        scope='Real keyboard line-down/up and exact row pixel correspondence at normal speed; no timing benchmark.',
        viewers=results)
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MGVIEW and ported viewer: same document, normal-speed line down/up pixels passed')
    return result
