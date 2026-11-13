#!/usr/bin/env python3
"""Derive bounded drawing input from a wide wait trace without changing capture."""
import argparse,json,statistics
from pathlib import Path
from native_program import require,sha256
from text_performance_trace import analyze


def run(out):
    record=json.loads((out/'results.json').read_text())
    definition=json.loads((out/'text-performance-markers.json').read_text())
    audit=json.loads((out/'wait-audit.json').read_text())
    original=out/'cpu-trace.log';raw_hash=sha256(original)
    require(audit['status']=='pass' and audit['trace_sha256']==raw_hash,'Unverified wait capture')
    require(sha256(out/'wait-observer.py')==definition['audit_observer_sha256'],'Changed capture observer')
    require(record['runtime']['status']==0 and record['runtime']['guards']=='intact' and record['heap_return'] and record['no_op'],
        'Incomplete functional capture')
    if record['status']!='pass':
        require(record.get('error')=='RuntimeError: Performance trace exceeded 256 MiB cap','Failure exceeds reader scope')
    delta=record['app']['base']-definition['reference']
    keep=set(definition['points'].values())|set(definition['scheduler']['points'].values())
    for pc,site in definition['shared'].items():keep.update((int(pc),site['end']))
    for pc,site in definition['local'].items():keep.update((int(pc)+delta,site['end']+delta))
    target=out/'drawing-audit';target.mkdir(exist_ok=True)
    retained=total=0;last=None;last_kept=False
    with original.open() as source,(target/'cpu-trace.log').open('w') as destination:
        for line in source:
            if line.startswith('[SIOTXN] anchor '):destination.write(line);continue
            if not line.startswith('[SIOTXN] cpu '):continue
            fields=line.split()[1:];pc=int(fields[4],16)
            # Preserve the original clock domain, prefix and final boundary too.
            last_kept=not total or pc in keep
            if last_kept:destination.write(line);retained+=1
            total+=1;last=line
        if last is not None and not last_kept:destination.write(last);retained+=1
    drawing=analyze(target,definition,record)
    # Scheduling/interrupt ownership must agree with the original full audit.
    cost={k:sum(row['mean_ms'] for row in audit['per_action'] if row['viewer_state']==state and (kind is None or row['kind']==kind))
        for k,state,kind in [('charged_cpu_ms','viewer','cpu'),('interrupt_ms','viewer','irq'),
            ('runnable_off_cpu_ms','runnable',None),('blocked_off_cpu_ms','blocked',None)]}
    for field,value in cost.items():
        require(abs(statistics.mean(r[field] for r in drawing['records'])-value)<1e-6,'Drawing budget differs from full trace: '+field)
    if record['status']=='pass':
        require(record['breakdown']['records']==drawing['records'],'Filtered drawing records differ')
    note=dict(status='pass',scope=__doc__,raw_trace_sha256=raw_hash,drawing_trace_sha256=sha256(target/'cpu-trace.log'),
        raw_rows=total,retained_rows=retained,kept_pc_count=len(keep),raw_bytes=original.stat().st_size,
        derived_bytes=(target/'cpu-trace.log').stat().st_size,budgets_match_full_audit=True,
        prior_result_sha256=sha256(out/'results.json'),capture_observer_sha256=definition['audit_observer_sha256'],
        tool_sha256=sha256(Path(__file__)))
    (target/'reanalysis.json').write_text(json.dumps(note,indent=2)+'\n')
    if record['status']!='pass':
        completed={**record,'status':'pass','breakdown':{**drawing,'audit':'wait-audit.json','viewer_dp':audit['viewer_dp']},
            'drawing_reanalysis':note}
        completed.pop('error',None)
        (out/'completed-results.json').write_text(json.dumps(completed,indent=2)+'\n')
    print('Drawing reanalysis:',retained,'/',total,'rows;',note['derived_bytes'],'bytes; budgets match',flush=True)
    return note


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    run(a.parse_args().output.resolve())
