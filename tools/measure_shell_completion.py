#!/usr/bin/env python3
"""Passive completion timings on the extracted, pinned OF816 distribution."""
import argparse,json,shutil,zipfile
from pathlib import Path
from types import SimpleNamespace

from bitmap_console_performance import native_markers
from native_program import ROOT,read_build,require,sha256
from sio_transaction_trace import BASE_HZ,read_events
from measure_read_8k import observe
from measure_spartados_listing import spans,in_clock_window
from measure_loading_breakdown import packets
import test_demo


def run(bundle,out):
    out.mkdir(parents=True,exist_ok=True)
    copied=out/'bundle'
    require(not copied.exists(),'Choose a fresh measurement output')
    shutil.copytree(bundle,copied,symlinks=True,ignore=shutil.ignore_patterns('emulator.log','distribution','pixels-*'))
    with zipfile.ZipFile(copied/'exec816-demo.zip') as archive:
        archive.extractall(out/'distribution')
    distribution=out/'distribution/exec816-demo'
    p=read_build(copied)
    prefix='SHELLAPP' if json.loads((copied/'demo-manifest.json').read_text()).get('shell_only') else 'DEMO'
    names=[(prefix+'_SHELLCOMPLETE','completion'),(prefix+'_SHELLCOMPLETIONNAMES','names'),
           (prefix+'_SHELLCOMPLETIONDIRECTORY','directory'),(prefix+'_SHELLCOMPLETIONMATCH','candidate'),
           (prefix+'_SHELLCOMPLETIONAPPLY','apply'),('DOSCALLS_EXNEXTBATCH','batch'),
           ('DOSCLIENT_CALL','packet'),('COOKEDLINE_REPLACE','replace'),('COOKEDLINE_RENDER','render')]
    routines=native_markers(p,names)
    require(all(name in routines for _,name in names),'Missing native completion marker')
    marks={}
    for name,routine in routines.items():
        marks[name+'_entry']=routine['entry']
        for i,pc in enumerate(routine['returns']):marks[name+'_return_'+str(i)]=pc
    (out/'markers.json').write_text(json.dumps(dict(routines=routines,marks=marks),indent=2)+'\n')

    def exercise(c):
        baseline=c.ledger();measurements=[]
        # Empty RAM directories isolate resident candidates without disk I/O.
        # Changes use ordinary commands; there is no cache or input injection.
        c.command('CD RAM:')
        c.command('PATH SET RAM:')
        cases=[('resident','UNM','UNMOUNT '),('alias','MK','MKDIR ')]
        def attempt(kind,text,wanted,sample):
            for char in text:c.press(char)
            generation=c.number(c.saved['scope']+14)
            start=c.b.eval_expr('@clk')
            c.press('\t');c.ready()
            screen=c.cells('completion-'+kind+'-'+str(sample))
            settled=c.saved['settled_clock']
            handle=c.number(c.saved['shell'],3);session=c.number(handle+16,3)
            length=c.number(session+2,2)
            require(c.far(session+16,length)==wanted.encode(),'Wrong measured completion: '+text)
            require(c.number(c.saved['scope']+14)==generation,'TAB submitted the measured line')
            require(c.ledger()==baseline,'Completion retained ownership')
            measurements.append(dict(kind=kind,text=text,sample=sample,input_clock=start,settled_clock=settled))
            c.press('\x15');c.ready()
        for kind,text,wanted in cases:
            for sample in range(2):attempt(kind,text,wanted,sample)
        c.command('CD SYS:');c.command('PATH RESET')
        for kind,text,wanted in [('default-search','UNM','UNMOUNT '),
                                 ('current-file','TYPE READM','TYPE README.TXT '),
                                 ('explicit-disk','TYPE SYS:SELECT/A001','TYPE SYS:SELECT/A001.TXT ')]:
            for sample in range(2):attempt(kind,text,wanted,sample)
        c.saved['measurements']=measurements
        c.save_screen(c.p['output']/'boot-smoke.png')
        for char in 'EXIT':c.press(char)
        c.b._cmd_ok('KEY RETURN down');c.b.bp_clear_all()

    observe(marks)
    record=test_demo.run(copied,boot_smoke=True,measurement_commands=[],profile_commands=True,
        distribution_root=distribution,integration=SimpleNamespace(exercise=exercise))
    (out/'run.json').write_text(json.dumps(record,indent=2)+'\n')
    events=read_events(copied/'emulator.log')
    measured=spans(events,routines)
    wire=packets(events)
    rows=[]
    for sample in record['measurements']:
        windows=[s for s in measured if s['kind']=='completion' and in_clock_window(s,sample['input_clock'],sample['settled_clock'])]
        require(len(windows)==1,'Missing resolver interval')
        window=windows[0]
        inside=[s for s in measured if window['begin']<=s['begin']<=s['end']<=window['end']]
        row={**sample,'resolver_ms':window['ms'],
             'input_to_visible_ms':((sample['settled_clock']-sample['input_clock'])&0xffffffff)/BASE_HZ*1000,
             'directories':sum(s['kind']=='directory' for s in inside),
             'batches':sum(s['kind']=='batch' for s in inside),
             'candidates':sum(s['kind']=='candidate' for s in inside),
             'filesystem_call_ms':sum(s['ms'] for s in inside if s['kind']=='packet'),
             'resident_names_ms':sum(s['ms'] for s in inside if s['kind']=='names')}
        row['outside_filesystem_calls_ms']=row['resolver_ms']-row['filesystem_call_ms']
        row['apply_ms']=sum(s['ms'] for s in inside if s['kind']=='apply')
        transactions=[s for s in wire if window['begin']<=s['begin']<=window['end']]
        row['sio_transactions']=len(transactions)
        require(all(s['rx'] for s in transactions),'Incomplete SIO response')
        row['sio_wire_and_device_ms']=sum(s['rx'][-1][0]+10*s['rx'][-1][2]-s['begin'] for s in transactions)/BASE_HZ*1000
        row['redraw_render_ms']=sum(s['ms'] for s in measured if s['kind']=='render'
            and s['begin']>=window['end'] and in_clock_window(s,sample['input_clock'],sample['settled_clock']))
        rows.append(row)
    return dict(status='pass',tier='development',rows=rows,machine=record['machine'],runtime=record['runtime'],
        bank_zero=record['bank_zero_delta'],autoboot_frames=record['autoboot_frames'],
        scope='Physical TAB on the extracted package, accurate disk timing. Routine elapsed times include preemption; filesystem calls include CPU and wait. Input-to-visible includes the physical-key/checkpoint intervals. First/warm attempts are reported; SIO transaction counts establish actual cold reads. No pure CPU or hardware timing qualification is claimed.',
        package_sha256=sha256(bundle/'exec816-demo.zip'),trace_sha256=sha256(copied/'emulator.log'),runner_sha256=sha256(Path(__file__)))


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();result=run(args.bundle.resolve(),args.output.resolve())
    (args.output/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps(result['rows'],indent=2),flush=True)
