"""Start and cooperatively retire every shipped APP on the current provider."""
import json,struct,shutil
from pathlib import Path
from native_program import ROOT,require,sha256
from c_program import ABI
from test_c_process import run as process_run


def run(out,applications,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    records={name:json.loads((applications/'apps'/name/'app.json').read_text())
             for name in ('panel','counter','files','desktop','dialog','calc','g4bench','text','basic','gemarc')}
    media={}
    for name,app in records.items():
        path=applications/'apps'/name/'program.app'
        require(app['abi']==ABI and sha256(path)==app['sha256'],'Stale shipped APP: '+name)
        for source,digest in {**app['inputs'],**app['c_runtime']['inputs']}.items():
            require(sha256(Path(source))==digest,'Changed shipped APP source: '+source)
        media[name.upper()+'.APP']=path.read_bytes()
    media['CALC.RSC']=(applications/'apps/calc/CALC.RSC').read_bytes()
    media['GEMARC.RSC']=(applications/'apps/gemarc/GEMARC.RSC').read_bytes()
    old=bytearray(media['PANEL.APP']);struct.pack_into('<H',old,6,ABI['version']-1)
    media['OLD.APP']=old
    prefix=(ROOT/'tests/programs/c_process.act').read_text().split('\nPROC Main()')[0]
    fixture=out/'applications.act'
    fixture.write_text(prefix+'''
CARD currentApp
BYTE ARRAY resourceChunk(256)

PROC InstallResource()
  LONGINT count

  LET source=DOS.Open(BYTE POINTER(c"SYS:DESKTOP.RSC"),DOS.MODE_OLDFILE)
  LET target=DOS.Open(BYTE POINTER(c"RAM:DESKTOP.RSC"),DOS.MODE_NEWFILE)
  Require(source<>NULL AND target<>NULL)
  DO
    count=DOS.Read(source,@resourceChunk(0),SIZEOF(resourceChunk))
    Require(count>=0)
    IF count=0 THEN
      EXIT
    FI

    Require(DOS.Write(target,@resourceChunk(0),count)=count)
  OD
  Require(DOS.Close(source)<>0 AND DOS.Close(target)<>0)

RETURN

PROC RunApp(BYTE POINTER name)
  BYTE turn
  PROCESS.Result result

  currentApp==+1
  LET image=PROGRAMFILE.Load(name)
  Require(image<>NULL)
  LET child=PROCESS.StartLoaded(BYTE POINTER(image),BYTE POINTER(c""),0,0)
  Require(child<>0)
  FOR turn=0 TO 127 DO
    EXEC.Yield()
  OD

  LET service=AESSTATE.Get()
  Require(service.count=1 AND image.running<>0)
  Require(PROCESS.RequestStop(child)<>0)
  Require(PROCESS.Wait(child,@result)<>0)
  lastPrimary=result.primary
  Require(result.primary=0 AND result.secondary=0)
  PROGRAM.Unload(image)
  Require(service.count=0 AND AESCORE.Idle(service)<>0)
  completed==+1

RETURN

PROC Main()

  LET input=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_OLDFILE)
  LET output=DOS.Open(BYTE POINTER(c"NIL:"),DOS.MODE_NEWFILE)
  Require(input<>NULL AND output<>NULL)
  LET oldInput=DOS.SelectInput(input)
  LET oldOutput=DOS.SelectOutput(output)
  InstallResource()
  RunApp(BYTE POINTER(c"SYS:PANEL.APP"))
  baseline=EXEC.AvailMem(0)
'''+''.join('  RunApp(BYTE POINTER(c"SYS:'+name.upper()+'.APP"))\n'
            '  Require(EXEC.AvailMem(0)=baseline)\n' for name in records)+'''
  Bad(BYTE POINTER(c"SYS:OLD.APP"),LONGINT(O65TYPES.ERROR_BAD_FORMAT))
  DOS.SelectInput(oldInput)
  DOS.SelectOutput(oldOutput)
  Require(DOS.Close(input)<>0 AND DOS.Close(output)<>0)
  Require(DOS.ReleaseContext()<>0)

RETURN

ENDMODULE
''')
    def application(target):
        target.mkdir(exist_ok=True)
        shutil.copyfile(applications/'apps/panel/program.app',target/'program.app')
        return records['panel']
    result=process_run(out,True,reuse=reuse,rebuild_app=reuse,app_builder=application,fixture_source=fixture,
        expected_completed=1+len(records),task_capacity=12,native_optimize=True,release_compiler=True,
        loader_failures=False,media_files=media,ram=True)
    result['shipped_applications']={name:dict(sha256=app['sha256'],minimum_stack=app['minimum_stack'])
                                   for name,app in records.items()}
    result['obsolete_abi_rejected']=ABI['version']-1
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--applications',type=Path,required=True)
    parser.add_argument('--from-build',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.applications.resolve(),args.from_build)
