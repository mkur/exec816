"""Focused physical-key walkthrough for a packaged bitmap shell and PRIMES."""
import json,os,zipfile
import hashlib
from collections import Counter
from pathlib import Path
from native_program import ROOT,read_build,require,sha256
from prime_observer import state,symbols,process_record
from sio_transaction_trace import read_events
import test_demo
from package_demo import GEM_NOTICES,LICENSE_FILES

def check_archive(bundle):
    manifest=json.loads((bundle/'demo-manifest.json').read_text())
    require(manifest.get('bitmap') and manifest.get('shell_only') and not manifest.get('desktop'),
            'Use the bitmap shell-only preview')
    expected={'Exec-of816.xex',manifest['media'],'altirraos-816.rom',
            'ALTIRRAOS-LICENSE.txt','OF816-LICENSE.txt','README.txt','SHA256SUMS',
            *GEM_NOTICES,*LICENSE_FILES,*(m['name'] for m in manifest['additional_media'])}
    with zipfile.ZipFile(bundle/'exec816-demo.zip') as archive:
        require(len(archive.namelist())==len(expected) and set(archive.namelist())==
                {'exec816-demo/'+name for name in expected},'Unexpected preview ZIP contents')
        content={name:archive.read('exec816-demo/'+name) for name in expected}
    sums={name:digest for digest,name in (line.split('  ',1) for line in content['SHA256SUMS'].decode('ascii').splitlines())}
    require(set(sums)==expected-{'SHA256SUMS'},'Incomplete preview checksums')
    for name,digest in sums.items():
        require(hashlib.sha256(content[name]).hexdigest()==digest,'Changed archived file: '+name)
    for name in ('Exec-of816.xex',manifest['media'],'altirraos-816.rom',*(m['name'] for m in manifest['additional_media'])):
        require(sha256(bundle/'of816'/name)==sums[name],'Archive differs from exercised bytes: '+name)
    return dict(sha256=sha256(bundle/'exec816-demo.zip'),checksums=sums)

class Integration:
    def __init__(self,bundle):self.bundle=bundle
    def exercise(self,h):
        b=h.b;read=h.far;number=h.number;c=h.console
        job=h.at('job');windows=h.p['build']['memory']['console_storage']['WINDOWS']
        pane=windows+c['WINDOWS_PANE'];height=h.saved['top']+c['INSTANCE_HEIGHT']
        def current():return state(read,h.p,self.bundle,number(job))
        def snapshot(label):
            text=h.cells(label)
            require(len(text)==2400,'Full display dimensions changed')
            return text
        def retired(identity):
            row=process_record(read,h.p,identity)
            h.rendezvous(f'db(${row+77:x})=4')
            h.rendezvous(f'dw(${height:x})=30')
            require(h.ledger()['live']==baseline,'Completed job retained a Task')
        def field_addresses():return symbols(read,h.p,self.bundle,number(job))
        require(number(height,2)==30 and number(pane)==0,'Default shell is split')
        baseline=h.ledger()['live']
        h.command('RUN PRIMES')
        identity=number(job)
        h.rendezvous(f'dw(${height:x})=24')
        objects=field_addresses();candidate=objects['candidate'][0]
        h.rendezvous(f'dw(${candidate:x})>=2000')
        first=current();require(first['count']>0,'Background calculation made no progress')
        require(h.ledger()['live']==baseline+1,'Pane added a worker Task')
        h.command('JOBS',b'running')
        h.command('HELLO',b'Hello from disk!')
        h.command('HELLO | WC',b'1 3 17')
        h.command('COPY SYS:STORY.TXT WORK:PRIME.TXT')
        h.command('CMP SYS:STORY.TXT WORK:PRIME.TXT')
        h.command('RUN PRIMES',error=202)
        h.command('PRIMES PASSES 1',error=202)
        static=snapshot('before-ctrl-l')
        for char in 'ECHO draft':h.press(char)
        file=number(h.saved['shell'],3);cooked=number(file+16,3)
        require(number(cooked+2,2)==10 and read(cooked+16,10)==b'ECHO draft','Missing edited input')
        h.press('\x0c');h.ready()
        require(number(cooked+2,2)==10 and read(cooked+16,10)==b'ECHO draft','Ctrl-L lost edited input')
        after=snapshot('ctrl-l-draft')
        require(b'>  ECHO draft' in after[:1920],'Ctrl-L lost prompt')
        require(after[1920:2080]==static[1920:2080],'Ctrl-L changed separator/title')
        for row in (26,27,28):require(after[row*80:row*80+10]==static[row*80:row*80+10],'Ctrl-L changed a label')
        # Physical BREAK cancels this cooked read only, leaving the private job alive.
        h.press('\x03');h.ready()
        scope=number(process_record(read,h.p,identity)+125,3)
        require(number(scope+18,1)==0,'Foreground BREAK cancelled the background job')
        snapshot('foreground-break-alive')
        b.profile_start()
        trace_start=b.eval_expr('@clk')
        before=current()['progress'];h.frames(120)
        trace_end=b.eval_expr('@clk')
        b.profile_stop()
        require(current()['progress']>before,'Background calculation stopped after foreground BREAK')
        h.save_screen(self.bundle/'primes-running.png')
        h.command('BREAK '+str(identity))
        retired(identity);snapshot('break-restored')
        h.command('JOBS',b'304')
        require(number(job+4)==10 and number(job+8)==304,'Wrong stopped-job outcome')
        h.command('BREAK '+str(identity),error=305)
        h.command('RUN PRIMES PASSES 1')
        successor=number(job);require(successor!=identity,'Reused Process identity')
        h.rendezvous(f'dw(${height:x})=24')
        h.command('BREAK '+str(identity),error=305)
        for char in 'ECHO kept':h.press(char)
        retired(successor)
        final=current()
        require((final['count'],final['latest'],final['pass'])==(1229,9973,1),'Wrong finite sieve result')
        require(final['pane']==0,'Finished command retained its pane')
        require(number(cooked+2,2)==9 and read(cooked+16,9)==b'ECHO kept','Natural completion lost the draft')
        restored=snapshot('finite-completion-draft');require(b'ECHO kept' in restored,'Restored display lost edited text')
        previous=number(h.saved['scope']+14)
        h.press('\n');h.ready(previous);h.result()
        require(number(job+12,1)==3,'Command boundary did not collect completion')
        h.command('PRIMES PASSES 1')
        snapshot('foreground-finite')
        h.command('RUN PRIMES')
        h.rendezvous(f'dw(${height:x})=24')
        h.saved['integration']=dict(baseline_tasks=baseline,background_tasks=baseline+1,final_sieve=final,
                drafts=['ECHO draft','ECHO kept'],foreground_break_isolated=True,ctrl_l_prompt=True,
                natural_restore_while_read=True,restart=True,exit_with_running_job=True,
                idle_trace=dict(start=trace_start,end=trace_end))
        h.save_screen(self.bundle/'boot-smoke.png')
        for char in 'EXIT':h.press(char)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()

def run(bundle):
    archive=check_archive(bundle)
    p=read_build(bundle)
    foreign=json.loads((bundle/'bitmap-console/c-image.json').read_text())
    marks={k:foreign['symbols'][k] for k in ('GemDrawingText','GemDrawingFill','GemDrawingTextFill','GemDrawingCopy','GemDrawingScrollStart','_text_record') if k in foreign['symbols']}
    for name in ('Delay','WriteAt'):
        marks[name]=next(r['address'] for r in p['image']['routines'] if r['name'].startswith('M_PROGRAMAPI_'+name.upper()+'_'))
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS');old={k:os.environ.get(k) for k in keys}
    try:
        os.environ['EXEC816_LATENCY_TRACE']='1';os.environ['EXEC816_LATENCY_PCS']=','.join(f'{v:x}' for v in marks.values())
        record=test_demo.run(bundle,boot_smoke=True,integration=Integration(bundle))
    finally:
        for k,v in old.items():
            if v is None:os.environ.pop(k,None)
            else:os.environ[k]=v
    record['archive']=archive
    (bundle/'primes-walkthrough.json').write_text(json.dumps(record,indent=2)+'\n')
    counts=Counter();intervals=[];previous=None
    bounds=record['integration']['idle_trace']
    # @clk is the low 32 bits. Hardware events extend the same clock across boot.
    def in_idle(tick):return (int(tick)-bounds['start'])%(1<<32)<=(bounds['end']-bounds['start'])%(1<<32)
    names={v:k for k,v in marks.items()}
    for tick,event in read_events(bundle/'emulator.log'):
        if event[0]!='cpu':continue
        name=names.get(int(event[4],16))
        if name=='Delay':
            if previous is not None and in_idle(previous) and in_idle(tick) and counts.get('WriteAt')==2:
                intervals.append(dict(tick=tick,calls=dict(counts)))
            counts.clear();previous=tick
        elif name:counts[name]+=1
    require(intervals,'No ordinary numeric update observed')
    for i in intervals:
        calls=i['calls']
        require(calls.get('GemDrawingText',0)==2 and calls.get('_text_record',0)==10,'Numeric update drew extra glyphs')
        require(not any(calls.get(k,0) for k in ('GemDrawingFill','GemDrawingTextFill','GemDrawingCopy','GemDrawingScrollStart')),'Numeric update filled or scrolled the pane')
    record['numeric_updates']=intervals;record['trace_sha256']=sha256(bundle/'emulator.log')
    (bundle/'primes-results.json').write_text(json.dumps(record,indent=2)+'\n')
    return record

if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    args=parser.parse_args()
    run(args.bundle.resolve())
    print('Packaged PRIMES integration passed')
