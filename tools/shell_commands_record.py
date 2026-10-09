#!/usr/bin/env python3
"""Collect native command output, ownership, maps and full TYPE evidence."""
from image_data_usage import used as image_data_used
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import historical,account,current
from test_shell_commands_suite import cases

def validate(r,*,current_layout=False):
    budgets=current()['after'] if current_layout else historical()
    # The checked-in qualification record predates the bank-$01 reservation.
    names=[n if current_layout else n.replace('basic-bank2-','basic-bank1-') for n,*_ in cases()]
    expected={(m,n)for m in ('raw','opt')for n in names}
    require(r['status']=='pass'and {(c['mode'],c['name'])for c in r['cases']}==expected and len(r['cases'])==22,'Missing command matrix case')
    require(r['shell_allocation']==1288 and r['fixed_bank_zero_delta']==r['per_task_bank_zero_delta']==0,'Shell budget changed')
    require({c['mode']for c in r['entry_checks']}=={'raw','opt'}and all(c['runtime']['status']==0 and c['runtime']['guards']=='intact'for c in r['entry_checks']),'Missing shipped entry execution')
    for c in r['cases']:
        rt=c['runtime'];require(rt['native_nmi_count']<=30000,'Command completion frame bound exceeded')
        require(c['status']=='pass'and rt['status']==0 and rt['guards']=='intact','Command execution failed')
        require(c['bank_zero']==budgets['eight']and rt['created']==3,'Command capacity changed')
        require(c['compiler_revision']==r['compiler']['revision']and not c['override'],'Compiler override')
        require(all(s['untouched_above_floor']>=0 for s in rt['stack_observations'])and rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Interrupt reserve used')
        require(c['writes_sha256']==c['expected_sha256']and len(c['writes_sha256'])==64,'Actual Write output differs')
        require(all(r['production_inputs'][p]==h for p,h in c['production_inputs'].items()),'Mixed production sources')
        if c['scenario']=='basic':
            require(c['counts']['executed']==17 and c['counts']['checks']>=60,'Missing basic commands')
            require(c['memory']['memBefore']==c['memory']['memAfter']and c['memory']['memBefore'][0]-c['memory']['memDuring'][0]==520,'MEM query/allocation mismatch')
            require({x.get('source_bytes')for x in c['commands']} >= {0,259,511,512,513,777},'Missing TYPE boundaries')
            require([x['error']for x in c['commands'][:7]]==[0,0,0,0,212,205,212],'DIR/TYPE errors changed')
        elif c['scenario']=='large':
            x=c['commands'][0];require(x['source_bytes']==70003 and x['output_bytes']==69730 and c['counts']['captureCount']==69774,'Incomplete large TYPE')
        elif c['scenario']=='raw-text':
            x=c['commands'][0];require(x['source_bytes']==1025 and x['output_bytes']==1021 and len(c['observations'])==1,'Missing exact RAW conversion/display')
        else:
            x=c['commands'][0];require(x['status']==10 and x['error']==(213 if c['scenario']=='fault-read'else 210) and x['output_bytes']==(10 if c['scenario']=='fault-read'else 17),'Fault prefix/causal error changed')

def collect(directory):
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),shell_allocation=1288,fixed_bank_zero_delta=0,per_task_bank_zero_delta=0,production_inputs={},cases=[],
        scope='Slice 5: actual shared command Write buffers, full 70003-byte TYPE to selected NIL, bounded RAW conversion/display, directory metadata and error paths, public memory queries and balanced resources.',
        harness_revision_note='Original command harness uses capture C0000 and command E0000. Raw bank 3 uses D0000/F8000 to avoid its larger executable. Each generated hook/image is hashed; command semantics and production sources are identical. The long-running original optimized runner retained its loaded original module, recorded explicitly.')
    for mode in ('raw','opt'):
        for name,*_ in cases():
            out=directory/mode/name;c=json.loads((out/'results.json').read_text());b=c['build']
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs'],**{p:h for p,h in c['source_inputs'].items()if p.startswith('examples/')}}
            for p,h in inputs.items():require(sha256(ROOT/p)==h,'Production input changed: '+p);r['production_inputs'][p]=h
            im=json.loads((out/'program.a816.json').read_text())
            near=image_data_used(im,b['memory'])
            item={k:v for k,v in c.items()if k not in ('build','runtime')}
            item.update(name=name,production_inputs=inputs,bank_zero=account(b['memory']),near_image_used=near,compiler_revision=b['revision'],override=b['override'],compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],generated=b['task_generated'],runtime={k:v for k,v in c['runtime'].items()if not isinstance(v,list)or k=='stack_observations'},result_sha256=sha256(out/'results.json'))
            require(sha256(out/'writes.bin')==c['writes_sha256']and sha256(out/'expected.bin')==c['expected_sha256'],'Command artifacts changed')
            r['cases'].append(item)
    r['entry_checks']=[]
    for mode in ('raw','opt'):
        path=ROOT/'build/shell-commands-entry'/mode/'results.json';e=json.loads(path.read_text())
        require(all(sha256(ROOT/p)==h for p,h in e['source_inputs'].items()),'Shipped entry inputs changed')
        r['entry_checks'].append(dict(mode=mode,source_inputs=e['source_inputs'],image_sha256=e['build']['image_sha256'],xex_sha256=e['build']['xex_sha256'],runtime={k:v for k,v in e['runtime'].items()if not isinstance(v,list)or k=='stack_observations'},machine=e['machine'],pin=e['pin'],commands=e['commands'],result_sha256=sha256(path)))
    r['collector_sha256']=sha256(Path(__file__));validate(r,current_layout=True);return r
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('directory',type=Path);p.add_argument('--output',type=Path,required=True);a=p.parse_args();a.output.write_text(json.dumps(collect(a.directory),indent=2)+'\n')
