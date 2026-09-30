#!/usr/bin/env python3
"""Execute native DOS call/layout probes; stream suites exercise production semantics."""
from library_paths import module_args, record_input_paths
import argparse,json,re
from pathlib import Path
from native_program import ROOT,build,compiler,execute,require,verify_machine,sha256,command
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from banked_test_memory import read as far_read
from test_heap_api import clean_ownership
from generate_dos import ABI,check_routine,generate as generate_abi
from dos_abi_fixture import FIXTURES,generate,buffers
from ports_budget import current
CALLS={
 'BeginForeground':'result=DOS.BeginForeground(file)','EndForeground':'result=DOS.EndForeground()',
 'BreakPending':'result=DOS.BreakPending()','ClearBreak':'DOS.ClearBreak()',
 'Open':'file=DOS.Open(name,LONGINT(1005))',
 'Read':'result=DOS.Read(file,name,LONGINT(70000))',
 'Write':'result=DOS.Write(file,name,LONGINT(70000))',
 'Seek':'result=DOS.Seek(file,LONGINT(-70000),LONGINT(-1))',
 'Close':'result=DOS.Close(file)','IoErr':'result=DOS.IoErr()',
 'SetIoErr':'result=DOS.SetIoErr(123456)',
 'Lock':'lock=DOS.Lock(name,LONGINT(-2))','UnLock':'DOS.UnLock(lock)',
 'Examine':'result=DOS.Examine(lock,info)','ExNext':'result=DOS.ExNext(lock,info)',
 'ReleaseContext':'result=DOS.ReleaseContext()',
 'Input':'file=DOS.Input()','Output':'file=DOS.Output()',
 'SelectInput':'file=DOS.SelectInput(file)','SelectOutput':'file=DOS.SelectOutput(file)',
 'IsInteractive':'result=DOS.IsInteractive(file)','CurrentDir':'lock=DOS.CurrentDir(lock)','NameFromLock':'result=DOS.NameFromLock(lock,name,LONGINT(70000))'}
PRELUDE='MODULE DOSIMPORTS\nUSE DOS\nDOS.FileHandle POINTER file\nDOS.FileLock POINTER lock\nDOS.FileInfoBlock POINTER info\nBYTE POINTER name\nLONGINT result\nPROC Main()\n'

def interface_source(path,names):path.write_text(PRELUDE+'\n'.join('  '+CALLS[n] for n in names)+'\nRETURN\n\nENDMODULE\n')

def run(t,out,optimize):
    out.mkdir(parents=True,exist_ok=True)
    facts=generate(out);generate_abi(out);generate_abi(out,True)
    (out/'dos-packets.inc').write_bytes((ROOT/'lib/dos/dos-packets.inc').read_bytes())
    (out/'dos_abi.act').write_bytes((ROOT/'tests/programs/dos_abi.act').read_bytes())
    # This is a callee/record-layout probe with fixed cross-bank guard buffers.
    # Use its original isolated DOS fixture, without linking the full filesystem.
    p=build(t,out/'dos_abi.act',out,optimize=optimize,tasks=True,dos_test=True,image_data=[(a-16,bytes([0xa5])*(s+32)) for _,a,s,_ in FIXTURES])
    routines={}
    for name in ABI['imports']:
        r=next(r for r in p['image']['routines'] if re.fullmatch('M_DOSABI_'+name.upper()+'_[0-9A-F]+',r['name']))
        check_routine(r,name);routines[name]={k:r[k] for k in ('arguments','outgoing_bytes','result_bytes','fixed_frame','local_stack_peak')}
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        runtime,_=execute(b,p,timeout=180,frame_limit=6000)
        clean_ownership(b,p,out)
        def values(name,width):
            raw=bytes(data(b,p['image'],name));return [int.from_bytes(raw[i:i+width],'little') for i in range(0,len(raw),width)]
        actual=values('facts',2);require(actual==facts,'DOS field layout/array stride: '+str(actual))
        observed=values('seen',4);expected=[0x5ffff,1005,0,0,0,0x70000,0xfffeee8e,0xffffffff,0x70000,0x5ffff,0xfffffffe,0x90000,0x90000,0x6fff0,0x90000,0x6fff0,0x9ffff,70001,0x70000,0x70000,0,0xffffffff,0x70000,0xdfffe,70003,0x90000,0x70000,0x70000,0x90000,0x90000,0xaffff,70003,0xbfffe,0x87654321,123456]
        require(observed==expected,'DOS arguments: '+str(observed))
        returns=values('returns',4);require(returns==[0x70000,70001,0xfffeee8e,0xffffffff,70000,0x90000,0xffffffff,0,0xffffffff,0,70003,0xffffffff,0x70000,0x90000,0x70000,0x90000,0xffffffff,0x70000,0xffffffff,0xffffffff,0xffffffff,0xffffffff,0xfffeee90],'DOS signed/pointer results: '+str(returns))
        for address,expected in buffers():require(far_read(b,address,len(expected),out)==expected,'DOS adjacent guard or record mismatch: '+hex(address))
        return dict(status='pass',optimize=optimize,build=p['build'],runtime=runtime,machine=machine,facts=actual,seen=observed,returns=returns,routines=routines,checks=values('checks',2),guarded_record_bytes=sum(s+32 for _,_,s,_ in FIXTURES),fixture_sha256=sha256(out/'dos-abi-fields.inc'))

# This archival record qualifies the original ten-call ABI/packaging milestone.
# New imports are executed by run() and recorded in the streams slice evidence.
ARCHIVAL_CALLS={'Open','Read','Seek','Close','IoErr','Lock','UnLock','Examine','ExNext','ReleaseContext'}
def validate_record(r):
    r=record_input_paths(r)
    require(r['status']=='pass','DOS ABI failed')
    require(len(r['cases'])==2 and {c['optimize'] for c in r['cases']}=={False,True},'Missing DOS ABI execution mode')
    for case in r['cases']:
        require(case['status']=='pass' and case['runtime']['guards']=='intact','Failed DOS ABI guards')
        require(case['returns']==[0x70000,70001,0xfffeee8e,0xffffffff,70000,0x90000,0xffffffff,0,0xffffffff,0],'Invalid DOS returns')
        for name in ARCHIVAL_CALLS:check_routine(case['routines'][name],name)
    require(len(r['production_rejections'])==len(ARCHIVAL_CALLS) and {c['name'] for c in r['production_rejections'] if c['status']=='rejected'}==ARCHIVAL_CALLS,'DOS production stubs or missing rejections')

def validate_current(r):
    require(r['status']=='pass' and {c['optimize'] for c in r['cases']}=={False,True},'Missing current ABI execution')
    for case in r['cases']:
        require(case['runtime']['guards']=='intact' and set(case['routines'])==set(ABI['imports']),'Missing ABI call/guard')
        for name in ABI['imports']:check_routine(case['routines'][name],name)

def record(report,path):
    import copy
    r=copy.deepcopy(report);validate_current(r)
    for case in r['cases']:
        b=case['build'];case['build']={k:b[k] for k in ('revision','changes','override','binary_sha256','abi_sha256','abi_assembly_sha256','source_sha256','image_sha256','xex_sha256','optimize','task_inputs','task_generated')}
        case['build']['kernel_bank']=b['memory']['constants']['KERNEL_BANK']
        case['runtime']={k:case['runtime'][k] for k in ('status','guards','native_nmi_count','native_irq_count','os_busy','fault_required','switches','live_tasks')}
    path.write_text(json.dumps(r,indent=2)+'\n')

def main():
    a=argparse.ArgumentParser();a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'));a.add_argument('--record',type=Path);a.add_argument('--output',type=Path,default=ROOT/'build/dos-abi');args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    t=compiler(args.compiler_dir)
    inputs=('abi/dos.json','lib/dos/dos.act','lib/dos/dos-types.inc','lib/dos/dos-packets.inc','lib/dos/doswire.act','tools/generate_dos.py','tools/generate_tasks.py','tools/native_program.py','tools/dos_abi_fixture.py','tools/test_dos_abi.py','tests/programs/dos_abi.act')
    result=dict(schema_version=2,status='running',scope='Current emitted native DOS ABI and record layout; production semantics are qualified by DOS stream suites',platform=PIN,inputs={p:sha256(ROOT/p) for p in inputs},cases=[],bank_zero=current(),completion_limits=dict(host_seconds=180,frames=6000))
    try:
        for mode in ([args.case] if args.case else ['raw','opt']):
            print('DOS ABI',mode,flush=True);result['cases'].append(run(t,out/mode,mode=='opt'))
        source=out/'imports.act';interface_source(source,CALLS)
        interfaces=json.loads(command([t['binary'],*module_args(),'--emit-interfaces',source]))
        chosen={i['name'].split('.')[1]:i for i in interfaces if i['name'].startswith('DOS.')}
        require(set(chosen)==set(CALLS),'Missing DOS declarations')
        for name,i in chosen.items():check_routine(i,name)
        result['interfaces']=chosen
        result['status']='pass'
        if not args.case:validate_current(result)
        if args.record:record(result,args.record)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DOS ABI passed',flush=True)
if __name__=='__main__':main()
