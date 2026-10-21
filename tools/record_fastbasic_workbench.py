#!/usr/bin/env python3
"""Record passing workbench development slices without rewriting old evidence."""
import argparse,hashlib,json,subprocess
from pathlib import Path
from native_program import ROOT,sha256,require

SOURCES={
    'WB9':[
        'abi/c-program.json',
        'c/calypsi/dos-bridge.inc',
        'c/calypsi/dos.c',
        'c/include/exec816/program.h',
        'examples/gem-basic/assist-ui.c',
        'examples/gem-basic/assist-ui.h',
        'examples/gem-basic/assist.c',
        'examples/gem-basic/assist.h',
        'examples/gem-basic/build-job.h',
        'examples/gem-basic/build.c',
        'examples/gem-basic/build.h',
        'examples/gem-basic/editor.c',
        'examples/gem-basic/editor-paint.c',
        'examples/gem-basic/editor.h',
        'examples/gem-basic/file-ui.c',
        'examples/gem-basic/files.c',
        'examples/gem-basic/files.h',
        'lib/dos/c-program-abi.inc',
        'lib/dos/programfile.act',
        'lib/dos/programload.act',
        'tests/programs/basic_assist.c',
        'tests/programs/basic_build_cancel.act',
        'tests/programs/basic_build_cancel.c',
        'tests/programs/basic_build_interaction.act',
        'tests/programs/basic_build_layout.c',
        'tests/programs/basic_files.c',
        'tests/programs/c_launch_arguments.c',
        'tests/test_c_program_package.py',
        'tools/basic_build_model.py',
        'tools/build_bitmap_console.py',
        'tools/build_demo.py',
        'tools/build_gem_desktop.py',
        'tools/record_fastbasic_workbench.py',
        'tools/test_aes_exec_wait.py',
        'tools/test_c_launch_arguments.py',
        'tools/test_console_window.py',
        'tools/test_directory_batch.py',
        'tools/test_directory_metadata_abi.py',
        'tools/test_fastbasic_build.py',
        'tools/test_fastbasic_build_cancel.py',
        'tools/test_fastbasic_workbench.py',
        'tools/test_mount_api_bridges.py',
        'tools/workbench_build_interaction.py',
        'tools/workbench_files_interaction.py',
        'tools/workbench_interaction.py',
        'tests/test_workbench_refresh.py',
        'tools/test_workbench_demo.py',
        'tools/test_workbench_source.py',
        'tools/test_fastbasic_editor.py',
    ],
    'WB8':['abi/fastbasic.json','abi/fastbasic-diagnostics.json',
        'lib/dos/fbabi.act','lib/dos/fbdiagabi.act','lib/dos/fbdiagnostic.act','lib/dos/fbservice.act','lib/dos/fbstate.act',
        'c/include/exec816/fastbasic-diagnostic.h','c/calypsi/fastbasic-diagnostic.c',
        'ports/fastbasic/patches/exec6502.patch','ports/fastbasic/target/cmdline.bas',
        'ports/fastbasic/target/callbacks.asm','ports/fastbasic/target/helpers.asm','ports/fastbasic/target/fastbasic.inc',
        'tools/generate_fastbasic.py','tools/generate_fastbasic_diagnostics.py','tools/build_fastbasic.py',
        'tools/test_fastbasic_diagnostics.py','tools/test_fastbasic_diagnostic_faults.py',
        'tools/test_fastbasic_diagnostic_layout.py','tools/test_fastbasic_faults.py','tools/test_fastbasic_workbench.py',
        'tests/test_fastbasic_diagnostic_schema.py','tests/programs/fastbasic_diagnostic_layout.c','tests/programs/fbdiagnostic_fault.act'],
    'WB7':['abi/aes-server.json','abi/c-program.json','abi/console.json','c/include/exec816/console.h',
        'c/calypsi/console.c','c/calypsi/console.s','c/calypsi/console-bridge.inc','c/calypsi/aes-windows.c',
        'c/include/exec816/aes-wire.h','lib/aes/aestypes.act','lib/aes/aeswindow.act','lib/aes/aeswindowstate.act',
        *['lib/desktop/'+n for n in ('deskstate.act','deskconsole.act','desk-owned-console.inc','deskcore.act',
            'deskpaint.act','deskmove.act','deskcache.act','deskhost.act','deskmenucache.act','deskboot.act')],
        *['lib/console/'+n for n in ('console.act','consoledriver.act','consoledisplay.act','consoletypes.act','console-requests.inc')],
        'lib/dos/fbservice.act','platform/altirraos/console-layout.inc','tools/generate_console.py',
        'tests/programs/console_cell_io.act','tools/test_console_cells.py',
        'lib/display/layers.act','lib/dos/c-program-abi.inc','tests/test_c_program_package.py',
        'tests/programs/console_window.c','tests/programs/console_calls.c','tests/programs/layers-external-checks.inc',
        'tools/test_console_window.py','tools/console_window_interaction.py','tools/test_fastbasic_workbench.py',
        'tools/build_bitmap_console.py'],
    'WB6':['abi/aes-wait.json','abi/c-program.json','c/include/exec816/aes-wait.h',
        'c/include/exec816/aes.h','c/calypsi/aes-events.c','lib/dos/c-program-abi.inc',
        'tools/generate_aes_wait.py','tools/generate_c_program.py','tools/test_aes_exec_wait.py',
        'tools/test_aes_input_events.py','tools/test_aes_server.py','tools/test_fastbasic_workbench.py',
        'tests/programs/aes_exec_wait.c','tests/programs/aes_wait_layout.c',
        'tests/test_aes_wait_abi.py','tests/test_c_program_package.py','platform/altirraos/console.s',
        'tools/build_bitmap_console.py','tools/test_console_bitmap.py',
        'tests/programs/console_bridge.c','tests/programs/console_bridge.s'],
    'WB5':['abi/c-program.json','abi/process.json',
        *['c/'+n for n in ('calypsi/dos.c','calypsi/dos-bridge.inc','calypsi/program-start.inc',
            'include/exec816/program.h','include/exec816/program-start.h','include/proto/dos.h')],
        *['lib/dos/'+n for n in ('process.act','processlaunch.act','process-types.inc','processstate.act',
            'dosprocess.act','dosclient.act','programimage.act','cprogram.act','c-program-abi.inc','task-process.inc')],
        'examples/gem-browser/browser.c','examples/gem-browser/desktop.inc','examples/gem-desktop/resident.c',
        *['tests/programs/'+n for n in ('program_launch.act','program_launch.c','program_launch_child.act',
            'program_launch_child.c','program_start_layout.c','c_launch_arguments.c','c_process.act','c_process.c','process_lifetime.act')],
        'tests/fastbasic/launch.bas','tests/test_c_program_package.py',
        *['tools/'+n for n in ('test_program_launch.py','test_c_launch_arguments.py','test_c_process.py','test_process_lifetime.py',
            'build_c_program.py','c_program.py','generate_c_program.py','generate_process.py','build_bitmap_console.py',
            'build_gem_desktop.py','test_directory_batch.py','test_directory_metadata_abi.py','test_mount_api_bridges.py',
            'test_fastbasic_workbench.py','workbench_interaction.py')]],
    'WB4':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor-paint.c','editor.h','document.c','document.h','files.c','files.h','file-ui.c','file-ui.h','assist.c','assist.h','assist-ui.c','assist-ui.h')]+[
        'tests/programs/basic_assist.c','tests/programs/basic_editor.c','tests/programs/basic_editor_layout.c',
        'tests/programs/basic_interaction.act','tests/programs/basic_files_interaction.act',
        'tools/test_fastbasic_assist.py','tools/test_fastbasic_editor.py','tools/workbench_pixels.py',
        'tools/workbench_interaction.py','tools/workbench_files_interaction.py','tools/test_fastbasic_workbench.py',
        'tools/build_demo.py','tools/build_gem_desktop.py','c/calypsi/file-list.c'],
    'WB0':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor-paint.c','editor.h','document.c',
        'document.h','files.c','files.h','file-ui.c','file-ui.h','assist.c','assist.h','assist-ui.c','assist-ui.h')]+['c/calypsi/file-list.c',
        'tests/programs/basic_lifecycle.act','tests/programs/basic_lifecycle.c',
        'tools/test_fastbasic_workbench.py','tools/test_basic_workbench_baseline.py',
        'tools/build_demo.py','tools/build_gem_desktop.py','tools/gem_applications.py','tools/gem_desktop_oracle.py'],
    'WB1':['examples/gem-basic/document.c','examples/gem-basic/document.h',
        'tests/programs/basic_document.c','tools/test_fastbasic_document.py'],
    'WB3':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor-paint.c','editor.h','document.c','document.h','files.c','files.h','file-ui.c','file-ui.h')]+[
        'tests/programs/basic_files.c','tests/programs/basic_file_ui.c','tests/programs/basic_files_interaction.act',
        'tests/programs/basic_interaction.act','tools/test_fastbasic_files.py','tools/test_fastbasic_file_ui.py',
        'tools/workbench_files_interaction.py','tools/workbench_interaction.py','tools/build_demo.py','tools/build_gem_desktop.py','c/calypsi/file-list.c','c/calypsi/aes-alert.c'],
    'WB2':['examples/gem-basic/'+n for n in ('main.c','basic.c','basic.h','editor.c','editor-paint.c','editor.h','document.c','document.h')]+[
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
        for key in ('checks','abi_checks','transcripts','stop_frames','root_mode_preserved','root_cells_preserved','client_checks','bridge_words','AESChecks','AESFailures','AESWaitChecks','AESWaitFailures','AESWaitStage','controllerChecks','scope_checks','completed','machine','stack_usage','integration','runtime','free_upper_words','cases','latencies','peer_progress','typing','typing_frames','fixture_overrides','optimize','c_elf_sha256','native_image_sha256'):
            if key in r:
                if key=='runtime':
                    case[key]={k:r[key][k] for k in ('status','guards','native_nmi_count','native_irq_count',
                        'stack_observations','kernel_stack_observation') if k in r[key]}
                else:case[key]=r[key]
        cases.append(case)
    result=dict(format='exec816-fastbasic-workbench-slice-v1',slice=slice,status='pass',
        tier='development',qualification=False,date=__import__('datetime').date.today().isoformat(),
        base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
        source_inputs=inputs,pins={n:sha256(ROOT/n) for n in ('toolchain/actionc.json','ports/fastbasic/upstream.json',
            'abi/fastbasic.json','abi/c-program.json','toolchain/altirra-gem-vdi.json','toolchain/altirra-shell-paced.json')},
        evidence=cases,reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0,
            includes='Guards, alignment and unused capacity; existing Task pools and 544-byte guest pool retained'))
    if slice=='WB9':
        before=ROOT/'build/fastbasic-workbench/wb0-demo/build.json'
        after=ROOT/'build/fastbasic-workbench/wb9-demo-final/build.json'
        baseline=json.loads(before.read_text())['memory']['bank_zero_budget']
        current=json.loads(after.read_text())['memory']['bank_zero_budget']
        require(baseline==current,'Changed complete WB9 reserved bank-zero map')
        result['memory_map']=dict(baseline=str(before.relative_to(ROOT)),baseline_sha256=sha256(before),
            build=str(after.relative_to(ROOT)),build_sha256=sha256(after),bank_zero_budget=current)
        application=ROOT/'build/fastbasic-workbench/wb9-demo-final/bitmap-console/apps/basic/app.json'
        app=json.loads(application.read_text())
        for name,digest in app['inputs'].items():require(sha256(Path(name))==digest,'Changed WB9 APP input: '+name)
        require(app['minimum_stack']==1312,'Wrong BASIC stack declaration')
        result['application']={k:app[k] for k in ('sha256','bytes','span','minimum_stack','verified_banks')}
        result['controller']=dict(job_static_upper_bytes=2415,publication_static_upper_bytes=2524,
            scratch_recovery_static_upper_bytes=51,immutable_source_upper_bytes=32768,
            editor_bytes=1664,document_requested_upper_bytes=65540,document_rounded_upper_bytes=65544,
            indentation='256 caller-owned bytes reuse the lexical buffer; one additional static upper byte',
            event_workspace_static_upper_bytes=80,file_ui_workspace_static_upper_bytes=6,
            renderer='Separate translation unit keeps painting workspace out of the persistent event-loop frame',
            children=1,child_poll_timers=0,loader_requested_upper_bytes=43,loader_rounded_upper_bytes=48,
            loader_read_bytes=1024,loader_staging_limit=262144,native_c_table_upper_delta=12,c_import_table_upper_delta=12)
        result['runtime_allocations']=dict(session_requested=2310,session_rounded=2312,
            diagnostic_record=224,output_requested=1664,output_rounded=1672,
            image_metadata_requested=74,image_metadata_rounded=80,
            app_backing_requested=app['span']+65535,app_backing_rounded=(app['span']+65542)//8*8,
            includes='Allocation rounding and unused alignment capacity; APP static objects are inside its backing')
        result['capacity']=dict(public_tasks=8,normal_desktop=6,BASIC=1,sequential_child=1,
            BASIC_reserved_stack=1312,large_pools='Existing Desktop and console worker pools retained',
            guest_slots=2,AES_clients=4,windows=6,consoles=4)
        result['packages']={}
        for name,directory in [('GEM','wb9-release'),('text','wb9-text-release')]:
            archive=ROOT/'build/fastbasic-workbench'/directory/'exec816-demo.zip'
            result['packages'][name]=dict(path=str(archive.relative_to(ROOT)),sha256=sha256(archive),
                bytes=archive.stat().st_size,contents='OF816 XEX, old/new Atarimax CAR, raw 1 MiB BIN, matching SYS/WORK, ROM, guide, notices, checksums')
        result['source_delivery']=dict(archive='build/fastbasic-workbench/exec816-fastbasic-source.zip',
            checksum='Companion .zip.sha256; kept outside this archived source record to avoid a self-hash cycle',
            final_rebuild='build/fastbasic-workbench/wb9-source-final/results.json',
            tools='Bundled FastBasic/cc65/mini65 sources; installed external Calypsi 5.18')
        result['wb8_accounting_erratum']='Frozen WB8 rounded absolute values included an inapplicable 8-byte prefix; correct 2304 -> 2312 for requested 2304 -> 2310. Delta remains 8 upper bytes and zero reserved bank-zero.'
        result['delivery']='First FB7 editor/Check/Run/Stop/Build delivery; debugger and native graphics remain WB10 onward'
    elif slice=='WB0':
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
            alignment=65536,metadata_bytes=74,rounded_metadata_bytes=80)
        result['capacity']=dict(public_tasks=8,normal_startup=6,IDE=1,sequential_child=1,
            guest_slots=2,AES_clients=4,windows=6,consoles=4,
            control='Close extra graphical applications or a second Shell before Run; startup is unchanged')
        result['parent_desktop_warming']=dict(bytes=368,resolved_path=256,timer_records=112,
            lifetime='Existing live desktop context; freed with context/endpoint retirement')
        result['fastbasic_compilers']=json.loads((ROOT/'build/fastbasic/build.json').read_text())['compilers']
    elif slice=='WB8':
        guest_path=ROOT/'build/fastbasic/build.json';guest=json.loads(guest_path.read_text())
        for name,digest in guest['inputs'].items():require(sha256(ROOT/name)==digest,'Changed compiler input: '+name)
        result['compilers']=dict(path=str(guest_path.relative_to(ROOT)),sha256=sha256(guest_path),
            target=guest['target'],variants=guest['compilers'])
        before=ROOT/'build/fastbasic-workbench/wb0-demo/build.json'
        after=ROOT/'build/fastbasic-workbench/wb8-diagnostics/build.json'
        baseline=json.loads(before.read_text())['memory']['bank_zero_budget']
        current=json.loads(after.read_text())['memory']['bank_zero_budget']
        require(baseline==current,'Changed complete WB8 reserved bank-zero map')
        result['memory_map']=dict(baseline=str(before.relative_to(ROOT)),baseline_sha256=sha256(before),
            build=str(after.relative_to(ROOT)),build_sha256=sha256(after),bank_zero_budget=current)
        result['diagnostics']=dict(record_bytes=224,registration_bytes=18,
            session_requested_upper_delta=6,session_before=2304,session_after=2310,
            session_rounded_before=2312,session_rounded_after=2320,transient_record_upper_bytes=224,
            source_limit='Existing flat guest allocation; 255 bytes per source line',
            identity='Nonzero 32-bit job plus immutable absolute source path',
            completion='Process success and matching complete diagnostic and fresh validated COM are all required')
    elif slice=='WB7':
        before=ROOT/'build/fastbasic-workbench/wb0-demo/build.json'
        after=ROOT/'build/fastbasic-workbench/wb7-final/program/build.json'
        baseline=json.loads(before.read_text())['memory']['bank_zero_budget']
        current=json.loads(after.read_text())['memory']['bank_zero_budget']
        require(baseline==current,'Changed complete WB7 reserved bank-zero map')
        result['memory_map']=dict(baseline=str(before.relative_to(ROOT)),baseline_sha256=sha256(before),
            build=str(after.relative_to(ROOT)),build_sha256=sha256(after),bank_zero_budget=current)
        result['console']=dict(columns=64,rows=20,workers_added=0,signals_added=0,
            selected_identity_upper_bytes=4,c_bridge_table_upper_bytes=15,import_table_growth_upper_bytes=15,
            instance_requested_bytes=1664,instance_rounded_bytes=1672,
            lifetime='Owned window until deletion, then streams/scope until exact retirement',
            backing='Shell unchanged; other windows share bounded clipped retained-cell rendering')
        app_path=ROOT/'build/fastbasic-workbench/wb7-final/app/app.json';app=json.loads(app_path.read_text())
        for name,digest in app['inputs'].items():require(sha256(Path(name))==digest,'Changed WB7 APP input: '+name)
        result['application']=dict(path=str(app_path.relative_to(ROOT)),sha256=sha256(app_path),
            bytes=app['bytes'],span=app['span'],verified_banks=app['verified_banks'])
    elif slice=='WB6':
        before=ROOT/'build/fastbasic-workbench/wb5-c-process/program/build.json'
        after=ROOT/'build/fastbasic-workbench/wb6-wait/program/build.json'
        baseline=json.loads(before.read_text())['memory']['bank_zero_budget']
        current=json.loads(after.read_text())['memory']['bank_zero_budget']
        require(baseline==current,'Changed complete WB6 reserved bank-zero map')
        result['memory_map']=dict(baseline=str(before.relative_to(ROOT)),baseline_sha256=sha256(before),
            build=str(after.relative_to(ROOT)),build_sha256=sha256(after),bank_zero_budget=current,
            scope='Matching GEM fixtures; optional guest pool remains unchanged in the combined demo')
        result['wait']=dict(descriptor_bytes=58,context_growth=0,worker_growth=0,signal_growth=0,
            mask='Caller-owned until return; private AES/timer masks excluded',
            errors='Observed external bits restored on unsuccessful GUI decisions',
            retirement='New arrivals after the frozen decision stay pending for the next call')
        result['platform_bridge']=dict(lower_dp_bytes=24,boundary='RTL target keeps the original bank when entry low PC is zero',
            resident_used_delta=10,resident_reserved_delta=0,transient_stack_delta=4,
            fixture='Two opposite stack parities dispatch through a fixture-only JML at an exact upper-bank boundary')
        result['layouts']={}
        for mode,directory in [('optimized','layout'),('raw','layout-raw')]:
            path=ROOT/'build/fastbasic-workbench/wb6-wait'/directory/'app.json';app=json.loads(path.read_text())
            result['layouts'][mode]=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),
                checked_layout=app['image']['provenance']['checked_layout'],verified_banks=app['verified_banks'])
    elif slice=='WB5':
        baseline_path=ROOT/'build/fastbasic-workbench/wb0-demo/build.json'
        build_path=ROOT/'build/fastbasic-workbench/wb5-launch/program/build.json'
        before=json.loads(baseline_path.read_text())['memory']['bank_zero_budget']
        after=json.loads(build_path.read_text())['memory']['bank_zero_budget']
        require(before==after,'Changed complete WB5 reserved bank-zero map')
        result['memory_map']=dict(baseline=str(baseline_path.relative_to(ROOT)),baseline_sha256=sha256(baseline_path),
            build=str(build_path.relative_to(ROOT)),build_sha256=sha256(build_path),bank_zero_budget=after)
        result['launch']=dict(c_descriptor_bytes=24,native_descriptor_bytes=20,process_record_bytes=128,
            setup='Adoption and independent scope/console binding acknowledged before returning an identity',
            streams='Owned clones; aliases cloned once; parent context remains usable')
        result['upper_memory']=dict(image_requested_bytes=74,image_rounded_bytes=80,image_rounded_delta=8,
            transient_admission_bytes=12,transient_admission_delta=3)
        result['stack_admission']=dict(default_c_reserved_bytes=2560,minimum_c_declaration=1312,
            failure='103 when no existing pool fits; no reserved stack/DP growth',
            graphical_console='Existing console worker uses one 2560-byte pool; BASIC uses the other; sequential FB65/native child uses an existing smaller pool')
        result['provider']=dict(path='build/fastbasic-workbench/wb5-launch/c-image.json',
            sha256=sha256(ROOT/'build/fastbasic-workbench/wb5-launch/c-image.json'))
        result['applications']={}
        for name,directory in [('controller','wb5-launch/controller'),('child','wb5-launch/child'),('loader-probe','wb5-c-process/app')]:
            path=ROOT/'build/fastbasic-workbench'/directory/'app.json';app=json.loads(path.read_text())
            for source,digest in app['inputs'].items():
                require(inputs[str(Path(source).relative_to(ROOT))]==digest,'WB5 application source differs: '+source)
            result['applications'][name]=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),
                payload_sha256=app['sha256'],minimum_stack=app['minimum_stack'],bytes=app['bytes'],span=app['span'],verified_banks=app['verified_banks'])
    elif slice=='WB4':
        applications={}
        for mode,directory in [('optimized','wb4-physical/app'),('raw','wb4-raw-layout')]:
            path=ROOT/'build/fastbasic-workbench'/directory/'app.json';app=json.loads(path.read_text())
            for name,digest in app['inputs'].items():
                require(inputs[str(Path(name).relative_to(ROOT))]==digest,'APP/staged WB4 source differs: '+name)
            applications[mode]=dict(record=str(path.relative_to(ROOT)),record_sha256=sha256(path),
                sha256=app['sha256'],bytes=app['bytes'],span=app['span'],verified_banks=app['verified_banks'],
                checked_layout=app['image']['provenance']['checked_layout'])
        result['applications']=applications
        result['assistance']=dict(find_bytes=80,replace_bytes=80,comparisons_per_step=1024,procedure_entries=256,
            procedure_lines_per_step=4,folding='Presentation only; edits invalidate the index and folds',
            replacement='One atomic undo group, subject to the existing 16 KiB undo budget')
        result['latency_scope']='Physical key submission through accepted edit/independently checked scanout, including debugger overhead; PAL'
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
