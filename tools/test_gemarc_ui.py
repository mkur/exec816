#!/usr/bin/env python3
"""Load/list and cooperative retirement of real GemARC windows and instances."""
import argparse,json
from pathlib import Path
from native_program import ROOT,require
from build_gemarc import build as application
from test_gemarc_host import corpus,member
from os_boundary import run_to
from test_c_process import run as process_run


def run(out,reuse=False):
    out=out.resolve();out.mkdir(parents=True,exist_ok=True)
    # Build first so native observations use emitted offsets from this APP.
    app=application(out/'prepared-app')
    offset=app['image']['symbols']['nlist']-(app['abi']['link_bank']<<16)
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    source=out/'gemarc-ui.act'
    source.write_text(prefix+'''
CARD control,phase

PROC Ready(PROGRAMIMAGE.Image POINTER image)
  CARD turn

  LET count=CARD POINTER(ADDRESS(LONGCARD(ADDRESS(image.text))+LONGCARD($'''+format(offset,'x')+''')))
  FOR turn=0 TO 19999 DO
    IF count^=27 THEN
      RETURN
    FI

    EXEC.Yield()
  OD

  HEAPCORE.Abort($fbf0)

RETURN

LONGCARD FUNC Launch(PROGRAMIMAGE.Image POINTER image)

RETURN(PROCESS.StartLoaded(BYTE POINTER(image),BYTE POINTER(c"SYS:CORPUS.ARC"),14,0))

PROC Main()

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  LET warm=Load()
  LET first=Launch(warm)
  Require(first<>0)
  Ready(warm)
  phase=1
  WHILE control=0 DO
    EXEC.Yield()
  OD

  Require(PROCESS.RequestStop(first)<>0)
  Collected(first,0)
  PROGRAM.Unload(warm)
  baseline=EXEC.AvailMem(0)
  LET one=Load()
  LET two=Load()
  LET a=Launch(one)
  LET b=Launch(two)
  Require(a<>0 AND b<>0)
  Ready(one)
  Ready(two)
  Require(PROCESS.RequestStop(a)<>0 AND PROCESS.RequestStop(b)<>0)
  Collected(a,0)
  Collected(b,0)
  PROGRAM.Unload(one)
  PROGRAM.Unload(two)
  Require(EXEC.AvailMem(0)=baseline)
  LET service=AESSTATE.Get()
  Require(service.count=0 AND AESCORE.Idle(service)<>0)
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    def staged(target):
        import shutil
        target.mkdir(exist_ok=True)
        shutil.copyfile(out/'prepared-app/program.app',target/'program.app')
        return app
    def interact(b,program,application,record,owner):
        b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
        sy={name:owner['image_base']+address-(app['abi']['link_bank']<<16)
            for name,address in app['image']['symbols'].items()}
        native=lambda name:next(row['address'] for row in program['image']['data'] if row['name'].startswith('M_CPROCESSTEST_'+name.upper()+'_'))
        def reach(condition):
            b.bp_clear_all();b.bp_set(program['labels']['native_cop'],condition=condition)
            run_to(b,program['labels']['native_cop'],timeout=180,frame_limit=10000,condition=condition)
            b.bp_clear_all()
        def frames(count):
            reach('@frame>=%d'%(b.eval_expr('@frame')+count))
        def key(name,ctrl=False):
            if ctrl:b._cmd_ok('KEY CTRL down')
            b._cmd_ok('KEY '+name+' down');frames(4);b._cmd_ok('KEY '+name+' up')
            if ctrl:b._cmd_ok('KEY CTRL up')
            frames(6)
        reach('dw($%x)=1'%native('phase'))
        key('EQUALS',True);reach('dw($%x)=1'%sy['top'])
        key('MINUS',True);reach('dw($%x)=0'%sy['top'])
        key('A',True)
        pointer=int.from_bytes(b.memdump(sy['list'],4),'little')
        reach('&'.join('db($%x)=1'%(pointer+33*i+14) for i in (0,13,26)))
        record['physical_gui']=dict(scroll_down=True,scroll_up=True,select_all_members=27)
        b.memload(native('control'),b'\x01\0')
    result=process_run(out,True,reuse=reuse,rebuild_app=reuse,app_builder=staged,fixture_source=source,
        expected_completed=3,native_optimize=True,release_compiler=True,task_capacity=12,
        loader_failures=False,observe_stacks=True,interaction=interact,media_files={'GEMARC.RSC':(out/'prepared-app/GEMARC.RSC').read_bytes(),
            'CORPUS.ARC':b''.join(member(*row) for row in corpus()+[('E%07d.DAT'%i,2,b'',b'') for i in range(20)])+b'\x1a\0'})
    result['gemarc_ui']=dict(instances=3,concurrent=2,listed_members=27,
        cooperative_stop=True,exact_heap_restoration=True)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true');args=parser.parse_args()
    run(args.output,args.from_build)
