"""Private observation and failure injection for caller hidden-window lifetime."""
from pathlib import Path
from library_paths import read_source
from native_program import ROOT, require

ROOTS = ['LifeNative','LifeGate','LifeOwner','LifeWaiting','LifeNext','LifeBusy','LifeLocks','LifePhase']


def instrument(out):
    (out/'lifecycleprobe.act').write_text('''MODULE LIFECYCLEPROBE
USE EXEC
USE AESSTATE
USE AESGATE
USE HEAPCORE
PUBLIC CARD ARRAY stats(8)
PUBLIC BYTE busy
PUBLIC PROC Observe(BYTE deleting)
  BYTE slot

  LET service=AESSTATE.Get()
  IF service.sceneOwner<>EXEC.FindTask(NULL) THEN
    HEAPCORE.Abort($fc60)
  FI
  slot=2*deleting
  IF service.policyGate=AESGATE.CLOSED THEN
    slot==+1
  FI
  stats(slot)==+1
  stats(4)==+1
  stats(6)=SIZEOF(AESSTATE.Client)
  stats(7)=SIZEOF(AESSTATE.Service)

RETURN
ENDMODULE
''')
    source=read_source(ROOT/'lib/aes/aeswindow.act').replace('USE EXEC\n',
        'USE EXEC\nUSE LIFECYCLEPROBE\n',1)
    needle='PUBLIC BYTE FUNC Ready(AESSTATE.Service POINTER service\n    AESSTATE.Client POINTER client)\n'
    require(source.count(needle)==1,'Window admission boundary changed')
    source=source.replace(needle,needle+'\n  IF LIFECYCLEPROBE.busy<>0 THEN\n    RETURN(0)\n  FI\n')
    for routine,deleting in (('CreateHidden',0),('DeleteHidden',1)):
        start=source.index('PUBLIC CARD FUNC '+routine+'(')
        at=source.index('\n\n',start)+2
        source=source[:at]+f'  LIFECYCLEPROBE.Observe({deleting})\n'+source[at:]
    (out/'aeswindow.act').write_text(source)
    binding=read_source(ROOT/'c/calypsi/aes-windows.c').replace(
        '#include "aes-private.h"','#include "'+str(ROOT/'c/calypsi/aes-private.h')+'"\n'
        'APTR LifeAllocView(ULONG,ULONG);\nvoid LifeFreeView(APTR,ULONG);')
    require(binding.count('view=AllocMem(')==1,'View allocation boundary changed')
    binding=binding.replace('view=AllocMem(','view=LifeAllocView(')
    binding=binding.replace('FreeMem(view,','LifeFreeView(view,').replace('FreeMem(retired,','LifeFreeView(retired,')
    (out/'aes-windows.c').write_text(binding)


def emitter(original, out):
    def emit(output,sources,*args,**kwargs):
        sources=[out/'aes-windows.c' if Path(p)==ROOT/'c/calypsi/aes-windows.c' else p for p in sources]
        return original(output,sources,*args,**kwargs)
    return emit


def setup(symbols):
    fields={'LifeNative':'@LIFECYCLEPROBE.stats(0)','LifeBusy':'@LIFECYCLEPROBE.busy',
        'LifeGate':'@service.policyGate','LifeOwner':'@service.sceneOwner',
        'LifeWaiting':'@service.windowPending','LifeNext':'@service.nextWindow','LifeLocks':'@service.lockCount'}
    text=''
    for name,field in fields.items():
        text+=f'  BEGIN\n    LET target=LONGCARD POINTER(${symbols[name]:x})\n    target^=LONGCARD(ADDRESS({field}))\n  END\n'
    return text
