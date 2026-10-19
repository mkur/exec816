#!/usr/bin/env python3
"""Exercise disk C/native dispatch and Process-owned image/AES teardown."""
import argparse,json,shutil,struct
from pathlib import Path
from native_program import ROOT,compiler,read_build,require,sha256,verify_machine
from build_c_program import build as application
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

def variant(base,out,filesystem):
    """Reuse emitted routines; change only the serialized mount descriptor."""
    from banked_image import emit
    from generate_dos_mounts import encode
    out.mkdir(parents=True,exist_ok=True)
    for name in ('program','app','media'):
        shutil.copytree(base/name,out/name,dirs_exist_ok=True)
    p=read_build(out/'program');record=p['build'];original=record['image_sha256']
    mounts=record['dos_mounts'];mounts[0]['format']=2 if filesystem=='sdfs' else 1
    address=record['task_storage']['BASE']+0x900
    segment=next(s for s in p['image']['segments'] if s['address']==address)
    encoded=encode(mounts);require(len(encoded)==len(segment['bytes']),'Changed mount extent')
    segment['bytes']=list(encoded)
    (p['output']/'program.a816.json').write_text(json.dumps(p['image'],indent=2)+'\n')
    payload,_=emit(p['output'],p['image'],record['memory'],p['labels'])
    (p['output']/'program.xex').write_bytes(payload)
    record.update(image_sha256=sha256(p['output']/'program.a816.json'),
        xex_sha256=sha256(p['output']/'program.xex'),manifest_sha256=sha256(p['output']/'manifest.bin'),
        configuration_variant=dict(base_image_sha256=original,change='Serialized filesystem format only'))
    for name in record['generated_sha256']:
        if (p['output']/name).exists():record['generated_sha256'][name]=sha256(p['output']/name)
    (p['output']/'build.json').write_text(json.dumps(record,indent=2)+'\n')
    media=out/'media'
    make(out/'system.atr',media,binary_names={p.name for p in media.iterdir()},
         filesystem=filesystem,sector_bytes=256,sectors=2880)

def run(out,optimize,reuse=False,filesystem='sdfs',app_sources=None,app_options=None,
        fixture_source=None,expected_completed=12,native_optimize=None,
        release_compiler=False,rebuild_app=False):
    out.mkdir(parents=True,exist_ok=True)
    if reuse:
        p=read_build(out/'program');app=json.loads((out/'app/app.json').read_text())
    if not reuse or rebuild_app:
        if reuse:
            from c_program import ABI
            provider=p['build']['foreign_image']['c_program_provider']
            require(app['abi']==ABI and provider['abi']==ABI['version'] and
                    provider['imports']==ABI['imports'],
                    'Rebuild the provider after a C application ABI change')
        app=application(out/'app',app_sources or [ROOT/'tests/programs/c_process.c'],
                        optimize,**(app_options or {}))
        raw=(out/'app/program.app').read_bytes();media=out/'media';media.mkdir(exist_ok=True)
        (media/'PROBE.APP').write_bytes(raw);(media/'DESKTOP.RSC').write_bytes(resource())
        (media/'TRUNC.APP').write_bytes(raw[:-1])
        count=struct.unpack_from('<H',raw,10)[0];imports=struct.unpack_from('<H',raw,24)[0]
        for name,at,fmt,value in [('VERSION',6,'<H',0),('IMPORT',32+count*16,'<H',65535),
                                 ('FIXUP',32+count*16+imports*8,'<I',app['span'])]:
            changed=bytearray(raw);struct.pack_into(fmt,changed,at,value);(media/(name+'.APP')).write_bytes(changed)
        native=out/'native/HELLO'
        compile_command(compiler(ROOT/'build/actionc',release=release_compiler),ROOT/'examples/commands/hello.act',native,optimize)
        (media/'HELLO').write_bytes(native.read_bytes())
        make(out/'system.atr',media,binary_names={p.name for p in media.iterdir()},
             filesystem=filesystem,sector_bytes=256,sectors=2880)
        # Isolated allocation-failure injection at the actual image allocator.
        text=read_source(ROOT/'lib/dos/o65memory.act').replace('USE EXEC\n','USE EXEC\nUSE O65CONTROL\n')
        text=text.replace('RETURN(EXEC.AllocMem','  O65CONTROL.allocations==+1\n'
                          '  IF O65CONTROL.failAt<>0 AND O65CONTROL.allocations=O65CONTROL.failAt THEN\n'
                          '    RETURN(NULL)\n  FI\n\nRETURN(EXEC.AllocMem')
        (out/'o65memory.act').write_text(text)
        (out/'o65control.act').write_text((ROOT/'tests/programs/o65control.act').read_text())
        if not reuse:
            p=build_desktop(out,source=fixture_source or ROOT/'tests/programs/c_process.act',program_output=out/'program',
                optimize=optimize if native_optimize is None else native_optimize,
                release_compiler=release_compiler,
                build_applications=False,
                system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,
                    profile=4,format=2 if filesystem=='sdfs' else 1)])
    record=dict(status='running',tier='development',qualification=False,filesystem=filesystem,
                app=app,build=p['build'],bank_zero_delta=bank_zero_delta(p['build']['memory']))
    try:
        require(sha256(BRIDGE/'AltirraBridgeServer')==PIN['mouse_input']['tooling']['sha256'],'Unpinned emulator')
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
            b.mount(0,str(out/'system.atr'))
            record['machine']=verify_machine(b,ROM,PIN)
            try:runtime,_=execute(b,p,timeout=600,frame_limit=30000)
            except Exception:
                record['checks']=data(b,p['image'],'checks',True)
                record['completed']=data(b,p['image'],'completed',True)
                if any(d['name'].startswith('M_CPROCESSTEST_LASTPRIMARY_') for d in p['image']['data']):
                    record['last_primary']=data(b,p['image'],'lastPrimary',True)
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
            ownership(b,p,p['output'])
            require(data(b,p['image'],'completed',True)==[expected_completed],'Incomplete C/native Process cycles')
            record.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                          completed=data(b,p['image'],'completed',True))
    except Exception as error:
        record.update(status='fail',error=str(error))
        raise
    finally:(out/'results.json').write_text(json.dumps(record,indent=2)+'\n')
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
