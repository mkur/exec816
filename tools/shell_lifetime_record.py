#!/usr/bin/env python3
"""Collect shell failure, directory/stream lifetime and serial recovery evidence."""
from image_data_usage import used as image_data_used
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import historical,account,current
from test_shell_lifetime_suite import cases
NAMES={name for name,_ in cases(None,'raw')}

def guard(rt,status=0):
    require(rt['status']==status and rt['guards']=='intact','Unexpected native exit')
    require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0 and all(s['untouched_above_floor']>=0 for s in rt['stack_observations']),'Interrupt reserve used')

def validate(r,*,current_layout=False):
    budgets=current()['after'] if current_layout else historical()
    require(r['status']=='pass'and len(r['cases'])==26 and {(c['mode'],c['name'])for c in r['cases']}=={(m,n)for m in ('raw','opt')for n in NAMES},'Incomplete shell lifetime matrix')
    require(r['fixed_bank_zero_delta']==r['per_task_bank_zero_delta']==0,'Bank-zero growth')
    for c in r['cases']:
        name=c['name'];require(c['compiler_revision']==r['compiler']['revision']and not c['override']and c['bank_zero']==budgets['eight'],'Compiler/capacity changed')
        require(all(r['inputs'][p]==h for p,h in c['inputs'].items()),'Mixed production inputs')
        if name.startswith('serial'):
            require({x['name']for x in c['serial_cases']}=={'checksum','device','short','firstcause','framing','protocol'}and c['sector_size']==int(name[-3:]),'Missing real fault responder')
            require(c['shell_fixture_sha256'],'Missing serial fixture provenance')
            for x in c['serial_cases']:
                unsafe=x['name']not in ('checksum','device');guard(x['runtime'],0xff93 if unsafe else 0)
                state=x['runtime']['shell_cleanup'];require(state['directory_checked']and state['directory_released']and state['unsafe_retained']==unsafe,'Wrong fault lifecycle')
                require(bool(state['shell_pointer'])==unsafe and x['posts_baseline']==1 and x['cleanup_reached'],'Wrong retained shell or completion count')
            continue
        guard(c['runtime'],4 if name=='removal-guard'else 0)
        if name in ('basic-bank1','filesystem-first-bank3'):
            tags=[e['tag']for e in c['events']];require(tags==([1,1,1,2]if name=='basic-bank1'else [])+[0,3,4,5,6,7,8],'Missing allocation/directory failure')
            require(c['counts']['commands']==6 and c['hooks'],'Missing native command/hooks')
            for e in c['events'][-6:]:require(e['objects']==2 and e['directory']==1 and e['endpoint_references']==1 and not e['temporary_input']and not e['temporary_output'],'Directory failure leaked ownership')
            require([e['error']for e in c['events'][-6:]]==[103,202,202,103,103,213],'Saved command cause changed')
        elif name in ('restore-failure','close-failure'):
            a,b=c['events'][1:];require(a['tag']==9 and b['tag']==10 and {k:v for k,v in a.items()if k!='tag'}=={k:v for k,v in b.items()if k!='tag'},'Dispatch continued after fatal cleanup')
            require(a['status']==20 and a['done']==1 and a['objects']==3 and a['directory']==1,'Unsafe ownership released')
            require((a['error'],a['restore_failure'],a['temporary_input'],a['temporary_output'],a['output_console'])==((202,1,0,1,0)if name=='restore-failure'else(209,0,1,0,1)),'Cleanup overwrote first cause or defaults')
        elif name=='removal-guard':require(c['events'][0]['objects']==2 and c['events'][0]['directory']==1,'Removal lost live ownership')
        elif name.startswith('stream-'):
            require(c['checkpoints']==[1,2,6,5,3,4,3,3]and c['hooks']and c['fixture_sha256'],'Missing reply collection/race checkpoints')
            require(c['checks']['checks']>=144 and c['checks']['childChecks']>=3,'Missing race checks')
        elif name=='headless':require(c['observations']['checks']==40,'Incomplete independent directory clients')
        elif name=='reuse':require(c['checks']==[2081]and c['runtime']['created']==260,'Missing repeated Task admission/release')
        else:require(c['no_mount']and c['runtime']['created']==1 and c['commands']==['HELP','ECHO','CD','EXIT'],'Missing unmounted shell')

def collect(directory):
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),fixed_bank_zero_delta=0,per_task_bank_zero_delta=0,inputs={},cases=[],
        scope='Slice 7: real shell allocation/selector/close failures; independent directories through queued/collected RAW replies; headless/reuse/unmounted entry; real 128/256-byte serial fault responders with directory live during transfer and shell/RAW retained at unsafe SIO shutdown.')
    def runtime(rt):return {k:v for k,v in rt.items()if not isinstance(v,list)or k=='stack_observations'}
    for mode in ('raw','opt'):
        for name in sorted(NAMES):
            out=directory/mode/name;p=out/'results.json';c=json.loads(p.read_text());b=c['build'];require(c['status']=='pass','Failed '+name)
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs'],**c.get('source_inputs',{})}
            for path,h in inputs.items():require(sha256(ROOT/path)==h,'Changed lifetime input '+path);r['inputs'][path]=h
            im=json.loads((out/'program.a816.json').read_text());near=image_data_used(im,b['memory'])
            item={k:v for k,v in c.items()if k not in ('build','runtime','cases')}
            item.update(name=name,mode=mode,inputs=inputs,compiler_revision=b['revision'],override=b['override'],bank_zero=account(b['memory']),kernel_bank=b['memory']['constants']['KERNEL_BANK'],near_image_used=near,image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],source_sha256=b['source_sha256'],compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],generated=b['task_generated'],result_sha256=sha256(p))
            if 'runtime'in c:item['runtime']=runtime(c['runtime'])
            else:
                from test_sio_recovery import CASES as oracles
                from test_sio_device import PIN as serial_pin
                item['pin']=serial_pin if c['sector_size']==128 else json.loads((ROOT/'toolchain/altirra-sio-sectors.json').read_text())
                item['serial_cases']=[dict(x,runtime=runtime(x['runtime']),expected_error=oracles[x['name']][2],expected_offline=oracles[x['name']][3])for x in c['cases']]
            r['cases'].append(item)
    for path in ('tools/shell_lifetime_record.py','tools/test_shell_lifetime_suite.py','tools/test_shell_lifetime.py','tools/shell_stream_races.py','tools/shell_serial_recovery.py'):
        r['inputs'][path]=sha256(ROOT/path)
    validate(r,current_layout=True);return r
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('directory',type=Path);a.add_argument('--output',type=Path,required=True);o=a.parse_args();o.output.write_text(json.dumps(collect(o.directory),indent=2)+'\n')
