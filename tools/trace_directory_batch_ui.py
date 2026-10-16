#!/usr/bin/env python3
"""Packaged batch-scanner walkthrough with only UI completion boundaries."""
import argparse,json,os,re,shutil,zipfile
from collections import Counter
from pathlib import Path
from native_program import require,sha256
from browser_model import FIELDS as F
from gem_applications import instances
from desktop_menu_check import Menus
from desktop_mouse import schedule
from g4bench_trace import listing_returns,calls
from sio_transaction_trace import read_events,BASE_HZ
from trace_files_enumeration import Enumeration
from test_demo import run


def setup(out):
    shared=json.loads((out/'bitmap-console/c-image.json').read_text())
    app=json.loads((out/'bitmap-console/apps/desktop/app.json').read_text())
    # Retain complete section bytes for relocation matching, but select only
    # calls to these two routines. No broad C return/instruction trace.
    directory=out/'ui-markers';directory.mkdir(exist_ok=True)
    for p in (out/'bitmap-console/apps/desktop').glob('*.lst'):
        if p.name=='link.lst':continue
        source=re.sub(r'\bjsl\s+(\S+)',lambda m:m[0] if m[1].removeprefix('long:') in ('redraw','desktop_new') else 'unobserved '+m[1],p.read_text())
        (directory/p.name).write_text(source)
    returns=listing_returns(app['image'],directory)
    base=9<<16;delta=base-(app['abi']['link_bank']<<16)
    entries={app['image']['symbols'][n]+delta:n for n in ('redraw','desktop_new')}
    entries.update({shared['symbols'][n]:n for n in ('fsel_exinput','ExecAESEvents','UnLock')})
    checked=shared['provenance']['checked_layout']
    definition=dict(entries=entries,returns=[pc+delta for pc in returns],base=base,
        browser_fields={k.removeprefix('Browser '):v for k,v in checked.items() if k.startswith('Browser ') and k!='Browser size'},
        batch='ExNextBatch' in shared['symbols'])
    (out/'ui-definition.json').write_text(json.dumps(definition,indent=2)+'\n')
    return definition


class UI(Enumeration):
    def exercise(self,s):
        from directory_batch_gui import exercise
        d=json.loads((s.p['output']/'ui-definition.json').read_text());F.update(d['browser_fields'])
        b=s.b
        app=next(a for a in instances(b,s.p,s.p['output']/'bitmap-console') if a['name']=='desktop')
        require(app['base']==d['base'],'Desktop moved outside UI marker bank')
        def at(name):return next(v['address'] for v in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in v['name'])
        def move(x,y):
            old=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            pos=schedule(b,s.p,old,(x,y));s.saved['pointer']=pos
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),pos[0],at('cursorY'),pos[1]));s.frames(3)
        def click(x,y):
            move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(25)
            b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(80)
        menus=Menus(s,click,move)
        b.profile_start();menus.select('SYS:')
        exercise(s,menus,move,click,apps='WORK:',batch=d['batch'],standalone=self.standalone)
        s.save_screen(s.p['output']/'boot-smoke.png')
        menus.select('Shell')
        for ch in 'EXIT':s.press(ch)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def analyze(out,partial=False):
    d=json.loads((out/'ui-definition.json').read_text())
    ui=json.loads((out/('directory-batch-ui-progress.json' if partial else 'directory-batch-ui.json')).read_text())
    events=read_events(out/'emulator.log',kinds={'cpu'})
    entries={int(k):v for k,v in d['entries'].items()}
    def interval(sample):
        start=sample['start']+round((events[0][0]-sample['start'])/(1<<32))*(1<<32)
        return start,start+(sample['end']-sample['start'])%(1<<32)
    left,right=interval(ui['new_window'])
    dp=next(int(e[9],16) for t,e in events if left<=t<right and entries.get(int(e[4],16))=='desktop_new')
    spans,_=calls(events,{pc:n for pc,n in entries.items() if n in ('desktop_new','redraw')},set(d['returns']),dp)
    new=next(s for s in spans if s['kind']=='desktop_new' and left<=s['start']<s['end']<=right)
    paints=[s for s in spans if s['kind']=='redraw' and new['end']<=s['start']<s['end']<=right]
    require(len(paints)==1,'Expected one initial folder paint')
    paint=paints[0]
    ui['new_window']['service_to_initial_paint_ms']=(paint['end']-new['start'])*1000/BASE_HZ
    left,right=interval(ui['selector_open'])
    start,e=next((t,e) for t,e in events if left<=t<right and entries.get(int(e[4],16))=='fsel_exinput')
    dp=int(e[9],16)
    unlocked=max(t for t,e in events if start<=t<right and int(e[9],16)==dp and entries.get(int(e[4],16))=='UnLock')
    # The selector's first blocking AES event call follows completed scanning,
    # filtering, focus setup and fenced form paint. No helper delay is charged.
    ready=next(t for t,e in events if t>unlocked and int(e[9],16)==dp and entries.get(int(e[4],16))=='ExecAESEvents')
    ui['selector_open']['entry_to_usable_list_ms']=(ready-start)*1000/BASE_HZ
    if 'selector_cancel' in ui:
        left,right=interval(ui['selector_cancel'])
        serial=read_events(out/'emulator.log',kinds={'command','rxstart','receive'})
        ui['selector_cancel']['serial_events']=dict(Counter(e[0] for t,e in serial if left<=t<right))
        ui['selector_cancel']['physical_commands']=sum(e[0]=='command' and e[2]=='1' for t,e in serial if left<=t<right)
    ui.update(tier='development',qualification=False,partial_capture=partial,archive_sha256=sha256(out/'exec816-demo.zip'),
        completion='New Window service entry through first fenced redraw return; selector entry through first blocking AES event call after directory unlock.')
    (out/('ui-partial.json' if partial else 'ui-analysis.json')).write_text(json.dumps(ui,indent=2)+'\n')
    print(json.dumps(ui,indent=2),flush=True)


def main():
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    a.add_argument('--bundle',type=Path);a.add_argument('--media',type=Path);a.add_argument('--analyze',action='store_true')
    a.add_argument('--partial',action='store_true',help='Analyze completed New Window/open phases from a stopped capture')
    a.add_argument('--selector-only',action='store_true',help='Skip an already completed standalone Files phase')
    args=a.parse_args();out=args.output.resolve()
    if args.analyze:return analyze(out,args.partial)
    require(args.bundle and not out.exists(),'Supply bundle and fresh output')
    shutil.copytree(args.bundle.resolve(),out,ignore=shutil.ignore_patterns('extracted','*.log','*.bgra','*.png'))
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    d=setup(out)
    os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in sorted(set(d['returns'])|set(d['entries']))))
    integration=UI(bundle=out);integration.standalone=not args.selector_only
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',profile_commands=False,
        integration=integration,media_path=args.media.resolve() if args.media else None,
        measurement_commands=[],measurement_media_sha256=sha256(args.media) if args.media else None)
    (out/'ui-runtime.json').write_text(json.dumps(result,indent=2)+'\n')
    analyze(out)

if __name__=='__main__':main()
