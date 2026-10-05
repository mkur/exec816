#!/usr/bin/env python3
"""Loaded asynchronous scroll phases with physical input and scanout sampling.

Uses the unchanged eight-Task fixture with an 80x24 producer. Frame samples
bound first correct scanout; they are not exact first-pixel timestamps.
"""
import argparse
import inspect
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import patch

import generate_tasks
from measure_rectangle_scroll import loaded_run,replace_once
from native_program import ROOT,require,sha256
from sio_transaction_trace import read_events,BASE_HZ


def measure_tiles(out,replay=False):
    """Exact pixels and scrolling in the production shell/prime tile geometry."""
    import bitmap_console_oracle as oracle
    import test_console_bitmap_scroll as fixture
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'tests/programs/console_bitmap_scroll.act'
    text=source.read_text()
    for a,b in (('Create(17,3)','Create(80,24)'),('Create(1,1)','Create(80,6)'),
                ('Show(first,5,7)','Show(first,0,0)'),('Show(second,30,12)','Show(second,0,24)'),
                ('Pattern(a,17,3,8)','Pattern(a,80,24,8)'),('Pattern(a,17,5,47)','Pattern(a,80,26,47)')):
        require(a in text,'Missing tile boundary '+a);text=text.replace(a,b)
    text=replace_once(text,'  Require(CONSOLE.Focus(second)<>0)',
        '  Require(CONSOLE.Focus(second)<>0)\n  Pattern(b,80,6,14)')
    target=out/'shell-prime-tiles.act';target.write_text(text)
    text=inspect.getsource(oracle.scroll_scenes)
    for a,b in (('Terminal(17,3)','Terminal(80,24)'),('Terminal(1,1)','Terminal(80,6)'),
                ('a,5,7','a,0,0'),('b,30,12','b,0,24'),('pattern(17,3,8)','pattern(80,24,8)'),
                ('pattern(17,5,47)','pattern(80,26,47)')):
        require(a in text,'Missing oracle tile boundary '+a);text=text.replace(a,b)
    text=replace_once(text,"    b.feed(b'X');snapshot(tiles)","    b.feed(pattern(80,6,14));b.feed(b'X');snapshot(tiles)")
    namespace=dict(vars(oracle));exec(compile(text,'shell_prime_oracle','exec'),namespace)
    original=fixture.build_bitmap
    with patch.object(fixture,'build_bitmap',lambda source,*a,**k:original(target,*a,**k)), \
         patch.object(oracle,'scroll_scenes',namespace['scroll_scenes']):
        fixture.run(out,'opt',replay=replay,observe=not replay,performance=not replay)
    if not replay:shutil.copyfile(out/'emulator.log',out/'observed-emulator.log')


def instrument_loaded(text,phase):
    hook='''        def scanout_key(key,started):
            if key not in ('Z','A'):return
            from gem_render_oracle import Raster,font_bytes,PALETTE,PENS
            from bitmap_console_oracle import Terminal
            left,top=(40,24) if key=='Z' else (25,25)
            raster=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
            terminal=Terminal(2,1);terminal.cells[0]=ord(key.lower());terminal.column=1
            terminal.paint(raster,left,top,key=='A')
            width=16 if key=='A' else 8
            packed=raster.packed();rgb=bytes((v&254)+(v>>7) for v in PALETTE)
            colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
            want=b''.join(colors[(packed[y*320+x//2]>>(4 if x%2==0 else 0))&15]
                for y in range(top*8,top*8+8) for x in range(left*8,left*8+width))
            row=dict(key=key,includes_caret=key=='A',**started,samples=[])
            for sample in range(40):
                frame=b.rawscreen(str(out/('input-'+key+'.bgra')))
                require((frame.width,frame.height)==(672,240),'Unexpected scanout geometry')
                raw=(out/('input-'+key+'.bgra')).read_bytes()
                actual=b''.join(raw[y*frame.stride+64+x*4:y*frame.stride+67+x*4]
                    for y in range(top*8,top*8+8) for x in range(left*8,left*8+width))
                row['samples'].append(dict(clock=b.eval_expr('@clk')&0xffffffff,
                    frame=b.eval_expr('@frame'),correct=actual==want))
                if actual==want:break
                frames(1)
            require(row['samples'][-1]['correct'],'Input never reached correct scanout')
            saved.setdefault('scanout',[]).append(row)

'''
    text=replace_once(text,"    marks['sector_end']=sector_end_marker(p)",
        "    from bitmap_console_performance import markers as drawing_markers\n"
        "    details=drawing_markers(p,json.loads((p['output'].parent/'c-image.json').read_text()),p['output'].parent/'drawing')\n"
        "    marks['rectangle_launch']=details.get('async_launch',details['launch'])['entry']\n"
        "    completion_marks={key:value for key,value in details.items() if key.startswith('completion_') or key in ('GemDrawingScrollStart','GemDrawingPoll','async_launch','launch','bitmap_complete')}\n"
        "    marks.update({key:value['entry'] for key,value in completion_marks.items()})\n"
        "    marks['rectangle_complete']=routine('M_CONSOLEDISPLAY_BITMAPCOMPLETE_')\n"
        "    marks['input_service']=routine('M_CONSOLEINPUT_SERVICE_')\n"
        "    marks['sector_end']=sector_end_marker(p)")
    text=replace_once(text,'        def press(key):',hook+'        def press(key):')
    text=replace_once(text,"            try:run_to(b,p['labels'][point],9000,180,condition)","            try:run_to(b,p['labels'][point],9000,45,condition)\n            except Exception:\n                print('Pending condition',condition,'state',[(n,b.eval_expr(f'db(${at(n):x})')) for n in ('phase','floods','smalls','smallRead','reads')],flush=True)\n                raise")
    text=replace_once(text,"                if stage<5:","                print('Async phase',stage,flush=True)\n                if stage<5:")
    text=replace_once(text,'            old=b.eval_expr(captured)',f'''            old=b.eval_expr(captured)
            print('Awaiting busy for',key,'clock',b.eval_expr('@clk'),flush=True)
            pending=next(d['address'] for d in p['image']['data'] if '_CONSOLEBITMAP_DRAWINGPENDING_' in d['name'])
            rendezvous(f'(db(${{pending:x}})!=0)&((db($d653)&3)!=0)',point='native_irq')
            print('Confirmed BUSY',key,flush=True)
            start=b.eval_expr('@clk')
            if {phase}:
                rendezvous(f'@clk>={{start+{phase}}}',point='native_irq')
            started=dict(key_down_clock=b.eval_expr('@clk')&0xffffffff,
                busy_at_key_down=bool(b.eval_expr('db($d653)&3')),phase_base_cycles={phase})''')
    text=replace_once(text,"            rendezvous(f'{captured}>{old}')",
        "            rendezvous(f'{captured}>{old}',point='native_irq')")
    text=replace_once(text,"            b._cmd_ok(f'KEY {key} up');frames(2)",
        "            b._cmd_ok(f'KEY {key} up')\n"
        "            if key=='Z':b.poke(at('gate'),1)\n"
        "            scanout_key(key,started)\n"
        "            if key not in ('Z','A'):frames(2)")
    # Releasing phase 2 at capture lets the client echo immediately. The next
    # phase still has its own gate; do not release that gate from phase 2.
    text=replace_once(text,"                b.poke(at('gate'),1)",
        "                if stage!=2:b.poke(at('gate'),1)")
    text=replace_once(text,"source_inputs={str(source.relative_to(ROOT))",
        "scanout=saved.get('scanout'),source_inputs={str(source.relative_to(ROOT))")
    return text


@contextmanager
def bounded_candidate(out,enabled):
    """Fixture-only 64-row copies, each followed by an eight-row fill.

    The next chunk replaces the previous exposed strip. It only reads lower
    rows, so that fill cannot destroy a future source. One list stays in flight.
    """
    if not enabled:
        yield
        return
    original=generate_tasks.policy_modules
    def policy(*args,**kwargs):
        directory=original(*args,**kwargs)
        source=ROOT/'lib/console/console-bitmap-display.inc'
        text=source.read_text()
        text=replace_once(text,
            '    okay=CONSOLEBITMAP.Scroll(view.left,view.top,view.width,view.height)',
            '    rows=view.height-1-(view.scrollRow RSH 3)\n'
            '    IF rows>8 THEN\n      rows=8\n    FI\n'
            '    bitmapRows=rows LSH 3\n'
            '    okay=CONSOLEBITMAP.Scroll(view.left,view.top+(view.scrollRow RSH 3),\n'
            '        view.width,rows+1)')
        text=replace_once(text,
            '          view.scrollRow=view.height LSH 3\n'
            '          CONSOLECORE.Clean(instance)\n'
            '          view.presentedGeneration=instance.generation',
            '          view.scrollRow==+bitmapRows\n'
            '          IF view.scrollRow<((view.height-1) LSH 3) THEN\n'
            '            view.scrollState=1\n'
            '          ELSE\n'
            '            view.scrollRow=view.height LSH 3\n'
            '            CONSOLECORE.Clean(instance)\n'
            '            view.presentedGeneration=instance.generation\n'
            '          FI')
        target=directory/'bounded-scroll.inc';target.write_text(text)
        module=directory/'consoledisplay.act'
        text=replace_once(module.read_text(),str(source),str(target))
        text=replace_once(text,'LONGCARD bitmapUnit,bitmapGeneration,bitmapModel',
            'LONGCARD bitmapUnit,bitmapGeneration,bitmapModel\nCARD bitmapRows')
        module.write_text(text)
        (out/'async-candidate.json').write_text(json.dumps(dict(copy_rows=64,
            production=False,source_sha256=sha256(source),generated_sha256=sha256(target),
            module_sha256=sha256(module)),indent=2)+'\n')
        return directory
    with patch.object(generate_tasks,'policy_modules',policy):yield


def run(out,phase,reuse=False,replay=False,bounded=False,profile_turns=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    with bounded_candidate(out,bounded and not (reuse or replay)):
        result=loaded_run(out,'opt',replay,reuse,phase,profile_turns)
    (out/('replay-workload.json' if replay else 'workload.json')).write_text(json.dumps(result,indent=2)+'\n')
    result['candidate']=json.loads((out/'async-candidate.json').read_text()) if (out/'async-candidate.json').exists() else None
    if not replay:
        if profile_turns:
            from console_turn_profile import analyze
            result['turn_profile']=analyze(out/'trace.log',result['turn_definition'],result['marks'])
        captures=[tick for tick,event in read_events(out/'trace.log')
            if event[0]=='cpu' and int(event[4],16)==result['marks']['input_capture']]
        require(len(captures)==4,'Missing physical captures')
        submitted=False;active=None;lists=[];services=[]
        for tick,event in read_events(out/'trace.log'):
            if event[0]!='cpu':continue
            pc=int(event[4],16)
            if pc==result['marks']['rectangle_copy']:submitted=True
            elif pc==result['marks']['rectangle_launch'] and submitted:
                require(active is None,'Overlapping async lists')
                active=tick;submitted=False
            elif pc==result['marks']['rectangle_complete'] and active is not None:
                lists.append(dict(start=active,end=tick,upper_ms=(tick-active)/BASE_HZ*1000))
                active=None
            elif pc==result['marks']['input_service']:services.append(tick)
        require(active is None and lists,'Missing async completion')
        services=[t for t in services if lists[0]['start']<=t<=lists[-1]['end']]
        from blitter_completion_trace import analyze as completion_analyze
        completion_marks={key:dict(entry=value,returns=[]) for key,value in result['marks'].items()
            if key.startswith('completion_') or key in ('GemDrawingScrollStart','GemDrawingPoll','async_launch','launch','bitmap_complete')}
        result['completion_timing']=completion_analyze(out/'trace.log',completion_marks)
        if 'async_launch' in completion_marks:
            completions=result['completion_timing']['scrolls']
            require(len(completions)==len(lists) and all(row['polls']==1 and row['waits']>=1
                    and row['irq'] is not None and row['expired'] is None
                    for row in completions), 'Loaded worker did not wait for one completion notification')
        result['async_timing']=dict(occupancy_scope='Launch to confirmed idle poll; upper bound, not exact BUSY edges.',
            lists=lists,max_occupancy_upper_ms=max(row['upper_ms'] for row in lists),
            captures_in_pending_interval=sum(any(row['start']<=t<=row['end'] for row in lists) for t in captures),
            input_service_gap_max_ms=max(b-a for a,b in zip(services,services[1:]))/BASE_HZ*1000)

        for row,index in zip(result['scanout'],(0,1)):
            capture=captures[index]
            for sample in row['samples']:
                tick=sample['clock']+round((capture-sample['clock'])/(1<<32))*(1<<32)
                sample['capture_ms']=(tick-capture)/BASE_HZ*1000
            row['first_correct_frame_upper_ms']=row['samples'][-1]['capture_ms']
            wrong=[s['capture_ms'] for s in row['samples'] if not s['correct']]
            row['last_incorrect_frame_ms']=max(wrong) if wrong else None
            row['target_40ms']='pass' if row['includes_caret'] and row['first_correct_frame_upper_ms']<=40 else (
                'fail' if wrong and max(wrong)>40 else 'unresolved')
        for name in ('trace.log','emulator.log'):
            shutil.copyfile(out/name,out/('observed-'+name))
    (out/('replay-results.json' if replay else 'results.json')).write_text(json.dumps(result,indent=2)+'\n')
    print('Async loaded measurement',result['status'],[(r['key'],r.get('first_correct_frame_upper_ms'),r.get('target_40ms')) for r in result.get('scanout',[])],flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--phase',type=int,default=0,choices=(0,3547,14188))
    p.add_argument('--reuse',action='store_true')
    p.add_argument('--replay',action='store_true')
    p.add_argument('--bounded',action='store_true',help='Fixture-only 64-row copy candidate')
    p.add_argument('--tiles',action='store_true',help='80x24 shell and 80x6 prime pixel/scroll scenes')
    p.add_argument('--profile-turns',action='store_true',help='Separate worker CPU, interrupt and off-CPU time')
    a=p.parse_args()
    if a.tiles:measure_tiles(a.output,a.replay)
    else:run(a.output,a.phase,a.reuse,a.replay,a.bounded,a.profile_turns)
