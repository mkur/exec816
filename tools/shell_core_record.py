#!/usr/bin/env python3
"""Collect emitted shell/parser, real keys/display and shipped-entry evidence."""
from image_data_usage import used as image_data_used
import argparse,json
from library_paths import record_input_paths
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import historical,account,current
CASES={'physical','parser','start-failure','entry','entry-no-mount','heap'}
STAGES={'startup','initial','quoted-echo','one','thirty-six','thirty-seven','back-to-thirty-six','max-line','max-command','overflow','tab','typeahead','input-loss-resync','exit'}

def validate(r,*,current_layout=False):
    budgets=current()['after'] if current_layout else historical()
    r=record_input_paths(r)
    require(r['status']=='pass' and len(r['cases'])==12,'Incomplete shell core')
    require({(c['mode'],c['name'])for c in r['cases']}=={(m,n)for m in ('raw','opt')for n in CASES},'Missing shell mode/case')
    require(r['shell_allocation']==1288 and r['shell_header']==128,'Shell buffer growth')
    require(r['fixed_bank_zero_delta']==r['per_task_bank_zero_delta']==0,'Bank-zero growth')
    for c in r['cases']:
        require(c['status']=='pass' and c['runtime']['status']==0 and c['runtime']['guards']=='intact','Native shell failure')
        require(c['compiler_revision']==r['compiler']['revision'] and not c['override'],'Compiler override')
        require(c['bank_zero']==budgets['eight'],'Wrong task/bank-zero budget')
        require(all(r['inputs'][p]==h for p,h in c['inputs'].items()),'Mixed shell sources')
        require(all(s['untouched_above_floor']>=0 for s in c['runtime']['stack_observations']),'Task interrupt reserve used')
        require(c['runtime']['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Kernel reserve used')
        if c['name']=='physical':
            require(not c['smoke'] and not c['no_mount'],'Incomplete physical run')
            require({o['stage']for o in c['observations']}==STAGES,'Missing physical editor/command/loss stage')
            startup=next(o for o in c['observations']if o['stage']=='startup')
            require((startup['created'],startup['live'])==(3,4) and c['runtime']['created']==3,'Unexpected public Task count')
            require(startup['shell_pointer']>=65536,'Shell state in bank zero')
            require(c['exact_writes'] and c['counts']['output_bytes']>30000 and c['writes_sha256'],'Missing exact output')
            require(next(o for o in c['observations']if o['stage']=='max-line')['length']==255,'Missing maximum line')
            keys={e['key']for e in c['schedule']if e['state']=='down'}
            require({'SHIFT','CTRL','BREAK','TAB','BACKSPACE','ASTERISK','GREATER','RETURN'}<=keys,'Missing physical control/syntax key')
        if c['name']=='parser':require(c['checks']==100 and len(c['parser_cases'])==32 and c['runtime']['created']==0,'Incomplete native parser/bounds')
        if c['name']=='start-failure':require(c['checks']==5 and c['runtime']['created']==0,'Incomplete startup unwind')
        if c['name']=='heap':
            require(c['checks']==8 and c['heap']['peakObjects']==3 and c['heap']['peakUsed']==c['heap']['baseline']-c['heap']['minimum'] and c['heap']['peakUsed']>=1288 and c['hook_sha256'],'Incomplete heap/CD peak')
        if c['name'].startswith('entry'):
            require(c['commands']==['HELP','ECHO','CD','EXIT'],'Shipped entry command missing')
            require(c['no_mount']==c['name'].endswith('no-mount'),'Wrong startup configuration')
            require(c['runtime']['created']==(1 if c['no_mount']else 3),'Entry created extra services')
            require(c['source_sha256']==r['inputs']['examples/shell/shell.act'],'Not the shipped shell entry')

def collect(directory):
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
           scope='Slice 4: shared shell core with exact writes and physical/retained display, parser/editor bounds, setup rollback and uninstrumented resident entry; foreground commands only.',
           shell_allocation=1288,shell_header=128,fixed_bank_zero_delta=0,per_task_bank_zero_delta=0,inputs={},cases=[])
    for mode in ('raw','opt'):
        for name in sorted(CASES):
            out=directory/mode/name;c=json.loads((out/'results.json').read_text());b=c['build']
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs'],**c['source_inputs']}
            for path,h in inputs.items():require(sha256(ROOT/path)==h,'Changed core input: '+path);r['inputs'][path]=h
            im=json.loads((out/'program.a816.json').read_text())
            near=image_data_used(im,b['memory'])
            result=dict(name=name,mode=mode,status=c['status'],compiler_revision=b['revision'],override=b['override'],compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],
                inputs=inputs,generated=b['task_generated'],image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],source_sha256=b['source_sha256'],
                bank_zero=account(b['memory']),near_image_used=near,runtime={k:v for k,v in c['runtime'].items()if not isinstance(v,list)or k=='stack_observations'},machine=c['machine'],
                result_sha256=sha256(out/'results.json'))
            for key in ('observations','schedule','commands','counts','no_mount','smoke','writes_sha256','checks','hook_sha256','fixture_sha256','limits','pin','media_sha256','heap','sample_scope'):
                if key in c:result[key]=c[key]
            if name=='physical':result['exact_writes']=True
            if name=='parser':result['parser_cases']=c['cases']
            r['cases'].append(result)
    for path in ('tools/shell_core_record.py','toolchain/altirra-shell-console.json','toolchain/patches/altirra-shell-keys.patch'):
        r['inputs'][path]=sha256(ROOT/path)
    validate(r,current_layout=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    a.output.write_text(json.dumps(collect(a.directory),indent=2)+'\n')
