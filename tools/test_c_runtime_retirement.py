"""Bounded observation of failed GUI retirement; the guest stays owned/parked."""
import json
from pathlib import Path
import adapter_state as adapter
from native_program import ROOT,require,compiler,read_build,sha256,verify_machine
from build_c_program import build as application
from build_gem_desktop import build_desktop
from build_gem_resource import resource
from make_data_disk import make
from os_boundary import emulator,run_to
from test_mouse_observe import PIN,BRIDGE,ROM
from qed_stack_observer import capture
from program_image_layout import FIELDS,LAYOUT
from c_program import ABI

class ObservedPark(Exception):pass


def run(out,reuse=False):
    source=ROOT/'tests/programs/c_runtime_lifecycle.c'
    if reuse:
        app=json.loads((out/'app/app.json').read_text())
        require(app['abi']==ABI and sha256(out/'app/program.app')==app['sha256'],'Changed retirement APP')
        for name,digest in {**app['inputs'],**app['c_runtime']['inputs']}.items():
            require(sha256(Path(name))==digest,'Changed retirement APP input: '+name)
    else:
        app=application(out/'app',[source],main_signature='args',minimum_stack=ABI['stack_floor_bytes'],
            includes=[ROOT/'c/runtime'],definitions={name:['-DEXEC_CRT_TEST'] for name in ('allocation.c','files.c')})
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'PROBE.APP').write_bytes((out/'app/program.app').read_bytes())
    (media/'DESKTOP.RSC').write_bytes(resource())
    make(out/'system.atr',media,binary_names={'PROBE.APP','DESKTOP.RSC'},filesystem='sdfs',sector_bytes=256,sectors=2880)
    (out/'o65control.act').write_text((ROOT/'tests/programs/o65control.act').read_text())
    fixture=out/'retirement.act'
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture.write_text(prefix+'''
PROC Main()

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  DOS.SelectInput(input)
  DOS.SelectOutput(output)
  LET image=Load()
  LET child=Start(image,BYTE POINTER(c"D"))
  Require(child<>0)
  PROGRAM.Unload(image)
  Collected(child,0)
  HEAPCORE.Abort($fbff)

RETURN

ENDMODULE
''')
    p=read_build(out/'program') if reuse else build_desktop(out,source=fixture,
        program_output=out/'program',optimize=True,release_compiler=True,
        build_applications=False,system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,
            sectors=2880,sector_bytes=256,profile=4,format=2,access='readonly')],
        provider_sources=[ROOT/'tests/programs/c_runtime_retirement.c'],
        provider_definitions={'program.c':['-DExecAESDetach=RuntimeTestDetach']})
    resident=json.loads((out/'c-image.json').read_text())
    record=dict(status='running',tier='development',qualification=False,app=app,build=p['build'],pin=PIN,
        expected_completion=False,scope='Failed GUI retirement retains Task, execution Image lease and C backing; cold emulator stop only')
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
            b.mount(0,str(out/'system.atr'));record['machine']=verify_machine(b,ROM,PIN)
            b.bp_clear_all();b.boot(str(p['xex']))
            run_to(b,p['labels']['loader_start'],frame_limit=1800,timeout=180)
            b.bp_set(p['labels']['start']);run_to(b,p['labels']['start']);b.bp_clear_all()
            def observe(owner):
                base=owner['image_base'];sy=app['image']['symbols'];delta=base-(ABI['link_bank']<<16)
                address={name:sy[name]+delta for name in ('scope','totals','report','__global_streams')}
                process=json.loads((ROOT/'abi/process.json').read_text())
                fields={name:offset for name,kind,offset in process['record']}
                slot=b.eval_expr(f'db(${owner["record"]+fields["slot"]:x})')
                # Observe the real Wait gateway at the pinned bank-zero COP
                # rendezvous; this server cannot qualify upper-bank PC stops.
                wait=p['labels']['native_cop']
                selector=json.loads((ROOT/'abi/tasks.json').read_text())['services']['WAIT']
                condition=f'(db(${adapter.CURRENT:x})={slot})&(dw(${address["scope"]:x})=5)&(@a={selector})'
                b.bp_clear_all();b.bp_set(wait,condition=condition)
                def snapshot():
                    image=b.memdump(owner['image'],LAYOUT['size'])
                    report=b.memdump(address['report'],16)
                    number=lambda data,at,n:int.from_bytes(data[at:at+n],'little')
                    title=number(report,8,4)
                    return dict(process_state=b.eval_expr(f'db(${owner["record"]+fields["state"]:x})'),
                        scope_state=b.eval_expr(f'dw(${address["scope"]:x})'),
                        blocks=b.eval_expr(f'dw(${address["totals"]:x})'),
                        references=number(image,FIELDS['references'],4),owner_held=image[FIELDS['ownerHeld']],
                        running=image[FIELDS['running']],callbacks=number(report,0,2),order=number(report,2,2),
                        writes=number(report,4,2),closes=number(report,6,2),title=b.memdump(title,17).hex())
                try:run_to(b,wait,condition=condition,frame_limit=3000,timeout=60)
                except Exception:
                    record['park_diagnostics']=dict(snapshot=snapshot(),current=b.eval_expr(f'db(${adapter.CURRENT:x})'),slot=slot,owner=owner)
                    raise
                first=snapshot()
                require(first==dict(process_state=2,scope_state=5,blocks=4,references=1,
                    owner_held=0,running=1,callbacks=3,order=321,writes=1,closes=1,
                    title=b'Runtime retained\0'.hex()),'Wrong retained state: '+str(first))
                b.bp_clear_all()
                condition=f'db(${adapter.CURRENT:x})!={slot}'
                b.bp_set(p['labels']['native_nmi'],condition=condition)
                run_to(b,p['labels']['native_nmi'],condition=condition,frame_limit=1200,timeout=30)
                require(snapshot()==first,'Retained resources changed after parking')
                pool=p['build']['memory']['task_pools'][slot]
                require(b.memdump(pool['stack_base'],256)==bytes([0xa5])*256,'Park consumed interrupt reserve')
                record['retained']=dict(owner=owner,first=first,after_scheduling=snapshot(),interrupt_reserve_intact=True)
                raise ObservedPark()
            try:capture(b,p,record,0,during_run=observe)
            except ObservedPark:record['status']='pass'
            else:raise RuntimeError('Retirement fault unexpectedly completed')
    except Exception as error:
        record.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
