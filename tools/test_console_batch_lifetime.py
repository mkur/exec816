#!/usr/bin/env python3
"""Exercise public cancellation/control at each retained batch phase."""
import argparse,json,shutil
from pathlib import Path
from test_console_bitmap_scroll import run


def check(out,mode,replay=False,phases=range(1,6)):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    reports=[]
    # Accumulation, submission, DMA, repaint and partial row: abort, hide/show, stale view,
    # focus and final close/Stop. Reuse one emitted image for all interleavings.
    for phase,action in [(p,a) for p in phases for a in range(6)]:
        run(out,mode,replay or bool(reports),batch=True,phase=phase,action=action)
        path=out/('results-replay.json' if replay or reports else 'results.json')
        report=json.loads(path.read_text());reports.append(report)
        shutil.copyfile(path,out/f'phase-{phase}-action-{action}.json')
    record=dict(status='pass',tier='development',mode=mode,build=reports[0]['build'],
        cases=[dict(phase=r['phase'],action=r['action'],runtime=r['runtime'],
                    observations=r['observations'],batch_launches=r['batch_launches']) for r in reports])
    (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--mode',choices=('raw','opt'),default='opt')
    p.add_argument('--replay',action='store_true')
    p.add_argument('--phases',type=int,nargs='+',choices=range(1,6),default=list(range(1,6)))
    a=p.parse_args();check(a.output,a.mode,a.replay,a.phases)
