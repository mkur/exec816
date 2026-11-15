#!/usr/bin/env python3
"""Check matched-image Action!/C semaphore CPU gates from passive captures."""
import argparse
import json
from pathlib import Path
from native_program import require, sha256


def check(composition,native,capture,output):
    records=[json.loads(p.read_text()) for p in (composition,native,capture)]
    require(all(r['status']=='pass' for r in records),'Unsuccessful cost capture')
    before,after,c=records
    require(before['build']['image_sha256']==after['build']['image_sha256'],
            'Action! costs must use the same current image')
    result=dict(status='pass',tier='development',qualification=False,
        gate_minimum_saving_percent=25,samples_per_case=32,
        inputs={str(p):sha256(p) for p in (composition,native,capture)},cases=[])
    for batch,old,new in [('free','FreePairs','NativeFreePairs'),
                          ('recursive','RecursivePairs','NativeRecursivePairs')]:
        for language,a,b in [('Action!',before['timing']['batches'][old],after['timing']['batches'][new]),
                              ('C',c['timing']['ComposedPair'][batch],c['timing']['NativePair'][batch])]:
            require(len(a['samples'])==len(b['samples'])==32,'Wrong sample count')
            x,y=a['charged_cpu_ms']['median'],b['charged_cpu_ms']['median']
            require(y<=x*.75,'Semaphore cost gate failed: '+str((language,batch,x,y)))
            result['cases'].append(dict(language=language,batch=batch,composition_ms=x,native_ms=y,
                                         saving_percent=(1-y/x)*100))
    output.write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['cases'],indent=2))
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--composition',type=Path,required=True)
    p.add_argument('--native',type=Path,required=True)
    p.add_argument('--c',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    a=p.parse_args()
    check(a.composition,a.native,a.c,a.output)
