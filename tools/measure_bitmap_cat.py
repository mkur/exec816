#!/usr/bin/env python3
"""Trace the unchanged bitmap shell's CAT: cold, cached and cached to NIL:."""
import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import shutil

from bitmap_console_performance import markers as drawing_markers, native_markers
from console_turn_profile import markers as turn_markers, flat_markers, Timeline
from measure_loading_breakdown import packets, partition_packet
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_bitmap_package import stage
from test_demo import run as run_demo

COMMANDS = ['CAT LONG.TXT', 'CAT LONG.TXT', 'CAT LONG.TXT >NIL:']


def definitions(program, foreign, drawing):
    turns = turn_markers(program, foreign, drawing)
    spans = {**turns['spans'], **native_markers(program, [
        ('SHELLAPP_SHELLDISPATCH', 'command'), ('PROGRAMFILE_LOAD', 'load'),
        ('PROGRAM_LOAD', 'relocate'), ('DOSCALLS_READ', 'dos_read'),
        ('DOSCALLS_WRITE', 'dos_write'), ('DOSCLIENT_CALL', 'packet'),
        ('SDFSFILE_CONSUME', 'file_consume'), ('FSOPERATION_PUMP', 'fs_pump'),
        ('CONSOLEDISPLAY_BITMAPEDIT', 'bitmap_edit'),
        ('CONSOLEDISPLAY_BITMAPCOMPLETE', 'bitmap_complete'),
        ('CONSOLEBATCH_BEGIN', 'batch_begin'), ('CONSOLEBATCH_FEED', 'batch_feed'),
        ('CONSOLEBATCH_PUBLISH', 'batch_publish'),
        ('CONSOLECORE_EDITRETAINED', 'retained_edit'),
        ('CONSOLECORE_FEEDINTO', 'retained_feed'),
        ('CONSOLEDISPLAY_PRESENTBATCH', 'batch_paint')])}
    draws = drawing_markers(program, foreign, drawing)
    points = {**flat_markers(turns)}
    for name, item in {**draws, **spans}.items():
        points[name+'_entry'] = item['entry']
        for i, pc in enumerate(item['returns']):
            points[name+'_return_'+str(i)] = pc
    for name in ('fsworker_worker', 'siodriver_worker'):
        points[name] = next(r['address'] for r in program['image']['routines']
                            if r['name'].startswith('M_'+name.upper()+'_'))
    require(all(spans[n]['returns'] for n in ('command','dos_read','dos_write','load')),
            'Missing command/read/write/load return boundaries')
    # Derive value probes from this emitted image, without guest instrumentation.
    # The first Scroll predicate tests its row argument; Publish reads its
    # retained reason and optionally replaces zero with the caller's reason.
    import re
    def code(prefix):
        r=next(r for r in program['image']['routines'] if r['name'].startswith(prefix))
        s=next(s for s in program['image']['segments'] if s['address']<=r['address']<s['address']+len(s['bytes']))
        start=r['address']-s['address']
        return r['address'],bytes(s['bytes'][start:start+r['size']])
    base,body=code('M_CONSOLEBITMAP_SCROLL_')
    matches=list(re.finditer(b'\x1b\xa3.\xf0\x02',body,re.S))
    if 'batch_publish' in spans:
        require(len(matches)==1,'Unrecognized emitted Scroll row predicate')
        points['scroll_rows']=base+matches[0].start()+3
    if 'batch_publish' in spans:
        from generate_console import constants
        context=next(d['address'] for d in program['image']['data'] if d['name'].startswith('M_CONSOLEBATCH_BATCH_'))
        reason=(context+constants()['BATCH_REASON']).to_bytes(3,'little')
        base,body=code('M_CONSOLEBATCH_PUBLISH_')
        for name,opcode in (('reason_read',0xaf),('reason_write',0x8f)):
            needle=bytes([opcode])+reason
            require(body.count(needle)==1,'Unrecognized emitted batch reason access')
            points[name]=base+body.index(needle)+4
    return dict(turns=turns, spans=spans, draws=draws, points=points)


def timeline(events, definition):
    """Reuse the console profiler's IRQ frame/Task ownership convention."""
    points = definition['turns']['points']
    active, spans, boundaries = {}, [], defaultdict(list)
    for name, spec in definition['spans'].items():
        boundaries[spec['entry']].append((name, True))
        for pc in spec['returns']:
            boundaries[pc].append((name, False))
    owner = None
    frames, segments, task_names = [], [], {}
    previous, previous_cpu = events[0][0], None
    for tick, event in events:
        if event[0] != 'cpu':
            continue
        pc, dp = int(event[4],16), int(event[9],16)
        if tick > previous:
            segments.append((previous,tick,owner,bool(frames)))
        previous = tick
        if pc in (points['native_irq'],points['native_nmi']):
            frame = int(event[8],16)-9
            if not (frames and frames[-1] == frame and previous_cpu == event[4:]):
                frames.append(frame)
        elif pc == points['interrupt_schedule']:
            require(frames and frames.pop() == int(event[8],16), 'Unbalanced IRQ frame')
        elif pc == points['selected']:
            require(not frames, 'Task selected within interrupt')
            owner = dp
        if pc == points['turn']:
            task_names[dp] = 'console'
        for name in ('fsworker_worker','siodriver_worker'):
            if pc == definition['points'][name]:
                task_names[dp] = name.split('_')[0]
        for name, entering in boundaries[pc]:
            key = (name,dp)
            if entering:
                require(key not in active, 'Nested routine '+name)
                active[key] = tick
            elif key in active:
                spans.append(dict(kind=name,dp=dp,start=active.pop(key),end=tick,
                                  result=int(event[5],16)|(int(event[6],16)<<16)))
        previous_cpu = event[4:]
    # Workers can be suspended inside a call when the resident stop arrives.
    require(not frames, 'Trace ends within an interrupt')
    return segments, spans, task_names


def summarize(output):
    definition = json.loads((output/'markers.json').read_text())
    shell = json.loads((output/'shell.json').read_text())
    require(shell['status']=='pass' and shell['xex_sha256']==sha256(output/'program/program.xex')
            and shell['bundle_manifest_sha256']==sha256(output/'program/demo-manifest.json')
            and shell['runner_sha256']==sha256(ROOT/'tools/test_demo.py'), 'Stale measurement inputs')
    events = read_events(output/'program/emulator.log')
    segments, spans, task_names = timeline(events,definition)
    commands = sorted((s for s in spans if s['kind']=='command'),key=lambda s:s['start'])
    require(len(commands)==len(COMMANDS)+1,'Missing command or EXIT boundaries')
    root = commands[0]['dp'];task_names[root]='shell'
    task_names[definition['turns']['task_dps'][-1]]='idle'
    for span in spans:
        if span['kind']=='dos_read' and span['dp']!=root:
            task_names[span['dp']]='cat'
    timers = {dp:Timeline(segments,dp) for dp in {s[2] for s in segments}}
    transactions = [partition_packet(p) for p in packets(events)
                    if commands[0]['start']<=p['begin']<commands[-1]['end']]
    from blitter_completion_trace import analyze_events as completion_events
    scrolls = completion_events(events,definition['draws'])['scrolls']
    values=defaultdict(list)
    for tick,event in events:
        if event[0]=='cpu':
            for name in ('scroll_rows','reason_read','reason_write'):
                if int(event[4],16)==definition['points'].get(name):
                    values[name].append((tick,int(event[5],16)))
    batches=[]
    for end in (s for s in spans if s['kind']=='batch_publish'):
        begin=max((s for s in spans if s['kind']=='batch_begin' and s['result']&255==1 and s['end']<=end['start']),key=lambda s:s['end'])
        feeds=[s for s in spans if s['kind']=='batch_feed' and begin['end']<=s['start']<=s['end']<=end['start']]
        reasons=sorted((t,v&255) for n in ('reason_read','reason_write') for t,v in values[n] if end['start']<=t<=end['end'])
        require(reasons and reasons[-1][1]>0,'Missing batch flush reason')
        batches.append(dict(start=begin['start'],end=end['end'],bytes=sum(s['result']&65535 for s in feeds),turns=len(feeds),
            rows=sum(1 for s in spans if s['kind']=='retained_edit' and begin['end']<=s['start']<=s['end']<=end['start']),reason=reasons[-1][1]))
    results=[]
    for index,(command,observed) in enumerate(zip(commands, shell['measurements'])):
        a,b=command['start'],command['end']
        rows=[s for s in spans if a<=s['start']<=s['end']<=b]
        wire=[p for p in transactions if a<=p['begin']<b]
        task_cpu=defaultdict(float)
        irq=0
        for start,end,dp,interrupt in segments:
            length=max(0,min(b,end)-max(a,start))/BASE_HZ*1000
            if interrupt:irq+=length
            else:task_cpu[task_names.get(dp,f'dp_{dp}')]+=length
        routines={}
        for name in definition['spans']:
            selected=[s for s in rows if s['kind']==name]
            if selected:
                charges=[timers[s['dp']].measure(s['start'],s['end']) for s in selected]
                routines[name]=dict(calls=len(selected),elapsed_ms=sum(c['elapsed_ms'] for c in charges),
                    charged_ms=sum(c['charged_cpu_ms'] for c in charges),
                    off_cpu_ms=sum(c['off_cpu_ms'] for c in charges),
                    interrupt_ms=sum(c['interrupt_ms'] for c in charges))
        cat_reads=[s for s in rows if s['kind']=='dos_read' and s['dp']!=root]
        cat_writes=[s for s in rows if s['kind']=='dos_write' and s['dp']!=root]
        cat_dp={s['dp'] for s in cat_reads}
        require(len(cat_dp)==1,'Missing unique CAT Task')
        require(sum(s['result'] for s in cat_reads)==23872,'CAT did not read the complete file')
        require(sum(s['result'] for s in cat_writes)==23872,'CAT did not forward the complete file')
        elapsed=(b-a)/BASE_HZ*1000
        require(abs(sum(task_cpu.values())+irq-elapsed)<1e-6,'CPU partition does not add up')
        scroll_rows=[s for s in scrolls if a<=s['start']<=s['adopt_begin']<=b]
        def total(items):return sum(s['end']-s['start'] for s in items)/BASE_HZ*1000
        def phase_cpu(items):
            charges={task_names.get(dp,str(dp)):sum(t.measure(s['start'],s['end'])['charged_cpu_ms']
                for s in items) for dp,t in timers.items() if dp is not None}
            charges['native_interrupts']=total(items)-sum(charges.values())
            return charges
        item=dict(command=observed['command'],case=('cold','warm','warm-nil')[index],
            elapsed_ms=elapsed,bytes_per_second=23872/(elapsed/1000),
            cat_read_ms=total(cat_reads),cat_write_ms=total(cat_writes),
            cat_reads=len(cat_reads),cat_writes=len(cat_writes),
            cat_read_cpu_ms=phase_cpu(cat_reads),cat_write_cpu_ms=phase_cpu(cat_writes),
            wire_reads=len(wire),wire_ms=sum(p['end']-p['begin'] for p in wire)/BASE_HZ*1000,
            task_cpu_ms=dict(task_cpu),native_interrupt_ms=irq,routines=routines,
            cache=observed,scrolls=len(scroll_rows),
            scroll_launch_to_adoption_ms=sum(s['launch_to_adoption_upper_ms'] for s in scroll_rows),
            scroll_launch_to_irq_ms=sum(s['launch_to_irq_observation_upper_ms'] or 0 for s in scroll_rows),
            scroll_post_to_adoption_ms=sum(s['post_to_adoption_ms'] or 0 for s in scroll_rows))
        console_parts=('collect','input','control','arrival','take','read','write','present','poll','advance','runnable')
        item['console_cpu_parts_ms']={n:routines[n]['charged_ms'] for n in console_parts if n in routines}
        item['console_cpu_parts_ms']['loop_and_gateway_remainder']=task_cpu['console']-sum(item['console_cpu_parts_ms'].values())
        require(item['console_cpu_parts_ms']['loop_and_gateway_remainder']>=0,'Overlapping console partitions')
        item['wire_parts_ms']={n:sum(p['parts_ms'][n] for p in wire) for n in (wire[0]['parts_ms'] if wire else [])}
        counts=defaultdict(int)
        for tick,rows in values['scroll_rows']:
            if a<=tick<=b:counts[rows]+=1
        require(sum(counts.values())==len(scroll_rows),'Scroll row probes and completion count differ')
        item['scroll_rows_distribution']=dict(counts)
        item['logical_scrolls']=sum(n*count for n,count in counts.items())
        item['copy_bytes']=sum((30-n)*2560*count for n,count in counts.items())
        item['fill_bytes']=item['logical_scrolls']*2560
        selected=[v for v in batches if a<=v['start']<=v['end']<=b]
        from collections import Counter
        item['batches']=dict(count=len(selected),rows=dict(Counter(v['rows'] for v in selected)),
            flush_reasons=dict(Counter(v['reason'] for v in selected)),
            max_bytes=max((v['bytes'] for v in selected),default=0),max_turns=max((v['turns'] for v in selected),default=0))
        require(item['batches']['max_bytes']<=256 and item['batches']['max_turns']<=4,'Batch bound exceeded')
        if 'settled_clock' in observed:
            settled=observed['settled_clock']
            settled+=round((b-settled)/(1<<32))*(1<<32)
            require(settled>=b,'Settled sample precedes command return')
            item['command_to_settled_prompt_upper_ms']=(settled-a)/BASE_HZ*1000
        prompt=min((s for s in spans if s['kind']=='dos_write' and s['dp']==root
                    and s['start']>=b and s['result']==2),key=lambda s:s['start'])
        item['command_through_next_prompt_write_return_ms']=(prompt['end']-a)/BASE_HZ*1000
        results.append(item)
    require(results[1]['wire_reads']==results[2]['wire_reads']==0,'Warm command unexpectedly accessed disk')
    record=dict(status='pass',tier='development',samples=results,
        boundary='ShellDispatch entry through return: includes command loading, execution and unload; '
                 'excludes typing, redirection setup and subsequent prompt rendering. Outstanding asynchronous '
                 'echo presentation may overlap the boundary. Guest cycles exclude debugger pauses.',
        accounting='Task CPU columns plus global native IRQ/NMI are disjoint. Routine totals include nested '
                   'calls and must not be added to one another. Read/Write intervals include suspension. '
                   'Scroll launch-to-IRQ is an upper bound on hardware completion, not exact BUSY time.',
        shell=shell,trace_sha256=sha256(output/'program/emulator.log'),
        harness_sha256=sha256(Path(__file__)),
        source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in (
            ROOT/'tools/test_demo.py',ROOT/'tools/console_turn_profile.py',
            ROOT/'tools/bitmap_console_performance.py',ROOT/'tools/blitter_completion_trace.py',
            ROOT/'tools/measure_loading_breakdown.py',ROOT/'tools/sio_transaction_trace.py')},
        reserved_bank_zero_delta=dict(fixed=0,per_task=0))
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    print(json.dumps(results,indent=2),flush=True)
    return record


def stage_bundle(bundle,output):
    output.mkdir(parents=True,exist_ok=True)
    program_dir=stage(bundle,output/'program',bundle/'program.xex',bundle/'system.atr')
    shutil.copyfile(bundle/'hosted.bin',program_dir/'hosted.bin')
    boot_dir=program_dir/'of816';boot_dir.mkdir(exist_ok=True)
    boot=json.loads((bundle/'of816/of816.json').read_text())
    for name in ('Exec-of816.xex','system.atr','altirraos-816.rom','ALTIRRAOS-LICENSE.txt','OF816-LICENSE.txt'):
        shutil.copyfile(bundle/'of816'/name,boot_dir/name)
    boot['exec_build']=str(program_dir)
    boot['media']['manifest_sha256']=sha256(program_dir/'demo-manifest.json')
    (boot_dir/'of816.json').write_text(json.dumps(boot,indent=2)+'\n')
    return program_dir


def input_summary(output):
    definition=json.loads((output/'markers.json').read_text())
    events=read_events(output/'program/emulator.log')
    _,spans,_=timeline(events,definition)
    captures=[t for t,e in events if e[0]=='cpu' and int(e[4],16)==definition['points']['key_capture']]
    keys='ECHO A\nEXIT\n'
    require(len(captures)==len(keys),'Missing unloaded physical key captures')
    rows=[]
    for index,(key,start) in enumerate(zip(keys,captures)):
        end=captures[index+1] if index+1<len(captures) else float('inf')
        feed=min((s for s in spans if s['kind']=='feed' and start<=s['start']<s['end']<end),key=lambda s:s['start'])
        present=min((s for s in spans if s['kind']=='present' and feed['end']<=s['start']<s['end']<end),key=lambda s:s['start'])
        read=min((s for s in spans if s['kind']=='read' and start<=s['start']<s['end']<=feed['start']),key=lambda s:s['start'])
        rows.append(dict(key=repr(key),capture_to_read_return_ms=(read['end']-start)/BASE_HZ*1000,
            capture_to_echo_draw_ms=(present['end']-start)/BASE_HZ*1000,
            feed_to_draw_ms=(present['end']-feed['start'])/BASE_HZ*1000))
    result=dict(status='pass',tier='development',keys=rows,
        scope='Physical ECHO A and EXIT. Capture IRQ to first echo presentation return: drawing completion, not scanout or key-down time.',
        xex_sha256=sha256(output/'program/program.xex'),trace_sha256=sha256(output/'program/emulator.log'))
    (output/'input-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


def run(bundle,output,commands=None,analyze=True):
    program_dir=stage_bundle(bundle,output)
    program=read_build(program_dir)
    foreign=json.loads((bundle/'bitmap-console/c-image.json').read_text())
    definition=definitions(program,foreign,bundle/'bitmap-console/drawing')
    definition['points']['key_capture']=program['labels']['input_capture']
    (output/'markers.json').write_text(json.dumps(definition,indent=2)+'\n')
    env=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS','EXEC816_MASK_TRACE')
    previous={n:os.environ.get(n) for n in env}
    try:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in sorted(set(definition['points'].values())))
        os.environ.pop('EXEC816_MASK_TRACE',None)
        shell=run_demo(program_dir,boot_smoke=True,measurement_commands=commands or COMMANDS)
        (output/'shell.json').write_text(json.dumps(shell,indent=2)+'\n')
    finally:
        for name,value in previous.items():
            if value is None:os.environ.pop(name,None)
            else:os.environ[name]=value
    return summarize(output) if analyze else shell


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/demo-bitmap-shell')
    parser.add_argument('--output',type=Path,default=ROOT/'build/cat-long-trace')
    parser.add_argument('--analyze-only',action='store_true')
    parser.add_argument('--input-only',action='store_true',help='Measure physical unloaded ECHO A and EXIT instead of CAT')
    args=parser.parse_args()
    if args.input_only:
        if not args.analyze_only:run(args.bundle.resolve(),args.output.resolve(),['ECHO A'],False)
        input_summary(args.output.resolve())
    elif args.analyze_only:summarize(args.output.resolve())
    else:run(args.bundle.resolve(),args.output.resolve())
