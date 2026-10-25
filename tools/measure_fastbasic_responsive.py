#!/usr/bin/env python3
"""Physical editor input, full client pixels and readiness on frozen packages."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import zipfile
from unittest.mock import patch

from desktop_menu_check import Menus
from desktop_mouse import schedule
from file_selector_model import FIELDS as SELECTOR, FORM_SELECTOR
from filesystem_audit import Audit
from gem_applications import instances
from gem_render_oracle import Raster, font_bytes, DESKTOP_PALETTE, PENS
from generate_aes_server import expected_layout, layout
from make_data_disk import make
from measure_fastbasic_editor import distribution
from native_program import ROOT, require, sha256
from sio_transaction_trace import BASE_HZ,read_events
from test_bootable_atr import DiskBoot
from test_demo import run
from test_shell_core import KEYS
from workbench_interaction import FIELDS


def fixture_source():
    lines=[b'alphaq']
    for row in range(128):
        pattern=(chr(97+row%26)+'bcdefghijklmnopqrstuvwxyz').encode()
        lines.append(b"'"+(pattern*10)[:254])
    return b'\n'.join(lines)[:32767]


KEYWORDS=set(b'AND BYTE DATA DIM DO ELSE ELSEIF END ENDIF ENDPROC EXEC EXIT FOR IF INPUT INT NEXT NOT OR PAUSE PEEK POKE PRINT PROC PUT RAND REPEAT RETURN STEP THEN TIME TO UNTIL VAL WEND WHILE XOR'.split())


def lexical(line):
    """Independent source-byte colours; no target colour/cache readback."""
    result=[1]*len(line);i=0
    while i<len(line):
        if line[i]==39:
            result[i:]=[3]*(len(line)-i);break
        if line[i]==34:
            end=line.find(b'"',i+1);end=len(line) if end<0 else end+1
            result[i:end]=[2]*(end-i);i=end;continue
        if chr(line[i]).isalnum() or line[i] in b'_$%':
            end=i+1
            while end<len(line) and (chr(line[end]).isalnum() or line[end] in b'_$%'):end+=1
            word=line[i:end].upper()
            if word==b'REM':result[i:]=[3]*(len(line)-i);break
            result[i:end]=[4 if word in KEYWORDS else 1]*(end-i);i=end
        else:i+=1
    return result


class ResponsiveMeasurement:
    interrupt_marker='native_nmi'

    def __init__(self,bundle,output,count):
        self.bundle,self.output,self.count=bundle,output,count
        self.record=dict(samples=[],key_hold_frames=3,
            scope='Physical input to independently matching complete client pixels; frame observations are upper bounds')

    def exercise(self,s):
        b,n,frames,reach=s.b,s.number,s.frames,s.rendezvous
        clock=lambda:b.eval_expr('@clk')&0xffffffff
        def address(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[n(address(k),2) for k in ('cursorX','cursorY')]
            x,y=schedule(b,s.p,current,(x,y));s.saved['pointer']=(x,y)
            reach('(dw($%x)=%d)&(dw($%x)=%d)'%(address('cursorX'),x,address('cursorY'),y));frames(3)
        def edge(value):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(value))
            reach('dw($%x)=%d'%(address('buttons'),value));frames(5)
        def click(x,y):move(x,y);edge(1);edge(0)
        def physical(name,ctrl=False,shift=False):
            if ctrl:b._cmd_ok('KEY CTRL down')
            if shift:b._cmd_ok('KEY SHIFT down')
            b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
            if shift:b._cmd_ok('KEY SHIFT up')
            if ctrl:b._cmd_ok('KEY CTRL up')
            frames(3)
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        print('Responsive observer: launching BASIC',flush=True)
        menus.select('Shell');owners=s.ledger();live=n(s.p['build']['task_storage']['LIVE'],1)
        old=s.begin('RUN C:BASIC.APP');s.ready(old);s.result()
        app=next(i for i in instances(b,s.p,self.bundle/'bitmap-console') if i['name']=='basic')
        base,task=app['symbols']['Basic'],app['task']
        foreign=json.loads((self.bundle/'bitmap-console/c-image.json').read_text())['symbols']
        rf=layout()['Request']['fields']
        context=next(c for c in (n(foreign['contexts']+4*i,4) for i in range(4)) if c and n(c+rf['owner'],3)==task)
        inbox=n(context+rf['receiving'],3);mask=1<<n(inbox+12,1)
        self.record['task_dp']=n(n(task+58,3)+16,2)
        form=context+dict(expected_layout())['C context form']
        def ready():return n(task+12,1)==4 and bool(n(task+20,4)&mask)
        def settled():
            reach('(dw($%x)=1)&(dw($%x)=0)&(db($%x)=4)&(((dw($%x)&%d)!=0)|((dw($%x)&%d)!=0))'%
                  (base+FIELDS['ready'],base+FIELDS['dirty'],task+12,task+20,mask&65535,task+22,mask>>16))
        settled();menus.select('FastBasic')
        self.record.update(application=app,app_sha256=sha256(self.bundle/'bitmap-console/apps/basic/program.app'),
                           native_sha256=sha256(self.bundle/'program.xex'))
        source=b'';caret=0
        font=font_bytes(self.bundle/'bitmap-console/selected/src/vdi/font8x8.c')
        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
        colors={hw:rgb[i*3:i*3+3][::-1] for i,hw in enumerate(PENS)}
        def xy(tree,index):
            obj=tree+index*24
            return (n(tree+16,2)+n(obj+16,2)+n(obj+20,2)//2,
                    n(tree+18,2)+n(obj+18,2)+n(obj+22,2)//2)
        def active_form():
            reach('(dw($%x)|dw($%x))!=0'%(form,form+2));frames(12)
            return n(form,4)
        def load():
            nonlocal source,caret
            print('Responsive observer: opening benchmark source',flush=True)
            physical('O',ctrl=True)
            f=active_form();selector=n(f+FORM_SELECTOR,4)
            if not selector:
                click(*xy(n(f,4),8));f=active_form();selector=n(f+FORM_SELECTOR,4)
            require(selector!=0,'Open did not enter the selector')
            reach('dw($%x)=1'%(selector+SELECTOR['valid']));frames(10)
            tree=selector
            click(*xy(tree,5))
            current=b.memdump(selector+SELECTOR['file'],13).split(b'\0')[0]
            for _ in current:physical('BACKSPACE')
            for char in 'AAA.BAS':
                name,shift=KEYS[char];physical(name,shift=shift)
            physical('RETURN')
            reach('(dw($%x)=32767)&(dw($%x)=0)'%(base+FIELDS['document']+20,base+FIELDS['caret']))
            source=fixture_source();caret=0;settled();move(630,230);frames(4)
        def geometry():
            return [n(base+FIELDS['work']+2*i,2) for i in range(4)]
        def position(row,column):
            nonlocal caret
            x,y,w,h=geometry();first=n(base+FIELDS['first'],2);left=n(base+FIELDS['left'],2)
            lines=source.split(b'\n');line=first+row
            caret=sum(len(q)+1 for q in lines[:line])+min(len(lines[line]),left+column)
            click(x+4+column*8+3,y+row*8+3)
            reach('dw($%x)=%d'%(base+FIELDS['caret'],caret));settled();move(630,230)
        def expected():
            x,y,w,h=geometry();rows=n(base+FIELDS['rows'],2);columns=n(base+FIELDS['columns'],2)
            first=n(base+FIELDS['first'],2);left=n(base+FIELDS['left'],2)
            raster=Raster(font);raster.clip=(x,y,x+w-1,y+h-1)
            raster.fill=0;raster.apply(11,(x,y,x+w-1,y+h-1))
            lines=source.split(b'\n');line_no=source[:caret].count(b'\n')
            caret_column=caret-(source.rfind(b'\n',0,caret)+1)
            for row in range(rows):
                line=first+row;raw=lines[line] if line<len(lines) else b''
                pens=lexical(raw)
                for column in range(columns):
                    at=left+column;char=raw[at] if at<len(raw) else 32
                    raster.text=pens[at] if at<len(pens) else 1
                    raster.apply(8,(x+4+column*8,y+row*8+6),bytes([char]))
                if line==line_no and left<=caret_column<left+columns:
                    raster.fill=1;raster.apply(11,(x+4+(caret_column-left)*8,y+row*8,
                                                   x+4+(caret_column-left)*8,y+row*8+7))
            status=b.memdump(base+1495,81).split(b'\0')[0]
            dirty=n(base+FIELDS['document']+32,4)!=n(base+FIELDS['document']+36,4)
            text=((b'*' if dirty else b' ')+b' '+status).ljust(columns)[:columns]
            raster.text=1;raster.apply(8,(x+4,y+rows*8+10),text)
            return b''.join(colors[raster.pixels[yy*640+xx]] for yy in range(y,y+h) for xx in range(x,x+w))
        def capture():
            x,y,w,h=geometry();path=self.output/'scanout.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            region=b''.join(raw[yy*frame.stride+64+x*4:yy*frame.stride+64+(x+w)*4] for yy in range(y,y+h))
            return b''.join(region[i:i+3] for i in range(0,len(region),4))
        def key(operation,index,name,ctrl=False,shift=False,edit=None,movement=None,measure=True):
            nonlocal source,caret
            settled();frames(1+index%3)
            previous_caret=caret;old_first=n(base+FIELDS['first'],2);old_left=n(base+FIELDS['left'],2)
            if edit=='insert':source=source[:caret]+b'q'+source[caret:];caret+=1
            elif edit=='return':source=source[:caret]+b'\n'+source[caret:];caret+=1
            elif edit=='backspace':source=source[:caret-1]+source[caret:];caret-=1
            elif movement in ('left','right'):caret+=-1 if movement=='left' else 1
            elif movement in ('up','down'):
                lines=source.split(b'\n');line=source[:caret].count(b'\n');col=caret-(source.rfind(b'\n',0,caret)+1)
                line+=-1 if movement=='up' else 1
                caret=sum(len(q)+1 for q in lines[:line])+min(col,len(lines[line]))
            wanted=None;model=readiness=visible=None;before=n(base+FIELDS['paintTurns'],4)
            if ctrl:b._cmd_ok('KEY CTRL down')
            if shift:b._cmd_ok('KEY SHIFT down')
            started=clock();b._cmd_ok('KEY '+name+' down')
            for poll in range(240):
                frames(1);now=clock()
                if poll==2:
                    b._cmd_ok('KEY '+name+' up')
                    if shift:b._cmd_ok('KEY SHIFT up')
                    if ctrl:b._cmd_ok('KEY CTRL up')
                target_first=old_first+(1 if operation=='scroll_up' else -1 if operation=='scroll_down' else 0)
                target_left=old_left+(1 if operation=='scroll_left' else -1 if operation=='scroll_right' else 0)
                if model is None and n(base+FIELDS['caret'],4)==caret and n(base+FIELDS['first'],2)==target_first and n(base+FIELDS['left'],2)==target_left:
                    model=now;wanted=expected()
                if model is not None:
                    if readiness is None and ready():readiness=now
                    actual=capture()
                    if visible is None and actual==wanted:visible=now
                if poll>=2 and visible is not None:break
            else:
                (self.output/'expected.bgr').write_bytes(wanted or b'')
                (self.output/'actual.bgr').write_bytes(capture())
                raise RuntimeError('Editor did not settle: '+operation+' '+str(index))
            sample=dict(operation=operation,index=index,model_ms=((model-started)&0xffffffff)*1000/BASE_HZ,
                input_ready_ms=((readiness-started)&0xffffffff)*1000/BASE_HZ if readiness is not None else None,
                scanout_ms=((visible-started)&0xffffffff)*1000/BASE_HZ,
                scanout_sha256=hashlib.sha256(wanted).hexdigest(),
                paint_turns=n(base+FIELDS['paintTurns'],4)-before,
                caret_before=previous_caret,caret_after=caret,
                first_before=old_first,first_after=n(base+FIELDS['first'],2),
                left_before=old_left,left_after=n(base+FIELDS['left'],2),
                started_clock=started,model_clock=model,observation_end_clock=clock())
            if operation.startswith('scroll_'):
                field='first' if operation in ('scroll_up','scroll_down') else 'left'
                sign=1 if operation in ('scroll_up','scroll_left') else -1
                require(sample[field+'_after']-sample[field+'_before']==sign,'Scroll did not move one cell: '+str(sample))
            if measure:
                self.record['samples'].append(sample)
                (self.output/'samples.json').write_text(json.dumps(self.record,indent=2)+'\n')
                print(operation,index,round(sample['scanout_ms'],2),'ms scanout',flush=True)
            settled()
        load()
        key('far_gap',0,'Q',edit='insert')
        key('warm',0,'BACKSPACE',edit='backspace',measure=False)
        for index in range(self.count):
            key('top_newline',index,'RETURN',edit='return')
            key('top_join',index,'BACKSPACE',edit='backspace')
        rows=n(base+FIELDS['rows'],2);columns=n(base+FIELDS['columns'],2)
        position(rows//2,0)
        key('warm',0,'RETURN',edit='return',measure=False);key('warm',0,'BACKSPACE',edit='backspace',measure=False)
        for index in range(self.count):
            key('middle_newline',index,'RETURN',edit='return')
            key('middle_join',index,'BACKSPACE',edit='backspace')
        position(rows-1,3)
        for index in range(self.count):key('scroll_up',index,'EQUALS',ctrl=True,movement='down')
        position(0,3)
        for index in range(self.count):key('scroll_down',index,'MINUS',ctrl=True,movement='up')
        position(1,columns-1)
        for index in range(self.count):key('scroll_left',index,'ASTERISK',ctrl=True,movement='right')
        position(1,0)
        for index in range(self.count):key('scroll_right',index,'PLUS',ctrl=True,movement='left')
        position(0,6)
        for index in range(self.count):
            key('append',index,'Q',edit='insert');key('backspace',index,'BACKSPACE',edit='backspace')
        position(0,3)
        for index in range(self.count):
            key('insert',index,'Q',edit='insert');key('delete',index,'BACKSPACE',edit='backspace')
            key('caret_left',index,'PLUS',ctrl=True,movement='left')
            key('caret_right',index,'ASTERISK',ctrl=True,movement='right')
        before=n(base+FIELDS['paintTurns'],4);frames(20)
        require(n(base+FIELDS['paintTurns'],4)==before,'Idle editor repainted')
        physical('Q',ctrl=True);f=active_form();click(*xy(n(f,4),8))
        reach('db($%x)=%d'%(s.p['build']['task_storage']['LIVE'],live))
        menus.select('Shell');s.command('MEM');frames(20);require(s.ledger()==owners,'Editor leaked resources')
        s.saved['integration']=self.record
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def measure(bundle,output,count=20,snapshot=None,observer_pin=None):
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    original=Audit((output/'extracted/exec816-demo'/manifest['media']).read_bytes());original.sdfs()
    source=output/'media';source.mkdir(exist_ok=True)
    for name,data in original.files.items():
        path=source/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
    (source/'WORK/AAA.BAS').write_bytes(fixture_source())
    media=output/'measurement.atr'
    make(media,source,binary_names={p.relative_to(source).as_posix() for p in source.rglob('*') if p.is_file()},
         filesystem='sdfs',sector_bytes=256,sectors=manifest['mounts'][0]['sectors'])
    observer=ResponsiveMeasurement(bundle,output,count)
    bootstrap=DiskBoot(bundle,native_snapshot=snapshot) if snapshot else None
    wait=json.loads((bundle/'bitmap-console/c-image.json').read_text())['symbols']['ExecAESWait']
    with patch.dict(os.environ,EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=f'{wait:x}',EXEC816_EDITOR_HISTORY='1'):
        result=run(bundle,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
            integration=observer,profile_commands=False,bootstrap=bootstrap,media_path=media,
            diagnostic_media_sha256=sha256(media),emulator_output=output,emulator_override=observer_pin)
    waits=[t for t,e in read_events(output/'emulator.log',kinds={'cpu'})
           if int(e[4],16)==wait and int(e[9],16)==observer.record['task_dp']]
    for sample in observer.record['samples']:
        start=sample['started_clock'];model=(sample['model_clock']-start)&0xffffffff
        end=(sample['observation_end_clock']-start)&0xffffffff
        entries=[(t-start)%(1<<32) for t in waits if model<=(t-start)%(1<<32)<=end]
        candidates=[min(entries)*1000/BASE_HZ] if entries else []
        if sample['input_ready_ms'] is not None:candidates.append(sample['input_ready_ms'])
        require(candidates,'No event-dispatch readiness evidence: '+str(sample))
        sample['input_ready_ms']=min(candidates)
    observer.record['readiness_observer']='First Task-owned ExecAESWait entry after model observation, or earlier observed waiting state; includes frame-observation upper bounds'
    observer.record['summaries']={op:{key:distribution([v[key] for v in observer.record['samples'] if v['operation']==op])
        for key in ('input_ready_ms','scanout_ms')} for op in sorted({v['operation'] for v in observer.record['samples']})}
    record=dict(status='pass',tier='development',qualification=False,measurement=observer.record,
        machine=result['machine'],runtime=result['runtime'],zip_sha256=sha256(bundle/'exec816-demo.zip'),
        observer_sha256=sha256(Path(__file__)),media_sha256=sha256(media),
        fixture_source_sha256=hashlib.sha256(fixture_source()).hexdigest(),
        replay_snapshot_sha256=sha256(snapshot) if snapshot else None)
    record['emulator_override']=observer_pin
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n');return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--samples',type=int,default=20);parser.add_argument('--native-snapshot',type=Path)
    parser.add_argument('--observer-pin',type=Path)
    args=parser.parse_args()
    observer=json.loads(args.observer_pin.read_text()) if args.observer_pin else None
    require(observer is not None,'Four-direction physical input requires the separately recorded PLUS observer')
    measure(args.bundle.resolve(),args.output.resolve(),args.samples,args.native_snapshot,observer)
