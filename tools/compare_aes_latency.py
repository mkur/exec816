#!/usr/bin/env python3
"""Apply the frozen AS0 comparison limits to matched AS4 panel observations."""
import argparse
import json
from pathlib import Path
from native_program import ROOT, require, sha256


def compare(baseline, candidate, limits, loaded):
    rows=[]
    for load in ('idle','scroll','disk'):
        before=baseline['latency'][load];after=candidate['latency'][load]
        for metric in ('capture_to_button_consumed_ms','capture_to_button_pixels_ms',
                       'capture_to_visible_ms'):
            limit=(limits['input_consumption_p95_extra_ms']['loaded' if loaded or load!='idle' else 'idle']
                if metric=='capture_to_button_consumed_ms' else limits['scanout_p95_extra_ms'])
            a=before[metric]['p95_ms'];b=after[metric]['p95_ms']
            rows.append(dict(load=load,metric=metric,before=a,after=b,delta=b-a,
                             allowance=limit,pass_limit=b-a<=limit))
        a=baseline['work'][load]['max_quantum_cpu_ms']
        b=candidate['work'][load]['max_quantum_cpu_ms']
        limit=limits['render_quantum_cpu_growth_fraction']
        rows.append(dict(load=load,metric='max_render_quantum_cpu_fraction',before=a,
                         after=b,delta=b/a-1,allowance=limit,pass_limit=b<=a*(1+limit)))
    return dict(pass_limits=all(r['pass_limit'] for r in rows),rows=rows)


def pointer_compare(before,after,limits,loaded):
    rows=[]
    for metric in ('visible','button_consumption'):
        limit=(limits['scanout_p95_extra_ms'] if metric=='visible' else
               limits['input_consumption_p95_extra_ms']['loaded' if loaded else 'idle'])
        a=before[metric]['p95_ms'];b=after[metric]['p95_ms']
        rows.append(dict(metric=metric,before=a,after=b,delta=b-a,allowance=limit,pass_limit=b-a<=limit))
    return dict(pass_limits=all(r['pass_limit'] for r in rows),rows=rows)


def run(out,disabled,idle,loaded,pointers=None):
    paths=dict(disabled=disabled,idle=idle,loaded=loaded)
    records={name:json.loads(path.read_text()) for name,path in paths.items()}
    for r in records.values():
        require(r['status']=='pass' and r['ownership']=='restored','Incomplete panel run')
        require(r['count_per_load']==10 and r['feedback_observer'],'Unmatched observation scenario')
    frozen=json.loads((ROOT/'docs/development/aes-server-as0a.json').read_text())
    limits=frozen['comparison_contract'];native=frozen['native_baseline']
    baseline=dict(latency=native['panel_latency'],work=native['panel_work'])
    comparisons={}
    for name in records:
        comparisons['AS0_to_'+name]=compare(baseline,records[name],limits,name=='loaded')
        if name!='disabled':
            comparisons['matched_disabled_to_'+name]=compare(records['disabled'],records[name],limits,name=='loaded')
    if pointers:
        pointer_records={name:json.loads(path.read_text()) for name,path in pointers.items()}
        for name,record in pointer_records.items():
            require(record['status']=='pass' and len(record['samples'])==60,'Incomplete pointer run')
            require(record.get('graphical_keyboard',{}).get('keys')==1
                    and record['graphical_keyboard'].get('breaks')==1
                    and record.get('quiet_application_control'),
                    'Pointer comparison requires the matched AS0 raw-event fixture and quiet application')
            value=record['timing']['two_clients']
            comparisons['AS0_pointer_to_'+name]=pointer_compare(native['two_client_pointer'],value,limits,name=='loaded')
            if name!='disabled':
                comparisons['matched_pointer_to_'+name]=pointer_compare(pointer_records['disabled']['timing']['two_clients'],value,limits,name=='loaded')
            paths[name+'_pointer']=pointers[name]
    result=dict(status='pass' if all(v['pass_limits'] for v in comparisons.values()) else 'fail',
        tier='development',qualification=False,limits=limits,comparisons=comparisons,
        scope='Loaded allowance applies when either GEM clients or native scroll/disk work is active. Both frozen AS0 and matched AES-disabled comparisons are retained. Combined visibility includes the sequential label-observation upper bound.',
        artifacts={name:dict(path=str(path),sha256=sha256(path)) for name,path in paths.items()})
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(result,indent=2)+'\n')
    for name,comparison in comparisons.items():
        for row in comparison['rows']:
            if not row['pass_limit']:print(name,row.get('load','pointer'),row['metric'],round(row['delta'],3),'>',row['allowance'])
    require(result['status']=='pass','AS4 latency comparison limits exceeded; see '+str(out))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ('output','disabled','idle','loaded'):parser.add_argument('--'+name,type=Path,required=True)
    for name in ('disabled','idle','loaded'):parser.add_argument('--'+name+'-pointer',type=Path)
    args=parser.parse_args()
    pointers={name:getattr(args,name+'_pointer') for name in ('disabled','idle','loaded')}
    require(all(pointers.values()) or not any(pointers.values()),'Supply all three pointer comparisons')
    run(args.output,args.disabled,args.idle,args.loaded,pointers if all(pointers.values()) else None)
