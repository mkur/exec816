#!/usr/bin/env python3
"""Measure a quiet Terminal behind the viewer; separate from matched cohorts."""
import argparse,json
from pathlib import Path
from unittest.mock import patch
import trace_viewer_waits as audit
from native_program import require,sha256
from sio_transaction_trace import read_events,BASE_HZ
from text_performance_trace import extend_clock


def run(bundle,out):
    quiet={};original_pixels=audit.pixels
    def pixels(s,app,label):
        result=original_pixels(s,app,label)
        if label=='initial':
            s.frames(60)  # Drain startup and exposure hints before the interval.
            s.b.profile_start()
            s.b.profile_start=lambda:None  # Retain the quiet trace at cohort start.
            quiet['start']=s.b.eval_expr('@clk')
            s.frames(120)
            quiet['end']=s.b.eval_expr('@clk')
            after=audit.viewer_pixels(s,app,'quiet-after')
            require(after['sha256']==result['sha256'],'Quiet viewer pixels changed')
            quiet['pixels']=after['sha256']
        return result
    with patch.object(audit,'pixels',pixels):
        # These four actions retain the normal cleanup/heap/no-op/EXIT gates.
        # Their timings are not compared with the frozen eight-action cohorts.
        report=audit.run(bundle,out,2,None,True)
    definition=json.loads((out/'text-performance-markers.json').read_text())
    events=read_events(out/'cpu-trace.log',kinds={'cpu'})
    start=extend_clock(quiet['start'],events[0][0]);end=extend_clock(quiet['end'],start)
    term=next(t for t in report['audit_rosters'][0]['tasks'] if t.get('name')=='terminal')
    delta=term['image_base']-definition['terminal_reference']
    sites={int(pc)+delta:s for pc,s in definition['terminal_sites'].items()}
    counts=dict(session_queries=0,directory_scans=0,timer_arms=0)
    for tick,e in events:
        if not start<=tick<end or int(e[9],16)!=term['dp']:continue
        pc=int(e[4],16);site=sites.get(pc)
        if site and site['callee']=='exchange':counts['session_queries']+=1
        if site and site['callee']=='ExecConsoleView' and int(e[5],16)==9:counts['directory_scans']+=1
        if pc==definition['terminal_timer_send']:counts['timer_arms']+=1
    require(term['directory_watch'] and not any(counts.values()),'Quiet Terminal polled: '+str(counts))
    record=dict(status='pass',tier='development',qualification=False,
        milliseconds=(end-start)*1000/BASE_HZ,counts=counts,watch_live=True,pixels=quiet['pixels'],
        zip_sha256=report['zip_sha256'],trace_sha256=sha256(out/'cpu-trace.log'),
        observer_sha256=sha256(Path(__file__)),scope=__doc__)
    (out/'quiet-terminal.json').write_text(json.dumps(record,indent=2)+'\n')
    print('Quiet Terminal:',record['milliseconds'],'ms',counts,flush=True)
    return record


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--bundle',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();run(args.bundle.resolve(),args.output.resolve())
