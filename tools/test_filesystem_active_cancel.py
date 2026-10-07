#!/usr/bin/env python3
"""Native active cancellation checkpoints, committed cursors and safe wire retirement."""
from library_paths import library_file, read_source
import argparse,json,shutil
from pathlib import Path
from native_program import ROOT,build,compiler,require,verify_machine,sha256
from os_boundary import emulator
from test_dos_stack import execute,ownership
from test_cooperative import data
PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())
CASES={'first':1,'middle':2,'final':3,'before-send':4,'wire':5,'open-allocation':6,'lock-allocation':7,'open-publication':8,'lock-publication':9,'directory-scan':10,'directory-publication':11,'copy':12,'seek':13,'directory-accounting':14,'lookup':17,'preparing':15,'terminal':16,'extent-publication':18}

def instrument(out,filesystem):
    for name in ('filesystem_active_cancel.act','fsactiveprobe.act'):(out/name).write_bytes((ROOT/'tests/programs'/name).read_bytes())
    source=(out/'filesystem_active_cancel.act').read_text()
    if filesystem=='sdfs':
        source=source.replace('68 49 58 84 79 79 76 83 47 83 85 66 47 68 65 84 65 46 66 73 78 0','68 49 58 66 73 78 65 82 89 46 66 73 78 0').replace('info.fib_FileName(0)=84','info.fib_FileName(0)=65').replace('LONGINT(sectorBytes-3)','LONGINT(sectorBytes)')
    (out/'filesystem_active_cancel.act').write_text(source)
    edits={
        'fsworker.act':[('    FSOPERATION.Pump(registry)','    FSOPERATION.Pump(registry)\n    FSACTIVEPROBE.Deliver(service,1)')],
        'blockwire.act':[
            ('  IF cancellable<>0 AND FSOPERATION.Canceled(scope)<>0 THEN','  FSACTIVEPROBE.BeforeSend()\n  IF cancellable<>0 AND FSOPERATION.Canceled(scope)<>0 THEN'),
            ('attempted=0\n  aborted=0\n  EXEC.SendIO(EXEC.IORequest POINTER(request))','attempted=0 aborted=0 EXEC.SendIO(EXEC.IORequest POINTER(request))\n  FSACTIVEPROBE.OnWire(EXEC.IORequest POINTER(request))'),
            ('attempted=1\n      aborted=SIODRIVER.TryCancel(EXEC.IORequest POINTER(request))','attempted=1 aborted=SIODRIVER.TryCancel(EXEC.IORequest POINTER(request))\n      FSACTIVEPROBE.accepted=aborted FSACTIVEPROBE.attempts==+1'),
            ('  error=INT(CARD(state))','  error=INT(CARD(state))\n  FSACTIVEPROBE.Point(10)')],
        'fshandler.act':[('  ; The object kind is set before any failure or cancellation can free it.','  FSACTIVEPROBE.Deliver(service,4)\n  ; The object kind is set before any failure or cancellation can free it.')],
        'fspacket.act':[('  DOSOBJECTS.Link(service.owner,@item.header)','  DOSOBJECTS.Link(service.owner,@item.header)\n  FSACTIVEPROBE.Deliver(service,5)')],
        'fsdirectory.act':[('  LET status=FSBACKEND.BufferedEntry(service.work)','  FSACTIVEPROBE.Deliver(service,6)\n  LET status=FSBACKEND.BufferedEntry(service.work)'),('  FSINFO.Save(FSINFO.FileInfoBlock POINTER(service.info),\n      FSTYPES.LockObject POINTER(service.object),\n      service.enumIndex)','  FSINFO.Save(FSINFO.FileInfoBlock POINTER(service.info),FSTYPES.LockObject POINTER(service.object),service.enumIndex)\n  FSACTIVEPROBE.Deliver(service,7)')],
        'mydosfile.act':[('    target(index)=source(index)','    target(index)=source(index)\n    IF index=amount RSH 1 THEN FSACTIVEPROBE.Point(8) FI')],
        'siodriver.act':[('  okay=SIOADAPTER.Start()','  FSACTIVEPROBE.Point(9)\n  okay=SIOADAPTER.Start()')],
    }
    edits['fshandler.act'].append(('  LET status=FSBACKEND.ResolveStep(service.work)','  FSACTIVEPROBE.Deliver(service,12)\n  LET status=FSBACKEND.ResolveStep(service.work)'))
    edits['fsdirectory.act'].append(('  LET status=FSBACKEND.Measure(service.work,@service.measured,1)','  FSACTIVEPROBE.Deliver(service,11)\n  LET status=FSBACKEND.Measure(service.work,@service.measured,1)'))
    edits['fsdirectory.act'].append(('    service.nextStep=@PublishStep','    service.nextStep=@PublishStep\n    FSACTIVEPROBE.Deliver(service,13)'))
    if filesystem=='sdfs':
        edits['sdfsdir.act']=[('  IF received=0 AND SDFSEXTENTS.Lookup(work,file)<>0 THEN',
                             '  IF received=0 AND SDFSEXTENTS.Lookup(work,file)<>0 THEN\n    FSACTIVEPROBE.extentHits==+1')]
        del edits['mydosfile.act']
        edits['sdfsfile.act']=[('    IF sparse<>0 THEN\n      output(index)=0\n    ELSE\n      output(index)=adapter.buffer(offset+index)\n    FI','    IF sparse<>0 THEN output(index)=0 ELSE output(index)=adapter.buffer(offset+index) FI\n    IF index=amount RSH 1 THEN FSACTIVEPROBE.Point(8) FI')]
    for name,changes in edits.items():
        source=read_source(library_file(name))
        if 'USE EXEC\n' in source:source=source.replace('USE EXEC\n','USE EXEC\nUSE FSACTIVEPROBE\n',1)
        else:source=source.replace('\nUSE ','\nUSE FSACTIVEPROBE\nUSE ',1)
        for old,new in changes:
            require(source.count(old)==1,'Stale active checkpoint '+name+' '+old);source=source.replace(old,new)
        (out/name).write_text(source)
    return {name:sha256(out/name) for name in (*edits,'fsactiveprobe.act')}

def run(out,optimize,size,profile,names,bank,filesystem='mydos',warm=False):
    out.mkdir(parents=True,exist_ok=True);observers=instrument(out,filesystem)
    require(filesystem=='mydos' or 'seek' not in names,'SDFS seeks complete without an active-I/O cancellation point')
    require(filesystem=='sdfs' or 'directory-accounting' not in names,'MyDOS directory sizes complete without an accounting checkpoint')
    require(filesystem=='sdfs' or 'extent-publication' not in names,'Extent-cache publication requires SDFS')
    require(not warm or set(names)<={'middle','final'}, 'Warm checks require progress before cancellation')
    fixture=f'sdfs/sdfs-21-{size}.atr' if filesystem=='sdfs' else f'mydos/mydos450-{size}.atr'
    media=out/'volume.atr';shutil.copyfile(ROOT/'tests/fixtures'/fixture,media);media_sha=sha256(media)
    p=build(compiler(ROOT/'build/actionc'),out/'filesystem_active_cancel.act',out,optimize=optimize,tasks=True,task_capacity=8,console=True,kernel_bank=bank,
            dos_mounts=[dict(alias='D1',unit=49,sectors=2000 if filesystem=='sdfs' or size==256 else 720,sector_bytes=size,profile=profile,format=2 if filesystem=='sdfs' else 1)])
    def at(name):return next(d['address'] for d in p['image']['data'] if '_FILESYSTEMACTIVETEST_'+name.upper()+'_' in d['name'])
    cases=[]
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        for k,v in PIN['configuration'].items():b.config(k,str(v).lower() if isinstance(v,bool) else v)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        def read(name,words=False,module='FILESYSTEMACTIVETEST'):
            selected=dict(p['image'],data=[d for d in p['image']['data'] if '_'+module+'_' in d['name']])
            return data(b,selected,name,words)
        b.config('diskemu','fastest' if profile==1 else 'generic56k');b.mount(0,str(media))
        for i,name in enumerate(names):
            print('Active cancellation',name,flush=True);caseout=out/name;caseout.mkdir(exist_ok=True);saved={}
            if i:b.state_load(slot='loaded')
            def before(b):
                if not i:b.state_save(slot='loaded')
                b.memload(at('scenario'),CASES[name].to_bytes(2,'little'));b.memload(at('sectorBytes'),size.to_bytes(2,'little'))
                b.poke(at('warm'),int(warm))
                saved.update(at=b.peek16(88),mask=b.peek(16),cursor=b.peek(752));saved['screen']=b.memdump(saved['at'],960)
            try:runtime,_=execute(b,{**p,'output':caseout},before_run=before,timeout=600,frame_limit=30000,preloaded=bool(i))
            except Exception:
                print('Active failure',{n:read(n,True) for n in ('checks','scenario','result','error')},flush=True);raise
            ownership(b,p,out)
            require(b.memdump(saved['at'],960)==saved['screen'] and b.peek(16)==saved['mask'] and b.peek(752)==saved['cursor'],'OS console not restored')
            cases.append(dict(status='pass',name=name,runtime=runtime,checks=read('checks',True),result=read('result'),error=read('error'),
                              probe={n:read(n,False,'FSACTIVEPROBE') for n in ('fired','attempts','accepted','wirePhase','committed','extentHits')}))
            if name=='extent-publication':
                require(cases[-1]['probe']['extentHits'][0]>0,'No completed extent cache hit')
        require(sha256(media)==media_sha,'Read-only media changed')
    return dict(status='pass',build=p['build'],cases=cases,machine=machine,pin=PIN,sector_bytes=size,profile=profile,filesystem=filesystem,warm=warm,observers=observers,media_sha256=media_sha,
                scope='Controlled Task-side injection through the real foreground delivery function; unchanged production collection/abort/checkpoint logic. Scheduling hooks are not latency evidence.',bank_zero=dict(fixed_delta=0,per_task_delta=0))

if __name__=='__main__':
    a=argparse.ArgumentParser(description=__doc__);a.add_argument('--case',choices=('raw','opt'),required=True);a.add_argument('--size',type=int,choices=(128,256),default=128)
    a.add_argument('--profile',type=int,choices=(1,4),default=1);a.add_argument('--bank',type=int,choices=(1,3),default=1)
    a.add_argument('--format',choices=('mydos','sdfs'),default='mydos');a.add_argument('--suite',default=','.join(name for name in CASES if name not in ('directory-accounting','lookup','extent-publication')));a.add_argument('--output',type=Path,required=True)
    a.add_argument('--warm',action='store_true')
    args=a.parse_args();out=args.output.resolve();out.mkdir(parents=True,exist_ok=True);r={'status':'running'}
    try:r=run(out,args.case=='opt',args.size,args.profile,args.suite.split(','),args.bank,args.format,args.warm)
    except Exception as error:r.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('Active filesystem cancellation passed',args.case,args.size,args.profile,flush=True)
