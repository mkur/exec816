#!/usr/bin/env python3
"""Reuse the session ownership fixture with a desktop bind held across CLOSE."""
import argparse
import json
from pathlib import Path

from build_bitmap_console import build_bitmap
from library_paths import read_source
from native_program import ROOT, read_build, require, verify_machine
from os_boundary import emulator
from test_mouse_observe import PIN, BRIDGE, ROM
from test_dos_stack import execute, ownership
from test_cooperative import data


def run(out,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    source=read_source(ROOT/'tests/programs/shell_two_sessions.act')
    source=source.replace('USE FSBOOT\n','USE FSBOOT\nUSE DESKPAINT\nUSE LAYERS\nUSE LAYERTYPES\n')
    source=source.replace('LONGCARD baseline,peer','LONGCARD closeTarget,baseline,peer')
    helper='''; A distinct producer keeps one ordinary request outstanding per Task.
LONGINT FUNC ClosePending()
  BYTE ignored
  ShellSessionControl control

  control.port=shellRequests
  LET request=ShellSessionMessage POINTER(EXEC.AllocMem(
      SHELLSESSIONMESSAGE_SIZE,EXEC.MEMF_UPPER OR EXEC.MEMF_CLEAR))
  Check(request<>NULL)
  request.operation=SESSION_CLOSE
  request.session=closeTarget
  ignored=ShellSessionExchange(@control,request)
  Check(request.primary=0)
  EXEC.FreeMem(BYTE POINTER(request),SHELLSESSIONMESSAGE_SIZE)

RETURN(0)

'''
    source=source.replace('LONGINT FUNC Producer()',helper+'LONGINT FUNC Producer()')
    source=source.replace('LONGCARD first,second,replacement,available,oldUnit','LONGCARD first,second,replacement,available,oldUnit,token,closer\n  EXEC.Message POINTER reply')
    original='''  request.operation=SESSION_SELECT
  request.session=first
  ignored=ShellSessionExchange(@control,request)
  Check(request.primary=0 AND selectedSession=first)
  request.operation=SESSION_CLOSE
  ignored=ShellSessionExchange(@control,request)
  Check(request.primary=0)
'''
    replacement='''  ; Hold an existing scene transaction while root admits the bind.
  LET desktop=DESKSTATE.Get()
  WHILE desktop.scene.busy<>0 OR DESKPAINT.Runnable()<>0 DO
    EXEC.Yield()
  OD
  EXEC.Forbid()
  Check(LAYERS.Invalidate(@desktop.scene,0,@desktop.scene.screen)=LAYERTYPES.OK)
  Check(LAYERS.BeginPaint(@desktop.scene,0,@token)=LAYERTYPES.OK)
  EXEC.Permit()
  LET port=EXEC.CreateMsgPort()
  Check(port<>NULL)
  request.operation=SESSION_SELECT
  request.session=first
  request.message.mn_Node.ln_Type=EXEC.NT_MESSAGE
  request.message.mn_ReplyPort=port
  request.message.mn_Length=SHELLSESSIONMESSAGE_SIZE
  EXEC.PutMsg(shellRequests,@request.message)
  WHILE desktopPending=0 DO
    EXEC.Yield()
  OD
  Check(desktopTarget=first AND selectedSession=second)
  closeTarget=first
  closer=PROCESS.Start(@ClosePending,NULL,0)
  Check(closer<>0)
  Check(PROCESS.Wait(closer,@result)<>0 AND result.primary=0)
  ; Cancellation may need a final console write, so accepted close retains
  ; the Process until the held paint is released as well.
  Check(sessions(0).control.closeRequested<>0
      AND (sessions(0).state=SESSION_STATE_CLOSING
        OR sessions(0).state=SESSION_STATE_RETIRING))
  Check(desktopPending<>0 AND desktopTarget=first)
  Check(sessions(0).control.identity=first AND controllerLive=2)
  Check(LAYERS.Finish(@desktop.scene,token,0)=LAYERTYPES.OK)
  reply=EXEC.WaitPort(port)
  reply=EXEC.GetMsg(port)
  Check(reply=@request.message AND request.primary=PROCESS.RETURN_ERROR)
  EXEC.DeleteMsgPort(port)
'''
    require(source.count(original)==1,'Session close fixture boundary changed')
    source=source.replace(original,replacement)
    path=out/'lifetime.act';path.write_text(source)
    from generate_memory import PROFILE
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=9216
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=read_build(out/'program') if reuse else build_bitmap(path,out,desktop=True,
        release_compiler=True,dos_mounts=[],memory_profile=memory)
    report=dict(status='running',tier='development',qualification=False,build=p['build'])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            report['machine']=verify_machine(b,ROM,PIN)
            try:
                report['runtime'],_=execute(b,p,timeout=60,frame_limit=6000)
            except Exception:
                print('Desktop ownership checks',data(b,p['image'],'checks',True),flush=True)
                for name in ('desktopPending','desktopTarget','selectedSession','controllerLive','closeTarget'):
                    item=next(d for d in p['image']['data'] if '_'+name.upper()+'_' in d['name'])
                    print(name,int.from_bytes(b.memdump(item['address'],item['size']),'little'),flush=True)
                item=next(d for d in p['image']['data'] if '_SESSIONS_' in d['name'])
                for index in range(2):
                    raw=b.memdump(item['address']+330*index,330)
                    print('session',index,'state',raw[328],'process',int.from_bytes(raw[318:322],'little'),'close',raw[273],flush=True)
                raise
            ownership(b,p,p['output'])
            report['checks']=data(b,p['image'],'checks',True)[0]
            require(data(b,p['image'],'finished')==[1],'Missing final ownership check')
            report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:
        (out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    print('Desktop session lifetime passed',report['checks'],'checks',flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    args=parser.parse_args();run(args.output.resolve(),args.reuse)
