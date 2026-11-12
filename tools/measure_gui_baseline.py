#!/usr/bin/env python3
"""Current optimized OF816 viewer baseline, using existing physical-input fixtures."""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import zipfile
from pathlib import Path

from filesystem_audit import Audit
from gem_applications import instances
from gem_render_oracle import DESKTOP_PALETTE, PENS, Raster, font_bytes
from generate_aes_server import ABI, layout
from measure_text_viewer import distribution
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from program_image_layout import FIELDS as IMAGE
from sio_transaction_trace import BASE_HZ, read_events
from test_dos_stack import execute, ownership
from test_gem_acceptance import Session, bootstrap
from test_mouse_observe import BRIDGE, PIN
from text_model import FIELDS as F, LOAD_PHASE
from text_performance_trace import analyze, prepare
from text_viewer_oracle import paint as paint_viewer


def save_cpu_trace(out):
    """Keep timed CPU observations, excluding bridge credentials/serial noise."""
    events=read_events(out/'emulator.log',kinds={'cpu'})
    with (out/'cpu-trace.log').open('w') as destination:
        destination.write('[SIOTXN] anchor '+str(int(events[0][0]))+'\n')
        for _,fields in events:
            destination.write('[SIOTXN] '+' '.join(fields)+'\n')


def exposed_title(bounds,covering):
    left,top,right,bottom=bounds;y=top+5
    candidates=[x for x in range(left+20,right-2,4)
        if not any(l<=x<r and t<=y<b for l,t,r,b in covering)]
    require(candidates,'No exposed title')
    return candidates[0],y


def physical_focus(s,title):
    """Raise by the exposed title, keeping the Counter's digits visible."""
    from generate_desktop import layout as desktop_layout
    from generate_layers import layout as layers_layout
    types=desktop_layout();layers=layers_layout();wf=types['Window']['fields']
    windows=s.menus.windows();target=next(w for w in windows if w['title']==title)
    ident=target['id'];bounds={}
    service=s.menus.service;scene=service+types['Service']['fields']['scene']
    for slot in range(6):
        window=service+types['Service']['fields']['windows']+slot*types['Window']['size']
        window_id=s.number(window+wf['id'])
        if not window_id:continue
        layer=s.number(window+wf['layer'])
        for i in range(8):
            item=scene+layers['Scene']['fields']['items']+i*layers['Layer']['size']
            if s.number(item)!=layer:continue
            raw=s.far(item+layers['Layer']['fields']['bounds'],8)
            bounds[window_id]=[int.from_bytes(raw[i:i+2],'little',signed=True) for i in (0,2,4,6)]
    require(ident in bounds,'No physical title for '+title)
    covering=[bounds[w['id']] for w in windows if w['rank']<target['rank']]
    s.click(*exposed_title(bounds[ident],covering))
    s.rendezvous(f'dw(${s.menus.focus_address:x})={ident}')
    return ident


def pixels(s, app, label):
    """Compare the entire unobscured work area to the raw-document oracle."""
    a = app['symbols']['GEMText']
    x, y, w, h = [s.number(a+F['work']+i*2, 2) for i in range(4)]
    fields = layout()['Request']['fields']
    context = next(c for i in range(ABI['constants']['CONTEXTS'])
        if (c := s.number(s.provider['contexts']+i*4))
        and s.number(c+fields['owner'], 3) == app['task'])
    raster = Raster(font_bytes(s.directory/'selected/src/vdi/font8x8.c'))
    paint_viewer(s.b, {**app['symbols'], '__aes_context':context}, raster,
        (x-8, y-11, x+w+16, y+h+11))
    frame = s.b.rawscreen(str(s.out/(label+'.bgra')))
    raw = (s.out/(label+'.bgra')).read_bytes()
    require((frame.width,frame.height)==(672,240), 'Unexpected native scanout geometry')
    colours=[None]*16
    for pen,hardware in enumerate(PENS):
        colours[hardware]=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
    # Native scanout includes a 16-pixel left margin; its fourth byte is padding.
    actual = b''.join(raw[row*frame.stride+(col+16)*4:row*frame.stride+(col+16)*4+3]
        for row in range(y, y+h) for col in range(x,x+w))
    expected = b''.join(colours[raster.pixels[row*640+col]]
        for row in range(y, y+h) for col in range(x, x+w))
    require(actual == expected, 'Viewer pixels differ: '+label)
    return dict(label=label, pixels=w*h, sha256=hashlib.sha256(actual).hexdigest())


def exercise(s, report, count, load, observe):
    counter=None
    if load:
        from colour_desktop_model import FIELDS as D
        from browser_model import FIELDS as B
        desktop=next(a for a in instances(s.b,s.p,s.directory) if a['name']=='desktop')
        desk=desktop['symbols']['GEMDesk'];folder=s.number(desk+D['folders'])
        x,y=[s.number(folder+B['work']+i*2,2) for i in range(2)]
        # The startup folder's title is exposed above Terminal. Use its actual
        # physical title/gadget, as in the retained desktop walkthrough.
        s.click(x+48,y-6);s.click(296,8);s.click(304,72)
        for _ in range(100):
            apps=[a for a in instances(s.b,s.p,s.directory) if a['name']=='counter']
            if apps:break
            s.frames(10)
        require(apps,'Desk menu did not launch Counter')
        counter=apps[0]; counter_at=counter['symbols']['GEMCounter']
        s.rendezvous(f'dw(${counter_at+12:x})=1');s.frames(60)
        cx,cy=[s.number(counter_at+38+i*2,2) for i in range(2)]
        s.move(cx+40,cy-6);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(20)
        s.move(cx+40+480-(cx-8),cy-6)
        s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(100)
        s.rendezvous(f'dw(${counter_at+38:x})=488')
        report['counter_work']=[s.number(counter_at+38+i*2,2) for i in range(4)]
        s.click(x+48,y-6) # Raise the inactive folder before its close gadget.
        s.click(x-2,y-6);s.rendezvous(f'dw(${desk+D["folders"]:x})=0')
        s.menus.select=lambda title:physical_focus(s,title)
    # Close the startup folder; the desktop and loaded Terminal stay resident.
    for window in list(s.menus.windows()):
        if window['title'] not in ('Terminal','Counter'):
            s.menus.select(window['title']); s.menus.close(); s.frames(60)
    s.menus.select('Terminal')
    if load:
        s.command('MOUNT TEST: DRIVE 8 FORMAT SPARTA READWRITE')
    def memory():
        s.command('MEM')
        from console_model import read_cells
        text = read_cells(s.far, s.source(s.index())).decode('ascii')
        values = re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)', text)
        require(len(values) >= 4, 'Missing heap observation')
        return list(map(int, values[-4:]))
    baseline = memory(); report['heap_before']=baseline
    s.command('RUN C:TEXT.APP SYS:STORY.TXT')
    app = next(a for a in instances(s.b, s.p, s.directory) if a['name']=='text')
    report['app']=app
    a = app['symbols']['GEMText']
    n = lambda name, size=2:s.number(a+F[name], size)
    def settled():
        s.rendezvous(f'(dw(${a+F["ready"]:x})=1)&'
            f'(dw(${a+F["load"]+LOAD_PHASE:x})=0)&(dw(${a+F["dirty"]:x})=0)', 'native_irq')
    # TextStep clears load.phase before committing title/viewport/damage. Require
    # the document commit and a subsequent completed paint, not that gap.
    s.rendezvous(f'dw(${a+F["ready"]:x})=1')
    fields=layout()['Request']['fields']
    context=next(c for i in range(ABI['constants']['CONTEXTS']) if (c:=s.number(s.provider['contexts']+i*4))
        and s.number(c+fields['owner'],3)==app['task'])
    inbox=s.number(context+fields['receiving'],3)
    bit=s.number(inbox+12,1);require(bit<32,'Invalid observed inbox signal bit')
    mask=1<<bit
    s.rendezvous(f'(dw(${a+F["loads"]:x})=1)&(dw(${a+F["dirty"]:x})=0)&'
        f'(db(${app["task"]+12:x})=4)&(dw(${app["task"]+20:x})={mask&65535})&'
        f'(dw(${app["task"]+22:x})={mask>>16})','native_irq')
    settled()
    report['viewer_startup']=dict(loads=n('loads',4),
        status=s.far(a+F['status'],81).split(b'\0')[0].decode('ascii'),windows=s.menus.windows())
    require(n('loads',4)==1, 'Viewer did not load the document: '+repr(report['viewer_startup']))
    s.menus.select('STORY.TXT'); s.move(630, 230); s.frames(60)
    report.update(app=app, work=[s.number(a+F['work']+i*2, 2) for i in range(4)],
        columns=n('columns'), rows=n('rows'), samples=[], pixel_checks=[])
    doc = a+F['document']
    payload = s.far(s.number(doc), s.number(doc+8))
    require(hashlib.sha256(payload).hexdigest() == report['document_sha256'], 'Changed document')
    report['pixel_checks'].append(pixels(s, app, 'initial'))
    if load:
        s.menus.select('Terminal');disk=s.begin('TEST:GFLOAD')
        for _ in range(400):
            image = s.load_image()
            if image:break
            s.frames(3)
        require(image is not None, 'Disk command did not load')
        descriptor = json.loads((load/'GFLOAD.profile.json').read_text())
        item = next(o for o in descriptor['objects'] if '_PROGRESS_' in o['name'])
        status = s.number(image+IMAGE[item['location']['section'].lower()], 3)+item['location']['offset']
        s.rendezvous(f'(dw(${status:x})=2)&(db(${s.p["labels"]["SD_PHASE"]:x})>0)')
        report['disk_start'] = s.b.eval_expr('@clk')
        s.menus.select('STORY.TXT'); s.move(630, 230); settled(); s.frames(6)
        ticks = s.number(counter_at+14)
    if observe:s.b.profile_start()
    for operation in ('page', 'line'):
        for i in range(count):
            settled(); s.frames(6)
            first, paints = n('first'), n('paints', 4)
            row = dict(operation=operation, index=i, start=s.b.eval_expr('@clk'), first=first)
            cursor = operation == 'line'
            if cursor:s.b._cmd_ok('KEY CTRL down')
            elif i%2:s.b._cmd_ok('KEY SHIFT down')
            key = ('EQUALS' if i%2==0 else 'MINUS') if cursor else 'SPACE'
            s.b._cmd_ok('KEY '+key+' down'); s.frames(3); s.b._cmd_ok('KEY '+key+' up')
            if cursor:s.b._cmd_ok('KEY CTRL up')
            elif i%2:s.b._cmd_ok('KEY SHIFT up')
            s.rendezvous(f'dw(${a+F["first"]:x})!={first}', 'native_irq')
            row['model'] = s.b.eval_expr('@clk')
            s.rendezvous(f'dw(${a+F["paints"]:x})!={paints&65535}', 'native_irq')
            row['first_band'] = s.b.eval_expr('@clk')
            settled(); row['complete'] = s.b.eval_expr('@clk')
            row.update(final_first=n('first'), paint_bands=n('paints', 4)-paints)
            require(row['final_first'] == first+(n('rows') if not cursor else 1)*(1 if i%2==0 else -1),
                'Unexpected scrolling result')
            for key in ('model', 'first_band', 'complete'):
                row[key+'_ms'] = ((row[key]-row['start'])&0xffffffff)*1000/BASE_HZ
            if load:
                row['disk_phase'] = s.number(status, 2)
                row['sio_phase'] = s.number(s.p['labels']['SD_PHASE'], 1)
                row['disk_read_bytes'] = s.number(status+4)
                row['disk_written_bytes'] = s.number(status+8)
                require(row['disk_phase'] in (2, 3), 'Disk work ended before measured repaint')
            report['samples'].append(row)
            print(report['load'], operation, i, round(row['complete_ms'], 3), 'ms', flush=True)
        s.frames(3)
        report['pixel_checks'].append(pixels(s, app, operation))
    # Stop at a known boundary after the viewer returns to its event wait.
    s.frames(6); report['trace_end'] = s.b.eval_expr('@clk')
    if observe:s.b.profile_stop()
    before = n('paints', 4)
    s.b._cmd_ok('KEY CTRL down'); s.b._cmd_ok('KEY MINUS down'); s.frames(3)
    s.b._cmd_ok('KEY MINUS up'); s.b._cmd_ok('KEY CTRL up'); s.frames(30)
    require(n('first') == 0 and n('paints', 4) == before, 'Boundary no-op repainted')
    report['no_op'] = True
    if load:
        require(s.number(counter_at+14) > ticks, 'Counter did not advance')
        report['counter_progress'] = True
        s.menus.select('Terminal');s.ready(disk)
        require(s.result()[0]==0,'Disk command failed')
        report['disk_complete'] = s.b.eval_expr('@clk')
    s.menus.select('STORY.TXT'); s.menus.close(); s.frames(100)
    s.menus.select('Terminal'); s.command('JOBS')
    require(not any(a['name']=='text' for a in instances(s.b, s.p, s.directory)), 'Viewer not collected')
    report['heap_after']=memory()
    require(report['heap_after'] == baseline, 'Viewer heap did not return')
    report['heap_return'] = True
    if counter:s.close_counter('Counter')
    s.close_extra_session()
    s.menus.select('Terminal')
    for ch in 'EXIT':s.press(ch)
    s.b._cmd_ok('KEY RETURN down'); s.b.bp_clear_all()


def run(bundle, out, count=4, load=None, observe=False):
    require(count > 0 and count%2 == 0, 'Use a positive even sample count')
    require(not out.exists(), 'Use a fresh output directory')
    out.mkdir(parents=True)
    (out/'measurement-observer.py').write_text(Path(__file__).read_text())
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    require(all(sha256(bundle/name)==digest for name, digest in manifest['artifacts'].items()),
        'Changed demo bundle')
    p = read_build(bundle); directory = bundle/'bitmap-console'
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    extracted = out/'extracted/exec816-demo'
    shutil.copyfile(extracted/manifest['media'], out/'system.atr')
    if load:shutil.copyfile(load/'seed.atr', out/'load.atr')
    report = dict(status='running', tier='development', qualification=False, observe=observe,
        load='counter-disk' if load else 'idle', source_revision=subprocess.check_output(
            ['git','rev-parse','HEAD'], cwd=ROOT, text=True).strip(),
        zip_sha256=sha256(bundle/'exec816-demo.zip'), document_sha256=manifest['files']['STORY.TXT']['sha256'],
        reserved_bank_zero_delta=dict(fixed=0, root=0, kernel=0, each_public_task=0, idle=0),
        scope='Physical key offer to IRQ-observed completed repaint; scanout excluded')
    report['inputs']={str(path.relative_to(ROOT)):sha256(path) for path in (
        Path(__file__), ROOT/'tools/text_performance_trace.py', ROOT/'tools/bitmap_console_performance.py', ROOT/'toolchain/actionc.json',
        ROOT/'toolchain/altirra-gem-vdi.json', ROOT/'examples/gem-text/text.c',
        ROOT/'examples/gem-text/document.c', ROOT/'ports/gem4xe/adapter/gem-vbxe.c')}
    previous = {k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')}
    try:
        if observe:
            definition = prepare(bundle)
            (out/'text-performance-markers.json').write_text(json.dumps(definition, indent=2)+'\n')
            os.environ.update(EXEC816_LATENCY_TRACE='1',
                EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in definition['pcs']))
        else:
            os.environ.pop('EXEC816_LATENCY_TRACE', None); os.environ.pop('EXEC816_LATENCY_PCS', None)
        os.environ.pop('EXEC816_MASK_TRACE', None)
        require(sha256(BRIDGE/'AltirraBridgeServer') == PIN['mouse_input']['tooling']['sha256'], 'Unpinned emulator')
        with emulator(BRIDGE, extracted/'altirraos-816.rom', out, pin=PIN) as b:
            for k, v in PIN['configuration'].items():b.config(k, str(v).lower() if isinstance(v, bool) else v)
            report['machine'] = verify_machine(b, extracted/'altirraos-816.rom', PIN)
            b.mount(0, str(out/'system.atr'))
            if load:b.mount(7, str(out/'load.atr'))
            bootstrap(b, p, bundle, extracted, report)
            def before(b):
                b._cmd_ok('KEY ALL up'); b._cmd_ok('MOUSE ST')
                from shell_inspect import address
                selected = address(p['image'], 'selectedSession')
                b.bp_clear_all(); b.bp_set(p['labels']['native_nmi'], condition=f'dw(${selected:x})=1')
                run_to(b, p['labels']['native_nmi'], 12000, 180, f'dw(${selected:x})=1')
                s = Session(b, p, directory, out, report); s.ready(); s.startup()
                try:exercise(s, report, count, load, observe)
                except BaseException:
                    if 'app' in report:
                        app=report['app'];a=app['symbols']['GEMText']
                        report['viewer_diagnostic']={name:s.number(a+F[name],4 if name in ('paints','loads') else 2)
                            for name in ('ready','dirty','first','paints','loads')}
                        report['viewer_diagnostic'].update(task_state=s.number(app['task']+12,1),
                            wait_mask=s.number(app['task']+20),load_phase=s.number(a+F['load']+LOAD_PHASE,2),
                            status=s.far(a+F['status'],81).split(b'\0')[0].decode('ascii'))
                    b.screenshot(str(out/'failure.png'))
                    raise
            report['runtime'], _ = execute(b, {**p, 'output':out}, before_run=before,
                timeout=300, frame_limit=20000, preloaded=True)
            ownership(b, p, bundle)
            if load:b._cmd_ok('EJECT drive=7')
            b._cmd_ok('EJECT drive=0')
        if load:
            audit = Audit((out/'load.atr').read_bytes()); audit.sdfs()
            require(audit.files['RESULT.BIN'] == (load/'media/LOAD.BIN').read_bytes(), 'Disk bytes differ')
            report['disk_bytes_verified'] = True
        for operation in ('page','line'):
            selected = [r for r in report['samples'] if r['operation']==operation]
            report[operation+'_distribution'] = {k:distribution([r[k+'_ms'] for r in selected])
                for k in ('model','first_band','complete')}
        if observe:
            save_cpu_trace(out)
            report['breakdown'] = analyze(out, definition, report)
        report['status'] = 'pass'
    except BaseException as error:
        report.update(status='fail', error=type(error).__name__+': '+str(error)); raise
    finally:
        for k, v in previous.items():
            if v is None:os.environ.pop(k, None)
            else:os.environ[k] = v
        (out/'results.json').write_text(json.dumps(report, indent=2)+'\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--count', type=int, default=4)
    parser.add_argument('--load', type=Path, help='build_gem_load.py output; adds Counter and disk work')
    parser.add_argument('--observe', action='store_true')
    parser.add_argument('--analyze-only', action='store_true')
    args = parser.parse_args()
    if args.analyze_only:
        out=args.output.resolve()
        report=json.loads((out/'results.json').read_text())
        definition=json.loads((out/'text-performance-markers.json').read_text())
        save_cpu_trace(out)
        report['breakdown']=analyze(out,definition,report)
        require('runtime' in report and report.get('heap_return'), 'Incomplete native measurement')
        report.update(status='pass');report.pop('error',None)
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    else:
        run(args.bundle.resolve(), args.output.resolve(), args.count,
            args.load.resolve() if args.load else None, args.observe)
