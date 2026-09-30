#!/usr/bin/env python3
"""Verify the parser fix preserves already-qualified native DOS packet bytes."""
import json
from native_program import ROOT,build,compiler,require,sha256

def run():
    t=compiler(ROOT/'build/actionc');cases=[]
    for mode in ('raw','opt'):
        record=json.loads((ROOT/'docs/qualification/dos-client.json').read_text())
        suite=next(s for s in record['suites'] if s['optimize']==(mode=='opt'))
        old=next(c for c in suite['cases'] if c['case']=='call')
        p=build(t,ROOT/'tests/programs/dos_client.act',ROOT/f'build/dos-slice4/compiler-replay-{mode}',optimize=mode=='opt',tasks=True,dos_test=True)
        require(p['build']['xex_sha256']==old['build']['xex_sha256'],'Parser update changed qualified DOS image')
        cases.append(dict(mode=mode,status='identical',xex_sha256=p['build']['xex_sha256'],previous_compiler=old['build']['revision'],compiler=t['revision']))
    return cases
if __name__=='__main__':
    cases=run();out=ROOT/'build/dos-slice4/compiler-replay.json';out.write_text(json.dumps(cases,indent=2)+'\n');print('Qualified DOS image bytes unchanged in both modes')
