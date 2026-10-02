#!/usr/bin/env python3
"""Retain portable B0 evidence; refuse mismatched observation/control images."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, require, sha256

NAMES=('one-character','eight-characters','32-characters','64-even','64-odd',
       '80x30-repaint','blank','dense','mixed','left-clipped','zero-ink',
       'full-screen-fill','eight-pixel-copy')


def baseline(text, replay, console, console_replay, output):
    paths=[p/'results.json' for p in (text,replay,console,console_replay)]
    runs=[json.loads(p.read_text()) for p in paths]
    require(all(r['status']=='pass' for r in runs),'Incomplete baseline')
    measured,control,terminal,terminal_control=runs
    require(measured['xex_sha256']==control['xex_sha256'],'Different graphics images')
    require(terminal['build']['xex_sha256']==terminal_control['build']['xex_sha256'],
            'Different console images')
    require(measured['observed'] and not control['observed'],'Missing observer/control separation')
    require(len(measured['cases'])==len(control['cases'])==len(measured['observation'])==26,
            'Incomplete graphics corpus')
    cases=[]
    for case,repeat,timing in zip(measured['cases'],control['cases'],measured['observation']):
        require(all(case[k]==repeat[k] for k in ('phase','kind','calls','glyphs','pixels_sha256')),
                'Replay pixels or workload differ')
        require(abs(case['ticks']-repeat['ticks'])<=1,'Timing replay changed by more than one tick')
        entries=timing['entries'];blits=entries.get('VbxeBlit',0);transfers=entries.get('transfer',0)
        require(transfers>=blits,'Inconsistent B0 transfer count')
        cases.append(dict(name=NAMES[case['kind']],**case,cycles=timing,
            replay_ticks=repeat['ticks'],bcb_count=blits,
            memac_bytes=blits*21+(transfers-blits)*4096))
    record=dict(slice='B0',status='development-pass',date='2026-10-03',
        scope='Optimized pinned production operations; 26 graphics and 8 console phases. '
              'No disk or mouse drawing. ST capture disabled/enabled. No performance acceptance claim.',
        commands=[f'python3 tools/test_gem_text.py --output {text.relative_to(ROOT)} --observe',
                  f'python3 tools/test_gem_text.py --output {replay.relative_to(ROOT)} --replay',
                  f'python3 tools/test_console_scroll.py --case opt --observe --output {console.relative_to(ROOT)}'],
        reports={str(p.relative_to(ROOT)):sha256(p) for p in paths},
        xex_sha256=measured['xex_sha256'],compiler={k:measured['build'][k] for k in ('revision','override','compiler_contract','binary_sha256','abi_sha256')},
        platform_inputs=measured['build']['platform_inputs'],task_inputs=measured['build']['task_inputs'],
        provenance=measured['foreign_provenance'],machine=measured['machine'],pin=measured['pin'],
        observation_inputs=measured['source_inputs'],cases=cases,
        clock_boundaries=dict(ticks='DisplayTicks before and after complete request loop, 20 ms resolution.',
            cycles='BenchmarkStart RTL entry through BenchmarkEnd RTL entry; includes request preparation, '
                   'IPC, dispatch, drawing, fences, IRQs and scheduling; excludes font/clear setup and scanout capture.',
            packet_construction='GemPrepare entry to GemSubmit entry, including argument copy and interruptions.',
            launch_to_confirmed_idle='Instruction after START write to first following idle return; '
                'includes lease check, polling and interruptions; upper bound, not pure hardware occupancy.',
            memac_bytes='Derived from observed production transfer entries: 21 bytes per B0 blit, '
                '4096 bytes for each clipped-stage read/write. Source hashes pin this inference.',
            visibility='Independent exact scanout checked after two raster boundaries outside the timed loop; '
                'does not measure first-visible input latency or claim a 2 ms hardware limit.'),
        text_console={k:terminal[k] for k in ('ticks_50hz','nominal_ms_per_scroll','observation','inputs')},
        stack_usage=measured['stack_usage'],bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0),
        reserved_bank_zero=56128,runtime_free_bank_zero=9408,
        targets=dict(input_to_visible_ms=40,eligible_scroll_fenced_ms=20,
                     scroll_visible='following frame',full_repaint_visible_ms=500),
        limits=['First-visible input latency and loaded SDFS workloads belong to B8.',
                'Per-task CPU time and exact blitter occupancy are not isolated by elapsed driver timings.',
                'Raw correctness is required for changed rendering slices; this performance baseline is optimized.'])
    output.write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('text','replay','console','console-replay','output'):
        p.add_argument('--'+name,type=Path,required=True)
    a=p.parse_args()
    baseline(*(getattr(a,k).resolve() for k in ('text','replay','console','console_replay','output')))
