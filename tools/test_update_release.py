#!/usr/bin/env python3
"""Small emitted production UPDATE release/arm protocol and native FIFO cases."""
import argparse,json,re
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
from test_mouse_observe import BRIDGE,ROM,PIN


def run(out):
    out.mkdir(parents=True,exist_ok=True)
    source=ROOT/'lib/aes/aeslocks.act';text=source.read_text();bodies=[]
    starts=list(re.finditer(r'(?m)^(?:PUBLIC )?(?:PROC|(?:BYTE|CARD|LONGCARD) FUNC) (\w+)\(',text))
    for name in ('Notify','ReturnResource','PaintBlocked','SystemBlocked','Release'):
        match=next(m for m in starts if m[1]==name)
        end=next((m.start() for m in starts if m.start()>match.start()),text.index('ENDMODULE'))
        body=text[match.start():end].rstrip()
        body=re.sub(r'^(?:PUBLIC )?','PUBLIC ',body,count=1)
        body=body.replace('AESSTATE.','RELEASESTATE.').replace('AESWINDOWSTATE.','RELEASESTATE.').replace('AESMOUSE.','RELEASESTATE.')
        if name=='SystemBlocked':
            body=body.replace('  EXEC.Forbid()','  RELEASESTATE.BeforeArm()\n  EXEC.Forbid()',1)
        bodies.append(body+'\n\n')
    (out/'releasepolicy.act').write_text('MODULE RELEASEPOLICY\nUSE EXEC\nUSE AESTYPES\nUSE RELEASESTATE\nBYTE systemHeld\n'+''.join(bodies)+'ENDMODULE\n')
    (out/'releasestate.act').write_text('''MODULE RELEASESTATE
USE EXEC
PUBLIC CONST UPDATE_WAITING=1
PUBLIC TYPE Client=[LONGCARD id]
PUBLIC TYPE Service=[
  EXEC.Task POINTER owner
  LONGCARD mask,updateOwner,mouseOwner
  CARD updates,updateHolds,mouseHolds
  INT updateWindow
  BYTE live,updateHint
  EXEC.SignalSemaphore updateResource
]
PUBLIC Service storage
PUBLIC BYTE mouseDirty,releaseBeforeArm
PUBLIC Service POINTER FUNC Get()
RETURN(@storage)
PUBLIC PROC Updates(Client POINTER client CARD count)
RETURN
PUBLIC PROC EndUpdate(Client POINTER client)
RETURN
PUBLIC PROC Refresh()
RETURN
PUBLIC PROC BeforeArm()
  IF releaseBeforeArm<>0 THEN
    releaseBeforeArm=0
    storage.updates=0
    EXEC.ReleaseSemaphore(@storage.updateResource)
  FI
RETURN
ENDMODULE
''')
    import shutil
    shutil.copyfile(ROOT/'tests/programs/update_release.act',out/'update_release.act')
    p=build(compiler(ROOT/'build/actionc',release=True),out/'update_release.act',out/'program',tasks=True,optimize=True,task_capacity=4)
    with emulator(BRIDGE,ROM,out,pin=PIN) as b:
        machine=verify_machine(b,ROM,PIN);runtime,_=execute(b,p,timeout=120,frame_limit=1800)
        ownership(b,p,p['output']);checks=data(b,p['image'],'checks',True)[0]
        require(checks>=25,'Incomplete release cases')
    report=dict(status='pass',tier='development',qualification=False,checks=checks,source_sha256=sha256(source),
        native_sha256=sha256(p['xex']),machine=machine,runtime=runtime,
        scope='Production Release/Notify/ReturnResource/SystemBlocked; journal/mouse edges substituted. One deterministic release injected between initial check and guarded arm; two real native FIFO contenders.',
        bank_zero_reserved_delta_bytes=dict(fixed=0,root=0,kernel=0,idle=0,per_public_task=0))
    (out/'results.json').write_text(json.dumps(report,indent=2)+'\n');print('UPDATE release checks:',checks)

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True)
    run(a.parse_args().output.resolve())
