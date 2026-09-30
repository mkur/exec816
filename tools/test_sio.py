#!/usr/bin/env python3
"""Qualify slice 1 only: two-context buffered SIO and native phase alarms."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil
import subprocess

from os_boundary import ROOT, require, sha256
from sio_transactions import PIN, build, run
from sio_transaction_trace import analyze


CASES=[('target',dict()),('target-phase-3',dict(phase=3)),
       ('target-phase-13',dict(phase=13)),('target-phase-31',dict(phase=31)),
       ('target-vbi-32',dict(vcount_phase=32)),('target-vbi-121',dict(vcount_phase=121)),
       ('target-vbi-125',dict(vcount_phase=125)),
       ('stock-810',dict(divisor=40,disk_mode='810')),
       ('none-happy',dict(divisor=40,disk_mode='happy1050',scenario=3)),
       ('silent',dict(scenario=1)),('nak',dict(scenario=2)),
       ('keyboard',dict(press_key=True)),('negative-rx-stall',dict(stall=1600))]


def budget():
    # Reserved extents, not just assembled/active bytes. Host inspection runs
    # after the SIO probe; include its full declared scratch capacities too.
    return dict(production_delta=dict(fixed_bank_zero=0,per_task_bank_zero=0),
        production_runtime_including_os=dict(tasks4=57968,tasks8=61536),
        production_loading_including_os=dict(tasks4=58560,tasks8=57232),
        diagnostic=dict(code=4096,state=256,preflight_snapshot=32,os_stack_with_guard=240,
                        contexts=2,per_context_dp_with_guards=288,
                        per_context_stack_with_guards=1568,bank_zero_during_probe=8336,
                        post_probe_inspection_code=1536,post_probe_inspection_buffer=8192,
                        bank_zero_with_inspection=18064,upper_buffer_reservations=3*256))


def qualify_case(name,options,output,observer,replay,rom):
    options=dict(options)
    disk_mode=options.pop('disk_mode','fastest');press_key=options.pop('press_key',False)
    program=build(output/'observed',**options)
    observed=run(program,observer,rom,True,disk_mode,press_key)
    timing=analyze(program['output']/'emulator.log',program['labels'],program['definitions'],PIN['limits'])
    negative=bool(options.get('stall'))
    require(timing['verdict']==('fail' if negative else 'pass'),f'{name}: timing {timing}')
    if negative:require(not observed['functional_pass'],'Stall failed to damage the expected byte stream')
    replay_output=output/'replay';replay_output.mkdir(parents=True,exist_ok=True)
    # Exactly the same XEX, not a separately assembled non-observer variant.
    replay_program={**program,'output':replay_output}
    repeated=run(replay_program,replay,rom,False,disk_mode,press_key)
    for field in ('definitions','xex_sha256','media_initial_sha256','snapshot','state',
                  'transactions','buffers','guards','functional_pass','stack_written_extent','state_sha256'):
        require(observed[field]==repeated[field],f'{name}: observer/replay differs: {field}')
    facts=dict(name=name,status='pass',negative_control=negative,definitions=program['definitions'],
               disk_mode=disk_mode,keyboard=press_key,timing=timing,
               code_bytes=program['code_bytes'],
               verified_machine=observed['machine'],
               verified_cpu=observed['verified_cpu'],state_sha256=observed['state_sha256'],
               state=observed['state'],transactions=observed['transactions'],
               functional_pass=observed['functional_pass'],guards=observed['guards'],
               stack_written_extent=observed['stack_written_extent'],
               xex_sha256=observed['xex_sha256'],media_initial_sha256=observed['media_initial_sha256'],
               write_only_snapshot=observed['snapshot'],
               buffer_sha256={k:hashlib.sha256(bytes.fromhex(v)).hexdigest()
                              for k,v in observed['buffers'].items()},
               replay=dict(status='identical',emulator_sha256=repeated['emulator_sha256']))
    (output/'qualification.json').write_text(json.dumps(facts,indent=2)+'\n')
    return facts


def validate_record(report):
    """A successful reply or a partial case run must not qualify the gate."""
    require(report['status']=='pass','Incomplete or failed SIO run')
    require({c['name'] for c in report['cases']}=={n for n,_ in CASES},'Incomplete SIO case coverage')
    require(len(report['cases'])==len(CASES),'Duplicate SIO cases')
    for case in report['cases']:
        negative=case['name']=='negative-rx-stall'
        require(case['negative_control']==negative,'Wrong negative-control designation')
        require(case['status']=='pass' and case['guards']=='pass','Failed SIO integrity checks')
        require(case['replay']['status']=='identical','Missing identical-image replay')
        require(case['functional_pass']!=negative,'Unexpected functional result')
        require(case['timing']['verdict']==('fail' if negative else 'pass'),'Unexpected timing verdict')
        require(('late SERIN read' in case['timing']['violations'])==negative,'Missing/extra RX failure')
        require(0<case['code_bytes']<=4096,'Probe exceeds reserved code capacity')


def assembler():
    result={}
    for tool in ('ca65','ld65'):
        path=shutil.which(tool)
        require(path is not None,'Missing '+tool)
        version=subprocess.run([path,'--version'],capture_output=True,text=True,check=True,timeout=10)
        result[tool]=dict(version=(version.stdout+version.stderr).strip(),sha256=sha256(Path(path)))
    return result


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,default=ROOT/'build/sio-transactions/qualification')
    p.add_argument('--observer-dir',type=Path,default=ROOT/'build/altirra-sio-observer')
    p.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--case',action='append')
    a=p.parse_args();output=a.output.resolve();output.mkdir(parents=True,exist_ok=True)
    names={name for name,_ in CASES}
    require(not a.case or set(a.case)<=names,'Unknown SIO case')
    selected=[(n,o) for n,o in CASES if not a.case or n in a.case]
    observer=json.loads((ROOT/'toolchain/altirra-sio-observer.json').read_text())
    require(sha256(ROOT/observer['patch'])==observer['patch_sha256'],'Observer patch changed')
    inputs=['probes/sio-transactions/probe.s','probes/sio-transactions/engine.inc',
            'probes/sio-transactions/probe.cfg','tools/sio_transactions.py',
            'tools/sio_transaction_trace.py','tools/test_sio.py','toolchain/altirra-sio-device.json',
            'toolchain/altirra-sio-observer.json','toolchain/patches/altirra-sio-observer.patch',
            'tools/os_boundary.py','tools/native_program.py','tools/banked_test_memory.py',
            'tools/test_signal_concurrency.py']
    report=dict(schema_version=1,status='running',created_utc=datetime.now(timezone.utc).isoformat(),
        scope='Slice 1 two-context assembly probe; no public device API or production driver',
        compiler=dict(kind='assembly; raw/optimized NIR not applicable',tools=assembler()),
        platform=PIN,observer=observer,selected_cases=[n for n,_ in selected],
        gate='not qualified',
        inputs={name:sha256(ROOT/name) for name in inputs},memory=budget(),cases=[])
    try:
        for name,options in selected:
            print('Running '+name+' (observed + identical-image replay)...',flush=True)
            facts=qualify_case(name,options,output/name,a.observer_dir.resolve(),a.bridge_dir.resolve(),a.rom.resolve())
            report['cases'].append(facts)
            t=facts['timing']
            print(f"{name}: {t['verdict']}; TX {t['tx_refill']['max_us']}, RX {t['rx_service']['max_us']} us",flush=True)
            (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        report['status']='pass'
        if len(selected)==len(CASES):
            validate_record(report)
            report['gate']='pass for the pinned two-context probe'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(output/'results.json').write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
