#!/usr/bin/env python3
"""Retain key/deadline controls and reject a corrupted sector payload byte."""
import argparse,json
from pathlib import Path
from test_console_trace import run as existing_controls
from sio_transaction_trace import read_events
from console_concurrent_trace import analyze
from native_program import require,sha256


def run(probe,out):
    out.mkdir(parents=True,exist_ok=True)
    result=existing_controls(probe,out)
    source=json.loads((probe/'results.json').read_text())
    events=read_events(probe/'observed/trace.log')
    receives=[i for i,(_,e) in enumerate(events) if e[0]=='receive']
    require([int(events[i][1][2]) for i in receives[:2]]==[0x41,0x43],'Unexpected sector prefix')
    # The third received byte belongs to the first sector payload, after ACK/C.
    events[receives[2]][1][2]=str(int(events[receives[2]][1][2])^1)
    dest=out/'wrong-payload';dest.mkdir(exist_ok=True)
    trace=dest/'trace.log';trace.write_text(''.join('[SIOTXN] '+' '.join(e)+'\n' for _,e in events))
    checked=analyze(trace,source['marks'],probe/'observed/volume.atr',source['case']['sector_bytes'],0,source['case']['counters']['verified'])
    expected='wire bytes differ from original media'
    require(checked['verdict']=='fail' and expected in checked['violations'],'Corrupted payload escaped oracle')
    result['cases'].append(dict(name='wrong-payload',trace_sha256=sha256(trace),expected_violation=expected,violations=checked['violations']))
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--probe',type=Path,required=True);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    result=run(args.probe,args.output);(args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DOS stream timing negative controls passed')
