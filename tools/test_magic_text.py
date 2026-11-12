#!/usr/bin/env python3
"""Focused emitted-68000 checks for the original viewer on pinned MagiC."""
import json
import re
import time

from prepare_st_reference import sha256
from prepare_magic_counters import digit_pixels, parse_counter
from prepare_magic_text import controlled, reports, wait_for


def states(text):
    result=[]
    for line in text.splitlines():
        if not line.startswith('state '): continue
        fields,status=line[6:].split(' status=',1)
        row={key:([int(n) for n in value.split(',')] if key=='work' else int(value))
            for key,value in (field.split('=',1) for field in fields.split())}
        row['status']=status
        result.append(row)
    return result


def text_pixels(frame,work,row,columns):
    if len(frame)!=32000: raise ValueError('Incomplete ST monochrome framebuffer')
    x,y=work[0]+4,work[1]+4+row*8
    if x<0 or y<0 or x+columns*8>640 or y+8>400:
        raise ValueError('Text row outside the framebuffer')
    return bytes((frame[line*80+pixel//8]>>(7-pixel%8))&1
        for line in range(y,y+8) for pixel in range(x,x+columns*8))


def capture(output,record):
    directory=output/'capture';directory.mkdir(exist_ok=True)
    (output/'results.json').unlink(missing_ok=True)
    checkpoints={}
    with controlled(output,record,'capture/hatari.log') as (process,control):
        def command(text): control.sendall((text+'\n').encode('ascii'))
        def latest():
            rows=states(reports(output))
            return rows[-1] if rows else {}
        def settled(test=lambda row:True):
            return wait_for(process,lambda:(row if row and row['phase']==0 and
                row['dirty']==0 and test(row) else None) if (row:=latest()) else None,
                'viewer state')
        def key(code): command('hatari-event keypress '+hex(code))
        def shot(name):
            for suffix in ('.png','.bin'): (directory/(name+suffix)).unlink(missing_ok=True)
            command('hatari-debug screenshot '+str(directory/(name+'.png')))
            command('hatari-debug savebin '+str(directory/(name+'.bin'))+' "($44e)" #32000')
            wait_for(process,lambda:(directory/(name+'.bin')).exists() and
                (directory/(name+'.bin')).stat().st_size==32000,'framebuffer '+name)
            checkpoints[name]=latest().copy()
            return (directory/(name+'.bin')).read_bytes()
        initial=settled(lambda row:row['loads']==1)
        if initial['lines']!=901 or initial['bytes']!=56746 or initial['first']!=0:
            raise ValueError('Initial document was not indexed completely')
        first=shot('initial')
        command('hatari-option --fast-forward false')
        key(57)
        page=settled(lambda row:row['first']==initial['rows'])
        page_frame=shot('page')
        key(80)
        line=settled(lambda row:row['first']==page['first']+1)
        line_frame=shot('line')
        # Independently compare the old second row with the new first row.
        # Cursor pixels are outside these rows; no font extracted from the app.
        before=text_pixels(page_frame,page['work'],1,page['columns'])
        after=text_pixels(line_frame,line['work'],0,line['columns'])
        if not any(after) or before!=after:
            raise ValueError('One-line scrolling did not shift the visible text correctly')
        if text_pixels(first,initial['work'],0,initial['columns'])==after:
            raise ValueError('Page and line input changed the model without changing text pixels')
        # Exercise the real MagiC file selector with physical keyboard events.
        key(24)
        wait_for(process,lambda:'selector result=-1' in reports(output),'selector entry')
        command('hatari-option --fast-forward true')
        def selector_visible():
            frame=shot('selector')
            ink=sum((frame[y*80+x//8]>>(7-x%8))&1
                for y in range(24,32) for x in range(160,460))
            return ink<300
        wait_for(process,selector_visible,'the native selector dialog')
        command('hatari-option --fast-forward false')
        key(97)  # MagiC's standard Undo/Cancel dialog shortcut.
        wait_for(process,lambda:'selector result=1 button=0' in reports(output),
            'selector cancellation')
        unchanged=settled()
        if unchanged['loads']!=1 or unchanged['first']!=line['first']:
            raise ValueError('Selector cancellation replaced the current document')
        shot('cancel')
        def choose(filename,slow=False):
            previous=reports(output).count('selector result=-1')
            key(24)
            wait_for(process,lambda:reports(output).count('selector result=-1')>previous,
                'selector entry')
            command('hatari-option --fast-forward true')
            wait_for(process,selector_visible,'the native selector dialog')
            key(1)  # Escape clears the GEM filename edit field; Undo cancels.
            codes={'s':31,'m':50,'a':30,'l':38,'t':20,'x':45,'.':52,
                'i':23,'n':49,'g':34,'b':48,'o':24,'r':19,'y':21}
            for character in filename.lower():
                key(codes[character]);time.sleep(.03)
            if slow: command('hatari-option --fast-forward false')
            key(28)
        choose('SMALL.TXT')
        small=settled(lambda row:row['loads']==2)
        if small['lines']!=2 or small['bytes']!=44:
            raise ValueError('Native selector Open did not load the second document')
        shot('second-document')
        choose('MISSING.TXT')
        missing=settled(lambda row:row['status'].startswith('Cannot load:'))
        if missing['loads']!=2 or missing['lines']!=2 or missing['bytes']!=44:
            raise ValueError('Failed Open replaced the retained document')
        shot('missing-file')
        choose('BIG.TXT')
        large=settled(lambda row:row['status']=='File exceeds 64 KiB')
        if large['loads']!=2 or large['bytes']!=44:
            raise ValueError('Oversize replacement destroyed the old document')
        shot('size-limit')
        choose('STORY.TXT',slow=True)
        wait_for(process,lambda:latest()['phase']==3 and latest()['read']>0,
            'replacement disk read')
        key(1)
        cancelled=settled(lambda row:row['status']=='Load cancelled')
        if cancelled['loads']!=2 or cancelled['lines']!=2 or cancelled['bytes']!=44:
            raise ValueError('Read cancellation destroyed the old document')
        shot('read-cancel')
        command('hatari-option --fast-forward false')
        counter_path=output/'drive-c/COUNT2.LOG'
        wait_for(process,lambda:counter_path.exists() and
            len(counter_path.read_text().splitlines())>=8,'inactive Counter progress')
        complete=counter_path.read_text()
        counter=parse_counter(complete[:complete.rfind('\n')+1],2)
        if counter[-1]['top']==counter[-1]['window']:
            raise ValueError('Counter was not inactive beside the viewer')
        last=shot('coexistence')
        changes=sum(a!=b for a,b in zip(digit_pixels(first,counter[-1]['work']),
            digit_pixels(last,counter[-1]['work'])))
        if not changes: raise ValueError('Background Counter pixels did not change')
        key(16)
        wait_for(process,lambda:'exit=0 ' in reports(output),'normal viewer exit')
        wait_for(process,lambda:'resources allocations=0 files=0 locks=0 window=-1 vdi=0 menu=0'
            ' update=0' in reports(output),'viewer resource cleanup')
        wait_for(process,lambda:len(counter_path.read_text().splitlines())>len(counter)+1,
            'Counter progress after viewer exit')
        shot('closed')
        for name in ('TEXT.LOG','LAUNCH.LOG','COUNT2.LOG'):
            (directory/name).write_bytes((output/'drive-c'/name).read_bytes())
        launch=(directory/'LAUNCH.LOG').read_text()
        identities=re.search(r'counter=(\d+) text=(\d+)',launch)
        if not launch.startswith('magic=1 ') or not identities:
            raise ValueError('The demonstration did not boot MagiC')
        counter_id,text_id=map(int,identities.groups())
        if counter_id<=0 or text_id<=0 or counter_id==text_id or \
                counter_id!=counter[-1]['app'] or text_id!=initial['id'] or \
                counter[-1]['window']==initial['window']:
            raise ValueError('Viewer and Counter do not have independent identities')
        command('hatari-debug quit')
        process.wait(timeout=10)
    result=dict(status='pass',tier='development',qualification=False,
        checkpoints=checkpoints,counter_count=counter[-1]['count'],
        counter_digit_pixels_changed=changes,
        read_chunks=[row['read'] for row in states((directory/'TEXT.LOG').read_text()) if row['read']],
        artifacts={str(p.relative_to(output)):sha256(p) for p in
            [*(directory/(name+suffix) for name in checkpoints for suffix in ('.png','.bin')),
             *(directory/name for name in ('TEXT.LOG','LAUNCH.LOG','COUNT2.LOG'))]})
    (output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('MagiC viewer: load, page/line pixels, native Open/Cancel, errors, '
        'read cancellation, inactive Counter and cleanup passed')
    return result
