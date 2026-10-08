#!/usr/bin/env python3
"""Shared GEM runtime with three independently loaded desktop applications."""
import argparse,json,os,re
from pathlib import Path
from build_bitmap_console import drawing,prepare
from generate_aes_server import expected_layout
from generate_memory import PROFILE
from native_program import ROOT,build,compiler,require


def build_desktop(out,source=None,program_output=None,files=False,disk_component=False,**options):
    from library_paths import read_source
    from c_program import ABI,binding
    from build_c_program import build as application
    out.mkdir(parents=True,exist_ok=True)
    options.pop('desktop',None)
    applications={}
    for name,folder in [('panel','gem-panel'),('counter','gem-counter'),('files','gem-browser')]:
        body='browser' if name=='files' else name
        applications[name]=application(out/'apps'/name,[ROOT/'examples'/folder/'main.c',
                                                       ROOT/'examples'/folder/(body+'.c')])
    from build_calculator import build as calculator
    applications['calc']=calculator(out/'apps/calc')
    if 'dos_mounts' not in options:
        from make_data_disk import make
        from build_gem_resource import resource
        media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
        for name in applications:
            (media/'C'/(name.upper()+'.APP')).write_bytes((out/'apps'/name/'program.app').read_bytes())
        (media/'DESKTOP.RSC').write_bytes(resource())
        (media/'CALC.RSC').write_bytes((out/'apps/calc/CALC.RSC').read_bytes())
        make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
             binary_names={*(f'C/{name.upper()}.APP' for name in applications),'DESKTOP.RSC','CALC.RSC'})
        options.update(system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                       sector_bytes=256,profile=4,format=2)])
    foreign=drawing(out,True,widgets=True,client_sources=[
        ROOT/'c/calypsi/aes.c',ROOT/'c/calypsi/aes-messages.c',ROOT/'c/calypsi/aes-events.c',
        ROOT/'c/calypsi/program.c',ROOT/'examples/gem-desktop/resident.c'],
        client_roots=['GEMDesktopStart','GEMDesktopStop','GEMDesktopCollect','GEMDesktopChildren',
                      'GEMDesktopDone','GEMDesktopFailure','ExecProgramRun',*ABI['imports']],
        client_probes=[(ROOT/'c/calypsi/aes-layout.c',expected_layout()),
            (ROOT/'tests/programs/gem_panel_layout.c',[
                ('Panel size',400),('Panel ready',8),('Panel actions',10),('Panel paints',14),
                ('Panel work',34),('Panel tree',178),('Panel status',370),('Panel focus',392),('Panel armed',394)]),
            (ROOT/'tests/programs/gem_browser_layout.c',[('Browser size',1992),('Browser ready',8),('Browser work',26),
                ('Browser tree',170),('Browser path',178),('Browser names',306),('Browser status',1386),
                ('Browser count',1962),('Browser selected',1966),('Browser launches',1972),('Browser child',1980)])])
    binding(foreign,out)
    if disk_component:
        from gem_component import prepare as prepare_component
        prepare_component(foreign,out)
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    text=read_source(source or ROOT/'tests/programs/gem_desktop_session.act')
    sy=foreign['symbols']
    require(not {'PanelRun','CounterRun','BrowserRun','GEMPanel','GEMCounter','GEMBrowser',
                 'Calculator','calc_start','calc_ws','calc_panel'} & sy.keys(),
            'Application body or model retained in shared GUI image')
    service=''
    if '      ShellReadStep()' in text:
        service='''  ShellCollectJob()
  IF job.state=JOB_RUNNING OR job.state=JOB_STOPPING THEN
    mask=mask OR PROCESS.CompletionMask(job.identity)
  FI

'''
        text=text.replace('      ShellReadStep()', '      DesktopReap()\n      ShellReadStep()')
    for module in ('AESBOOT','CALYPSICALL','DOSCLIENT','PROCESS'):
        if not re.search(r'(?m)^USE '+module+r'\s*$',text):
            text=re.sub(r'(?m)^(MODULE \w+\n)',r'\1USE '+module+'\n',text,count=1)
    text=text.replace('ENDMODULE',f'''
; Collect only owned completions. This callback performs no recursive DOS I/O
; while a shell read or packet owns the caller's DOS context.
LONGCARD FUNC DesktopService()
  LONGCARD mask

  mask=LONGCARD(CALYPSICALL.Invoke(ADDRESS(${sy['GEMDesktopCollect']:x}),0))
{service}RETURN(mask)

PROC DesktopReap()

  LET client=DOSCLIENT.Ensure()
  client.waitMask=DesktopService()

RETURN

BYTE FUNC DesktopStart()

  LET started=CALYPSICALL.Invoke(ADDRESS(${sy['GEMDesktopStart']:x}),{int(files)})
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
    launcher=prepare(source,out,foreign,desktop=True,aes=True,mouse_profile=mouse_profile)
    program=build(compiler(compiler_dir),launcher,program_output or out/'program',
        tasks=True,task_capacity=8,foreign_image=foreign,console_deferred=True,
        memory_profile=memory,**options)
    from generate_mouse_acceleration import metadata
    program['build']['desktop_mouse']=metadata(mouse_profile)
    program['build']['gem_applications']={name:dict(bytes=app['bytes'],sha256=app['sha256'],
        span=app['span'],relative_manifest=os.path.relpath(out/'apps'/name/'app.json',program['output']))
        for name,app in applications.items()}
    (program['output']/'build.json').write_text(json.dumps(program['build'],indent=2)+'\n')
    return program

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    build_desktop(args.output.resolve(),stack_checks=True)
