#!/usr/bin/env python3
"""Measure cold/warm commands on the unchanged standard shell/prime image."""
import argparse
import json
import shutil
from pathlib import Path

from dos_concurrent_trace import call_marker
from measure_loading_breakdown import packets, partition_packet
from measure_read_8k import observe
from native_program import ROOT, read_build, require, sha256
from sio_transaction_trace import BASE_HZ, read_events
from test_demo import run as run_demo


def run(bundle, output, replay=False):
    output.mkdir(parents=True,exist_ok=True)
    program = read_build(bundle)
    for label,prefix in [('dispatch','M_DEMO_SHELLDISPATCH_'),('relocate','M_PROGRAM_LOAD_')]:
        program['labels'][label] = next(r['address'] for r in program['image']['routines']
                                       if r['name'].startswith(prefix))
    command = call_marker(program,'M_DEMO_SHELLCOMMAND_','dispatch')
    relocate = call_marker(program,'M_PROGRAMFILE_LOAD_','relocate')
    marks = dict(command_begin=command,command_end=command+4,
                 relocate_begin=relocate,relocate_end=relocate+4)
    cases = []
    for blocks in (0,512):
        out = output/f'blocks-{blocks}'
        out.mkdir(exist_ok=True)
        print('Commands with cache blocks:',blocks,flush=True)
        if replay:
            shell = json.loads((out/'shell.json').read_text())
            require(shell['status']=='pass' and shell['xex_sha256']==program['build']['xex_sha256'] and
                    shell['bundle_manifest_sha256']==sha256(bundle/'demo-manifest.json') and
                    shell['runner_sha256']==sha256(ROOT/'tools/test_demo.py'), 'Stale shell observations')
        else:
            observe(marks)
            shell = run_demo(bundle,cache_smoke=True,cache_override=blocks,expected_cache=blocks)
            (out/'shell.json').write_text(json.dumps(shell,indent=2)+'\n')
            shutil.copyfile(bundle/'emulator.log',out/'emulator.log')
        events = read_events(out/'emulator.log')
        def stamps(name):
            return [t for t,e in events if e[0]=='cpu' and int(e[4],16)==marks[name]]
        starts,ends = stamps('command_begin'),stamps('command_end')
        # The passive PC observer also records EXIT after profiling stops.
        require(len(starts)==len(ends)==len(shell['cache_commands'])+1,'Incomplete command trace')
        require(not any(starts[-1]<=p['begin']<ends[-1] for p in packets(events)),
                'Unexpected disk request during EXIT')
        starts,ends = starts[:-1],ends[:-1]
        relocation = list(zip(stamps('relocate_begin'),stamps('relocate_end')))
        wire = packets(events)
        samples = []
        for index,(start,end,observed) in enumerate(zip(starts,ends,shell['cache_commands'])):
            rows = [partition_packet(packet) for packet in wire if start<=packet['begin']<end]
            require(start<end and (not rows or rows[-1]['end']<=end),'Incomplete command I/O')
            if blocks and index in (1,5,6,7,8):
                require(not rows,'Warm command unexpectedly missed cache: '+observed['command'])
            samples.append(dict(**observed,seconds=(end-start)/BASE_HZ,wire_reads=len(rows),
                relocate_seconds=sum(b-a for a,b in relocation if start<=a<b<=end)/BASE_HZ))
        # MEM can finish within the prime tile's display-update interval.
        commands = [s for s in samples if s['command']!='MEM']
        require(all(b['prime_frames']>a['prime_frames'] for a,b in zip(commands,commands[1:])),
                'Prime task did not progress between commands')
        result = dict(blocks=blocks,status='pass',samples=samples,shell=shell,
                      log_sha256=sha256(out/'emulator.log'))
        (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        cases.append(result)
        print(json.dumps(dict(blocks=blocks,samples=samples)),flush=True)
    record = dict(status='pass',cases=cases,build=program['build'],
                  bundle_manifest_sha256=sha256(bundle/'demo-manifest.json'),
                  harness_sha256=sha256(Path(__file__)),marks=marks,
                  boundary='ShellDispatch call through return, including load, execution and unload; '
                           'elapsed guest time, excluding typing, redirection setup, prompt rendering and debugger pauses. '
                           'Prime worker active; same XEX/media/configuration and a fresh boot per capacity.',
                  bank_zero_delta=dict(fixed=0,per_task=0))
    (output/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,default=ROOT/'build/demo')
    parser.add_argument('--output',type=Path,default=ROOT/'build/sector-cache/commands')
    parser.add_argument('--replay',action='store_true',help='Analyze retained checked shell runs without executing again')
    args = parser.parse_args()
    run(args.bundle.resolve(),args.output.resolve(),args.replay)
