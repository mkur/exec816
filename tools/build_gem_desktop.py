#!/usr/bin/env python3
"""Shared GEM runtime, RAM-installed desktop and disk-loaded applications."""
import argparse,hashlib,json,os,re,struct
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT,build,compiler,require


def build_desktop(out,source=None,program_output=None,files=False,basic_workbench=False,**options):
    from library_paths import read_source
    from c_program import ABI,binding
    from build_c_program import build as application
    out.mkdir(parents=True,exist_ok=True)
    options.pop('desktop',None)
    applications={}
    for name,folder in [('panel','gem-panel'),('counter','gem-counter'),('files','gem-browser'),('desktop','gem-browser'),('dialog','gem-dialog')]:
        body='browser' if name in ('files','desktop') else name
        applications[name]=application(out/'apps'/name,[ROOT/'examples'/folder/('desktop-main.c' if name=='desktop' else 'main.c'),
                                                       ROOT/'examples'/folder/(body+'.c'),
                                                       *([ROOT/'c/calypsi/file-list.c'] if name in ('files','desktop') else [])],
            probes=[(ROOT/'tests/programs/gem_colour_desktop_layout.c',__import__('colour_desktop_model').LAYOUT)] if name=='desktop' else [])
    from build_calculator import build as calculator
    applications['calc']=calculator(out/'apps/calc')
    from build_g4bench import build as g4bench
    applications['g4bench']=g4bench(out/'apps/g4bench')
    applications['text']=application(out/'apps/text',[
        ROOT/'examples/gem-text'/name for name in ('main.c','text.c','document.c')]+
        [ROOT/'c/calypsi/file-list.c'],probes=[
            (ROOT/'tests/programs/gem_text_layout.c',__import__('text_model').LAYOUT)])
    if basic_workbench:
        applications['basic']=application(out/'apps/basic',[
            ROOT/'examples/gem-basic'/name for name in ('main.c','basic.c','editor.c','document.c')])
    from build_gem_resource import resource
    desktop_resource=resource()
    if 'dos_mounts' not in options:
        from make_data_disk import make
        media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        if files:
            (media/'DESKTOP.RSC').unlink(missing_ok=True)
            (media/'C/DESKTOP.APP').unlink(missing_ok=True)
        disk_apps=[name for name in applications if not files or name!='desktop']
        for name in disk_apps:
            (media/'C'/(name.upper()+'.APP')).write_bytes((out/'apps'/name/'program.app').read_bytes())
        if not files:(media/'DESKTOP.RSC').write_bytes(desktop_resource)
        (media/'CALC.RSC').write_bytes((out/'apps/calc/CALC.RSC').read_bytes())
        make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
             binary_names={*(f'C/{name.upper()}.APP' for name in disk_apps),'CALC.RSC'}|
                          (set() if files else {'DESKTOP.RSC'}))
        options.update(system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                       sector_bytes=256,profile=4,format=2)])
    foreign=drawing(out,True,widgets=True,client_sources=[
        ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
        ROOT/'c/calypsi/program.c',ROOT/'examples/gem-desktop/resident.c'],
        client_roots=['GEMDesktopStart','GEMDesktopStop','GEMDesktopCollect','GEMDesktopChildren',
                      'GEMDesktopDone','GEMDesktopFailure','ExecProgramRun',*ABI['imports']],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_panel_layout.c',[
                ('Panel size',404),('Panel ready',8),('Panel actions',10),('Panel paints',14),
                ('Panel work',34),('Panel tree',178),('Panel status',370),('Panel focus',392),('Panel armed',394)]),
            (ROOT/'tests/programs/gem_browser_layout.c',__import__('browser_model').LAYOUT),
            (ROOT/'tests/programs/gem_dialog_layout.c',__import__('dialog_model').LAYOUT)])
    boot_address=0;boot_files={}
    if files:
        app=(out/'apps/desktop/program.app').read_bytes()
        # Keep serialized files outside the provider's single C data bank.
        # Native placement already follows all foreign load segments.
        end=max([s['address']+len(s['bytes']) for s in foreign['segments']]+
                [s['address']+s['size'] for s in foreign['zero_fill']])
        boot_address=(end+65535)//65536*65536
        payload=struct.pack('<II',len(app),len(desktop_resource))+app+desktop_resource
        foreign['segments'].append(dict(address=boot_address,bytes=list(payload),
                                        writable=False,executable=False))
        boot_files={name:dict(bytes=len(data),sha256=hashlib.sha256(data).hexdigest())
                    for name,data in [('RAM:DESKTOP.APP',app),('RAM:DESKTOP.RSC',desktop_resource)]}
        foreign['provenance']['desktop_boot_files']=boot_files
    binding(foreign,out)
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    text=read_source(source or ROOT/'tests/programs/gem_desktop_session.act')
    sy=foreign['symbols']
    require(not {'PanelRun','CounterRun','BrowserRun','GEMPanel','GEMCounter','GEMBrowser',
                 'Calculator','calc_start','calc_ws','calc_panel','TextRun','GEMText','TextStep'} & sy.keys(),
            'Application body or model retained in shared GUI image')
    for module in ('AESBOOT','CALYPSICALL','DOSCLIENT','PROCESS'):
        if not re.search(r'(?m)^USE '+module+r'\s*$',text):
            text=re.sub(r'(?m)^(MODULE \w+\n)',r'\1USE '+module+'\n',text,count=1)
    text=text.replace('ENDMODULE',f'''
; Root collects its desktop children; shell jobs belong to their shell Process.
; This callback performs no recursive DOS I/O.
LONGCARD FUNC DesktopService()
  LONGCARD mask

  mask=LONGCARD(CALYPSICALL.Invoke(ADDRESS(${sy['GEMDesktopCollect']:x}),0))
RETURN(mask)

BYTE FUNC DesktopStart()

  LET started=CALYPSICALL.Invoke(ADDRESS(${sy['GEMDesktopStart']:x}),${boot_address:x})
  LET client=DOSCLIENT.Ensure()
  client.waitService=@DesktopService
  client.waitMask=DesktopService()

RETURN(started<>0)

BYTE FUNC DesktopStop()

  LET client=DOSCLIENT.Ensure()
  client.waitMask=0

RETURN(CALYPSICALL.Invoke(ADDRESS(${sy['GEMDesktopStop']:x}),0)<>0)

ENDMODULE
''')
    source=out/'gem-session.act';source.write_text(text)
    memory=options.pop('memory_profile',None)
    if memory is None:
        profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
        memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    mouse_profile=options.pop('mouse_profile',None)
    compiler_dir=options.pop('compiler_dir',ROOT/'build/actionc')
    release_compiler=options.pop('release_compiler',False)
    launcher=prepare(source,out,foreign,desktop=True,aes=True,mouse_profile=mouse_profile)
    program=build(compiler(compiler_dir,release=release_compiler),launcher,program_output or out/'program',
        tasks=True,task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,**options)
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse']=metadata(mouse_profile)
    program['build']['gem_applications']={name:dict(bytes=app['bytes'],sha256=app['sha256'],
        span=app['span'],relative_manifest=os.path.relpath(out/'apps'/name/'app.json',program['output']))
        for name,app in applications.items()}
    if boot_files:program['build']['desktop_boot_files']=boot_files
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build_desktop(args.output.resolve(),stack_checks=True)
