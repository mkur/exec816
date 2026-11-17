#!/usr/bin/env python3
"""Build and measure the pinned standalone GEM4XE MGVIEW fixture."""
import argparse
from collections import Counter
from hashlib import sha256
import json
import os
from pathlib import Path
import shutil
import struct
from unittest.mock import patch

from filesystem_audit import Audit
from gem_render_oracle import Raster, font_bytes
from native_program import ROOT, command, require, verify_machine
from os_boundary import emulator
from prepare_mgview import PORT, prepare
from sio_transaction_trace import BASE_HZ, read_events
from test_mouse_observe import BRIDGE, PIN, ROM

GEM4XE_REVISION = '2bf10f6788372dcfa94f6d9416e4b957eb4ce394'
GEM4XE_REPOSITORY = 'https://github.com/slaapliedje/gem4xe.git'
DOCUMENT_SHA256 = '02230472cd9d7a55b977b91c63da82fe57db3141242e0898455d7e39654d880a'


APP_RULES = '''include Makefile

MGVIEW_SRC = ../source
MGVIEW_OBJS = $(G4A_LIB_LD) $(addprefix build/mgview-,mgview.o mgwind.o windows.o support.o)

build/mgview-%.o: $(MGVIEW_SRC)/%.c
	$(CC) --code-model=large --data-model=large -O2 --char-is-unsigned --no-inline -Werror=implicit-function-declaration -I src -I src/app -o $@ $<

$(eval $(call g4a,mgview,$(MGVIEW_OBJS),2560,1024,1024,,,$(LIB_LD)))
'''


def prepare_fixture(root, baseline_disk):
    upstream = root / 'upstream'
    if not upstream.exists():
        command(['git', 'clone', '--filter=blob:none', '--no-checkout', GEM4XE_REPOSITORY, upstream])
        command(['git', 'checkout', '--detach', GEM4XE_REVISION], cwd=upstream)
    require(command(['git', 'rev-parse', 'HEAD'], cwd=upstream).strip() == GEM4XE_REVISION,
            'Wrong GEM4XE revision')
    require(not command(['git', 'status', '--porcelain', '-uno'], cwd=upstream).strip(),
            'GEM4XE source tree has tracked changes')
    require(baseline_disk.is_file(), 'Missing frozen Exec scroll fixture disk')
    disk = Audit(baseline_disk.read_bytes())
    disk.sdfs()
    document = root / 'view.txt'
    document.write_bytes(disk.files['VIEW.TXT'])
    require(sha256(document.read_bytes()).hexdigest() == DOCUMENT_SHA256, 'Changed fixture document')

    source = root / 'source'
    prepare(source)

    def replace(name, changes):
        path = source / name
        text = path.read_text()
        for before, after in changes:
            require(before in text, f'Changed {name} compatibility site: {before}')
            text = text.replace(before, after)
        path.write_text(text)

    replace('mgview.c', [
        ('int main( int argc, char *argv[] )', 'int main(void)'),
        ('Pterm(-1);', 'return 1;'),
        ('for\t(i = 1,argv++; i < argc; i++,argv++)\n\t\t{\n\t\topen_textwind(*argv);\n\t\t}',
         'open_textwind("A:\\\\GEM\\\\VIEW.TXT");\n'
         '\tscrg.g_w = 617; /* Clip the work area to x=1 through x=616. */'),
        ('ExecAESInputWindow(MU_KEYBD)', 'top_whdl()'),
    ])
    replace('mgwind.c', [
        ('XATTR xa;', 'long file_size;'),
        ('err = Fcntl(handle, (long) &xa, FSTAT);',
         'err = Fseek(0, handle, 2);\n\tif (err >= 0) { file_size=err; err=Fseek(0,handle,0); }'),
        ('xa.size', 'file_size'),
        ('= Malloc(', '= (void *)Malloc('),
    ])
    replace('windows.c', [
        ('WINDOW *windows[NWINDOWS]', 'WINDOW *windows[NWINDOWS] SECTION("zdata")'),
        ('fd_addr = NULL', 'fd_addr = 0'),
        ('\tw->snap(w);\n\tif(!wind_open_grect',
         '\tw->snap(w);\n\tw->out.g_w -= 8; /* Match the Exec MGVIEW comparison viewport. */\n'
         '\tif(!wind_open_grect'),
    ])
    for name in ('mgview-native.h', 'support.c'):
        shutil.copyfile(PORT / 'native' / name, source / name)
    replace('mgview-native.h', [
        ('#include <compat/gem-rect.h>\n#include <compat/gemdos.h>\n#include <exec816/aes.h>\n', ''),
        ('#define SCREEN 0', '#define SCREEN 0\n#define WF_HSLSIZE WF_HSLSIZ\n#define WF_VSLSIZE WF_VSLSIZ'),
        ('#define K_CTRL 4\n', ''),
        ('#define E_OK 0\n', ''),
        ('#define ENSMEM GEMDOS_ENSMEM\n', '#define GEMDOS_ENSMEM ENSMEM\n#define GEMDOS_ERANGE (-64L)\n'),
    ])
    replace('support.c', [
        ('void form_xerr(', 'NEAR volatile LONG mgview_error;\n\nvoid form_xerr('),
        ('(void)path;', '(void)path; mgview_error=error;'),
    ])
    build = upstream / 'build'
    build.mkdir(exist_ok=True)
    (build / 'mgview.mk').write_text(APP_RULES)
    cc = shutil.which('cc65816')
    require(cc is not None and command([cc, '--version']).strip().endswith('version 5.18'),
            'The benchmark uses Calypsi 5.18')
    calypsi = Path(cc).resolve().parent.parent
    command(['make', '-f', 'build/mgview.mk', '-j6', f'CALYPSI={calypsi}',
             'build/gem.xex', 'build/lang.rsc', 'build/gem4xe.cfg', 'build/816.com',
             'build/fdos.elf', 'build/fdboot.elf', 'build/mgview.g4a'], cwd=upstream, timeout=180)
    command(['python3', 'tools/mkfloppy.py', root / 'mgview.atr', '--app', 'build/mgview.g4a',
             '--add', document, 'GEM>VIEW.TXT'], cwd=upstream)


def observe(root):
    upstream=root/'upstream'
    output=root/'matched'
    def symbols(path):
        return {k:int(v,16) for k,v in (line.split() for line in path.read_text().splitlines()
                                       if len(line.split())==2)}
    gem=symbols(upstream/'build/gem.sym')
    app=symbols(upstream/'build/mgview.sym')
    loaded=0x70000
    names=('set_shift','window_calc_slider','vro_cpyfm','_my_draw','v_gtext',
           'wind_update','evnt_multi_moblk','_my_keyed','graf_mouse','vr_recfl')
    app_points={app[name]-0x20000+loaded:name for name in names}
    core_points={gem[name]:name for name in ('vdi_vro_cpyfm','vdi_v_gtext','blit_start','copy_rows','blit_move')}
    points={**app_points,**core_points}
    trace=dict(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
    content=(root/'view.txt').read_bytes()
    require(sha256(content).hexdigest()==DOCUMENT_SHA256,'Changed fixture document')
    lines=content.splitlines()
    font=font_bytes(upstream/'src/vdi/font8x8.c')
    def glyph_mask(work,shift):
        x,y,w,h=work
        raster=Raster(font)
        raster.clip=(x,y,x+w-1,y+h-1)
        for i,line in enumerate(lines[shift:shift+h//8]):
            raster.apply(8,[x,y+i*8+6],list(line.expandtabs(8)[:272]))
        return b''.join(raster.pixels[yy*640+x:yy*640+x+w] for yy in range(y,y+h))

    with patch.dict(os.environ,trace), emulator(BRIDGE,ROM,output,pin=PIN) as b:
        for name,value in PIN['configuration'].items():
            b.config(name,str(value).lower() if isinstance(value,bool) else value)
        b.mount(0,str(root/'mgview.atr'))
        verify_machine(b,ROM,PIN)
        b.config('siopatch','on')  # Speed up the untimed disk boot.
        b.cold_reset()
        def n(addr,size=2):
            return int.from_bytes(b.memdump(addr,size),'little')
        def app_word(name,size=2):
            return n(n(gem['app_vars'],4)+app[name]-0x30000,size)
        for _ in range(25):
            b.frame(50)
            near=n(gem['app_near'])
            if near:
                error=n(near+app['mgview_error']-0x1000,4)
                require(error==0,f'MGVIEW open error {error:#x}')
                if app_word('nwindows')==1:
                    break
        else:
            raise RuntimeError('GEM4XE did not open the MGVIEW window')
        require(n(gem['app_far'],4)==loaded,'Unexpected MGVIEW code placement')
        b.frame(120)
        b.config('siopatch','off')
        machine=b.config()
        b._cmd_ok('KEY ALL up')
        b._cmd_ok('MOUSE ST')
        for i in range(400):
            b._cmd_ok(f'MOUSE AT {2000+i*6000} 16 -12 -1')
        b.frame(75)

        win=n(near+app['windows']-0x1000,4)
        # Calypsi large-data WINDOW has four-byte pointers, with in at byte 268.
        window_work=struct.unpack('<hhhh',b.memdump(win+268,8))
        require(window_work==(1,22,617,200),'Expected GEM4XE rounded work area')
        screen_work=struct.unpack('<hhhh',b.memdump(n(gem['app_vars'],4)+app['scrg']-0x30000,8))
        require(screen_work[0]==0 and screen_work[2]==617,'Unexpected fixture clip')
        dims=(*window_work[:2],screen_work[2]-window_work[0],window_work[3])
        cell=struct.unpack_from('<hh',b.memdump(n(gem['app_vars'],4)+app['text_attrib']-0x30000+16,4))
        print('work',dims,'font cells',cell,'pointer',n(gem['xrat']),n(gem['yrat']),
              'near',hex(near),'window',hex(win),flush=True)
        x,y,w,h=dims
        require(dims==(1,22,616,200) and cell==(8,8),
               'Unexpected viewport layout')
        def screen(label='current'):
            path=output/f'{label}.bgra'
            f=b.rawscreen(str(path));raw=path.read_bytes()
            require(f.stride==672*4 and len(raw)==672*240*4,'Unexpected scanout layout')
            return b''.join(raw[yy*f.stride+(x+16)*4:yy*f.stride+(x+16+w)*4]
                            for yy in range(y,y+h))
        initial=screen('initial')
        mask=glyph_mask(dims,0)
        colours={tone:Counter(initial[i*4:i*4+3] for i,p in enumerate(mask) if p==tone)
                             .most_common(1)[0][0] for tone in set(mask)}
        require(len(set(colours.values()))==2,'Expected two distinct viewport colours')
        def render(shift):
            tone=glyph_mask(dims,shift)
            return b''.join(colours[p] for p in tone)
        def rgb(raw):
            return b''.join(raw[i:i+3] for i in range(0,len(raw),4))
        same=sum(initial[i*4:i*4+3]==colours[p] for i,p in enumerate(mask))
        print('initial pixels matched',same,len(mask),'colours',{p:c.hex() for p,c in colours.items()},flush=True)
        require(rgb(initial)==render(0),'Initial viewport glyphs or colours differ')
        geometry=dict(work=dims,window_work=window_work,cell=cell,pointer=[n(gem['xrat']),n(gem['yrat'])])
        require(geometry['pointer']==[639,0],'Pointer was not parked outside the viewport')
        b._cmd_ok('KEY CTRL down')
        b.frame(3)
        b.profile_start()
        observations=[]
        for index in range(6):
            down=index%2==0
            key='EQUALS' if down else 'MINUS'
            shift=int(down)
            desired=render(shift)
            start=b.eval_expr('@clk')
            b._cmd_ok(f'KEY {key} down')
            previous=0
            sample=dict(action='down' if down else 'up',start=start,polls=[])
            for frame_index in range(16):
                b.frame(1)
                tick=b.eval_expr('@clk')
                got=rgb(screen(f'scroll-{index:02d}'))
                match=got==desired
                sample['polls'].append((tick,match))
                if frame_index==1:
                    b._cmd_ok(f'KEY {key} up')
                if match:
                    sample.update(first_complete_tick=tick,pixel_sha256=sha256(got).hexdigest(),
                                  last_different_tick=previous)
                    break
                previous=tick
            b._cmd_ok(f'KEY {key} up')
            require(match,'Key did not produce a complete scroll')
            b.frame(5)
            sample['end']=b.eval_expr('@clk')
            print(sample['action'],(sample['first_complete_tick']-start)*1000/BASE_HZ,flush=True)
            observations.append(sample)
        b.profile_stop()
        b._cmd_ok('KEY CTRL up')

    events=read_events(output/'emulator.log',{'cpu'})
    for sample in observations:
        stamps={}
        for tick,event in events:
            pc=int(event[4],16)
            delta=(tick-sample['start']) % (1<<32)
            if delta<=sample['end']-sample['start'] and pc in points:
                stamps.setdefault(points[pc],[]).append(sample['start']+delta)
        sample['entries']=stamps
        require(len(stamps.get('set_shift',()))==len(stamps.get('vro_cpyfm',()))
                ==len(stamps.get('_my_draw',()))==len(stamps.get('v_gtext',()))==1,
                f'Unexpected scroll work {list((n,len(ts)) for n,ts in stamps.items())}')
        require(len(stamps.get('copy_rows',()))==2 and len(stamps.get('blit_move',()))==1
                and stamps['copy_rows'][0]<stamps['blit_move'][0]<stamps['copy_rows'][1],
                'Expected the two packed-edge passes around the interior blit')
        sample['key_to_pixels_ms']=(sample['first_complete_tick']-sample['start'])*1000/BASE_HZ
        sample['shift_to_event_wait_ms']=(stamps['evnt_multi_moblk'][0]-stamps['set_shift'][0])*1000/BASE_HZ
        sample['slider_to_copy_ms']=(stamps['vro_cpyfm'][0]-stamps['window_calc_slider'][0])*1000/BASE_HZ
        sample['copy_to_row_ms']=(stamps['_my_draw'][0]-stamps['vro_cpyfm'][0])*1000/BASE_HZ
        sample['row_to_mouse_show_ms']=(stamps['graf_mouse'][-1]-stamps['_my_draw'][0])*1000/BASE_HZ
        print(sample['action'],{k:round(v,2) for k,v in sample.items() if k.endswith('_ms')},flush=True)
    report=dict(status='pass',tier='development',qualification=False,
                geometry=geometry,machine=machine,samples=observations,
                gem4xe_revision=GEM4XE_REVISION,rom_sha256=sha256(ROM.read_bytes()).hexdigest(),
                emulator_sha256=sha256((BRIDGE/'AltirraBridgeServer').read_bytes()).hexdigest(),
                document_sha256=sha256(content).hexdigest(),
                gem_sha256=sha256((upstream/'build/gem.xex').read_bytes()).hexdigest(),
                app_sha256=sha256((upstream/'build/mgview.g4a').read_bytes()).hexdigest(),
                disk_sha256=sha256((root/'mgview.atr').read_bytes()).hexdigest(),
                base_clock_hz=BASE_HZ)
    (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'build/gem4xe-mgview')
    parser.add_argument('--baseline-disk', type=Path,
                        default=ROOT/'build/gem-direct-scrollbar/scratch-scroll/system.atr')
    parser.add_argument('--replay', action='store_true', help='Reuse the prepared image and symbols')
    args = parser.parse_args()
    directory = args.output.resolve()
    require(directory.is_relative_to(ROOT/'build'), 'Use a work directory under build/')
    directory.mkdir(parents=True, exist_ok=True)
    if not args.replay:
        prepare_fixture(directory, args.baseline_disk.resolve())
    observe(directory)
