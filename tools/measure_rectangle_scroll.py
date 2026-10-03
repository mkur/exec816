#!/usr/bin/env python3
"""Compare current console scrolling with one checked copy/fill list.

Only generated build inputs change. Public APIs, production limits and hardware
reads are untouched. Use separate processes/output directories for each run.
"""
import argparse
from contextlib import contextmanager
import json
from pathlib import Path
import shutil
from unittest.mock import patch

import build_bitmap_console
import generate_tasks
from native_program import ROOT, require, sha256


def replace_once(text, old, new):
    require(text.count(old)==1, 'Benchmark source boundary changed: '+old)
    return text.replace(old,new,1)


@contextmanager
def whole_rectangle(enabled):
    if not enabled:
        yield
        return
    require('rows=limit-view.scrollRow' in (ROOT/'lib/console/console-bitmap-display.inc').read_text(),
        'Historical synchronous experiment: reproduce from bb09a72 or replay its recorded image; current scrolling is asynchronous.')
    original_emit=build_bitmap_console.emit
    original_policy=generate_tasks.policy_modules
    original_drawing=build_bitmap_console.drawing
    overrides={}

    def emit(out,sources,*args,**kwargs):
        directory=Path(out).parent/'experiment'
        directory.mkdir(parents=True,exist_ok=True)
        sources=list(sources)
        for relative in ('platform/altirraos/vbxe.c','ports/gem4xe/adapter/gem-vbxe.c'):
            original=ROOT/relative
            text=original.read_text()
            if original.name=='vbxe.c':
                text+='\n'+(ROOT/'tests/programs/rectangle_scroll.inc.c').read_text()
            else:
                text=replace_once(text,'    status=VbxeOwnerCopyRect(&display,copy);',
                    '    status=BenchmarkRectangleScroll(&display,copy);')
                text=replace_once(text,'static struct VbxeDisplay display;',
                    'extern UWORD BenchmarkRectangleScroll(struct VbxeDisplay *,const struct VbxeCopy *);\n'
                    'static struct VbxeDisplay display;')
            target=directory/original.name
            target.write_text(text)
            sources[sources.index(original)]=target
            overrides[relative]=dict(original_sha256=sha256(original),
                generated=str(target.relative_to(ROOT)),generated_sha256=sha256(target))
        return original_emit(out,sources,*args,**kwargs)

    def policy(*args,**kwargs):
        directory=original_policy(*args,**kwargs)
        source=ROOT/'lib/console/console-bitmap-display.inc'
        text=source.read_text()
        text=replace_once(text,
            '    rows=limit-view.scrollRow\n    IF rows>16 THEN\n      rows=16\n    FI',
            '    rows=limit-view.scrollRow')
        text=replace_once(text,'  view.scrollRow==+rows',
            '  IF view.scrollState=1 THEN\n'
            '    ; The benchmark copy also cleared the exposed eight rows.\n'
            '    rows==+8\n    view.scrollState=2\n  FI\n\n'
            '  view.scrollRow==+rows')
        target=directory/'rectangle-scroll.inc'
        target.write_text(text)
        module=directory/'consoledisplay.act'
        module.write_text(replace_once(module.read_text(),str(source),str(target)))
        overrides[str(source.relative_to(ROOT))]=dict(original_sha256=sha256(source),
            generated=str(target.relative_to(ROOT)),generated_sha256=sha256(target))
        return directory

    def drawing(out,*args,**kwargs):
        foreign=original_drawing(out,*args,**kwargs)
        foreign['provenance']['rectangle_scroll_experiment']=dict(
            overrides=dict(overrides),fixture_sha256=sha256(ROOT/'tests/programs/rectangle_scroll.inc.c'),
            note='Whole upward rectangle plus eight-row fill; checked synchronous private two-record submission.')
        (Path(out)/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
        return foreign

    with patch.object(build_bitmap_console,'emit',emit), \
         patch.object(build_bitmap_console,'drawing',drawing), \
         patch.object(generate_tasks,'policy_modules',policy):
        yield overrides


def loaded_run(out,mode,replay,reuse=False,phase=None):
    """Reuse the eight-Task workload with an 80x24 producer and two 40x3 tiles.

    Physical keys arrive during sustained full-width output and real disk I/O.
    Capture/return traces report whether events overlapped a copy. Presentation
    markers are not scanout timestamps; this is not an exhaustive phase sweep.
    """
    source=out/'wide-fairness.act'
    text=(ROOT/'tests/programs/console_fairness.act').read_text()
    for old,new in (
        ('flood(20)','flood(80)'),('request.io_Length=20','request.io_Length=80'),
        ('request.io_Actual=20','request.io_Actual=80'),('floods<12','floods<24'),
        ('floods<16','floods<28'),('floods>=16','floods>=28'),
        ('first=CONSOLE.Create(20,12)','first=CONSOLE.Create(80,24)'),
        ('second=CONSOLE.Create(20,12)','second=CONSOLE.Create(40,3)'),
        ('third=CONSOLE.Create(40,12)','third=CONSOLE.Create(40,3)'),
        ('CONSOLE.Show(second,20,0)','CONSOLE.Show(second,0,24)'),
        ('CONSOLE.Show(third,0,12)','CONSOLE.Show(third,40,24)'),
        ('FOR index=0 TO 19 DO','FOR index=0 TO 79 DO')):
        text=replace_once(text,old,new)
    source.write_text(text)
    harness=(ROOT/'tools/test_console_fairness.py').read_text()
    harness=harness.replace("ROOT/'tests/programs/console_fairness.act'",f'Path({str(source)!r})')
    for old,new in (
        ("('first',0,0,20,12),('second',20,0,20,12),('third',0,12,40,12)",
         "('first',0,0,80,24),('second',0,24,40,3),('third',40,24,40,3)"),
        ("[(0,0,20,12),(20,0,20,12),(0,12,40,12)]",
         "[(0,0,80,24),(0,24,40,3),(40,24,40,3)]"),
        ("b'#'*220+b' '*20","b'#'*1840+b' '*80"),
        ("b' a'+b' '*174","b' a'+b' '*54"),
        ("b'z'+b' '*479","b'z'+b' '*119"),
        ('top==12','left==40'),
        ('    def routine(prefix):',
         "    foreign=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']\n"
         "    p['labels']['rectangle_copy']=foreign.get('GemDrawingScrollStart',foreign.get('GemDrawingCopy'))\n"
         '    def routine(prefix):'),
        ("    marks['sector_end']=sector_end_marker(p)",
         "    marks['rectangle_copy']=p['labels']['rectangle_copy']\n"
         "    marks['rectangle_done']=p['labels']['console_bitmap_done']\n"
         "    marks['sector_end']=sector_end_marker(p)"),
        ("        require(measured['verdict']=='pass','Bitmap SIO timing: '+str(measured['violations']))",
         "        # A benchmark records failed timing gates as well as successful measurements.\n"
         "        saved['benchmark_sio_verdict']=measured['verdict']")):
        harness=replace_once(harness,old,new)
    if phase is not None:
        from measure_async_scroll import instrument_loaded
        harness=instrument_loaded(harness,phase)
    generated=out/'wide-fairness.py'
    generated.write_text(harness)
    namespace={'__name__':'rectangle_fairness','__file__':str(generated)}
    exec(compile(harness,str(generated),'exec'),namespace)
    result=namespace['run'](out,mode,from_build=out/'program' if replay or reuse else None,
        bitmap=True,pointer=True,observe=not replay)
    result['benchmark_harness_sha256']=sha256(generated)
    if not replay and result['timing']['verdict']!='pass':
        result['status']='timing-fail'
    if not replay:
        from sio_transaction_trace import read_events,BASE_HZ
        marks=result['marks'];events=read_events(out/'trace.log')
        def times(name):
            return [t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
        captures=times('input_capture')
        require(len(captures)==4,'Expected Z, A, Return and BREAK')
        def delay(name,start):
            ends=times(name)
            require(len(ends)==1 and ends[0]>=start,'Missing input completion '+name)
            return (ends[0]-start)/BASE_HZ*1000
        active={};calls=[]
        for tick,event in events:
            if event[0]!='cpu':continue
            pc=int(event[4],16);dp=int(event[9],16)
            if pc==marks['rectangle_copy']:
                require(dp not in active,'Nested copy');active[dp]=tick
            elif pc==marks['rectangle_done'] and dp in active:
                start=active.pop(dp)
                calls.append(dict(start=start,end=tick,ms=(tick-start)/BASE_HZ*1000))
        require(calls and not active,'Incomplete loaded copy spans')
        result['input_latency']=dict(
            scope='Physical capture to fixture delivery/presentation-complete markers; not first scanout.',
            raw_key_delivery_ms=delay('third_collected',captures[0]),
            raw_key_presentation_ms=delay('third_visible',captures[0]),
            cooked_return_presentation_ms=delay('echo_visible',captures[2]),
            break_durable_ms=delay('break_durable',captures[3]),
            copies=len(calls),max_copy_elapsed_ms=max(c['ms'] for c in calls),
            captures_inside_copy=sum(any(c['start']<=t<=c['end'] for c in calls) for t in captures))
    return result


def run(out,variant,workload,mode,replay=False,reuse=False):
    out=out.resolve()
    out.mkdir(parents=True,exist_ok=True)
    with whole_rectangle(variant=='whole' and not (replay or reuse)) as overrides:
        if workload=='scroll':
            from test_console_bitmap_scroll import run as scroll
            scroll(out,mode,replay=replay or reuse,observe=not replay,performance=not replay)
            result=json.loads((out/('results-replay.json' if replay else 'results.json')).read_text())
        else:
            result=loaded_run(out,mode,replay,reuse)
            (out/('replay-results.json' if replay else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
        if not replay:
            if variant=='whole' and not overrides:
                foreign=json.loads((out/'c-image.json').read_text())
                overrides=foreign['provenance']['rectangle_scroll_experiment']['overrides']
                original=ROOT/'lib/console/console-bitmap-display.inc'
                target=out/'program/task-kernel/rectangle-scroll.inc'
                overrides[str(original.relative_to(ROOT))]=dict(original_sha256=sha256(original),
                    generated=str(target.relative_to(ROOT)),generated_sha256=sha256(target))
            report=dict(variant=variant,workload=workload,mode=mode,status=result['status'],
                fixture_only=True,production_changed=False,overrides=overrides or {},
                benchmark_sha256=sha256(Path(__file__)),xex_sha256=result['build']['xex_sha256'],
                bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
            if workload=='scroll':
                report['scrolls']=[s for s in result['performance']['stages'] if s['stage'] in (2,3,4,7)]
                report['operations']=[s for s in result['operations'] if s['kind']=='work' and s['stage'] in (2,3,4,7)]
            else:
                report['timing']=result['timing']
                report['mouse_timing']=result['mouse_timing']
                report['input_latency']=result['input_latency']
            (out/'benchmark.json').write_text(json.dumps(report,indent=2)+'\n')
            # The existing replay helpers reuse these log names. Keep the
            # observations that support the benchmark before a later replay.
            for name in ('emulator.log','trace.log'):
                if (out/name).exists():shutil.copyfile(out/name,out/('observed-'+name))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--variant',choices=('current','whole'),required=True)
    parser.add_argument('--workload',choices=('scroll','fairness'),default='scroll')
    parser.add_argument('--mode',choices=('raw','opt'),default='opt')
    parser.add_argument('--replay',action='store_true')
    parser.add_argument('--reuse',action='store_true',help='Measure an already built image again')
    args=parser.parse_args()
    run(args.output,args.variant,args.workload,args.mode,args.replay,args.reuse)
