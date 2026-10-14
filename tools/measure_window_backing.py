#!/usr/bin/env python3
"""Physical move/close latency in an immutable desktop ZIP, PAL-frame sampled.

Warm exact scanout references before timing. Separate client placement from
old-background repair; observe application repaint counts independently.
No guest code or production state is patched by this diagnostic.
"""
import argparse
import json
import shutil
import struct
import zipfile
from pathlib import Path

from browser_model import FIELDS as B
from colour_desktop_model import FIELDS as D
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances, symbols
from generate_desktop import layout, ABI
from generate_layers import layout as layers_layout, ABI as LAYERS_ABI
from measure_desktop import distribution
from native_program import require, sha256
from sio_transaction_trace import BASE_HZ
from test_demo import run


class Windows:
    def __init__(self, count):
        self.count = count
        self.results = {}

    def exercise(self, s):
        b = s.b
        directory = s.p['output']/'bitmap-console'
        shared = json.loads((directory/'c-image.json').read_text())['symbols']
        def at(module, name):
            return next(d['address'] for d in s.p['image']['data']
                        if '_'+module+'_'+name.upper()+'_' in d['name'])
        def move(x, y):
            old = [s.number(at('DESKINPUT', n), 2) for n in ('cursorX','cursorY')]
            pos = schedule(b, s.p, old, (x,y))
            s.saved['pointer'] = pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)' %
                (at('DESKINPUT','cursorX'),pos[0],at('DESKINPUT','cursorY'),pos[1]))
            s.frames(3)
        def button(value, frames=0):
            b._cmd_ok('MOUSE AT 2000 0 0 '+str(value))
            if frames: s.frames(frames)
        def click(x,y):
            move(x,y); button(1,20); button(0,90)
        menus = Menus(s,click,move)
        s.saved['desktop_menu'] = {}
        desk = symbols(b,s.p,directory,'desktop',
            s.number(shared['GEMDesktopChildren'],4))['GEMDesk']
        dl,ll = layout(),layers_layout()
        scene = menus.service+dl['Service']['fields']['scene']
        def geometry(ident):
            wf = dl['Window']['fields']
            base = menus.service+dl['Service']['fields']['windows']
            address = next(base+i*dl['Window']['size'] for i in range(ABI['constants']['WINDOWS'])
                           if s.number(base+i*dl['Window']['size']+wf['id'],4)==ident)
            layer = s.number(address+wf['layer'],4)
            base = scene+ll['Scene']['fields']['items']
            address = next(base+i*ll['Layer']['size'] for i in range(LAYERS_ABI['constants']['SLOT_COUNT'])
                           if s.number(base+i*ll['Layer']['size'],4)==layer)
            return struct.unpack('<4h',b.memdump(address+ll['Layer']['fields']['bounds'],8))
        path = s.p['output']/'window-sample.bgra'
        def capture(area):
            f = b.rawscreen(str(path)); raw = path.read_bytes()
            x,y,r,bot = area
            return b''.join(raw[row*f.stride+(x+16)*4:row*f.stride+(r+16)*4]
                            for row in range(y,bot))
        def wait_image(area,want,limit=250):
            for _ in range(limit):
                got=bytearray(capture(area)); reference=bytearray(want)
                # The emitted pointer oracle is separate. Mask its current
                # bounding box equally in reference and sample, including close.
                px,py=s.saved['pointer']; x,y,r,bot=area
                left,right=max(x,px),min(r,px+20)
                if left<right:
                    for row in range(max(y,py),min(bot,py+20)):
                        start=((row-y)*(r-x)+left-x)*4; end=start+(right-left)*4
                        got[start:end]=reference[start:end]=bytes(end-start)
                if got==reference: return
                s.frames(1)
            raise RuntimeError('Window did not reach reference pixels: '+str(area))
        def app(name):
            for _ in range(150):
                found = [a for a in instances(b,s.p,directory) if a['name']==name]
                if found: return found[0]['symbols']
                s.frames(10)
            raise RuntimeError('Missing '+name)
        def open_window(kind):
            # Desktop volume and application icons remain reachable at the left.
            y = 24 if kind=='files' else 24+4*28
            click(48,y); click(48,y)
            b._cmd_ok('KEY RETURN down'); s.frames(4)
            b._cmd_ok('KEY RETURN up'); s.frames(200)
            title = 'SYS:' if kind=='files' else 'Control Panel'
            for _ in range(100):
                if any(title in w['title'] for w in menus.windows()): break
                s.frames(10)
            s.save_screen(s.p['output']/('opened-'+kind+'.png'))
            ident = menus.select(title)
            if kind=='files':
                model = s.number(desk+D['active'],4)
                work,paints = model+B['work'],model+B['paints']
            else:
                model = app('panel')['GEMPanel']
                s.rendezvous('dw($%x)=1'%(model+8))
                work,paints = model+34,model+14
            s.frames(120)
            return ident,work,paints
        def close_start(ident):
            x,y,_,_ = geometry(ident)
            move(x+8,y+8); button(1,5)
            start = b.eval_expr('@clk')&0xffffffff
            button(0)
            return start
        def elapsed(start): return ((b.eval_expr('@clk')-start)&0xffffffff)/BASE_HZ*1000
        def drag_start(ident,dx):
            x,y,r,_ = geometry(ident)
            px = (x+r)//2
            move(px,y+8); button(1,8); move(px+dx,y+8); s.frames(8)
            start = b.eval_expr('@clk')&0xffffffff
            button(0)
            return start

        # A single quiet Shell behind the measured application. Close boot Files.
        ident = menus.select('SYS:'); close_start(ident); s.frames(200)
        for kind in ('files','panel'):
            ident,work,paints = open_window(kind)
            original = geometry(ident)
            dx = 16 if original[2]+16<=640 else -16
            reference = []
            # Exclude pointer/title/menu and the dynamic desktop status line.
            scene_area = (96,max(16,original[1]+16),640,224)
            for offset in (dx,-dx):
                drag_start(ident,offset); s.frames(180)
                x,y,w,h = struct.unpack('<4h',b.memdump(work,8))
                area = (x,y,x+w,y+h)
                reference.append((area,capture(area),capture(scene_area)))
            samples,background,redraws = [],[],[]
            for i in range(self.count):
                area,client_want,scene_want = reference[i%2]
                before = s.number(paints,4)
                start = drag_start(ident,dx if i%2==0 else -dx)
                wait_image(area,client_want)
                samples.append(elapsed(start))
                wait_image(scene_area,scene_want)
                background.append(elapsed(start))
                s.frames(80)
                redraws.append(s.number(paints,4)-before)
            self.results[kind+'_move'] = dict(
                client=dict(samples_ms=samples,**distribution(samples)),
                scene=dict(samples_ms=background,**distribution(background)),
                application_paints=redraws,initial_bounds=original,delta_x=dx)
            (s.p['output']/'window-samples.json').write_text(json.dumps(self.results,indent=2)+'\n')
            print(kind,'moves complete',flush=True)
            # Warm closed state; each new instance closes onto the same model.
            close_start(ident); s.frames(220); move(632,232); s.frames(20)
            close_area = (96,32,632,224)
            want = capture(close_area)
            closes = []
            for _ in range(self.count):
                ident,work,paints = open_window(kind)
                start = close_start(ident)
                wait_image(close_area,want)
                closes.append(elapsed(start)); s.frames(80)
            self.results[kind+'_close'] = dict(samples_ms=closes,**distribution(closes))
            print(kind,self.results[kind+'_move']['client']['median_ms'],
                  self.results[kind+'_close']['median_ms'],flush=True)
            (s.p['output']/'window-samples.json').write_text(json.dumps(self.results,indent=2)+'\n')
        menus.select('Shell');s.command('HELLO',b'Hello from disk!')
        s.save_screen(s.p['output']/'boot-smoke.png')
        for ch in 'EXIT':s.press(ch)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--count',type=int,default=20)
    a = p.parse_args(); out=a.output.resolve()
    require(not out.exists(),'Use a fresh measurement directory')
    shutil.copytree(a.bundle.resolve(),out,ignore=shutil.ignore_patterns(
        'extracted','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive: archive.extractall(out/'extracted')
    probe=Windows(a.count)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
               integration=probe,profile_commands=False)
    result.update(qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),
        windows=probe.results,scope='Idle physical release to client and scene scanout equality; '
        'one PAL frame polling; matched warm references, no production instrumentation.')
    (out/'window-results.json').write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__': main()
