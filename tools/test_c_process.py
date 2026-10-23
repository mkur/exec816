#!/usr/bin/env python3
"""Exercise disk C/native dispatch and Process-owned image/AES teardown."""
import argparse,os,json,shutil,struct
from pathlib import Path
from native_program import ROOT,compiler,read_build,require,sha256,verify_machine
from build_c_program import build as application
from c_program import ABI
from build_gem_desktop import build_desktop
from build_gem_resource import resource
from build_command import compile_command
from make_data_disk import make
from library_paths import read_source
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_mouse_observe import PIN,BRIDGE,ROM
from test_cooperative import data
from stack_budget import bank_zero_delta
from c_program import ABI

def variant(base,out,filesystem,unit=None,sectors=None):
    """Reuse emitted routines; change only the serialized mount descriptor."""
    from banked_image import emit
    from generate_dos_mounts import encode
    out.mkdir(parents=True,exist_ok=True)
    shutil.copy2(base/'c-image.json',out/'c-image.json')
    for name in ('program','app','media'):
        shutil.copytree(base/name,out/name,dirs_exist_ok=True)
    p=read_build(out/'program');record=p['build'];original=record['image_sha256']
    source=Path(record['source'])
    if source.name==str(source) and (base/source).is_file():shutil.copy2(base/source,out/source)
    mounts=record['dos_mounts'];mounts[0]['format']=2 if filesystem=='sdfs' else 1
    if unit is not None:mounts[0]['unit']=unit
    if sectors is not None:mounts[0]['sectors']=sectors
    address=record['task_storage']['BASE']+0x900
    segment=next(s for s in p['image']['segments'] if s['address']==address)
    encoded=encode(mounts);require(len(encoded)==len(segment['bytes']),'Changed mount extent')
    segment['bytes']=list(encoded)
    (p['output']/'program.a816.json').write_text(json.dumps(p['image'],indent=2)+'\n')
    payload,_=emit(p['output'],p['image'],record['memory'],p['labels'])
    (p['output']/'program.xex').write_bytes(payload)
    record.update(image_sha256=sha256(p['output']/'program.a816.json'),
        xex_sha256=sha256(p['output']/'program.xex'),manifest_sha256=sha256(p['output']/'manifest.bin'),
        configuration_variant=dict(base_image_sha256=original,change='Serialized filesystem format'+(' and physical unit' if unit is not None else '')+(' and geometry' if sectors is not None else '')+' only'))
    for name in record['generated_sha256']:
        if (p['output']/name).exists():record['generated_sha256'][name]=sha256(p['output']/name)
    (p['output']/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    media=out/'media'
    make(out/'system.atr',media,binary_names={p.name for p in media.iterdir()},
         filesystem=filesystem,sector_bytes=256,sectors=mounts[0]['sectors'])

def run(out,optimize,reuse=False,filesystem='sdfs',app_sources=None,app_options=None,
        fixture_source=None,expected_completed=12,native_optimize=None,
        release_compiler=False,rebuild_app=False,writable=False,ram=False,boundary_limits=False,observe_stacks=False,stack_media=False,stack_observation_index=0,media_files=None,app_builder=None,interaction=None,loader_failures=True,retirement_timeout=600,profile_all=False,prepare_media=None,execution=None,stack_observation_count=None):
    out.mkdir(parents=True,exist_ok=True)
    execution=execution or {}
    binary=execution.get('binary',BRIDGE);pin=execution.get('pin',PIN)
    drive=execution.get('drive',0);unit=execution.get('unit',49)
    sectors=execution.get('sectors',2880)
    alias=execution.get('alias','D1')
    expected_status=execution.get('status',0)
    if reuse:
        p=read_build(out/'program')
        app=json.loads((out/'app/app.json').read_text()) if (out/'app/app.json').exists() else None
        require(app is not None or rebuild_app,'Missing APP record; rebuild the application')
    if not reuse or rebuild_app:
        if reuse:
            provider=p['build']['foreign_image']['c_program_provider']
            require(provider['abi']==ABI['version'] and
                    provider['imports']==ABI['imports'],
                    'Rebuild the provider after a C application ABI change')
            mounts=p['build']['dos_mounts']
            require(mounts[0]['format']==(2 if filesystem=='sdfs' else 1) and mounts[0]['unit']==unit and mounts[0]['sectors']==sectors and mounts[0]['alias']==alias and
                    (mounts[0]['access']=='readwrite')==writable and
                    any(m['format']==3 for m in mounts)==ram,
                    'Rebuild or derive the fixture for changed mount configuration')
        app=app_builder(out/'app') if app_builder else application(out/'app',app_sources or [ROOT/'tests/programs/c_process.c'],
                        optimize,**(app_options if app_options is not None else dict(minimum_stack=ABI['stack_floor_bytes'])))
        raw=(out/'app/program.app').read_bytes();media=out/'media';media.mkdir(exist_ok=True)
        (media/'PROBE.APP').write_bytes(raw);(media/'DESKTOP.RSC').write_bytes(resource())
        for name,payload in (media_files or {}).items():(media/name).write_bytes(payload)
        if loader_failures:
            (media/'TRUNC.APP').write_bytes(raw[:-1])
            count=struct.unpack_from('<H',raw,10)[0];imports=struct.unpack_from('<H',raw,24)[0]
            for name,at,fmt,value in [('VERSION',6,'<H',ABI['version']-1),
                                     ('DPBYTES',26,'<B',0),('LENGTH',28,'<I',len(raw)+1),
                                     ('IMPORT',32+count*16,'<H',65535),
                                     ('FIXUP',32+count*16+imports*8,'<I',app['span'])]:
                changed=bytearray(raw);struct.pack_into(fmt,changed,at,value);(media/(name+'.APP')).write_bytes(changed)
        else:
            for name in ('TRUNC','VERSION','DPBYTES','LENGTH','IMPORT','FIXUP'):(media/(name+'.APP')).unlink(missing_ok=True)
        if boundary_limits:
            for name,at,fmt,value in [('COUNT',10,'<H',ABI['segment_limit']+1),
                                     ('SPAN',12,'<I',ABI['span_limit']+1)]:
                changed=bytearray(raw[:32]);struct.pack_into('<I',changed,28,32)
                struct.pack_into(fmt,changed,at,value);(media/(name+'.APP')).write_bytes(changed)
        if stack_media:
            for name,required in [('SMALL',0),('TALL',3008)]:
                changed=bytearray(raw)
                struct.pack_into('<H',changed,26,(struct.unpack_from('<H',raw,26)[0]&255)|((required//16)<<8))
                (media/(name+'.APP')).write_bytes(changed)
        native=out/'native/HELLO'
        compile_command(compiler(ROOT/'build/actionc',release=release_compiler),ROOT/'examples/commands/hello.act',native,optimize)
        (media/'HELLO').write_bytes(native.read_bytes())
        make(out/'system.atr',media,binary_names={p.name for p in media.iterdir()},
             filesystem=filesystem,sector_bytes=256,sectors=sectors)
        # Isolated allocation-failure injection at the actual image allocator.
        text=read_source(ROOT/'lib/dos/o65memory.act').replace('USE EXEC\n','USE EXEC\nUSE O65CONTROL\n')
        text=text.replace('RETURN(EXEC.AllocMem','  O65CONTROL.allocations==+1\n'
                          '  IF O65CONTROL.failAt<>0 AND O65CONTROL.allocations=O65CONTROL.failAt THEN\n'
                          '    RETURN(NULL)\n  FI\n\nRETURN(EXEC.AllocMem')
        (out/'o65memory.act').write_text(text)
        (out/'o65control.act').write_text((ROOT/'tests/programs/o65control.act').read_text())
        if not reuse:
            mounts=[dict(alias=alias,unit=unit,sectors=sectors,sector_bytes=256,
                profile=4,format=2 if filesystem=='sdfs' else 1,
                access='readwrite' if writable else 'readonly')]
            if ram:mounts.append(dict(alias='RAM',format=3))
            p=build_desktop(out,source=fixture_source or ROOT/'tests/programs/c_process.act',program_output=out/'program',
                optimize=optimize if native_optimize is None else native_optimize,
                release_compiler=release_compiler,
                build_applications=False,
                system_mount=execution.get('system_mount','D1'),dos_mounts=mounts)
    if prepare_media:prepare_media(out/'system.atr',filesystem)
    record=dict(initial_media_sha256=sha256(out/'system.atr'),status='running',tier='development',qualification=False,filesystem=filesystem,
                app=app,build=p['build'],bank_zero_delta=bank_zero_delta(p['build']['memory']))
    record['execution']=dict(pin=pin,drive=drive,unit=unit,sectors=sectors,expected_status=expected_status)
    try:
        digest=pin['fault_responder']['binary_sha256'] if 'fault_responder' in pin else pin['mouse_input']['tooling']['sha256']
        require(sha256(binary/'AltirraBridgeServer')==digest,'Unpinned emulator')
        if observe_stacks:
            from qed_stack_observer import markers,summarize_owned,capture
            points=markers(p,app)
            (out/'stack-markers.json').write_text(json.dumps(points,indent=2)+'\n')
            saved_trace={k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
            os.environ.update(EXEC816_LATENCY_TRACE='1',EXEC816_LATENCY_PCS=','.join(f'{pc:x}' for pc in points))
        with emulator(binary,ROM,out,pin=pin) as b:
            for k,v in pin['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.mount(drive,str(out/'system.atr'))
            record['machine']=verify_machine(b,ROM,pin)
            try:
                runtime,_=execute(b,p,timeout=600,frame_limit=30000,expected_status=expected_status,
                    before_run=(lambda b:capture(b,p,record,stack_observation_index,
                        during_run=(lambda owner:interaction(b,p,app,record,owner)) if interaction else None,
                        retirement_timeout=retirement_timeout,profile_all=profile_all,observation_count=stack_observation_count)) if observe_stacks else None)
            except Exception:
                record['checks']=data(b,p['image'],'checks',True)
                record['completed']=data(b,p['image'],'completed',True)
                if any(d['name'].startswith('M_CPROCESSTEST_LASTPRIMARY_') for d in p['image']['data']):
                    record['last_primary']=data(b,p['image'],'lastPrimary',True)
                if any(d['name'].startswith('M_CPROCESSTEST_LASTSECONDARY_') for d in p['image']['data']):
                    record['last_secondary']=data(b,p['image'],'lastSecondary',True)
                table=next(d for d in p['image']['data'] if d['name']=='M_PROCESSSTATE_TABLE')
                layout=json.loads((ROOT/'abi/process.json').read_text())
                offsets={name:offset for name,kind,offset in layout['record']}
                record['process_diagnostics']=[]
                for index in range((table['size']-4)//layout['record_bytes']):
                    at=table['address']+index*layout['record_bytes']
                    state=b.eval_expr(f'db(${at+offsets["state"]:x})')
                    if state:
                        primary=b.eval_expr(f'dw(${at+offsets["primary"]:x})')
                        primary|=b.eval_expr(f'dw(${at+offsets["primary"]+2:x})')<<16
                        record['process_diagnostics'].append(dict(index=index,state=state,
                            primary=primary-(1<<32) if primary&(1<<31) else primary))
                raise
            if expected_status==0xff93:
                # hosted.s parks before HEAP_SHUTDOWN on an unsafe bus. Bank
                # claims remain owned by the kernel heap until the cold reset.
                from banked_test_memory import read
                c=p['build']['memory']['constants']
                seed=(p['output']/'manifest.bin').read_bytes()[32:32+c['TABLE_BYTES']]
                actual=read(b,c['TABLE'],c['TABLE_BYTES'],p['output'])
                retained=[]
                for at in range(0,len(seed),4):
                    old,now=seed[at:at+4],actual[at:at+4]
                    if old==now:continue
                    require(old[0]==1 and now[0]==3 and now[1]==0 and int.from_bytes(now[2:4],'little')==5,
                            'Reset park changed a non-heap bank claim: '+str((at//4,list(old),list(now))))
                    retained.append(at//4)
                record['reset_park']=dict(heap_shutdown_skipped=True,retained_heap_banks=retained,
                    scope='Application retirement checked separately; live kernel heap storage retained until reset')
            else:ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[expected_completed],'Incomplete C/native Process cycles')
            if writable:b._cmd_ok('EJECT drive='+str(drive))
            record.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                          completed=data(b,p['image'],'completed',True))
            if any(d['name'].startswith('M_CPROCESSTEST_LASTSECONDARY_') for d in p['image']['data']):
                record['last_secondary']=data(b,p['image'],'lastSecondary',True)
    except Exception as error:
        record.update(status='fail',error=str(error))
        raise
    finally:
        if observe_stacks and 'saved_trace' in locals():
            for key,value in saved_trace.items():
                if value is None:os.environ.pop(key,None)
                else:os.environ[key]=value
            if record['status']=='pass':
                record['stacks']=summarize_owned(out/'emulator.log',p,app,p['build']['memory'],record.get('stack_windows',record.get('stack_window')))
                record['stack_marker_scope']='owned-image'
        (out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--raw',action='store_true');parser.add_argument('--from-build',action='store_true')
    parser.add_argument('--filesystem',choices=('sdfs','mydos'),default='sdfs')
    parser.add_argument('--variant-from',type=Path,help='Reuse emission with another filesystem')
    args=parser.parse_args()
    if args.variant_from:
        variant(args.variant_from.resolve(),args.output.resolve(),args.filesystem)
    run(args.output.resolve(),not args.raw,args.from_build or bool(args.variant_from),args.filesystem)
