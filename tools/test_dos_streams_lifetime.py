#!/usr/bin/env python3
"""Deterministic emitted RAW lifetime probes with private generated hooks."""
from library_paths import library_file, read_source
import argparse,json,shutil,time
from pathlib import Path
import generate_tasks
from native_program import ROOT,build,compiler,require,sha256,verify_machine
from test_console_coexistence import PIN
from test_dos_stack import execute,ownership
from test_cooperative import data
from os_boundary import emulator


def instrument(output,*args,**kwargs):
    directory=Path(original_policy(output,*args,**kwargs))
    def edit(name,changes):
        path=directory/(name+'.act')
        source=path.read_text() if name=='dosraw' else read_source(library_file(name+'.act'))
        for old,new in changes:
            require(old in source,'Missing private hook: '+old)
            source=source.replace(old,new)
        path.write_text(source)
    edit('dosraw',[
        ('USE HEAPCORE','USE HEAPCORE\nUSE DSTREAMPROBE'),
        ('  endpoint=RawEndpoint POINTER(EXEC.AllocMem','  DSTREAMPROBE.Checkpoint(1)\n  endpoint=RawEndpoint POINTER(EXEC.AllocMem'),
        ('  request=client.request\n  IF request=', '  DSTREAMPROBE.Checkpoint(5)\n  request=client.request\n  IF request='),
        ('  BYTE reading\n\n  request=client.request\n  endpoint=', '  BYTE reading\n  DSTREAMPROBE.State POINTER probe\n  DSTREAMPROBE.Checkpoint(4)\n  probe=DSTREAMPROBE.Get()\n  IF probe.zeroActual<>0 THEN client.request.io_Actual=0 probe.zeroActual=0 FI\n  request=client.request endpoint='),
        ('  EXEC.CloseDevice(EXEC.IORequest POINTER(@endpoint.owner))', '  DSTREAMPROBE.Checkpoint(2)\n  EXEC.CloseDevice(EXEC.IORequest POINTER(@endpoint.owner))'),
        ('  EXEC.FreeMem(BYTE POINTER(endpoint),SIZEOF(RawEndpoint))\n  EXEC.Forbid()\n  registry.state=CLOSED', '  DSTREAMPROBE.Checkpoint(6)\n  EXEC.FreeMem(BYTE POINTER(endpoint),SIZEOF(RawEndpoint))\n  EXEC.Forbid()\n  registry.state=CLOSED')])
    edit('doscancel', [('USE EXEC','USE EXEC\nUSE DSTREAMPROBE'),
        ('  EXEC.SendIO(request)','  EXEC.SendIO(request)\n  DSTREAMPROBE.Checkpoint(3)')])
    return directory

original_policy=generate_tasks.policy_modules


def run(t,out,mode,bank=1,scenario=0):
    out.mkdir(parents=True,exist_ok=True)
    names=bytearray(128)
    for offset,value in ((0,b'RAW:'),(32,b'NIL:'),(64,b'.'),(80,b'END!'),(96,b'D1:TOOLS/SUB/DATA.BIN')):
        names[offset:offset+len(value)]=value
    payload=bytearray(2048);payload[0]=12
    for i in range(1,2048):payload[i]=65
    generate_tasks.policy_modules=instrument
    try:
        p=build(t,ROOT/'tests/programs/dos_streams_lifetime.act',out,optimize=mode=='opt',tasks=True,
            task_capacity=8,kernel_bank=bank,console=True,dos_mounts=[] if scenario==3 else [dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=1)],
            image_data=[(0xd1000,bytes(names)),(0xd2000,bytes(1024)),(0xd3000,bytes(payload))])
    finally:generate_tasks.policy_modules=original_policy
    hooks={n:sha256(out/'task-kernel'/(n+'.act')) for n in ('dosraw','doscancel')}
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures/mydos/mydos450-128.atr',media);digest=sha256(media)
    def at(name):return next(d['address'] for d in p['image']['data'] if '_DOSSTREAMLIFE_'+name.upper()+'_' in d['name'])
    with emulator(ROOT/'build/console-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN);b.config('diskemu','fastest');b.mount(0,str(media));saved={}
        def before(b):
            saved.update(at=b.peek16(88),cursor=b.peek(752),mask=b.peek(16));saved['screen']=b.memdump(saved['at'],960)
            b.poke(at('mode'),scenario)
        original_regs=b.regs;last_report=time.monotonic()
        def regs():
            nonlocal last_report
            r=original_regs()
            if time.monotonic()-last_report>20:
                peer=int.from_bytes(b.memdump(at('peer'),3),'little')
                request=sum(b.eval_expr(f'db(${peer+77+i:x})')<<(8*i) for i in range(3)) if peer else 0
                actual=sum(b.eval_expr(f'db(${request+26+i:x})')<<(8*i) for i in range(4)) if request else None
                print('Lifetime progress',b.peek(at('stage')),b.peek16(at('checks')),b.peek(at('command')),'actual',actual,flush=True);last_report=time.monotonic()
            return r
        b.regs=regs
        try:rt,_=execute(b,p,before_run=before,expected_status=4 if scenario==2 else 0,timeout=240,frame_limit=12000)
        except Exception:
            print('State', {n:data(b,p['image'],n) for n in ('stage','baseline','observedFree','peerResult','peerError')},flush=True)
            print('Lifetime checks',data(b,p['image'],'checks',True),'child',data(b,p['image'],'childChecks',True),'command',data(b,p['image'],'command'),flush=True)
            raise
        counts={k:int.from_bytes(bytes(data(b,p['image'],k)),'little') for k in ('checks','childChecks')}
        events=[b.eval_expr(f'db(${0xd2005+i:x})') for i in range(b.eval_expr('db($d2004)'))]
        require(events==([] if scenario==2 else [1,2,6,5,3,4,3,3]),'Missing lifecycle checkpoint sequence')
        require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(752)==saved['cursor'] and b.peek(16)==saved['mask'],'Console state not restored')
        ownership(b,p,out);require(sha256(media)==digest,'Read-only media modified')
    return dict(status='pass',mode=mode,bank=bank,scenario=scenario,build=p['build'],runtime=rt,machine=machine,
        checks=counts,checkpoints=events,hooks=hooks,source_sha256=sha256(ROOT/'tests/programs/dstreamprobe.act'),media_sha256=digest,
        limits=dict(host_seconds=240,guest_frames=12000))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--compiler-dir',type=Path,default=ROOT/'build/actionc');a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--bank',type=int,default=1);a.add_argument('--scenario',type=int,default=0);a.add_argument('--output',type=Path,required=True)
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r=dict(status='running')
    try:r=run(compiler(args.compiler_dir),out,args.case,args.bank,args.scenario)
    except Exception as e:r.update(status='fail',error=str(e));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('DOS stream lifetime passed',args.case,args.bank,args.scenario,r['checks'],flush=True)
