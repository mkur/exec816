#!/usr/bin/env python3
"""Exercise the actual source engines through emitted Exec Processes."""
import argparse
import hashlib
import json
from decimal import Decimal
from pathlib import Path

from native_program import ROOT, build, compiler, read_build, require, verify_machine
from build_fastbasic import sha256
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
from test_sdx_md5 import PIN


def fixture(out,group):
    files={name+'.COM':(ROOT/'build/fastbasic'/ (name+'.COM')).read_bytes() for name in ('FB','FBI')}
    if group=='attach':files['FBCI.COM']=(ROOT/'build/fastbasic/FBCI.COM').read_bytes()
    calls=[];expected=b'';cases=[]
    def case(engine,name,raw,answer=b'',cause=0,location=None):
        nonlocal expected
        filename=f'S{len(cases)}.BAS';files[filename]=raw
        args='RAM:'+filename
        cases.append(dict(engine=engine,name=name,source_sha256=hashlib.sha256(raw).hexdigest(),cause=cause,line_start=expected.count(b'\x9b')))
        if cause:
            calls.append('  LET errorFile'+str(len(cases))+'=DOS.Open(BYTE POINTER(c"RAM:ERROR.TXT"),DOS.MODE_NEWFILE)\n  Require(errorFile'+str(len(cases))+'<>NULL)\n  LET saved'+str(len(cases))+'=DOS.SelectOutput(errorFile'+str(len(cases))+')')
        if group=='attach':
            invocation=f'RunAttached(BYTE POINTER(c"RAM:{engine}.COM"),BYTE POINTER(SOURCE_BUFFER_{len(cases)}),{len(raw)},{len(cases)},{20 if cause else 0})'
        else:
            invocation=f'Run(BYTE POINTER(c"RAM:{engine}.COM"),BYTE POINTER(c"{args}"),{len(args)},{20 if cause else 0})'
        calls.append(f'  currentCase={len(cases)}\n  {invocation}\n  Require(secondary={cause})')
        if location:
            calls.append(f'  Require(sourceLine={location[0]})\n  Require(sourceColumn={location[1]})')
        if cause:
            calls.append('  DOS.SelectOutput(saved'+str(len(cases))+')\n  Require(DOS.Close(errorFile'+str(len(cases))+')<>0)')
        expected+=answer
    if group=='session':
        for engine in ('FBI','FB'):
            calls.append(f'  Open(BYTE POINTER(c"RAM:{engine}.COM"))')
            def retained(raw,answer=b'',error=0):
                nonlocal expected
                number=len(cases)+1;address=f'RETAINED_SOURCE_{number}'
                cases.append(dict(engine=engine,name='session-'+str(number)))
                files[f'R{number}.BAS']=raw
                calls.append(f'  currentCase={number}\n  Run(BYTE POINTER({address}),{len(raw)},{error})')
                expected+=b'parse error' if error==306 else answer
            retained(b'A=7\nS$="saved"\nDIM V(2) WORD\nV(1)=42\n')
            retained(b'DIM V(2) WORD\n? A:? S$:? V(1)\nA=A+1\n',b'7\x9bsaved\x9b42\x9b')
            retained(b'B=99:? A:? B\n',b'8\x9b99\x9b')
            retained(b'A=1: ???\n',error=306)
            retained(b'? A:? S$:? V(1)\n',b'8\x9bsaved\x9b42\x9b')
            retained(b'DIM V(3) WORD\n',error=115)
            retained(b'DIM H(20000) BYTE\n',error=103)
            retained((b"'"+b'x'*254+b'\n')*128,error=103)
            retained(b'? A:? V(1)\n',b'8\x9b42\x9b')
            retained(b'OPEN #1,8,0,"RAM:KEEP.TXT"\n? #1,"kept"\n')
            calls.append('  Require(state.guest.handles(1)<>NULL)')
            retained(b'? #1,"across runs"\nCLOSE #1\n')
            calls.append('  Require(state.guest.handles(1)=NULL)')
            if engine=='FB':
                retained(b'X%=1.25\nDEG\n')
                retained(b'? X%:? SIN(90.0)\n',b'1.25\x9b1\x9b')
            raw=b'A=A+2\nDO: LOOP\n';number=len(cases)+1
            files[f'R{number}.BAS']=raw;cases.append(dict(engine=engine,name='stop'))
            calls.append(f'''  Submit(FBINTERPABI.COMMAND_RUN,BYTE POINTER(RETAINED_SOURCE_{number}),{len(raw)})
  WHILE SDXSTATE.ReadWord(state.guest.bank,FBINTERPABI.SESSION_VARIABLE_BASE)<>10 DO
    EXEC.Yield()
  OD
  Require(PROCESS.RequestBreak(identity)<>0)
  Reply()
  Require(secondary=304)''')
            retained(b'? A:? S$:? V(1)\nOPEN #1,8,0,"RAM:RESET.TXT"\n',b'10\x9bsaved\x9b42\x9b')
            calls.append('  Require(state.guest.handles(1)<>NULL)')
            calls.append('''  Submit(FBINTERPABI.COMMAND_RESET,NULL,0)
  Reply()
  Require(secondary=0)
  Require(state.interpreter.symbolBytes=0)
  Require(state.interpreter.prepared=0)
  Require(state.guest.handles(1)=NULL)''')
            retained(b'? A\n',error=306)
            retained(b'A=3:? A\n',b'3\x9b')
            calls.append('  Close()')
    elif group=='core':
        for engine,names in [('FBI',('hello','values','files','clock')),('FB',('fp_math','fp_values','fp_clock'))]:
            for name in names:
                raw=(ROOT/f'tests/fastbasic/{name}.bas').read_bytes()
                answer=(ROOT/f'tests/fastbasic/{name}.out').read_bytes().replace(b'\r\n',b'\n').replace(b'\n',b'\x9b')
                case(engine,name,raw,answer)
    elif group=='profile':
        for engine,raw,answer in (('FBI',b'? 6*7',b'42\x9b'),('FB',b'? 1.25*2.0',b'2.5\x9b')):
            for temperature in ('cold','warm'):case(engine,temperature,raw,answer)
    elif group in ('entry','attach','text'):
        case('FBI','integer',b'? 6*7',b'42\x9b')
        case('FB','float',b'? 1.25*2.0',b'2.5\x9b')
    elif group=='capacity':
        for engine,maximum in (('FBI',39164),('FB',35580)):
            source=f'DIM A(${maximum:X}) BYTE\nA(${maximum:X})=123\n? A(${maximum:X})\n'.encode()
            case(engine,'largest-array',source,b'123\x9b')
            source=f'DIM A(${maximum+1:X}) BYTE\n? "SHOULD NOT RUN"\n'.encode()
            case(engine,'one-past-array',source,cause=103)
            case(engine,'recovery',b'? 42\n',b'42\x9b')
    elif group=='transitions':
        for engine in ('FBI','FB'):
            for stage in (1,2,3,4):
                calls.append(f'  FBITRACE.wanted={stage}')
                case(engine,f'cancel-stage-{stage}',b'POKE 2304,1\n? 42\n',cause=304)
            calls.append('  FBITRACE.wanted=0')
            case(engine,'fresh-after-stop',b'? 42\n',b'42\x9b')
    elif group=='faults':
        for engine in ('FBI','FB'):
            for mode,error in ((1,0),(2,221),(3,213),(4,221),(8,221),(16,0),(0,0)):
                calls.append(f'  FBISOURCEFAULT.mode={mode}')
                case(engine,f'fault-{mode}',b'? "FAULT RECOVERY"\n',b'FAULT RECOVERY\x9b' if not error else b'',error)
            case(engine,'runtime-oom',(ROOT/'tests/fastbasic/allocation.bas').read_bytes(),cause=103)
            case(engine,'parser-oom',(b'? "'+b'x'*240+b'"\n')*128,cause=103)
    else:
        for engine in ('FBI','FB'):
            for name,raw,answer in [('empty',b'',b''),('unterminated',b'? 42',b'42\x9b'),
                    ('mixed',b'? 1\r\n? 2\r? 3\n? 4\x9b',b'1\x9b2\x9b3\x9b4\x9b'),
                    ('tab',b'\t?\t42\n',b'42\x9b'),('cr-boundary',b"'"+b'x'*253+b'\r\n'+b"'"+b'x'*253+b'\r\n'+b"'"+b'x'*253+b'\r\n'+b"'"+b'x'*254+b'\r\n?42',b'42\x9b')]:
                case(engine,name,raw,answer)
            case(engine,'line-255',b"'"+b'x'*254)
            case(engine,'line-256',b"'"+b'x'*255,cause=306,location=(1,255))
            case(engine,'nul',b'? 42\n\0',cause=306,location=(2,0))
            case(engine,'unsupported-byte',b'? 42\n\x80',cause=306,location=(2,0))
            case(engine,'parse',b'? 42\n???\n',cause=306)
            boundary=(b"'"+b'x'*254+b'\n')*128
            case(engine,'exact-cap',boundary)
            case(engine,'over-cap',boundary+b'\n',cause=306)
            case(engine,'recovery',b'? 42',b'42\x9b')
    payload=bytearray();setup=[]
    for name,raw in files.items():
        address=0x300000+len(payload)
        if group=='session' and name.startswith('R'):
            number=int(name[1:-4])
            calls=[c.replace(f'RETAINED_SOURCE_{number})',f'${address:x})') for c in calls]
        elif group=='attach' and name.startswith('S'):
            number=int(name[1:-4])+1
            calls=[c.replace(f'SOURCE_BUFFER_{number}',f'${address:x}') for c in calls]
        else:
            setup.append(f'  Put(BYTE POINTER(c"RAM:{name}"),BYTE POINTER(${address:x}),{len(raw)})')
        payload+=raw
    text=(ROOT/('tests/programs/fbisession.act' if group=='session' else 'tests/programs/fastbasic.act')).read_text()
    text=text.replace('SETUP_FILES','\n'.join(setup)).replace('RUN_PROGRAMS','\n'.join(calls)).replace('EXTRA_CHECKS','')
    text=text.replace('; RUN_COMPLETION_CHECKS','''IF state.interpreter<>NULL THEN
    sourceBase=SDXSTATE.ReadWord(state.guest.bank,state.interpreter.capability+10)
    sourcePhase=state.interpreter.result.phase
    sourceLine=state.interpreter.result.line
    sourceColumn=state.interpreter.result.column
  FI''')
    text=text.replace('CARD checks,','CARD sourceBase,sourcePhase,sourceLine,sourceColumn\nCARD checks,')
    if group=='faults':text=text.replace('USE FBSTATE','USE FBISOURCEFAULT\nUSE FBSTATE')
    if group=='text':
        text=text.replace('USE FBSTATE','USE CONSOLEDRIVER\nUSE CONSOLECORE\nUSE FBSTATE')
        text=text.replace('CARD checks,','BYTE ARRAY clearScreen(1)\nCARD checks,')
        run_calls='\n'.join(calls)
        text=text.replace(run_calls,'''  LET console=DOS.Open(BYTE POINTER(c"RAW:"),DOS.MODE_NEWFILE)
  Require(console<>NULL)
  clearScreen(0)=12
  Require(DOS.Write(console,@clearScreen,1)=1)
  DOS.SelectOutput(console)
'''+run_calls+'''
  LET terminal=CONSOLEDRIVER.GetInstance()
  Require(terminal.row>=2 AND terminal.column=0)
  LET firstRow=(terminal.row-2)*terminal.width
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,firstRow))='4)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,firstRow+1))='2)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,firstRow+terminal.width))='2)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,firstRow+terminal.width+1))='.)
  Require(terminal.cells(CONSOLECORE.CellOffset(terminal,firstRow+terminal.width+2))='5)
  DOS.SelectOutput(output)
  Require(DOS.Close(console)<>0)
'''+run_calls)
    if group=='profile':
        text=text.replace('USE FBSTATE','USE FBIPROFILE\nUSE FBSTATE')
        text=text.replace('  LET image=PROGRAMFILE.Load(name)','  FBIPROFILE.Reset()\n  FBIPROFILE.Mark(0)\n  LET image=PROGRAMFILE.Load(name)\n  FBIPROFILE.Mark(1)')
        text=text.replace('  primary=result.primary','  FBIPROFILE.Mark(7)\n  FBIPROFILE.Save()\n  primary=result.primary')
    if group=='transitions':
        text=text.replace('USE FBSTATE','USE FBITRACE\nUSE FBSTATE')
        text=text.replace('PROCESS.StartLoaded(BYTE POINTER(image),args,argumentBytes,0)',
            'PROCESS.StartBackgroundLoaded(BYTE POINTER(image),args,argumentBytes)')
        text=text.replace('  Require(identity<>0)\n  Require(PROCESS.Wait(identity,@result)<>0)', '''  Require(identity<>0)
  IF FBITRACE.wanted<>0 THEN
    WHILE FBITRACE.seen<>FBITRACE.wanted DO
      EXEC.Yield()
    OD
    Require(PROCESS.RequestBreak(identity)<>0)
  FI
  Require(PROCESS.Wait(identity,@result)<>0)
  Require(state.guest.bank($900)=0 OR FBITRACE.wanted=0)
  FBITRACE.seen=0''')
    if group=='attach':
        text=text.replace('USE FBSTATE','USE FBINTERPABI\nUSE FBSTATE')
        text=text.replace('USE FBSTATE','USE FBISTARTFAULT\nUSE PROCESSLAUNCH\nUSE FBSTATE')
        text=text.replace('CARD checks,','FBINTERPABI.Source sourceDescriptor\nFBINTERPABI.Result sourceReport\nCARD interpreterBytes\nLONGCARD ARRAY holders(10)\nCARD holder\nCARD checks,')
        text=text.replace('  stateBytes=SIZEOF(FBSTATE.Session)','  stateBytes=SIZEOF(FBSTATE.Session)\n  interpreterBytes=SIZEOF(FBSTATE.Interpreter)')
        text=text.replace('PROC Main()', '''PUBLIC LONGINT FUNC HolderEntry()

  WHILE DOS.BreakPending()=0 DO
    EXEC.Yield()
  OD
  DOS.SetIoErr(0)

RETURN(0)

PROC RunAttached(BYTE POINTER name,bytes CARD count,job LONGINT expectedPrimary)
  PROCESS.Result result
  PROGRAMIMAGE.Image POINTER image
  LONGCARD identity
  PROCESSLAUNCH.StartSpec specification

  image=PROGRAMFILE.Load(name)
  Require(image<>NULL)
  sourceDescriptor.version=FBINTERPABI.VERSION
  sourceDescriptor.bytes=FBINTERPABI.SOURCE_BYTES
  sourceDescriptor.source=LONGCARD(ADDRESS(bytes))
  sourceDescriptor.length=LONGCARD(count)
  sourceDescriptor.job=LONGCARD(job)
  sourceDescriptor.generation=123
  sourceDescriptor.result=LONGCARD(ADDRESS(@sourceReport))
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  sourceDescriptor.source=$ffffff
  sourceDescriptor.length=2
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))=0)
  Require(DOS.IoErr()=115)
  sourceDescriptor.source=LONGCARD(ADDRESS(bytes))
  sourceDescriptor.length=65536
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))=0)
  Require(DOS.IoErr()=115)
  ; Exhaust all public Tasks. A refused Start must retain the attachment.
  FOR holder=0 TO 9 DO
    holders(holder)=PROCESS.StartBackground(@HolderEntry,NULL,0)
    Require(holders(holder)<>0)
  OD
  Require(PROCESS.StartLoaded(BYTE POINTER(image),NULL,0,0)=0)
  Require(DOS.IoErr()=103)
  FOR holder=0 TO 9 DO
    Require(PROCESS.RequestBreak(holders(holder))<>0)
    Require(PROCESS.Wait(holders(holder),@result)<>0)
  OD
  ; An admitted background child can fail setup before BASIC enters. Collection
  ; still ends the borrow. Configured Start returns zero on the same failure and
  ; must preserve its attachment for retry.
  LET attachedState=FBSTATE.Session POINTER(image.extension)
  FBISTARTFAULT.failOnce=1
  identity=PROCESS.StartBackgroundLoaded(BYTE POINTER(image),NULL,0)
  Require(identity<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  Require(result.primary=20 AND result.secondary=103)
  Require(attachedState.interpreter.attached=0)
  sourceDescriptor.length=LONGCARD(count)
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  specification.arguments=NULL
  specification.input=NULL
  specification.output=BYTE POINTER(DOS.Output())
  specification.directory=NULL
  specification.console=NULL
  specification.length=0
  specification.minimumStack=0
  FBISTARTFAULT.failOnce=1
  Require(PROCESS.StartConfigured(BYTE POINTER(image),BYTE POINTER(@specification))=0)
  Require(DOS.IoErr()=103)
  Require(attachedState.interpreter.attached=1)
  identity=PROCESS.StartLoaded(BYTE POINTER(image),NULL,0,0)
  Require(identity<>0)
  PROGRAM.Unload(image)
  Require(PROCESS.Wait(identity,@result)<>0)
  primary=result.primary
  secondary=result.secondary
  Require(primary=expectedPrimary)
  Require(sourceReport.version=FBINTERPABI.VERSION)
  Require(sourceReport.bytes=FBINTERPABI.RESULT_BYTES)
  Require(sourceReport.job=LONGCARD(job))
  Require(sourceReport.generation=123)
  Require(sourceReport.primary=primary)
  Require(sourceReport.cause=secondary)
  Require(sourceReport.phase=FBINTERPABI.PHASE_COMPLETE)
  ; A retained Image accepts a fresh empty attachment after collection.
  image=PROGRAMFILE.Load(name)
  Require(image<>NULL)
  sourceDescriptor.source=0
  sourceDescriptor.length=0
  sourceDescriptor.job=LONGCARD(job)+100
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  identity=PROCESS.StartLoaded(BYTE POINTER(image),NULL,0,0)
  Require(identity<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  Require(result.primary=0 AND result.secondary=0)
  Require(sourceReport.job=LONGCARD(job)+100)
  sourceDescriptor.job=LONGCARD(job)+200
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  identity=PROCESS.StartLoaded(BYTE POINTER(image),NULL,0,0)
  Require(identity<>0)
  Require(PROCESS.Wait(identity,@result)<>0)
  Require(result.primary=0 AND result.secondary=0)
  Require(sourceReport.job=LONGCARD(job)+200)
  ; A valid replacement and final unstarted release own no extra references.
  sourceDescriptor.job=LONGCARD(job)+300
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  sourceDescriptor.job=LONGCARD(job)+400
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))<>0)
  PROGRAM.Unload(image)
  image=PROGRAMFILE.Load(BYTE POINTER(c"RAM:FBCI.COM"))
  Require(image<>NULL)
  Require(PROGRAM.BasicAttach(image,BYTE POINTER(@sourceDescriptor))=0)
  Require(DOS.IoErr()=307)
  PROGRAM.Unload(image)
  SDXSTATE.Guards()

RETURN

PROC Main()''')
    source=out/'probe.act';source.write_text(text)
    memory=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text())
    memory['image_data_bytes']=40960
    profile=out/'memory-profile.json';profile.write_text(json.dumps(memory))
    return source,profile,bytes(payload),expected,cases


def run(out,group='core',raw=False,replay=False,reuse=False):
    out.mkdir(parents=True,exist_ok=True)
    previous=(out/'probe.act').read_text() if reuse else None
    source,profile,payload,expected,cases=fixture(out,group)
    overrides={}
    if group=='session':
        path=out/'fbportfail.act';path.write_text('MODULE FBPORTFAIL\nUSE EXEC\nPUBLIC BYTE once\nPUBLIC EXEC.MsgPort POINTER FUNC Create()\n  IF once<>0 THEN\n    once=0\n    RETURN(NULL)\n  FI\nRETURN(EXEC.CreateMsgPort())\nENDMODULE\n');overrides[path.name]=sha256(path)
        text=(ROOT/'lib/dos/fbservice.act').read_text().replace('USE FBSESSION\n','USE FBSESSION\nUSE FBPORTFAIL\n')
        text=text.replace('  item.requests=EXEC.CreateMsgPort()','  item.requests=FBPORTFAIL.Create()')
        path=out/'fbservice.act';path.write_text(text);overrides[path.name]=sha256(path)
    if group=='attach':
        path=out/'fbistartfault.act';path.write_text('MODULE FBISTARTFAULT\nPUBLIC BYTE failOnce\nENDMODULE\n');overrides[path.name]=sha256(path)
        from library_paths import read_source
        text=read_source(ROOT/'lib/dos/dosprocess.act').replace('USE DOSCORE\n','USE DOSCORE\nUSE FBISTARTFAULT\n')
        text=text.replace('  owner=DOSCORE.Current()\n  console=process.console',
            '  IF FBISTARTFAULT.failOnce<>0 THEN\n    FBISTARTFAULT.failOnce=0\n    DOSCLIENT.SetError(103)\n    RETURN(0)\n  FI\n  owner=DOSCORE.Current()\n  console=process.console')
        path=out/'dosprocess.act';path.write_text(text);overrides[path.name]=sha256(path)
    if group=='faults':
        path=out/'fbisourcefault.act';path.write_text((ROOT/'tests/programs/fbisourcefault.act').read_text());overrides[path.name]=sha256(path)
        for module,names in [('fbsource',('Open','Read','Close')),('sdxprint',('Write',))]:
            text=(ROOT/f'lib/dos/{module}.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBISOURCEFAULT\n')
            for name in names:text=text.replace('DOS.'+name+'(','FBISOURCEFAULT.'+name+'(')
            path=out/(module+'.act');path.write_text(text);overrides[path.name]=sha256(path)
    if group=='transitions':
        path=out/'fbitrace.act';path.write_text('''MODULE FBITRACE
USE EXEC
USE DOS
PUBLIC BYTE wanted,seen
PUBLIC PROC Hold(BYTE point)
  IF wanted=point THEN
    seen=point
    WHILE DOS.BreakPending()=0 DO
      EXEC.Yield()
    OD
  FI
RETURN
ENDMODULE
''');overrides[path.name]=sha256(path)
        text=(ROOT/'lib/dos/fbsource.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBITRACE\n')
        text=text.replace('    total=total+LONGCARD(got)','    FBITRACE.Hold(1)\n    total=total+LONGCARD(got)')
        text=text.replace('  IF file<>NULL THEN\n    IF DOS.Close','  FBITRACE.Hold(2)\n  IF DOS.BreakPending()<>0 AND cause=0 THEN\n    cause=DOS.ERROR_BREAK\n  FI\n  IF file<>NULL THEN\n    IF DOS.Close')
        path=out/'fbsource.act';path.write_text(text);overrides[path.name]=sha256(path)
        text=(ROOT/'lib/dos/fbservice.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBITRACE\n')
        text=text.replace('    WHEN FBABI.CHECKPOINT_EVENT THEN','    WHEN FBABI.CHECKPOINT_EVENT THEN\n      IF state.interpreter<>NULL THEN\n        IF state.interpreter.result.phase=2 THEN\n          FBITRACE.Hold(3)\n        FI\n      FI')
        text=text.replace('      cause=FBRESULT.Phase(state,value)','      IF value=3 THEN\n        FBITRACE.Hold(4)\n      FI\n      cause=FBRESULT.Phase(state,value)')
        require('FBITRACE.Hold(3)' in text and 'FBITRACE.Hold(4)' in text,'Changed source transition seams')
        path=out/'fbservice.act';path.write_text(text);overrides[path.name]=sha256(path)
    if group=='profile':
        path=out/'fbiprofile.act';path.write_text('''MODULE FBIPROFILE
PUBLIC CARD ARRAY stamps(8),records(32)
PUBLIC CARD seen,sampleIndex
VOLATILE BYTE clockLow=$14,clockHigh=$13
PUBLIC PROC Reset()
  seen=0
RETURN
PUBLIC PROC Mark(BYTE point)
  BYTE high,low
  LET mask=CARD(1) LSH point
  IF (seen & mask)=0 THEN
    DO
      high=clockHigh
      low=clockLow
    UNTIL high=clockHigh
    OD
    stamps(point)=(CARD(high) LSH 8) OR CARD(low)
    seen=seen OR mask
  FI
RETURN
PUBLIC PROC Save()
  CARD index
  FOR index=0 TO 7 DO
    records(sampleIndex*8+index)=stamps(index)
  OD
  sampleIndex==+1
RETURN
ENDMODULE
''');overrides[path.name]=sha256(path)
        for module in ('fbsource','fbresult','fbservice'):
            text=(ROOT/f'lib/dos/{module}.act').read_text().replace('USE DOS\n','USE DOS\nUSE FBIPROFILE\n')
            if module=='fbsource':
                text=text.replace('  LET item=state.interpreter\n  file=NULL','  FBIPROFILE.Mark(2)\n  LET item=state.interpreter\n  file=NULL')
                text=text.replace('  item.result.phase=FBINTERPABI.PHASE_PARSE','  FBIPROFILE.Mark(3)\n  item.result.phase=FBINTERPABI.PHASE_PARSE')
            elif module=='fbresult':
                text=text.replace('  item.result.phase=phase','  IF phase=FBINTERPABI.PHASE_EXECUTE THEN\n    FBIPROFILE.Mark(4)\n  FI\n  item.result.phase=phase')
            else:
                text=text.replace('    WHEN FBABI.EVENT_PUT THEN','    WHEN FBABI.EVENT_PUT THEN\n      FBIPROFILE.Mark(5)')
                text=text.replace('  FBRESULT.Complete(state,cause)','  FBRESULT.Complete(state,cause)\n  FBIPROFILE.Mark(6)')
            path=out/(module+'.act');path.write_text(text);overrides[path.name]=sha256(path)
    p=read_build(out) if replay or reuse else build(compiler(ROOT/'build/actionc',release=True),source,out,
        optimize=not raw,tasks=True,task_capacity=12,console=group=='text',console_test=True,sdx=True,
        memory_profile=profile,dos_mounts=[dict(alias='RAM',format=3)],image_data=[(0x300000,payload)])
    result=dict(status='running',tier='development',group=group,raw=raw,cases=cases,
        engines={n:sha256(ROOT/f'build/fastbasic/{n}.COM') for n in ('FB','FBI')},build=p['build'],local_overrides=overrides,reused_native_fixture=reuse)
    stimulus=None
    if reuse:
        from fastbasic_test_support import guest_inputs
        stimulus=guest_inputs(p,previous,source.read_text(),[(0x300000,payload)])
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        result['machine']=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        try:result['runtime'],_=execute(b,p,timeout=240,frame_limit=12000,before_run=stimulus)
        except Exception:
            print({n:data(b,p['image'],n,True) for n in ('checks','currentCase','primary','secondary','reason')},flush=True)
            if group=='session':
                print('Session result:', data(b,p['image'],'report'),flush=True)
            if group=='text':
                from generate_console import constants
                from console_model import read_cells
                a=constants();at=p['build']['memory']['console_storage']['INSTANCE']
                print('Console:',{k:b.peek16(at+a[k]) for k in ('INSTANCE_ROW','INSTANCE_COLUMN')},
                    read_cells(b.memdump,at)[:400],flush=True)
            raise
        ownership(b,p,out)
        count=int.from_bytes(bytes(data(b,p['image'],'actualBytes')),'little')
        actual=bytes(data(b,p['image'],'actual'))[:count]
        compared=actual
        for case in cases:
            if case['name']=='fp_values':
                lines=compared.split(b'\x9b');index=case['line_start']+13
                value=Decimal(lines[index].decode())
                require(abs(value-Decimal(2))<=Decimal('1E-7'),'Power approximation outside existing provider tolerance')
                result['power_tolerance']=dict(actual=str(value),expected='2',absolute='1E-7')
                lines[index]=b'2';compared=b'\x9b'.join(lines)
        require(compared==expected,repr(dict(actual=actual,expected=expected)))
        result['checks']=int.from_bytes(bytes(data(b,p['image'],'checks')),'little')
        result['session_bytes']=int.from_bytes(bytes(data(b,p['image'],'stateBytes')),'little')
        if group=='attach':result['interpreter_bytes']=int.from_bytes(bytes(data(b,p['image'],'interpreterBytes')),'little')
        if group=='profile':
            values=bytes(data(b,p['image'],'records'))
            names=('load-begin','load-end','source-begin','source-end','execute-begin','first-output','cleanup-end','collection')
            result['timing']=[dict(case=case['engine']+'-'+case['name'],ticks={name:(int.from_bytes(values[(i*8+j)*2:(i*8+j+1)*2],'little')-int.from_bytes(values[i*16:i*16+2],'little'))&65535 for j,name in enumerate(names)}) for i,case in enumerate(cases)]
        result['output_hex']=actual.hex()
    result['status']='pass'
    return result


if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True)
    a.add_argument('--group',choices=('core','admission','entry','attach','text','faults','transitions','capacity','profile','session'),default='core');a.add_argument('--raw',action='store_true');a.add_argument('--replay',action='store_true');a.add_argument('--reuse-native',action='store_true')
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.group,args.raw,args.replay,args.reuse_native)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Source interpreter:',r['checks'],'checks; guards intact')
