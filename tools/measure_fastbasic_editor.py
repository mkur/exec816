#!/usr/bin/env python3
"""Matched physical-key to completed-scanout measurements for BASIC.APP."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances
from gem_render_oracle import Raster, font_bytes, DESKTOP_PALETTE, PENS
from generate_aes_server import layout, expected_layout
from native_program import ROOT, require, sha256
from sio_transaction_trace import BASE_HZ
from test_demo import run
from test_shell_core import KEYS
from workbench_interaction import FIELDS


def distribution(values):
    values=sorted(values)
    return dict(count=len(values),median=(values[(len(values)-1)//2]+values[len(values)//2])/2,
                p95=values[math.ceil(len(values)*.95)-1],maximum=values[-1])


class EditorMeasurement:
    interrupt_marker='native_nmi'

    def __init__(self,bundle,output,count,cache=False):
        self.bundle,self.output,self.count=bundle,output,count
        self.cache=cache
        self.record=dict(samples=[],scope='Physical key offer to first matching completed scanout; PAL-frame polling gives upper bounds')

    def exercise(self,s):
        b=s.b;n=s.number;frames=s.frames;reach=s.rendezvous
        clock=lambda:b.eval_expr('@clk')&0xffffffff
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[n(at(k),2) for k in ('cursorX','cursorY')]
            x,y=schedule(b,s.p,current,(x,y));s.saved['pointer']=(x,y)
            reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');frames(8)
            b._cmd_ok('MOUSE AT 2000 0 0 0');frames(20)
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        menus.select('Shell');owners=s.ledger();live=n(s.p['build']['task_storage']['LIVE'],1)
        old=s.begin('RUN C:BASIC.APP');s.ready(old);s.result()
        app=next(i for i in instances(b,s.p,self.bundle/'bitmap-console') if i['name']=='basic')
        base=app['symbols']['Basic'];task=app['task']
        foreign=json.loads((self.bundle/'bitmap-console/c-image.json').read_text())['symbols']
        fields=layout()['Request']['fields']
        contexts=[n(foreign['contexts']+4*i,4) for i in range(4)]
        context=next(c for c in contexts if c and n(c+fields['owner'],3)==task)
        inbox=n(context+fields['receiving'],3);mask=1<<n(inbox+12,1)
        def settled():
            reach('(dw($%x)=1)&(dw($%x)=0)&(db($%x)=4)&(dw($%x)=%d)&(dw($%x)=%d)'%
                  (base+FIELDS['ready'],base+FIELDS['dirty'],task+12,task+20,mask&65535,task+22,mask>>16))
        settled();menus.select('FastBasic');move(630,230);frames(3)
        self.record.update(app_sha256=sha256(self.bundle/'bitmap-console/apps/basic/program.app'),
                           kernel_sha256=sha256(self.bundle/'program.xex'),application=app)
        x,y,w,h=[n(base+FIELDS['work']+2*i,2) for i in range(4)]
        columns=n(base+FIELDS['columns'],2)
        font=font_bytes(self.bundle/'bitmap-console/selected/src/vdi/font8x8.c')
        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
        colors={hardware:rgb[pen*3:pen*3+3][::-1] for pen,hardware in enumerate(PENS)}
        source=b'';caret=0;display_rows=1
        def counters():
            if not self.cache:return None
            # Private packed C layout, checked by the emitted painter fixture.
            r=base+1664
            require(n(r+5101,1)==1,'Retained editor cache is not initialized')
            return dict(glyphs=n(r+5065,4),status=n(r+5069,4),publications=n(r+5073,4))
        def wanted():
            model=Raster(font);model.clip=(x,y,x+w-1,y+display_rows*8-1)
            lines=source.split(b'\n');offset=0
            for row,line in enumerate(lines):
                model.apply(8,(x+4,y+row*8+6),line.ljust(columns))
                if offset<=caret<=offset+len(line):
                    col=caret-offset;model.fill=1
                    model.apply(11,(x+4+col*8,y+row*8,x+4+col*8,y+row*8+7))
                offset+=len(line)+1
            return b''.join(colors[model.pixels[row*640+col]] for row in range(y,y+display_rows*8) for col in range(x,x+w))
        def capture():
            path=self.output/'scanout.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            region=b''.join(raw[row*frame.stride+64+x*4:row*frame.stride+64+(x+w)*4] for row in range(y,y+display_rows*8))
            return b''.join(region[i:i+3] for i in range(0,len(region),4))
        for operation in ('append','caret'):
            if operation=='caret':
                for char in '\n'+source.decode():
                    name,shift=KEYS[char]
                    if shift:b._cmd_ok('KEY SHIFT down')
                    b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
                    if shift:b._cmd_ok('KEY SHIFT up')
                    settled();frames(2)
                source+=b'\n'+source;caret=len(source);display_rows=2
            for index in range(self.count):
                settled();frames(1+index%3)
                if operation=='append':
                    char=chr(97+index%26);name,shift=KEYS[char];source+=char.encode();caret+=1
                    ctrl=False
                else:
                    up=index%2==0;caret+=-(self.count+1) if up else self.count+1
                    name='MINUS' if up else 'EQUALS';shift=False;ctrl=True
                expected=wanted();before=n(base+FIELDS['paintTurns'],4);counts=counters();model=None;paint=None
                if ctrl:b._cmd_ok('KEY CTRL down')
                if shift:b._cmd_ok('KEY SHIFT down')
                started=clock();b._cmd_ok('KEY '+name+' down');frames(1)
                b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                if ctrl:b._cmd_ok('KEY CTRL up')
                for polls in range(120):
                    now=clock()
                    if model is None and n(base+FIELDS['caret'],4)==caret:model=now
                    if paint is None and n(base+FIELDS['paintTurns'],4)!=before:paint=now
                    actual=capture()
                    if actual==expected:break
                    frames(1)
                else:
                    (self.output/'expected.bgr').write_bytes(expected);(self.output/'actual.bgr').write_bytes(actual)
                    raise RuntimeError('Editor scanout did not match '+operation)
                visible=clock();settled()
                sample=dict(operation=operation,index=index,ms=((visible-started)&0xffffffff)*1000/BASE_HZ,
                            model_ms=((model-started)&0xffffffff)*1000/BASE_HZ if model is not None else None,
                            paint_ms=((paint-started)&0xffffffff)*1000/BASE_HZ if paint is not None else None,
                            polls=polls+1,paints=n(base+FIELDS['paintTurns'],4)-before,
                            scanout_sha256=hashlib.sha256(actual).hexdigest())
                if counts:sample['cache']={k:v-counts[k] for k,v in counters().items()}
                self.record['samples'].append(sample)
                (self.output/'samples.json').write_text(json.dumps(self.record,indent=2)+'\n')
                print(operation,index,round(sample['ms'],3),'ms',flush=True)
        # Pointer delivery remains active beside the editor.
        start=clock();move(620,220);self.record['pointer_delivery_ms']=((clock()-start)&0xffffffff)*1000/BASE_HZ
        before=n(base+FIELDS['paintTurns'],4);frames(20)
        require(n(base+FIELDS['paintTurns'],4)==before,'Idle editor repainted')
        self.record['idle_draws']=0
        menus.key('Q',ctrl=True)
        form=context+dict(expected_layout())['C context form']
        reach('(dw($%x)|dw($%x))!=0'%(form,form+2));frames(12)
        tree=n(n(form,4),4);obj=tree+8*24
        click(n(tree+16,2)+n(obj+16,2)+n(obj+20,2)//2,n(tree+18,2)+n(obj+18,2)+8)
        reach('db($%x)=%d'%(s.p['build']['task_storage']['LIVE'],live))
        menus.select('Shell');s.command('MEM');frames(20)
        require(s.ledger()==owners,'Editor measurement retained resources')
        for operation in ('append','caret'):
            self.record[operation]=distribution([i['ms'] for i in self.record['samples'] if i['operation']==operation])
        s.saved['integration']=self.record;s.save_screen(self.bundle/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def measure(bundle,output,count=12,snapshot=None,cache=False):
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    observer=EditorMeasurement(bundle,output,count,cache)
    bootstrap=None
    if snapshot:
        from test_bootable_atr import DiskBoot
        bootstrap=DiskBoot(bundle,native_snapshot=snapshot)
    result=run(bundle,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
               integration=observer,profile_commands=False,bootstrap=bootstrap)
    record=dict(status='pass',tier='development',qualification=False,measurement=observer.record,
                machine=result['machine'],runtime=result['runtime'],gem_stacks=result.get('gem_stacks'),
                zip_sha256=sha256(bundle/'exec816-demo.zip'),observer_sha256=sha256(Path(__file__)),
                replay_snapshot_sha256=sha256(snapshot) if snapshot else None)
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True);p.add_argument('--samples',type=int,default=12)
    p.add_argument('--native-snapshot',type=Path)
    p.add_argument('--cache',action='store_true')
    a=p.parse_args();measure(a.bundle.resolve(),a.output.resolve(),a.samples,a.native_snapshot,a.cache)
