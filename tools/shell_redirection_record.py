#!/usr/bin/env python3
"""Collect shell redirection, parser and physical-entry qualification."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import account,current
from test_shell_redirection_suite import cases

def validate(r):
    require(r['status']=='pass'and len(r['cases'])==14 and {(c['mode'],c['name'])for c in r['cases']}=={(m,n)for m in ('raw','opt')for n,*_ in cases()},'Incomplete redirection matrix')
    require(r['shell_allocation']==1288 and r['fixed_bank_zero_delta']==r['per_task_bank_zero_delta']==0,'Shell budget changed')
    for c in r['cases']:
        rt=c['runtime'];require(rt['status']==0 and rt['guards']=='intact','Native failure')
        require(c['compiler_revision']==r['compiler']['revision']and not c['override']and c['bank_zero']==current()['after']['eight'],'Compiler/capacity changed')
        require(all(s['untouched_above_floor']>=0 for s in rt['stack_observations'])and rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0,'Interrupt reserve used')
        if c['name']=='physical':
            require(c['commands']==['TYPE <D1:TEXT.TXT >NIL:','CD TOOLS >NIL:','ECHO "<ok>"','EXIT >NIL:']and not c['no_mount'],'Missing physical command')
            require({'LESS','GREATER','SHIFT','RETURN'}<={s['key']for s in c['schedule']},'Missing physical operators')
        elif c['name']=='parser':require(len(c['parser_cases'])==35 and c['checks']>=150 and rt['created']==0,'Missing parser boundaries')
        else:
            require(c['writes_sha256']==c['expected_sha256']and len(c['writes_sha256'])==64,'Wrong actual DOS.Write buffers')
            require(c['counts']['executed']==len(c['commands'])and c['counts']['checks']>=9*len(c['commands'])+4,'Missing ownership checks')
            require(c['commands'][-1]['command']=='EXIT >NIL:'and c['commands'][-1]['done']==1,'Missing redirected exit')
            if c['scenario']=='large':require(c['commands'][0]['source_bytes']==70003 and c['commands'][0]['output_bytes']==69730,'Shortened full-file TYPE')
            if c['scenario']=='basic':
                require(len(c['commands'])==35 and {c['error']for c in c['commands']}=={0,115,205,206,209,212,214},'Missing syntax/open/command error')
            if c['scenario']=='fault-read':require(c['commands'][0]['error']==213 and c['commands'][1]['status']==0,'Read fault did not unwind/recover')
        require(all(r['inputs'][p]==h for p,h in c['inputs'].items()),'Mixed redirection inputs')

def collect(directory):
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),shell_allocation=1288,fixed_bank_zero_delta=0,per_task_bank_zero_delta=0,inputs={},cases=[],
        scope='Slice 6: complete parse before opens, borrowed-default restoration before close, actual DOS.Write attempts and diagnostics, selected directory persistence, clean request/port/endpoint ownership, full TYPE through shell syntax and shipped-entry physical keys.')
    for mode in ('raw','opt'):
        for name,*_ in cases():
            out=directory/mode/name;c=json.loads((out/'results.json').read_text());b=c['build']
            inputs={**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs'],**c['source_inputs']}
            for p,h in inputs.items():require(sha256(ROOT/p)==h,'Changed redirection input: '+p);r['inputs'][p]=h
            im=json.loads((out/'program.a816.json').read_text());near=sum(len(s['bytes'])for s in im['segments']if 0x8800<=s['address']<0x9000)+sum(s['size']for s in im['zero_fill']if 0x8800<=s['address']<0x9000)
            item={k:v for k,v in c.items()if k not in ('build','runtime','cases')}
            item.update(name=name,inputs=inputs,bank_zero=account(b['memory']),near_image_used=near,compiler_revision=b['revision'],override=b['override'],image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],compiler_binary_sha256=b['binary_sha256'],abi_sha256=b['abi_sha256'],generated=b['task_generated'],runtime={k:v for k,v in c['runtime'].items()if not isinstance(v,list)or k=='stack_observations'},result_sha256=sha256(out/'results.json'))
            if name=='parser':item['parser_cases']=c['cases']
            r['cases'].append(item)
    r['collector_sha256']=sha256(Path(__file__));validate(r);return r
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('directory',type=Path);a.add_argument('--output',type=Path,required=True);p=a.parse_args();p.output.write_text(json.dumps(collect(p.directory),indent=2)+'\n')
