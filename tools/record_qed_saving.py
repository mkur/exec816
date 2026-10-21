#!/usr/bin/env python3
"""Freeze source-bound QED saving development evidence without rewriting history."""
import argparse,json,re
from pathlib import Path
from native_program import ROOT,require,sha256
from c_program import ABI

def record(slice_name,layout,cohorts,packages,host_log,destination):
    require(not destination.exists(),'Evidence is immutable: choose a new record')
    host=host_log.read_text()
    require(re.search(r'Ran \d+ tests.*\n\nOK(?: \(skipped=\d+\))?\s*$',host,re.S),
            'Missing passing host checks')
    data=dict(schema_version=1,slice=slice_name,tier='development',qualification=False,
        abi=ABI['version'],compiler_pin=json.loads((ROOT/'toolchain/actionc.json').read_text()),
        host_log=dict(path=str(host_log.relative_to(ROOT)),sha256=sha256(host_log)),
        cohorts=[],packages=[])
    def stamped(path):
        return dict(path=str(path.relative_to(ROOT)),sha256=sha256(path))
    if layout:
        info=json.loads((layout/'layout.json').read_text())
        frames=json.loads((layout/'stack-frames.json').read_text())
        require(info['image']['provenance']['analysis_only'] is False,'Analysis layout')
        data.update(layout=info['layout'],resident_provider=info['resident_provider'],
            executable=stamped(layout/'program.app'),layout_record=stamped(layout/'layout.json'),
            frames=frames,frame_record=stamped(layout/'stack-frames.json'))
    baseline=json.loads((ROOT/'build/qed-startup/qs4-failures/program/memory.json').read_text())
    for directory in cohorts:
        result=json.loads((directory/'results.json').read_text())
        require(result['status']=='pass' and result['tier']=='development','Failing cohort')
        require(result['build']['foreign_image']['c_program_provider']['abi']==ABI['version'],'Stale provider')
        memory=json.loads((directory/'program/memory.json').read_text())
        require(all(memory[k]==baseline[k] for k in ('regions','task_pools')),'Reservation amendment required')
        item=dict(result=stamped(directory/'results.json'),completed=result['completed'],
            checks=result['checks'],trace=stamped(directory/'emulator.log'),
            native=stamped(directory/'program/program.xex'),app=stamped(directory/'app/program.app'))
        minima=[v['headroom'] for v in result.get('stacks',{}).get('minima',[])
                if v.get('lifetime') and v['kind']!='async']
        if minima:item['minimum_headroom']=min(minima)
        data['cohorts'].append(item)
    for directory in packages:
        manifest=json.loads((directory/'demo-manifest.json').read_text())
        smoke=directory/('gem-desktop-results.json' if manifest.get('gem_desktop') else 'demo-results.json')
        result=json.loads(smoke.read_text())
        require(result['status']=='pass' and result['distribution_root'] and
            result['autoboot_frames']==249 and
            result['bundle_manifest_sha256']==sha256(directory/'demo-manifest.json'),
            'Missing matching exact-package smoke')
        data['packages'].append(dict(zip=stamped(directory/'exec816-demo.zip'),smoke=stamped(smoke)))
    data['bank_zero_delta']=dict(fixed=0,per_public_task=0,private_idle=0,
        basis='Complete regions and task_pools equal the retained QS4 map, including guards/alignment/slack')
    destination.write_text(json.dumps(data,indent=2)+'\n')
    return data

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--slice',required=True)
    p.add_argument('--layout',type=Path);p.add_argument('--cohort',type=Path,action='append',default=[])
    p.add_argument('--package',type=Path,action='append',default=[])
    p.add_argument('--host-log',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();record(a.slice,a.layout.resolve() if a.layout else None,
        [v.resolve() for v in a.cohort],[v.resolve() for v in a.package],a.host_log.resolve(),a.output.resolve())
