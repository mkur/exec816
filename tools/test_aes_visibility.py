"""GF7 private visibility and resource-admission boundaries."""
from generate_aes_server import layout
from generate_input_native import definitions
from library_paths import read_source
from native_program import ROOT,require
from os_boundary import run_to
import adapter_state as adapter

ROOTS=['VisNative','VisBusy','VisFail','VisFocus','VisHold','VisHeld','VisRelease',
       'VisEpoch','VisWaiting','VisLocks','VisOwner','VisPhase','VisGo','VisPoint',
       'VisOperation','VisResult','VisStatus','VisSequence','VisView',
       'VisPeerHeld','VisPeerRelease','VisWake','VisReady']


def instrument(out):
    (out/'visprobe.act').write_text('''MODULE VISPROBE
USE EXEC
USE INPUT
USE AESSTATE
USE AESTYPES
USE HEAPCORE
PUBLIC CARD ARRAY stats(8)
PUBLIC BYTE busy,failRoute,focusBusy,hold,held,release,ready

PUBLIC PROC Outside()

  LET service=AESSTATE.Get()
  EXEC.Forbid()
  IF service.sceneOwner=EXEC.FindTask(NULL) THEN
    HEAPCORE.Abort($fc68)
  FI
  EXEC.Permit()

RETURN

PUBLIC PROC Observe(AESSTATE.Client POINTER client CARD operation)
  BYTE slot

  LET service=AESSTATE.Get()
  IF service.sceneOwner<>EXEC.FindTask(NULL) THEN
    HEAPCORE.Abort($fc69)
  FI
  IF client.id=1 THEN
    slot=2*BYTE(operation=AESTYPES.OP_CLOSE)+BYTE(service.sceneOwner=service.owner)
    stats(slot)==+1
    stats(6)=SIZEOF(AESSTATE.Client)
    stats(7)=SIZEOF(AESSTATE.Service)
  FI

RETURN

PUBLIC CARD FUNC Create(INPUT.Lease POINTER lease CARD flags LONGCARD POINTER tag)
  LONGCARD ARRAY reserved(16)
  BYTE count,index
  CARD status

  Outside()
  stats(4)==+1
  count=0
  IF failRoute<>0 THEN
    WHILE count<16 DO
      status=INPUT.CreateRoute(lease,flags,@reserved(count))
      IF status<>INPUT.OK THEN
        EXIT
      FI
      count==+1
    OD
  FI
  status=INPUT.CreateRoute(lease,flags,tag)
  index=0
  WHILE index<count DO
    IF INPUT.RetireRoute(lease,reserved(index))<>INPUT.OK THEN
      HEAPCORE.Abort($fc6a)
    FI
    index==+1
  OD
  IF hold<>0 THEN
    held=1
    WHILE release=0 DO
      EXEC.Yield()
    OD
  FI

RETURN(status)

PUBLIC PROC Rollback()

  Outside()
  stats(5)==+1

RETURN
ENDMODULE
''')
    source=read_source(ROOT/'lib/aes/aeswindow.act').replace(
        'USE EXEC\n','USE EXEC\nUSE VISPROBE\n',1)
    needle='PUBLIC BYTE FUNC Ready(AESSTATE.Service POINTER service\n    AESSTATE.Client POINTER client)\n'
    require(source.count(needle)==1,'Window readiness boundary changed')
    source=source.replace(needle,needle+'\n  IF VISPROBE.busy<>0 THEN\n    RETURN(0)\n  FI\n')
    start=source.index('PUBLIC CARD FUNC Visibility(')
    at=source.index('\n\n',start)+2
    source=source[:at]+'''  IF request.operation=AESTYPES.OP_OPEN THEN
    VISPROBE.Observe(client,request.operation)
  FI
'''+source[at:]
    start=source.index('BYTE FUNC Close(');at=source.index('\n\n',start)+2
    source=source[:at]+'''  VISPROBE.Observe(AESSTATE.Find(AESSTATE.Get(),item.owner),
      AESTYPES.OP_CLOSE)
'''+source[at:]
    (out/'aeswindow.act').write_text(source)
    routes=read_source(ROOT/'lib/aes/aesroutes.act').replace(
        'USE INPUT\n','USE INPUT\nUSE VISPROBE\n',1)
    needle='status=INPUT.CreateRoute(keyboard,INPUT.ROUTE_UNFILTERED,route)'
    require(routes.count(needle)==1,'Route allocation boundary changed')
    routes=routes.replace(needle,'status=VISPROBE.Create(keyboard,INPUT.ROUTE_UNFILTERED,route)')
    start=routes.index('PUBLIC PROC Discard(');at=routes.index('\n\n',start)+2
    routes=routes[:at]+'  VISPROBE.Rollback()\n'+routes[at:]
    (out/'aesroutes.act').write_text(routes)
    core=read_source(ROOT/'lib/desktop/deskcore.act').replace(
        'USE EXEC\n','USE EXEC\nUSE VISPROBE\n',1)
    start=core.index('PUBLIC BYTE FUNC FocusMetadataReady(')
    at=core.index('\n\n',start)+2
    core=core[:at]+'  IF VISPROBE.focusBusy<>0 THEN\n    RETURN(0)\n  FI\n'+core[at:]
    (out/'deskcore.act').write_text(core)
    driver=read_source(ROOT/'lib/console/consoledriver.act').replace(
        'USE AESGATE\n','USE AESGATE\nUSE VISPROBE\n',1)
    require(driver.count('    AESGATE.Offer()')==1,'Presenter offer boundary changed')
    driver=driver.replace('    AESGATE.Offer()',
        '    VISPROBE.ready=policyReady AND DESKPAINT.Runnable()=0\n'
        '        AND CONSOLEBITMAP.Pending()=0\n    AESGATE.Offer()')
    (out/'consoledriver.act').write_text(driver)


def worker_probe(original,out):
    def policy(*args,**kwargs):
        directory=original(*args,**kwargs)
        text=(out/'consoledriver.act').read_text().replace('"console-storage-action.inc"',
            '"'+str(directory.parent/'console-storage-action.inc')+'"')
        (directory/'consoledriver.act').write_text(text)
        return directory
    return policy


def setup(symbols):
    fields={'VisNative':'@VISPROBE.stats(0)','VisBusy':'@VISPROBE.busy',
            'VisFail':'@VISPROBE.failRoute','VisFocus':'@VISPROBE.focusBusy',
            'VisHold':'@VISPROBE.hold','VisHeld':'@VISPROBE.held',
            'VisRelease':'@VISPROBE.release','VisReady':'@VISPROBE.ready',
            'VisEpoch':'@service.nextGuiEpoch','VisWaiting':'@service.windowPending',
            'VisLocks':'@service.lockCount','VisOwner':'@service.sceneOwner'}
    text='  DESKBOOT.Detach()\n'
    for name,field in fields.items():
        text+=f'  BEGIN\n    LET target=LONGCARD POINTER(${symbols[name]:x})\n    target^=LONGCARD(ADDRESS({field}))\n  END\n'
    return text


def physical(b,p,foreign,report):
    sy=foreign['symbols'];vf=layout()['WindowView']['fields']
    get=lambda address,size=2:int.from_bytes(b.memdump(address,size),'little')
    val=lambda name,size=2:get(sy[name],size)
    pointer=lambda name:val(name,4)
    def reach(condition):
        b.bp_clear_all()
        b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
    def phase(number,point):
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(sy['VisPhase'],number,sy['VisPoint'],point))
    tags=p['build']['memory']['input_storage']['STATE']+definitions()[0]['STATE_TAGS']
    report['visibility']=[]
    for number in range(1,15):
        print('Visibility phase',number,flush=True);phase(number,0)
        b.poke(pointer('VisReady'),0)
        b.poke16(sy['VisWake'],1)
        reach('db($%x)=1'%pointer('VisReady'))
        before=[get(pointer('VisNative')+2*i) for i in range(8)]
        old_tags=b.memdump(tags,64);epoch=get(pointer('VisEpoch'),4)
        if number==7:b.poke(pointer('VisFail'),1)
        if number==8:b.memload(pointer('VisEpoch'),bytes(4))
        if number==9:b.poke(pointer('VisHold'),1)
        if number==11:b.poke(pointer('VisBusy'),1)
        if number==13:b.poke(pointer('VisFocus'),1)
        b.poke16(sy['VisGo'],number*2-1)
        if number==9:
            reach('dw($%x)=1'%sy['VisPeerHeld'])
            require(get(pointer('VisHeld'),1)==1,'Peer acquired UPDATE before resource release')
            b.poke(pointer('VisRelease'),1)
        if number in (9,11):
            reach('db($%x)>0'%pointer('VisWaiting'))
            require(b.memdump(tags,64)==old_tags,'Pending open leaked its unpublished route')
            if number==9:b.poke16(sy['VisPeerRelease'],1)
            else:
                b.poke(pointer('VisBusy'),0);b.poke16(sy['VisWake'],1)
        phase(number,3)
        operation=val('VisOperation')
        direct=number not in (9,11,13) and (operation==101 or report['visibility_local']=='all')
        attempts=[get(pointer('VisNative')+2*i)-before[i] for i in range(8)]
        require(val('VisSequence',4)==(0 if direct else 1),
                f'Phase {number}: wrong transport; sequence={val("VisSequence",4)}, attempts={attempts}')
        slot=2*(operation==102)
        if direct:
            require(attempts[slot]>0 and attempts[slot+1]==0,f'Phase {number}: wrong Task')
        else:
            require(attempts[slot+1]>0,f'Phase {number}: no system continuation')
        if number in (7,8):require(b.memdump(tags,64)==old_tags,'Failed open leaked a route')
        view=val('VisView',4)
        state={n:get(view+vf[n],size) for n,size in [('handle',2),('shown',2),('epoch',4)]}
        state['bounds']=[get(view+vf['bounds']+2*i) for i in range(4)]
        report['visibility'].append(dict(phase=number,operation=operation,result=val('VisResult'),
            status=val('VisStatus'),sequence_delta=val('VisSequence',4),attempts=attempts,view=state))
        if number==7:b.poke(pointer('VisFail'),0)
        if number==8:b.memload(pointer('VisEpoch'),epoch.to_bytes(4,'little'))
        if number==9:b.poke(pointer('VisHold'),0)
        if number==13:b.poke(pointer('VisFocus'),0)
        b.poke16(sy['VisGo'],number*2)
    b.bp_clear_all()
