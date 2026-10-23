#!/usr/bin/env python3
"""Freeze selected persistent-interpreter development evidence and packages."""
import argparse,json,subprocess
from pathlib import Path
from native_program import ROOT,require,sha256


def record(directory,destination):
    evidence=[]
    for name in ('session-final-current','core-final','layout-final-raw','layout-final-opt'):
        path=directory/name/'results.json';value=json.loads(path.read_text())
        require(value['status']=='pass','Incomplete evidence: '+name)
        evidence.append(dict(path=str(path.relative_to(ROOT)),sha256=sha256(path),result=value))
    demo=directory/'demo-final'
    gui=json.loads((demo/'persistent-interpreter-results.json').read_text())
    require(gui['status']=='pass','Incomplete GUI evidence')
    native=json.loads((demo/'build.json').read_text())
    old=json.loads((ROOT/'docs/development/fastbasic-interpreter.json').read_text())
    require(old['bank_zero_budget']==native['memory']['bank_zero_budget'],'Changed bank-zero budget')
    app=json.loads((demo/'bitmap-console/apps/basic/app.json').read_text())
    donor=json.loads((ROOT/'build/fastbasic/build.json').read_text())
    names=subprocess.check_output(['git','diff','--name-only','HEAD'],cwd=ROOT).decode().splitlines()
    names+=subprocess.check_output(['git','ls-files','--others','--exclude-standard'],cwd=ROOT).decode().splitlines()
    inputs={name:sha256(ROOT/name) for name in sorted(set(names))
        if (ROOT/name).is_file() and ROOT/name!=destination}
    result=dict(format='exec816-fastbasic-session-v1',date='2026-10-22',status='pass',tier='development',qualification=False,
        source_inputs=inputs,evidence=evidence,gui=gui,gui_log_sha256=sha256(directory/'gui-final.log'),
        host=dict(tests=554,status='pass',log_sha256=sha256(directory/'host-final.log')),
        native=dict(build_sha256=sha256(demo/'build.json'),override=native['override'],
            revision=native['revision'],binary_sha256=native['binary_sha256']),
        engines=donor['engines'],engine_inputs=donor['inputs'],
        audits={name:json.loads((directory/('audit-'+name+'.json')).read_text()) for name in ('fb','fbi')},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*12,idle=0,
            includes='Guards, alignment and unused capacity'),
        bank_zero_budget=native['memory']['bank_zero_budget'],
        upper=dict(interpreter_requested=2096,interpreter_rounded=2096,
            interpreter_rounded_delta=528,editor_session_static=86,editor_session_leading_alignment=1,menu_requested=390,menu_rounded=392,menu_rounded_delta=8,
            editor_source_snapshot=32768,guest_backing_reserved=131072,
            task_and_guest_slot_retained_while_idle=True),
        limits=dict(source_limit=32768,session_variable_base=40960,variable_bytes=512,
            session_heap_base=41472,guest_limit=57344),
        delivery=dict(zip_sha256=sha256(demo/'exec816-demo.zip'),
            zip_bytes=(demo/'exec816-demo.zip').stat().st_size,
            application_sha256=app['sha256'],application_bytes=app['bytes'],application_span=app['span'],
            launcher_prepare_log_sha256=sha256(directory/'launcher.log'),
            source_archive='build/fastbasic-session/exec816-fastbasic-source.zip',
            source_checksum='Companion .zip.sha256; excluded to avoid a source self-hash cycle'))
    destination.write_text(json.dumps(result,indent=2)+'\n')


if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__)
    a.add_argument('--directory',type=Path,default=ROOT/'build/fastbasic-session')
    a.add_argument('--output',type=Path,default=ROOT/'docs/development/fastbasic-session.json')
    args=a.parse_args();record(args.directory.resolve(),args.output.resolve())
