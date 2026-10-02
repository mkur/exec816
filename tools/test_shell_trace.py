#!/usr/bin/env python3
"""Reject a missing key/command, delayed SERIN service and corrupted media byte."""
import argparse,copy,json
from pathlib import Path
from native_program import require,sha256
from sio_transaction_trace import read_events
from shell_concurrent_trace import analyze

def run(probe,out):
    out.mkdir(parents=True,exist_ok=True);r=json.loads((probe/'results.json').read_text())
    require(r['status']=='pass'and r['case']['speed']==0,'Controls need a passing FASTEST125 run')
    original=probe/'observed/trace.log';events=read_events(original);marks=r['marks']
    def marker(name):return next(i for i,(_,e)in enumerate(events)if e[0]=='cpu'and int(e[4],16)==marks[name])
    capture=marker('input_capture');command=marker('command_end')
    arrival=next(t for t,e in events if e[0]=='receive')
    index=next(i for i,(t,e)in enumerate(events)if e[0]=='read'and t>=arrival)
    delayed=list(events);_,fields=delayed.pop(index);fields=list(fields);fields[1]=str(arrival+141)
    at=next(i for i,(t,_)in enumerate(delayed)if t>=arrival+141);delayed.insert(at,(arrival+141,fields))
    wrong=copy.deepcopy(events);receives=[i for i,(_,e)in enumerate(wrong)if e[0]=='receive']
    require([int(wrong[i][1][2])for i in receives[:2]]==[0x41,0x43],'Wrong packet prefix')
    wrong[receives[2]][1][2]=str(int(wrong[receives[2]][1][2])^1)
    controls=[('missing-key',events[:capture]+events[capture+1:],'lost/duplicate key, read reply or visible echo'),
        ('missing-command',events[:command]+events[command+1:],'missing shell command completion'),
        ('late-rx',delayed,'RX physical byte deadline'),('wrong-payload',wrong,'wire bytes differ from original media')]
    results=[]
    for name,edited,expected in controls:
        target=out/name;target.mkdir(exist_ok=True);path=target/'trace.log';path.write_text(''.join('[SIOTXN] '+' '.join(e)+'\n'for _,e in edited))
        check=analyze(path,marks,probe/'observed/volume.atr',r['case']['sector_bytes'],0,r['case']['counters']['verified'])
        require(check['verdict']=='fail'and expected in check['violations'],'Corrupted observation accepted: '+name)
        results.append(dict(name=name,trace_sha256=sha256(path),expected_violation=expected,violations=check['violations']))
    return dict(status='pass',source_trace_sha256=sha256(original),cases=results,scope='Edited copies of passing observations; no new guest/hardware fault claim and no relaxed deadline.')
if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--probe',type=Path,required=True);a.add_argument('--output',type=Path,required=True);o=a.parse_args();r=run(o.probe,o.output);(o.output/'results.json').write_text(json.dumps(r,indent=2)+'\n');print('Shell trace negative controls passed',flush=True)
