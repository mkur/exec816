"""Two direct renderer borrowers beside native console/pointer work."""
from pathlib import Path
from library_paths import read_source
from native_program import ROOT, require
from os_boundary import run_to
from gem_render_oracle import PALETTE
import adapter_state as adapter


def instrument(out):
    source = (ROOT/'ports/gem4xe/adapter/gem-vbxe.c').read_text()
    source = source.replace('#include "gem-drawing.h"', '''#include "gem-drawing.h"
extern void DisplayNativeBegin(void);
extern void DisplayDMAStart(void);
extern void DisplayBorrowBegin(struct DisplayGrant *);
extern void DisplayBorrowEnd(struct DisplayGrant *);''')
    source = source.replace('    return DisplayOwnerEnter();', '''    UWORD status=DisplayOwnerEnter();
    if (status==DISPLAY_OK) DisplayNativeBegin();
    return status;''')
    source = source.replace('status=VbxeOwnerScrollStart(&display,copy,(UBYTE)(map_col[pen]*17),id);',
        'status=VbxeOwnerScrollStart(&display,copy,(UBYTE)(map_col[pen]*17),id);\n    if (status==DISPLAY_OK) DisplayDMAStart();')
    start = source.index('UWORD GemDrawingBorrow(')
    body = source[start:].replace('    if (!fault) {', '    DisplayBorrowBegin(grant);\n    if (!fault) {', 1)
    body = body.replace('    DisplayLeave(grant);', '    DisplayBorrowEnd(grant);\n    DisplayLeave(grant);')
    source = source[:start]+body
    target = out/'gem-vbxe.c'; target.write_text(source)
    return target


def producer(out, sy):
    source = '''MODULE DISPLAYBORROWPROBE
USE EXEC
USE DISPLAY

PUBLIC PROC Pump()

  LET command=CARD POINTER($DisplayCommand)
  IF command^=0 THEN
    RETURN
  FI

  LET grantAddress=LONGCARD POINTER($DisplayAdmission)
  LET status=CARD POINTER($DisplayStatus)
  status^=DISPLAY.Delegate(DISPLAY.Grant POINTER(ADDRESS(grantAddress^)))
  LET task=LONGCARD POINTER($DisplayController)
  LET wake=LONGCARD POINTER($DisplayWake)
  EXEC.Forbid()
  command^=0
  EXEC.Signal(EXEC.Task POINTER(ADDRESS(task^)),wake^)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for name in ('DisplayCommand','DisplayAdmission','DisplayStatus','DisplayController','DisplayWake'):
        source = source.replace('$'+name, '$%x'%sy[name])
    (out/'displayborrowprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE', 'USE AESCORE\nUSE DISPLAYBORROWPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Admission hook changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  DISPLAYBORROWPROBE.Pump()\n'+needle))


def physical(b, p, foreign, report, fault=0):
    if not fault: b.profile_start()
    sy = foreign['symbols']
    get = lambda name: int.from_bytes(b.memdump(sy[name],2), 'little')
    def reach(condition):
        b.bp_clear_all(); b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        original = b.regs
        def regs():
            r = original()
            if int(r['PC'].lstrip('$'),16) == p['labels']['done']:
                require(b.peek16(adapter.STATE) == 65535, 'Guest stopped: '+hex(b.peek16(adapter.STATE)))
            return r
        b.regs = regs
        try: run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        finally: b.regs = original
    def frames(n): reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    def phase(n): reach('dw($%x)=%d'%(sy['DisplayPhase'],n))
    b._cmd_ok('MOUSE ST'); b._cmd_ok('KEY ALL up')
    phase(1); frames(150)
    b.poke16(sy['DisplayFaultVariant'],fault)
    if not fault:
        from desktop_mouse import schedule
        position = schedule(b,p,[320,120],(575,185))
        frames(80)
        schedule(b,p,position,(625,185))
    b.poke16(sy['DisplayGo'],1)
    if fault == 2:
        b.bp_clear_all()
        return
    phase(2)
    if fault:
        b.poke16(sy['DisplayGo'],2)
        b.bp_clear_all()
        return
    frames(20)
    schedule(b,p,[625,185],(320,120)); frames(80)
    path = Path(p['output']).parent/'borrow-scan.bgra'
    screen = b.rawscreen(str(path)); raw = path.read_bytes()
    for who, pen in enumerate((4,2)):
        color = bytes((v&254)+(v>>7) for v in PALETTE[pen*3:pen*3+3])[::-1]
        for y in range(181,197):
            for x in range(563+who*40,597+who*40):
                at = y*screen.stride+(x+16)*4
                require(raw[at:at+3] == color, 'Borrowed fill pixel differs at '+str((x,y)))
    report['borrowed_renderer'] = {name:get(name) for name in
        ('DisplayBorrows','DisplayNative','DisplayCopies','DisplayOverlap','DisplayActive')}
    report['borrowed_renderer']['exact_pixels'] = 2*34*16
    b.poke16(sy['DisplayGo'],2)
    b.bp_clear_all()


def trace_setup(p, foreign, out):
    import os
    from console_turn_profile import markers, flat_markers
    from bitmap_console_performance import native_markers
    definition = markers(p,foreign,out/'drawing')
    points = flat_markers(definition)
    spans = native_markers(p,[('DISPLAY_ENTER','access_wait')])
    spans['borrow_unit'] = dict(entry=foreign['symbols']['DisplayBorrowBegin'],
                               returns=[foreign['symbols']['DisplayBorrowEnd']])
    for name, span in spans.items():
        points[name] = span['entry']
        for i, pc in enumerate(span['returns']): points[name+str(i)] = pc
    saved = {k:os.environ.get(k) for k in ('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')}
    os.environ['EXEC816_LATENCY_TRACE']='1'
    os.environ['EXEC816_LATENCY_PCS']=','.join(f'{v:x}' for v in set(points.values()))
    return definition,spans,saved


def trace_restore(saved):
    import os
    for key,value in saved.items():
        if value is None: os.environ.pop(key,None)
        else: os.environ[key]=value


def trace_result(out, config):
    from console_turn_profile import analyze_events, Timeline
    from sio_transaction_trace import read_events
    from math import ceil
    definition,marks,_ = config
    events = read_events(out/'emulator.log')
    profile = analyze_events(events,definition,include_segments=True)
    active={}; rows=[]; timelines={}
    for tick,event in events:
        if event[0]!='cpu': continue
        pc,dp=int(event[4],16),int(event[9],16)
        for name,mark in marks.items():
            key=(name,dp)
            if pc==mark['entry']:
                require(key not in active,'Nested display timing span')
                active[key]=tick
            elif pc in mark['returns'] and key in active:
                start=active.pop(key)
                if dp not in timelines: timelines[dp]=Timeline(profile['segments'],dp)
                rows.append(dict(kind=name,dp=dp,**timelines[dp].measure(start,tick)))
    require(not active,'Incomplete display timing span')
    result={}
    for kind in marks:
        selected=[r for r in rows if r['kind']==kind]
        result[kind]=dict(count=len(selected))
        for metric in ('elapsed_ms','charged_cpu_ms','off_cpu_ms','interrupt_ms'):
            values=sorted(r[metric] for r in selected)
            result[kind][metric]=dict(p50=values[len(values)//2],p95=values[ceil(.95*len(values))-1],maximum=values[-1])
    require(result['borrow_unit']['count']==48,'Missing borrowed timing units')
    result['scope']='Instrumented fill fixture, including assertion and marker costs. Conservative CPU charge excludes native interrupts and off-Task time. Two first units contain an injected Yield; access_wait includes arbitration and bridge costs.'
    return result


def faults(out):
    import json
    from native_program import read_build, verify_machine
    from test_dos_stack import execute, ownership
    from test_mouse_observe import BRIDGE,ROM,PIN
    from os_boundary import emulator
    from generate_mouse_acceleration import metadata
    p=read_build(out/'program'); p['build']['desktop_mouse']=metadata(None)
    foreign=json.loads((out/'c-image.json').read_text()); sy=foreign['symbols']
    report=dict(status='running',tier='development',qualification=False,cases=[])
    try:
        for variant in (1,2):
            folder=out/f'borrow-fault-{variant}'
            with emulator(BRIDGE,ROM,folder,pin=PIN) as b:
                machine=verify_machine(b,ROM,PIN)
                get=lambda n:int.from_bytes(b.memdump(sy[n],2),'little')
                try:
                    runtime,_=execute(b,p,before_run=lambda b:physical(b,p,foreign,{},variant),
                                      expected_status=0 if variant==1 else 0xff93,timeout=120,frame_limit=8000)
                except Exception:
                    report['failure_state']={n:get(n) for n in ('DisplayPhase','DisplayGo','DisplayActive','DisplayBorrows','AESChecks','AESFailures','AESFirstFailure','AESDone','ConsoleFaultMode','ConsoleStopCount')}
                    report['display_state']={d['name']:list(b.memdump(d['address'],d['size'])) for d in p['image']['data'] if '_DISPLAY_' in d['name']}
                    raise
                require(get('ConsoleStopCount')==1,'Missing bounded STOP')
                if variant==1:
                    ownership(b,p,p['output'])
                    require(get('AESFailures')==0 and get('AESDone')==2,'Quiescent borrower cleanup failed')
                else:
                    require(get('DisplayActive')!=0 and get('AESDone')==0,'Unquiesced borrower released ownership')
                report['cases'].append(dict(variant=variant,machine=machine,runtime=runtime,
                                           checks=get('AESChecks'),failures=get('AESFailures')))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'borrow-faults.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__ == '__main__':
    import argparse
    from test_aes_server import applications
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--replay',action='store_true')
    args=parser.parse_args(); output=args.output.resolve()
    applications(output,'display',replay=args.replay)
    faults(output)
