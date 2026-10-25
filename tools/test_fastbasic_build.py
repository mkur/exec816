#!/usr/bin/env python3
"""WB9 loadable workbench with real compiler/program children and GUI input."""
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,read_build,sha256
from basic_build_model import LAYOUT as JOB_LAYOUT
from workbench_interaction import LAYOUT as EDITOR_LAYOUT

def prepare(out,provider,app_only=False,fixture=None,extra_media=None,minimum_stack=None):
 from build_c_program import build as application
 from build_bitmap_console import prepare as launcher
 from c_program import ABI,binding
 from make_data_disk import make
 from generate_memory import PROFILE
 from generate_mouse_acceleration import metadata
 out.mkdir(parents=True,exist_ok=True)
 sources=[ROOT/'examples/gem-basic'/n for n in ('main.c','basic.c','editor.c','editor-paint.c','document.c','files.c','file-ui.c','assist.c','assist-ui.c','build.c')]+[ROOT/'c/calypsi/file-list.c',ROOT/'c/calypsi/fastbasic-diagnostic.c']
 app=application(out/'app',sources,minimum_stack=ABI['stack_floor_bytes'] if minimum_stack is None else minimum_stack,probes=[(ROOT/'tests/programs/basic_editor_layout.c',EDITOR_LAYOUT),(ROOT/'tests/programs/basic_build_layout.c',JOB_LAYOUT)])
 media=out/'media';(media/'C').mkdir(parents=True,exist_ok=True)
 for name,path in [('BASIC.APP',out/'app/program.app'),*[(n+'.COM',ROOT/f'build/fastbasic/{n}.COM') for n in ('FBC','FBCI','FB','FBI')]]:shutil.copyfile(path,media/'C'/name)
 for name,raw in (extra_media or {}).items():
  path=media/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(raw)
 (media/'REL.TXT').write_bytes(b'123\x9b')
 make(out/'system.atr',media,binary_names={'C/BASIC.APP','C/FBC.COM','C/FBCI.COM','C/FB.COM','C/FBI.COM','REL.TXT'}|set(extra_media or {}),filesystem='sdfs',sector_bytes=256,sectors=2880)
 if app_only:return app
 foreign=json.loads(provider.read_text())
 for path,digest in foreign['provenance']['source_inputs'].items():require(sha256(ROOT/path)==digest,'Changed provider: '+path)
 binding(foreign,out);(out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
 source=launcher(fixture or ROOT/'tests/programs/basic_build_interaction.act',out,foreign,desktop=True,aes=True)
 profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
 memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
 p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,foreign_image=foreign,console_deferred=True,memory_profile=memory,system_mount='D1',dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2),dict(alias='RAM',format=3)],sdx=True,sdx_drive_a='RAM:',stack_checks=True)
 p['build']['desktop_mouse']=metadata(None);(p['output']/'build.json').write_text(json.dumps(p['build'],indent=2)+'\n')
 return p,app

if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--provider',type=Path,default=ROOT/'build/fastbasic-workbench/wb9-provider/c-image.json');a.add_argument('--from-build',action='store_true');a.add_argument('--build-only',action='store_true');a.add_argument('--app-only',action='store_true');a.add_argument('--scenario',choices=('complete','release'),default='complete');args=a.parse_args();out=args.output.resolve()
 if not args.from_build:prepare(out,args.provider.resolve(),args.app_only)
 if not args.build_only:
  from workbench_build_interaction import exercise,release_build
  exercise(out,release_build if args.scenario=='release' else None)
