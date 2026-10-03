#!/usr/bin/env python3
"""Execute generic device services against explicit test-only residents."""
import adapter_state as adapter
from library_paths import read_source
import argparse
import json
import shutil
from pathlib import Path
from native_program import ROOT,build,command,compiler,execute,platform_files,read_build,require,sha256,verify_machine
from os_boundary import emulator
from test_banked import PIN
from test_cooperative import data
from test_heap_api import clean_ownership
from ports_budget import current


def context(bridge,t,output,optimize,variant,from_build=None):
    from test_banked import changed_image
    from generate_io import IMPLEMENTED
    from generate_tasks import ABI as tasks
    if from_build:
        shutil.copytree(from_build,output,dirs_exist_ok=True)
        program=read_build(output)
        require(program['build']['optimize']==optimize,'Context replay mode differs from retained build')
    else:
        program=build(t,ROOT/'tests/programs/io_context.act',output,optimize=optimize,tasks=True)
    mode,operation=variant.split(':');mode=int(mode)
    image=program['image'];base=0xe0000;item=0x70000
    labels=dict(ITEM=item,CHECKS=item+64,
                CALL=program['labels']['io_'+IMPLEMENTED[operation]],VARIANT=mode)
    (output/'context.cfg').write_text(f'MEMORY {{ RAM: start=${base:x},size=$1000,file=%O; }} SEGMENTS {{ PROBE: load=RAM,type=ro; }}\n')
    command(['ca65','-I',output,*[v for k,a in labels.items() for v in ('-D',f'{k}={a}')],'-o',output/'context.o',ROOT/'tests/programs/io_context.s'])
    command(['ld65','-C',output/'context.cfg','-o',output/'context.bin',output/'context.o'])
    image['segments'] += [dict(address=base,bytes=list((output/'context.bin').read_bytes()),writable=False,executable=True),
                          dict(address=item,bytes=[0]*80,writable=True,executable=False)]
    segment=next(s for s in image['segments'] if s['address']==image['entry'])
    segment['bytes'][:4]=[0x5c,*base.to_bytes(3,'little')];changed_image(program)
    runtime,_=execute(bridge,program,expected_status=4 if mode else 0,timeout=240,frame_limit=12000)
    from banked_test_memory import read
    snapshot=read(bridge,labels['CHECKS'],16,output)
    checks=[int.from_bytes(snapshot[i:i+2],'little') for i in range(0,16,2)]
    if mode:require(checks[7]==0,'Invalid context returned')
    else:require(checks[:4]==[0,7,tasks['constants']['PROFILE_TAG'],adapter.TASK0_DP] and checks[4]==checks[6] and
                 checks[5]&255==0x12 and checks[5]&0x3c00==0 and checks[7]==1,'I/O context: '+str(checks))
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,checks=checks,variant=variant,native_probe_sha256=sha256(output/'context.bin'))


def wait_fault(bridge,t,output,optimize,variant):
    program=build(t,ROOT/'tests/programs/io_wait_fault.act',output,optimize=optimize,tasks=True,io_test_device=True)
    image=program['image'];address=next(d['address'] for d in image['data'] if '_VARIANT_' in d['name'])
    runtime,_=execute(bridge,program,expected_status=4,before_run=lambda b:b.poke(address,variant),timeout=240,frame_limit=12000)
    require(data(bridge,image,'reached')==[0],'Invalid WaitIO/DoIO returned')
    require(data(bridge,image,'item')==data(bridge,image,'snapshot'),'Rejected wait changed request')
    clean_ownership(bridge,program,output)
    return dict(build=program['build'],runtime=runtime,variant=variant,unchanged_request=True)


def run_case(bridge,t,output,optimize,name,from_build=None):
    if ':' in name:return context(bridge,t,output,optimize,name,from_build)
    require(from_build is None,'Retained builds are supported only for native context overlays')
    if name.startswith('wait-fault-'):return wait_fault(bridge,t,output,optimize,int(name.rsplit('-',1)[1]))
    fixture='queues' if name.startswith('queues-publication-') else name
    probe=int(name.rsplit('-',1)[1]) if name.startswith('queues-publication-') else 0
    source=ROOT/'tests/programs'/('io_'+fixture+'.act')
    if name=='gap':
        output.mkdir(parents=True,exist_ok=True)
        text=read_source(ROOT/'lib/io/iocore.act').replace('USE EXEC','USE EXEC\nUSE IOGAP',1)
        text=text.replace('    bits=EXEC.Wait(', '    IOGAP.Release()\n    bits=EXEC.Wait(')
        (output/'iocore.act').write_text(text)
    program=build(t,source,output,optimize=optimize,tasks=True,io_test_device=name!='absent',policy_probe=probe,
                  image_data=[(0x4ffe0,bytes([0xa5])*64)] if name=='short' else [])
    try:runtime,_=execute(bridge,program,expected_status=4 if name=='short' else 0,timeout=240,frame_limit=12000)
    except Exception:
        print('Completed assertion count: '+str(data(bridge,program['image'],'checks',True)),flush=True)
        raise
    checks=data(bridge,program['image'],'checks',True)
    if name=='short':
        from banked_test_memory import read
        require(data(bridge,program['image'],'reached')==[0],'Short OpenDevice returned')
        expected=bytearray([0xa5]*64);expected[30:32]=bytes([16,0])
        require(read(bridge,0x4ffe0,64,output)==expected,'Short request tail/guards touched')
    else:require(checks==[{'lifetime':44,'handoff':4,'absent':2,'queues':32,'gap':1,'queued_handoff':5}[fixture]],'I/O assertions: '+str(checks))
    if name in ('handoff','queued_handoff'):
        end=program['labels']['io_send_io_end']-program['build']['task_storage']['BASE']-0x1000
        target=next(r['address'] for r in program['image']['routines'] if r['name'].startswith('M_IOCORE_SENDIO_'))
        require((output/'hosted.bin.signals').read_bytes()[end-4:end]==bytes([0x5c,*target.to_bytes(3,'little')]),
                'SendIO must tail-call its checked caller-context implementation')
    if probe:require(runtime['signal_nmi_checkpoints']>0,'Missing wait publication NMI')
    clean_ownership(bridge,program,output)
    extra={'caller_checkpoint_sha256':sha256(output/'iocore.act')} if name=='gap' else {}
    return dict(build=program['build'],runtime=runtime,checks=checks,**extra,
                native_helper_bytes=len((output/'hosted.bin.signals').read_bytes()))


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--compiler-dir',type=Path,required=True)
    p.add_argument('--bridge-dir',type=Path,default=ROOT/'build/altirra-irq-bridge')
    p.add_argument('--rom',type=Path,default=ROOT/'build/firmware/altirraos-816.rom')
    p.add_argument('--output',type=Path,default=ROOT/'build/io-services')
    p.add_argument('--suite',default='lifetime')
    p.add_argument('--case',choices=('raw','opt'))
    p.add_argument('--profile',choices=('1x','8x'),default='1x')
    p.add_argument('--from-build',type=Path,help='Reuse an unchanged kernel for native context overlays')
    a=p.parse_args();out=a.output.resolve();out.mkdir(parents=True,exist_ok=True)
    pin=PIN if a.profile=='1x' else json.loads((ROOT/'toolchain/altirra-signals-4m.json').read_text())
    t=compiler(a.compiler_dir);platform_files(a.bridge_dir,a.rom)
    paths=('abi/io.json','abi/tasks.json','lib/io/task-io.inc','lib/io/iocore.act','lib/io/io-call-types.inc',
           'lib/exec/taskpolicy.act','platform/altirraos/io.s','platform/altirraos/tasks.s',
           'tools/generate_io.py','tools/generate_tasks.py','tools/native_program.py','tools/test_io_services.py',
           'tests/programs/io_context.s','tests/programs/io-names.inc','tests/programs/ioprobe.act','tests/programs/iogap.act',*[f'tests/programs/io_{("queues" if name.startswith("queues-publication-") else "wait_fault" if name.startswith("wait-fault-") else name) if ":" not in name else "context"}.act' for name in a.suite.split(',')])
    report=dict(status='running',suite=a.suite,inputs={p:sha256(ROOT/p) for p in paths},
                bank_zero=current(),reservation_delta=dict(fixed_bank_zero=0,per_task_bank_zero=0,upper_resident_bytes=64),cases=[])
    try:
        with emulator(a.bridge_dir.resolve(),a.rom.resolve(),out,pin=pin) as bridge:
            report['platform']=pin
            report['machine']=verify_machine(bridge,a.rom,pin)
            for mode in ('raw','opt'):
                if a.case and mode!=a.case:continue
                for name in a.suite.split(','):
                    print('Running '+name+'-'+mode,flush=True)
                    case=run_case(bridge,t,out/(name+'-'+mode),mode=='opt',name,a.from_build)
                    report['cases'].append(dict(name=name+'-'+mode,status='pass',**case))
        report['status']='pass'
    except Exception as error:report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Passed '+str(len(report['cases']))+' I/O cases',flush=True)

if __name__=='__main__':main()
