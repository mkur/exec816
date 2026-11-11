"""GF6 private metadata observation and bounded call timing."""
import json
from pathlib import Path
import adapter_state as adapter
from generate_aes_server import layout
from library_paths import read_source
from native_program import ROOT,require
from os_boundary import run_to
from sio_transaction_trace import read_events,BASE_HZ

ROOTS=['GeoNative','GeoBusy','GeoWaiting','GeoLocks','GeoPhase','GeoGo','GeoPoint',
       'GeoField','GeoHandle','GeoResult','GeoStatus','GeoSequence','GeoView',
       'GeoCallBegin','GeoCallEnd']


def instrument(out):
    (out/'geoprobe.act').write_text('''MODULE GEOPROBE
USE EXEC
USE AESSTATE
USE AESGATE
USE HEAPCORE
PUBLIC CARD ARRAY stats(4)
PUBLIC BYTE busy
PUBLIC PROC Observe(BYTE mutation)

  LET service=AESSTATE.Get()
  IF service.sceneOwner<>EXEC.FindTask(NULL) THEN
    HEAPCORE.Abort($fc64)
  FI
  LET slot=2*mutation+BYTE(AESGATE.SystemOwned()<>0)
  stats(slot)==+1

RETURN
ENDMODULE
''')
    text=read_source(ROOT/'lib/aes/aeswindow.act').replace('USE EXEC\n','USE EXEC\nUSE GEOPROBE\n',1)
    needle='PUBLIC BYTE FUNC Ready(AESSTATE.Service POINTER service\n    AESSTATE.Client POINTER client)\n'
    require(text.count(needle)==1,'Window admission boundary changed')
    text=text.replace(needle,needle+'\n  IF GEOPROBE.busy<>0 THEN\n    RETURN(0)\n  FI\n')
    for signature,call in [('INT FUNC FindAt(', '  GEOPROBE.Observe(0)\n')]:
        start=text.index(signature);at=text.index('\n\n',start)+2
        text=text[:at]+call+text[at:]
    if 'PUBLIC CARD FUNC Geometry(' in text:
        start=text.index('PUBLIC CARD FUNC Geometry(');at=text.index('\n\n',start)+2
        text=text[:at]+'  GEOPROBE.Observe(1)\n'+text[at:]
    else:
        start=text.index('PUBLIC CARD FUNC Request(');at=text.index('\n\n',start)+2
        text=text[:at]+'''  IF request.operation=AESTYPES.OP_SET AND
      (request.intin(1)=AESTYPES.WF_CXYWH OR request.intin(1)=AESTYPES.WF_TOP) THEN
    GEOPROBE.Observe(1)
  FI
'''+text[at:]
    (out/'aeswindow.act').write_text(text)


def setup(symbols):
    text=''
    for name,field in [('GeoNative','@GEOPROBE.stats(0)'),('GeoBusy','@GEOPROBE.busy'),
                       ('GeoWaiting','@service.windowPending'),('GeoLocks','@service.lockCount')]:
        text+=f'  BEGIN\n    LET target=LONGCARD POINTER(${symbols[name]:x})\n    target^=LONGCARD(ADDRESS({field}))\n  END\n'
    return text


def physical(b,p,foreign,report):
    b.profile_start();sy=foreign['symbols'];vf=layout()['WindowView']['fields']
    get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
    val=lambda name,size=2:get(sy[name],size)
    def reach(phase,point):
        condition='(dw($%x)=%d)&(dw($%x)=%d)'%(sy['GeoPhase'],phase,sy['GeoPoint'],point)
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        original=b.regs
        def registers():
            r=original()
            if int(r['PC'].lstrip('$'),16)==p['labels']['done']:
                raise RuntimeError('Geometry fixture stopped: '+hex(get(adapter.STATE)))
            return r
        b.regs=registers
        try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        finally:b.regs=original
    report['geometry']=[]
    for phase in range(1,21):
        print('Geometry phase',phase,flush=True);reach(phase,0)
        before=[get(val('GeoNative',4)+2*i) for i in range(4)]
        b.poke16(sy['GeoGo'],phase*2-1);reach(phase,3)
        field=val('GeoField');direct=report['geometry_local']=='all' or (field==106 and report['geometry_local']=='query')
        require(val('GeoSequence',4)==(0 if direct else 1),f'Geometry phase {phase}: wrong transport')
        stats=[get(val('GeoNative',4)+2*i)-before[i] for i in range(4)]
        offset=0 if field==106 else 2
        require(stats[offset]>0 and stats[offset+1]==0 if direct else stats[offset]==0 and stats[offset+1]>0,
                f'Geometry phase {phase}: wrong executing Task {stats}')
        view=val('GeoView',4);raw=b.memdump(view,layout()['WindowView']['size'])
        state={n:int.from_bytes(raw[vf[n]:vf[n]+size],'little') for n,size in
               [('handle',2),('shown',2),('revision',4),('pixelsReady',2),('epoch',4),('visibleCount',2)]}
        for n in ['bounds','work']:
            state[n]=[int.from_bytes(raw[vf[n]+2*i:vf[n]+2*i+2],'little',signed=True) for i in range(4)]
        state['visible']=[list(int.from_bytes(raw[vf['visible']+i*8+j*2:vf['visible']+i*8+j*2+2],'little',signed=True)
                               for j in range(4)) for i in range(state['visibleCount'])]
        report['geometry'].append(dict(phase=phase,field=field,result=val('GeoResult'),status=val('GeoStatus'),
            sequence_delta=val('GeoSequence',4),helper_attempts=stats,view=state))
        b.poke16(sy['GeoGo'],phase*2)
    b.bp_clear_all()


def timings(out,foreign,report):
    names={foreign['symbols'][n]:n for n in ['GeoCallBegin','GeoCallEnd']}
    events=[(t,names[int(e[4],16)]) for t,e in read_events(out/'emulator.log',{'cpu'}) if int(e[4],16) in names]
    require(len(events)==40,'Incomplete geometry call brackets')
    for row,i in zip(report['geometry'],range(0,40,2)):
        (start,a),(end,z)=events[i:i+2];require((a,z)==('GeoCallBegin','GeoCallEnd'),'Geometry marker order changed')
        row['call_ms']=(end-start)/BASE_HZ*1000
    report['geometry_timing_scope']='Exact external C call brackets, inclusive of caller waits/preemption; physical input-to-pixels is observed separately in the current queued-UPDATE drag package.'
