#!/usr/bin/env python3
"""Execute task-local DOS contexts and private request/reply delivery."""
from library_paths import read_source
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,execute,verify_machine,require,sha256
from os_boundary import emulator
from test_sio_device import PIN
from test_cooperative import data
from test_heap_api import clean_ownership

def run(t,out,optimize,case='call'):
    out.mkdir(parents=True,exist_ok=True)
    if case.startswith('regression-'):
        from dos_client_regressions import run as regression
        with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            return dict(regression(b,t,out,optimize,case[11:]),status='pass',case=case,machine=machine)
    if case.startswith('context-'):
        from dos_context_probe import run as context
        with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
            machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
            return dict(context(b,t,out,optimize,int(case.rsplit('-',1)[1])),machine=machine)
    source='dos_lifetime.act' if case=='reuse' else 'dos_allocation.act' if case.startswith('alloc-') else 'dos_remove.act' if case=='remove' else 'dos_client.act'
    modified=None
    if case in ('alloc-context','alloc-port','early'):
        text=read_source(ROOT/'lib/dos/dosclient.act')
        if case=='alloc-context':
            old='client=ClientContext POINTER(EXEC.AllocMem(CLIENT_SIZE,EXEC.MEMF_UPPER\n      OR EXEC.MEMF_CLEAR))';new='client=ClientContext POINTER(0)'
        elif case=='alloc-port':old='client.port=EXEC.CreateMsgPort()';new='client.port=EXEC.MsgPort POINTER(0)'
        else:
            old='  EXEC.PutMsg(handler,@client.packet.sp_Msg)\n  EXEC.Permit()'
            new=old+'\n  ReplyBeforeWait(client)'
            text=text.replace('ENDMODULE','PROC ReplyBeforeWait(ClientContext POINTER client)\n  WHILE client.packet.sp_Msg.mn_Node.ln_Type<>EXEC.NT_REPLYMSG DO EXEC.Yield() OD\nRETURN\nENDMODULE')
        require(text.count(old)==1,'Stale DOS test transform')
        text=text.replace(old,new)
        (out/'dosclient.act').write_text(text);modified=sha256(out/'dosclient.act')
    p=build(t,ROOT/'tests/programs'/source,out,optimize=optimize,tasks=True,dos_test=True)
    with emulator(ROOT/'build/altirra-sio-multi',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def before(b):
            if case=='alloc-signal':
                variable=next(d for d in p['image']['data'] if '_VARIANT_' in d['name']);b.poke(variable['address'],2)
        try:runtime,_=execute(b,p,before_run=before,expected_status=4 if case=='remove' else 0,timeout=600 if case=='reuse' else 240,frame_limit=30000 if case=='reuse' else 12000)
        except Exception:
            print('DOS checks',data(b,p['image'],'checks',True),flush=True);raise
        if case!='remove':clean_ownership(b,p,out)
        else:require(data(b,p['image'],'reached')==[0],'Removed a live DOS context')
        return dict(status='pass',build=p['build'],runtime=runtime,machine=machine,checks=data(b,p['image'],'checks',True) if case!='remove' else data(b,p['image'],'reached'),case=case,fixture_override_sha256=modified)
if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--suite',default='call');a.add_argument('--output',type=Path,required=True);args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    paths=('abi/dos.json','lib/dos/dosclient.act','lib/dos/doscore.act','lib/dos/dos-core-types.inc','lib/dos/task-dos.inc','lib/exec/taskpolicy.act','platform/altirraos/dos.s','platform/altirraos/tasks.s','tools/generate_dos.py','tools/generate_tasks.py','tools/native_program.py','tools/test_dos_client.py','tools/dos_context_probe.py','tools/dos_client_regressions.py',*[str(p.relative_to(ROOT)) for p in sorted((ROOT/'tests/programs').glob('dos_*.act'))])
    inputs={p:sha256(ROOT/p) for p in paths}
    result=dict(status='running')
    try:
        t=compiler(ROOT/'build/actionc');cases=[]
        for case in args.suite.split(','):
            print('DOS client',case,flush=True)
            r=run(t,out/case,args.case=='opt',case);cases.append(r)
            (out/case/'results.json').write_text(json.dumps(r,indent=2)+'\n')
        result=dict(schema_version=1,status='pass',optimize=args.case=='opt',cases=cases,inputs=inputs,platform=PIN)
    except Exception as e:result.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('DOS client passed',args.case,flush=True)
