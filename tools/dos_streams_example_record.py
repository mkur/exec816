#!/usr/bin/env python3
"""Collect the shared resident DOS session and standalone headless NIL example."""
from image_data_usage import used as image_data_used
import argparse,json
from pathlib import Path
from native_program import ROOT,require,sha256
from ports_budget import account


def validate(r):
    require(r['status']=='pass' and len(r['cases'])==4 and
        {(c['mode'],c['nil']) for c in r['cases']}=={(m,n) for m in ('raw','opt') for n in (False,True)},'Incomplete example matrix')
    for c in r['cases']:
        rt=c['runtime']
        require(rt['status']==0 and rt['guards']=='intact','Failed example')
        require(rt['kernel_stack_observation']['interrupt_reserve_bytes_touched']==0 and
                all(s['untouched_above_floor']>=0 for s in rt['stack_observations']),'Example touched interrupt reserve')
        require(c['bank_zero']==r['baseline_bank_zero'],'Changed bank-zero reservation')
        require(c['compiler_revision']==r['compiler']['revision'] and not c['override'],'Wrong compiler')
        if c['nil']:
            require(c['counts']==dict(checks=6) and rt['created']==0,'NIL example needs a service')
        else:
            require(c['counts']==dict(typed=2,duringRead=1,redirected=2,verified=70003),'Incomplete session/large read')
            require(rt['created']==4,'Unexpected example worker')
            require([o['stage'] for o in c['observations']]==['ready-with-restored-defaults',
                'keyboard-wait-overlaps-file-read','disk-completed-while-parent-still-waits',
                'disk-message-before-next-key','final-display'],'Missing background output evidence')
            require(all(o['live']==5 and o['created']==4 for o in c['observations'][:3]),'Missing simultaneous example Tasks')
            require([(s['key'],s['state']) for s in c['schedule']]==[('A','down'),('A','up'),('Q','down'),('Q','up')],'Missing physical key schedule')
            require(all(o['cells_sha256'] and o['screen_sha256'] for o in c['observations'][3:]),'Missing display oracle')
    require(r['bank_zero_fixed_delta']==r['bank_zero_per_task_delta']==0,'Bank-zero growth')
    require({p['mode'] for p in r['packaged_examples']}=={'raw','opt'},'Resident entry point was not packaged in both modes')
    require(r['emulator_sha256']==r['platform_pin']['emulator']['sha256'],'Unpinned emulator')


def collect(out):
    pin=json.loads((ROOT/'toolchain/altirra-console.json').read_text())
    r=dict(schema_version=1,status='pass',compiler=json.loads((ROOT/'toolchain/actionc.json').read_text()),
        platform_pin=pin,emulator_sha256=sha256(ROOT/'build/console-bridge/AltirraBridgeServer'),
        baseline_bank_zero=json.loads((ROOT/'docs/qualification/dos-streams-raw.json').read_text())['baseline_bank_zero'],
        bank_zero_fixed_delta=0,bank_zero_per_task_delta=0,
        scope='Shared resident example Session executes through a bounded fixture, including borrowed redirection and real 70003-byte MyDOS Read; the headless NIL example executes unchanged.',inputs={},cases=[])
    for mode in ('raw','opt'):
        for nil in (False,True):
            path=out/(('nil-' if nil else '')+mode)/'results.json';v=json.loads(path.read_text());require(v['status']=='pass','Incomplete example')
            b=v['build']
            for name,digest in {**b['task_inputs'],**b['platform_inputs'],**b['banked_inputs'],**v['source_inputs']}.items():
                require(sha256(ROOT/name)==digest,'Changed example input: '+name);r['inputs'][name]=digest
            image=json.loads((path.parent/'program.a816.json').read_text())
            near=image_data_used(image,b['memory'])
            r['cases'].append(dict(mode=mode,nil=nil,compiler_revision=b['revision'],override=b['override'],
                image_sha256=b['image_sha256'],xex_sha256=b['xex_sha256'],runtime=v['runtime'],machine=v['machine'],
                bank_zero=account(b['memory']),near_image_used=near,counts=v['counts'],observations=v['observations'],schedule=v['schedule'],
                media_sha256=v['media_sha256'],limits=v['limits'],result_path=str(path.relative_to(ROOT)),result_sha256=sha256(path)))
    r['inputs']['tools/dos_streams_example_record.py']=sha256(ROOT/'tools/dos_streams_example_record.py')
    packages=json.loads((out/'packages.json').read_text())
    r['packaged_examples']=[dict(mode=p['mode'],source_sha256=p['build']['source_sha256'],
        image_sha256=p['build']['image_sha256'],xex_sha256=p['build']['xex_sha256']) for p in packages]
    require(all(p['source_sha256']==sha256(ROOT/'examples/dos-streams.act') for p in r['packaged_examples']), 'Wrong packaged example')
    validate(r);return r

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('directory',type=Path);a.add_argument('--output',type=Path,required=True);args=a.parse_args()
    require(not args.output.exists(),'Keep existing evidence');args.output.write_text(json.dumps(collect(args.directory.resolve()),indent=2)+'\n')
    print('Recorded passing DOS streams example')
