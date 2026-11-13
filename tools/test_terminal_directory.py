#!/usr/bin/env python3
"""Run the real Terminal scenario with timer-free native directory observers."""
import argparse,json
from pathlib import Path
from native_program import require
from shell_inspect import address
from test_gem_terminal import _run


def run(directory,out):
    snapshots={}
    def checkpoint(label,b,p,report):
        base=address(p['image'],'directoryCounts')
        counts=[int.from_bytes(b.memdump(base+i*4,4),'little') for i in range(2)]
        require(counts[0]==counts[1],'Observers disagree at '+label)
        snapshots[label]=counts
        if label in ('quiet-end','output'):
            require(counts==snapshots['quiet-start'],'Read/output manufactured a directory hint')
        if label=='created':require(counts[0]>snapshots['output'][0],'Missing creation/READY hint')
        if label=='selected-first':require(counts[0]>snapshots['created'][0],'Missing silent selection hint')
        if label=='selected-second':require(counts[0]>snapshots['selected-first'][0],'Missing second selection hint')
        if label=='fallback':require(counts[0]>snapshots['selected-second'][0],'Missing retirement/fallback hint')
        report['directory_observers']=snapshots
    report=_run(directory,out,checkpoint=checkpoint)
    # Native completion checks require both watches to withdraw after quiescence.
    report['directory_observer_scope']='Two Task-owned watches, no timer; source creation/retirement/epoch reuse and activation while UPDATE held; stable reads/output; real shell creation/READY/select/fallback and shutdown.'
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--build',type=Path,required=True);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();run(args.build.resolve(),args.output.resolve())
