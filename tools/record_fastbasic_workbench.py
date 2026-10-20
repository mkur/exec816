#!/usr/bin/env python3
"""Record passing workbench development slices without rewriting old evidence."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from native_program import ROOT,sha256,require

SOURCES={
    'WB0':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h')]+[
        'tests/programs/basic_lifecycle.act','tests/programs/basic_lifecycle.c',
        'tools/test_fastbasic_workbench.py','tools/test_basic_workbench_baseline.py',
        'tools/build_demo.py','tools/build_gem_desktop.py','tools/gem_applications.py','tools/gem_desktop_oracle.py'],
    'WB1':['examples/gem-basic/document.c','examples/gem-basic/document.h',
        'tests/programs/basic_document.c','tools/test_fastbasic_document.py'],
    'WB3':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor.h','document.c','document.h','files.c','files.h','file-ui.c','file-ui.h')]+[
        'tests/programs/basic_files.c','tests/programs/basic_file_ui.c','tests/programs/basic_files_interaction.act',
        'tests/programs/basic_interaction.act','tools/test_fastbasic_files.py','tools/test_fastbasic_file_ui.py',
        'tools/workbench_files_interaction.py','tools/workbench_interaction.py','tools/build_demo.py','tools/build_gem_desktop.py','c/calypsi/file-list.c','c/calypsi/aes-alert.c'],
    'WB2':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor.h','document.c','document.h')]+[
        'tests/programs/basic_editor.c','tests/programs/basic_editor_layout.c','tests/programs/basic_interaction.act',
        'tests/programs/basic_maximum.c','tools/test_fastbasic_editor.py','tools/workbench_interaction.py',
        'tools/build_demo.py','tools/build_gem_desktop.py'],
}


def record(slice,paths,staged=False):
    def identity(name):
        if staged:
            raw=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
            return hashlib.sha256(raw).hexdigest()
        return sha256(ROOT/name)
    inputs={n:identity(n) for n in SOURCES[slice]}
    cases=[]
    for path in paths:
        path=path.resolve();r=json.loads(path.read_text());require(r.get('status')=='pass','Failed evidence: '+str(path))
        case=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),status='pass')
        for key in ('checks','completed','machine','stack_usage','integration','runtime','free_upper_words','cases','latencies','peer_progress'):
            if key in r:
                if key=='runtime':
                    case[key]={k:r[key][k] for k in ('status','guards','native_nmi_count','native_irq_count',
                        'stack_observations','kernel_stack_observation') if k in r[key]}
                else:case[key]=r[key]
        cases.append(case)
    result=dict(format='exec816-fastbasic-workbench-slice-v1',slice=slice,status='pass',
        tier='development',qualification=False,date='2026-10-20',
        base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_inputs=inputs,pins={n:sha256(ROOT/n) for n in ('toolchain/actionc.json','ports/fastbasic/upstream.json',
            'abi/fastbasic.json','abi/c-program.json','toolchain/altirra-gem-vdi.json','toolchain/altirra-shell-paced.json')},
        evidence=cases,reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0,
            includes='Guards, alignment and unused capacity; existing Task pools and 544-byte guest pool retained'))
    if slice=='WB0':
        baseline_path=ROOT/'build/fastbasic-fp-demo/graphical/build.json'
        build_path=ROOT/'build/fastbasic-workbench/wb0-demo/build.json'
        baseline=json.loads(baseline_path.read_text())['memory']['bank_zero_budget']
        current=json.loads(build_path.read_text())['memory']['bank_zero_budget']
        require(current==baseline,'Changed complete reserved bank-zero budget')
        result['memory_map']=dict(baseline=str(baseline_path.relative_to(ROOT)),baseline_sha256=sha256(baseline_path),
            build=str(build_path.relative_to(ROOT)),build_sha256=sha256(build_path),bank_zero_budget=current)
        app=json.loads((ROOT/'build/fastbasic-workbench/wb0/app/app.json').read_text())
        for name,digest in app['inputs'].items():
            require(inputs[str(Path(name).relative_to(ROOT))]==digest,'APP/staged input differs: '+name)
        result['application']={k:app[k] for k in ('bytes','sha256','span','verified_banks','abi')}
        result['image_backing']=dict(requested=app['span']+65535,rounded=(app['span']+65542)//8*8,
            alignment=65536,metadata_bytes=72)
        result['capacity']=dict(public_tasks=8,normal_startup=6,IDE=1,sequential_child=1,
            guest_slots=2,AES_clients=4,windows=6,consoles=4,
            control='Close extra graphical applications or a second Shell before Run; startup is unchanged')
        result['parent_desktop_warming']=dict(bytes=368,resolved_path=256,timer_records=112,
            lifetime='Existing live desktop context; freed with context/endpoint retirement')
        result['fastbasic_compilers']=json.loads((ROOT/'build/fastbasic/build.json').read_text())['compilers']
    elif slice=='WB3':
        path=ROOT/'build/fastbasic-workbench/wb3-physical/app/app.json'
        app=json.loads(path.read_text())
        for name,digest in app['inputs'].items():
            require(inputs[str(Path(name).relative_to(ROOT))]==digest,'APP/staged WB3 source differs: '+name)
        result['application']=dict(record=str(path.relative_to(ROOT)),record_sha256=sha256(path),
            sha256=app['sha256'],bytes=app['bytes'],span=app['span'],verified_banks=app['verified_banks'])
        result['file_contract']=dict(path_bytes=127,transfer_unit=1024,temporary='exclusive same-directory 8.3',
            publication='no-replace rename; old target backup before replacement; not atomic',
            close='consumed on success or failure; complete/uncertain copies retained and reported')
        result['fixture_task_pools']='Three native holding/peer clients keep the APP in an existing large application pool; no stack reservation changes'
    elif slice=='WB2':
        applications={}
        for mode,directory in [('optimized','wb2-physical/app'),('raw','wb2-raw-layout')]:
            path=ROOT/'build/fastbasic-workbench'/directory/'app.json'
            app=json.loads(path.read_text())
            for name,digest in app['inputs'].items():
                require(inputs[str(Path(name).relative_to(ROOT))]==digest,'APP/staged WB2 source differs: '+name)
            applications[mode]=dict(record=str(path.relative_to(ROOT)),record_sha256=sha256(path),
                sha256=app['sha256'],bytes=app['bytes'],span=app['span'],verified_banks=app['verified_banks'],
                checked_layout=app['image']['provenance']['checked_layout'])
        result['applications']=applications
        result['latency_scope']='Physical key submission through independently checked scanout; includes debugger/probe overhead, PAL'
    elif slice=='WB1':
        result['document']=dict(bytes=32768,lines=4096,line_bytes=255,index_entries=4097,
            index_bytes=16388,undo_bytes=16384,requested_upper_bytes=65540,rounded_upper_bytes=65544,
            test_guards_upper_bytes=96)
    target=ROOT/f'docs/development/fastbasic-workbench-{slice.lower()}.json'
    target.write_text(json.dumps(result,indent=2)+'\n')
    summary_path=ROOT/'docs/development/fastbasic-workbench.json'
    summary=json.loads(summary_path.read_text()) if summary_path.exists() else dict(
        format='exec816-fastbasic-workbench-development-v1',tier='development',qualification=False,slices={})
    summary['slices'][slice]=dict(status='pass',record=str(target.relative_to(ROOT)),sha256=sha256(target))
    summary_path.write_text(json.dumps(summary,indent=2)+'\n')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--slice',choices=tuple(SOURCES),required=True)
    p.add_argument('--evidence',type=Path,action='append',required=True);p.add_argument('--staged',action='store_true')
    a=p.parse_args();record(a.slice,a.evidence,a.staged)
