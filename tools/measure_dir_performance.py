#!/usr/bin/env python3
"""Passive DIR timing on a selected optimized OF816 demo, with media-derived rows."""
import argparse
import json
import shutil
from pathlib import Path

from native_program import ROOT, read_build, require, sha256
from bitmap_console_performance import native_markers
from dos_concurrent_trace import call_marker, packet_marks, packet_observations
from make_sdfs_fixtures import Media
from measure_read_8k import observe
from sio_transaction_trace import read_events, BASE_HZ
from trace_command_io import call_intervals, stats
import test_demo

DEFAULT = ['DIR']*4 + ['DIR >NIL:']*3 + ['DIR SYS:C']*4 + ['DIR SYS:C >NIL:']*3


def markers(p):
    names = [('SHELLAPP_SHELLDIR','dir'), ('SHELLAPP_SHELLWRITE','write'),
             ('SDFSFILE_MEASURE','file_measure'), ('SDFSDIR_MEASURE','directory_measure'),
             ('SDFS_VALIDATEMAP','validate_map'), ('SDFS_CACHE','map_cache'),
             ('SDFSEXTENTS_LOOKUP','extent_lookup'), ('BLOCKCACHE_READ','cache_read'),
             ('BLOCKCACHE_COPY','cache_copy'), ('FSINFO_CLEAR','fib_clear'),
             ('CONSOLECORE_FEED','feed'), ('CONSOLECORE_FEEDBATCH','feed_batch'),
             ('CONSOLEBITMAP_TEXT','bitmap_text'), ('DOSCLIENT_CALL','dos_call')]
    routines = native_markers(p, names)
    points = {}
    for key, r in routines.items():
        points[key+'_entry'] = r['entry']
        for i, pc in enumerate(r['returns']): points[key+'_return_'+str(i)] = pc
    for name, prefix in [('lock','DOS_LOCK'), ('examine','DOS_EXAMINE'), ('exnext','DOS_EXNEXT')]:
        target = next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_'+prefix+'_'))
        q = {**p, 'labels': {**p['labels'], name: target}}
        points['dir_before_'+name] = call_marker(q, 'M_SHELLAPP_SHELLDIR_', name)
        points['dir_after_'+name] = points['dir_before_'+name]+4
    points.update(packet_marks(p))
    return dict(routines=routines, marks=points)


def listing(media, path):
    directory = media.word(25)
    for part in path.split('/'):
        if part:
            row = media.row(media.entry(directory, part))
            require(row[0]&32, 'Measurement path is not a directory')
            directory = int.from_bytes(row[1:3], 'little')
    _, sectors = media.chain(directory)
    data = b''.join(media.raw[media.at(s):media.at(s)+media.size] for s in sectors if s)
    length = int.from_bytes(data[3:6], 'little')
    rows = []
    for pos in range(23, length, 23):
        row = data[pos:pos+23]
        if not row[0]: break
        if row[0]&16: continue
        require(row[0]&0xc8 == 8, 'Invalid measurement fixture row')
        name = row[6:14].rstrip(b' ')
        ext = row[14:17].rstrip(b' ')
        if ext: name += b'.'+ext
        rows.append(name+b'/' if row[0]&32 else name+b' '+str(int.from_bytes(row[3:6],'little')).encode())
    return rows


def validator(bundle):
    manifest = json.loads((bundle/'demo-manifest.json').read_text())
    require(manifest['filesystem']=='sdfs', 'Measurement oracle requires SDFS media')
    media = Media((bundle/manifest['media']).read_bytes())
    width = 80 if manifest['bitmap'] else 40
    def validate(command, screen):
        if not command.upper().startswith('DIR') or '>' in command: return
        words = command.split()
        path = words[1].split(':',1)[-1] if len(words)>1 else ''
        rows = listing(media, path.upper())
        expected = b''.join(row.ljust(width,b' ') for row in rows)+b'> '
        require(expected in screen, 'DIR differs from media-derived listing: '+command)
    return validate


def analyze(bundle, record, definition):
    p = read_build(bundle)
    require(record['xex_sha256']==sha256(bundle/'program.xex'), 'Stale timing run')
    routines, points = definition['routines'], definition['marks']
    events = read_events(bundle/'emulator.log')
    cpus = [(t,e) for t,e in events if e[0]=='cpu']
    calls = call_intervals(cpus, points)
    entries, returns, active, spans = {}, {}, {}, []
    for name, r in routines.items():
        if not r['returns']: continue
        entries.setdefault(r['entry'],[]).append(name)
        for pc in r['returns']: returns.setdefault(pc,[]).append(name)
    for tick,e in cpus:
        pc, dp = int(e[4],16), int(e[9],16)
        for name in returns.get(pc,[]):
            key = (name,dp)
            if key in active:
                begin = active.pop(key)
                spans.append(dict(kind=name,dp=dp,begin=begin,end=tick,ms=(tick-begin)/BASE_HZ*1000))
        for name in entries.get(pc,[]):
            key = (name,dp)
            require(key not in active, 'Nested observation '+name)
            active[key] = tick
    failures = []
    _, packets = packet_observations(events,points,lambda ok,msg: failures.append(msg) if not ok else None)
    require(not failures, '; '.join(failures))
    windows = sorted((r for r in spans if r['kind']=='dir'),key=lambda r:r['begin'])
    commands = [m for m in record['measurements'] if m['command'].upper().startswith('DIR')]
    require(len(windows)==len(commands), 'Incomplete DIR observations')
    rows = []
    for w,m in zip(windows,commands):
        inside = [s for s in spans if w['begin']<=s['begin']<=s['end']<=w['end'] and s['kind']!='dir']
        writes = [s for s in inside if s['kind']=='write' and s['dp']==w['dp']]
        legacy = [c['begin'] for c in calls if c['site']=='dir_before_text' and w['begin']<=c['begin']<w['end']]
        first = writes[0]['begin'] if writes else (legacy[0] if legacy else None)
        row = dict(command=m['command'],total_ms=w['ms'],begin=w['begin'],end=w['end'],
                   cache_hits=m['cache_after']['hits']-m['cache_before']['hits'],
                   cache_misses=m['cache_after']['misses']-m['cache_before']['misses'],
                   physical_sio_commands=sum(1 for t,e in events if w['begin']<=t<=w['end'] and e[0]=='command' and e[2]=='1'),
                   output_writes=len(writes) if 'write' in routines else None,first_write_ms=(first-w['begin'])/BASE_HZ*1000 if first else None,
                   routines={name:stats([s['ms'] for s in inside if s['kind']==name]) for name in sorted({s['kind'] for s in inside})})
        for name in ('lock','examine','exnext'):
            values=[(c['end']-c['begin'])/BASE_HZ*1000 for c in calls if c['site']=='dir_before_'+name and w['begin']<=c['begin']<=c['end']<=w['end']]
            row[name]=stats(values)
        for name in ('bitmap_text','feed','feed_batch'):
            starts=[t for t,e in cpus if first is not None and first<=t<w['end'] and name in routines and int(e[4],16)==routines[name]['entry']]
            row['first_'+name+'_ms']=(starts[0]-w['begin'])/BASE_HZ*1000 if starts else None
        selected=[pkt for pkt in packets if pkt['dp']==w['dp'] and w['begin']<=pkt['submitted']<=pkt['collected']<=w['end']]
        row['packet_queue_ms']=sum(pkt['dispatched']-pkt['submitted'] for pkt in selected)/BASE_HZ*1000
        rows.append(row)
    return dict(tier='development',scope='Passive optimized native DIR entry through final RTL; includes preemption, excludes typing/dispatch/prompt. Routine times are inclusive. Drawing submission is not scanout.',
                compiler_revision=p['build']['revision'],source_inputs=p['build']['task_inputs'],
                image_sha256=sha256(bundle/'program.a816.json'),xex_sha256=sha256(bundle/'program.xex'),
                manifest_sha256=sha256(bundle/'demo-manifest.json'),log_sha256=sha256(bundle/'emulator.log'),
                rom=record['rom'],machine=record['machine'],rows=rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--analyze',action='store_true',help='Analyze an existing run.json and markers.json without executing')
    parser.add_argument('--command',action='append',help='Override command sequence; may be repeated')
    args = parser.parse_args(); out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    bundle = args.bundle.resolve()
    if not args.analyze:
        copy = out/'bundle'
        require(not copy.exists(), 'Choose a fresh measurement output')
        shutil.copytree(bundle,copy,symlinks=True,ignore=shutil.ignore_patterns('emulator.log','pixels-*'))
        bundle = copy
        p=read_build(bundle);require(p['build']['optimize'],'Timing requires optimized code')
        definition=markers(p);(out/'markers.json').write_text(json.dumps(definition,indent=2)+'\n')
        observe(definition['marks'])
        record=test_demo.run(bundle,boot_smoke=True,measurement_commands=args.command or DEFAULT,
                             profile_commands=True,measurement_validate=validator(bundle))
        (out/'run.json').write_text(json.dumps(record,indent=2)+'\n')
    else:
        record=json.loads((out/'run.json').read_text());definition=json.loads((out/'markers.json').read_text())
    result=analyze(bundle,record,definition)
    result['observer_sha256']=sha256(Path(__file__))
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    for r in result['rows']:
        print(r['command'],round(r['total_ms'],2),'ms',r['output_writes'],'writes',r['physical_sio_commands'],'SIO')

if __name__=='__main__': main()
