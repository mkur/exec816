#!/usr/bin/env python3
"""Physical EDX keys through input readiness and independent ATASCII scanout."""
import argparse
import hashlib
import json
import math
from pathlib import Path
import zipfile

from bitmap_console_performance import native_markers
from console_model import read_cells
from desktop_menu_check import Menus
from desktop_mouse import schedule
from generate_console import constants
from generate_desktop import layout as desktop_layout, ABI as DESKTOP
from generate_layers import layout as layers_layout, ABI as LAYERS
from gem_render_oracle import DESKTOP_PALETTE
from native_program import read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run
from measure_spartados_listing import spans


def distribution(values):
    values=sorted(values)
    return dict(count=len(values),median=(values[(len(values)-1)//2]+values[len(values)//2])/2,
                p95=values[math.ceil(len(values)*.95)-1],maximum=values[-1])


class Measurement:
    interrupt_marker='native_nmi'

    def __init__(self, output, count, trace=False, early_scanout=False):
        self.output,self.count,self.trace=output,count,trace
        self.early_scanout=early_scanout
        self.samples=[]

    def exercise(self,s):
        b=s.b
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[s.number(at(name),2) for name in ('cursorX','cursorY')]
            x,y=schedule(b,s.p,current,(x,y));s.saved['pointer']=(x,y)
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(8)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(20)
        s.saved['desktop_menu']={};Menus(s,click,move).select('Shell')
        move(639,239)
        owners=s.ledger();top=s.saved['top'];layout=constants()
        ready=top+layout['INSTANCE_READREADY'];dirty=top+layout['INSTANCE_DIRTYROWS']
        caps=top+layout['INSTANCE_CAPS']
        def clock():return b.eval_expr('@clk')&0xffffffff
        def input_ready():
            return s.number(ready,1)==2 and s.number(caps,1)&224==224
        # Derive the visible client rectangle from retained window/layer geometry.
        # Expected pixels use the ROM font and logical cells, never target VRAM.
        service_address=next(d['address'] for d in s.p['image']['data'] if '_DESKSTATE_SERVICE_' in d['name'])
        service=s.number(service_address,3);dl=desktop_layout();ll=layers_layout()
        sf=dl['Service']['fields'];wf=dl['Window']['fields'];lf=ll['Scene']['fields']
        window=next(service+sf['windows']+i*dl['Window']['size'] for i in range(DESKTOP['constants']['WINDOWS'])
                    if s.number(service+sf['windows']+i*dl['Window']['size']+wf['kind'],1)==1)
        layer=s.number(window+wf['layer'],4);scene=service+sf['scene']
        item=next(scene+lf['items']+i*ll['Layer']['size'] for i in range(LAYERS['constants']['MAX_LAYERS'])
                  if s.number(scene+lf['items']+i*ll['Layer']['size'],4)==layer)
        bounds=[int.from_bytes(s.far(item+4+i,2),'little',signed=True) for i in (0,2,4,6)]
        left=(bounds[0]+8)//8*8;upper=(bounds[1]+DESKTOP['constants']['FRAME_SHELL_TOP'])//8*8
        width=s.number(top+layout['INSTANCE_WIDTH'],2);height=s.number(top+layout['INSTANCE_HEIGHT'],2)
        require((width,height)==(64,20),'Measure the pinned 64x20 desktop')
        font=b.memdump(0xe000,1024)
        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
        colors=[rgb[i*3:i*3+3][::-1] for i in (0,1)]
        def expected(cells):
            result=bytearray()
            for row in range(height):
                for y in range(8):
                    for ch in cells[row*width:(row+1)*width]:
                        glyph=ch&127
                        glyph=glyph+64 if glyph<32 else glyph-32 if glyph<96 else glyph
                        bits=font[glyph*8+y]^(255 if ch&128 else 0)
                        for x in range(8):result+=colors[bool(bits&(128>>x))]
            return bytes(result)
        def capture():
            path=self.output/'scanout.bgra';frame=b.rawscreen(str(path));raw=path.read_bytes()
            crop=b''.join(raw[y*frame.stride+64+left*4:y*frame.stride+64+(left+width*8)*4]
                          for y in range(upper,upper+height*8))
            return b''.join(crop[i:i+3] for i in range(0,len(crop),4))
        old=s.begin('EDX EDIT.TXT')
        # The shell's former input request can remain ready during command startup.
        for _ in range(900):
            if input_ready():break
            s.frames(1)
        else:raise RuntimeError('EDX raw input did not become ready')
        s.frames(3)
        require(b'HELLO' in bytes(v&127 for v in read_cells(s.far,top)),'Missing EDX fixture')

        def key(operation,index,name,ctrl=False):
            previous=read_cells(s.far,top)
            observations=[]
            first_change=None
            def observe_early():
                nonlocal first_change
                tick=clock()
                if first_change is None and read_cells(s.far,top)!=previous:
                    first_change=tick
                observations.append((tick,capture()))
            if ctrl:b._cmd_ok('KEY CTRL down')
            started=clock();require(b._cmd_ok('KEY '+name+' down')['raw_scan'],'Physical matrix key required')
            if self.early_scanout:
                for _ in range(3):
                    s.frames(1);observe_early()
            else:
                s.frames(3)
            b._cmd_ok('KEY '+name+' up')
            if ctrl:b._cmd_ok('KEY CTRL up')
            completed=None;want=None;cells=None
            for polls in range(120):
                now=clock();current=read_cells(s.far,top)
                if self.early_scanout:
                    observe_early()
                if completed is None and current!=previous and input_ready() and s.number(dirty,1)==0:
                    completed=now;cells=current;want=expected(cells)
                if completed is not None:
                    actual=observations[-1][1] if self.early_scanout else capture()
                    if actual==want:break
                s.frames(1)
            else:
                if want is not None:
                    (self.output/'expected.bgr').write_bytes(want)
                    (self.output/'actual.bgr').write_bytes(actual)
                raise RuntimeError('EDX input/scanout timeout: '+operation)
            ended=clock()
            row=dict(operation=operation,index=index,key=name,control=ctrl,start=started,end=ended,
                     input_ready_ms=((completed-started)&0xffffffff)*1000/BASE_HZ,
                     scanout_ms=((ended-started)&0xffffffff)*1000/BASE_HZ,
                     polls=polls+1,changed_cells=sum(a!=c for a,c in zip(previous,cells)),
                     scanout_sha256=hashlib.sha256(actual).hexdigest())
            if self.early_scanout:
                first_visible=next(tick for tick,pixels in observations if pixels==want)
                row.update(first_model_change_ms=((first_change-started)&0xffffffff)*1000/BASE_HZ,
                           target_scanout_ms=((first_visible-started)&0xffffffff)*1000/BASE_HZ,
                           scanout_observations=[dict(ms=((tick-started)&0xffffffff)*1000/BASE_HZ,
                                                     sha256=hashlib.sha256(pixels).hexdigest())
                                                 for tick,pixels in observations])
            self.samples.append(row)
            (self.output/'samples.json').write_text(json.dumps(self.samples,indent=2)+'\n')
            print(operation,index,round(row['input_ready_ms'],3),round(row['scanout_ms'],3),'ms',flush=True)
        if self.trace:b.profile_start()
        key('setup',0,'Z',True)
        for i in range(self.count):key('insert',i,chr(65+i%26))
        # Home/End use supported physical matrix names in the frozen observer.
        for i in range(self.count):key('horizontal',i,'A' if i%2==0 else 'Z',True)
        for i in range(self.count):key('vertical',i,'EQUALS' if i%2==0 else 'MINUS',True)
        if self.trace:b.profile_stop()
        unchanged=read_cells(s.far,top);s.frames(20)
        require(read_cells(s.far,top)==unchanged and s.number(dirty,1)==0,'Idle EDX changed screen')
        b._cmd_ok('KEY BREAK down');s.frames(3);b._cmd_ok('KEY BREAK up');s.ready(old)
        result=tuple(int.from_bytes(s.far(s.saved['shell']+at,4),'little',signed=True) for at in (32,36))
        require(result==(20,304),'EDX cancellation did not preserve result')
        s.frames(20);require(s.ledger()==owners,'EDX retained resources')
        s.saved['integration']=dict(samples=self.samples,cancelled=True,ownership_restored=True)
        s.save_screen(Path(s.p['output'])/'boot-smoke.png')
        for ch in 'EXIT':s.press(ch)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def measure(bundle,output,count,snapshot=None,trace=False,early_scanout=False):
    output.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:archive.extractall(output/'extracted')
    program=read_build(bundle)
    markers=native_markers(program,[('SDXSCREEN_CALL','screen_call'),('SDXSCREEN_CELL','cell'),
                          ('SDXSCREEN_FLUSH','flush'),('SDXSERVICE_DISPATCH','dispatch'),
                          ('SDXSTATE_GUARDS','guards'),('DOSCALLS_CONSOLEIO','console_io'),
                          ('DOSRAW_PREPARE','request_prepare'),('DOSRAW_COMPLETE','request_complete'),
                          ('DOSCANCEL_TRANSFER','transfer'),
                          ('CONSOLEDRIVER_BEGINIO','publish'),
                          ('CONSOLEDRIVER_CLAIMWRITE','claim_write'),
                          ('CONSOLEDRIVER_SPANSWRITE','spans_write'),
                          ('CONSOLEDRIVER_FINISHREAD','finish_read'),
                          ('CONSOLEDRIVER_READQUANTUM','read_quantum'),
                          ('CONSOLEDRIVER_COMPLETE','reply'),
                          ('CONSOLEDRIVER_POSITIONEDWRITE','positioned_write'),
                          ('CONSOLEDRIVER_FINISHWRITE','finish_write'),
                          ('CONSOLECORE_WRITEAT','model_write'),
                          ('CONSOLEDISPLAY_PRESENT','present')])
    markers['guest_and_bridge']=dict(entry=program['labels']['sdx_probe_run'],
                                    returns=[program['labels']['sdx_probe_service_return']])
    # Assembly observation points are entry counts. D changes during the leaf,
    # so a native-routine D-keyed interval would invent an unmatched lifetime.
    for label, name in [('sdx_probe_cell_get', 'cell_get'),
                        ('sdx_probe_cell_put', 'cell_put'),
                        ('sdx_probe_cell_committed', 'cell_committed'),
                        ('sdx_probe_detach', 'detach'),
                        ('sdx_probe_guest_restore', 'guest_restore')]:
        if label in program['labels']:
            markers[name] = dict(entry=program['labels'][label], returns=[])
    import os
    pcs={pc for m in markers.values() for pc in [m['entry'],*m['returns']]}
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in sorted(pcs))
    observer=Measurement(output,count,trace,early_scanout);bootstrap=None
    # Capture only after the unchanged OF816 checker accepts its handoff.
    # Other GUI tests independently verify every native byte before replay.
    import test_of816
    checked=test_of816.check_loading_complete
    def checkpoint(bridge,boot,native,settings):
        checked(bridge,boot,native,settings)
        bridge.state_save(str(output/'native-checkpoint.altstate2'))
    if snapshot is None:test_of816.check_loading_complete=checkpoint
    if snapshot:
        from test_bootable_atr import DiskBoot
        bootstrap=DiskBoot(bundle,native_snapshot=snapshot)
    result=run(bundle,boot_smoke=True,distribution_root=output/'extracted/exec816-demo',
               integration=observer,profile_commands=False,bootstrap=bootstrap,boot_route='xex',emulator_output=output)
    events=read_events(output/'emulator.log');measured=spans(events,markers)
    for sample in observer.samples:
        low=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        high=low+((sample['end']-sample['start'])&0xffffffff)
        sample['routines']={name:dict(calls=len(found),elapsed_ms=sum(v['ms'] for v in found))
            for name in markers if (found:=[v for v in measured if v['kind']==name and low<=v['begin']<=v['end']<=high])}
    record=dict(status='pass',tier='development',qualification=False,
                scope='Physical keys; frame-quantized upper bounds to raw-input readiness and independent ATASCII client scanout; three-frame key hold',
                samples=observer.samples,machine=result['machine'],runtime=result['runtime'],
                rom=result['rom'],zip_sha256=sha256(bundle/'exec816-demo.zip'),
                observer_sha256=sha256(Path(__file__)),key_hold_frames=3,
                native_snapshot_sha256=sha256(snapshot) if snapshot else None,
                early_scanout=early_scanout,
                summaries={op:{kind:distribution([s[kind] for s in observer.samples if s['operation']==op])
                           for kind in (('input_ready_ms','scanout_ms','target_scanout_ms','first_model_change_ms')
                                        if early_scanout else ('input_ready_ms','scanout_ms'))}
                           for op in ('insert','horizontal','vertical')})
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--trace',action='store_true',help='Enable passive routine observations through CPU history')
    parser.add_argument('--samples',type=int,default=20)
    parser.add_argument('--early-scanout',action='store_true',
                        help='Also observe every held-key frame and find final target pixels before input readiness')
    parser.add_argument('--native-snapshot',type=Path)
    args=parser.parse_args()
    require(args.samples>=1,'Positive sample count required')
    measure(args.bundle.resolve(),args.output.resolve(),args.samples,args.native_snapshot,args.trace,args.early_scanout)
