#!/usr/bin/env python3
"""Matched real COPY runs: command loading excluded, physical I/O counted.

Frozen filesystem sources are private comparison inputs, never installed as a
production compatibility path. Accurate Generic 57600 timing is the default.
"""
import argparse
import json
import shutil
import time
import re
from pathlib import Path

from build_command import compile_command
from filesystem_audit import Audit
from filesystem_audit import word
from generate_dos_mounts import encode
from library_paths import library_file, read_source
from make_shell_disk import make as make_mydos
from native_program import ROOT, build, compiler, read_build, require, sha256, verify_machine
from os_boundary import emulator
from test_cooperative import data
from test_dos_stack import execute, ownership
import sdfs_reference

PIN=json.loads((ROOT/'toolchain/altirra-shell-paced.json').read_text())


def physical_phase(audit, sector, filesystem):
    if filesystem=='mydos':
        header=audit.image.sector(360)
        pages=1 if header[0]==2 else (header[0]-2)*(2 if audit.image.size==128 else 1)
        if sector==360:return 'header'
        if 361-pages<=sector<360:return 'bitmap'
        return 'payload' if audit.owners.get(sector) in audit.files else 'directory'
    header=audit.image.sector(1)
    owner=audit.owners.get(sector,'')
    if sector==1:return 'header'
    if word(header,16)<=sector<word(header,16)+header[15]:return 'bitmap'
    if owner.endswith(' map'):
        return 'map' if owner.removesuffix(' map') in audit.files else 'directory'
    return 'payload' if owner.removesuffix(' data') in audit.files else 'directory'


def instrument(out, frozen=None):
    includes={p.name:p for p in (ROOT/'lib').rglob('*.inc')}
    frozen_names=set()
    if frozen:
        for path in (frozen/'lib').rglob('*.act'):
            current=ROOT/path.relative_to(frozen)
            # Unchanged modules retain their owner paths and alias identities.
            # Only changed frozen inputs need private comparison overrides.
            if read_source(path,includes)!=read_source(current,includes):
                frozen_names.add(path.name)
                (out/path.name).write_text(read_source(path,includes))
    def original(name):
        path=out/name if name in frozen_names else library_file(name)
        return read_source(path,includes)
    (out/'writeperfprobe.act').write_text(read_source(ROOT/'tests/programs/writeperfprobe.act'))
    api=original('programapi.act').replace('USE PROCESS\n','USE PROCESS\nUSE WRITEPERFPROBE\nUSE FSTYPES\nUSE DOSCORE\n')
    api=api.replace('RETURN(DOSCALLS.Open(name,mode))','''  IF WRITEPERFPROBE.armed<>0 AND mode=1005 AND name(0)='S AND name(3)=': THEN
    BEGIN
      LET registry=DOSCORE.GetRegistry()
      LET service=FSTYPES.Service POINTER(registry.runtime)
      WRITEPERFPROBE.cacheHits=service.adapter.cache.hits
      WRITEPERFPROBE.cacheMisses=service.adapter.cache.misses
      WRITEPERFPROBE.cacheEvictions=service.adapter.cache.evictions
      WRITEPERFPROBE.Begin()
    END
  FI
  LET result=DOSCALLS.Open(name,mode)
  IF WRITEPERFPROBE.active<>0 AND mode=1006 THEN
    WRITEPERFPROBE.target=result
  FI
RETURN(result)''')
    api=api.replace('RETURN(DOSCALLS.Close(handle))','''  LET result=DOSCALLS.Close(handle)
  IF WRITEPERFPROBE.active<>0 AND handle=WRITEPERFPROBE.target THEN
    BEGIN
      LET registry=DOSCORE.GetRegistry()
      LET service=FSTYPES.Service POINTER(registry.runtime)
      WRITEPERFPROBE.cacheHits=service.adapter.cache.hits-WRITEPERFPROBE.cacheHits
      WRITEPERFPROBE.cacheMisses=service.adapter.cache.misses-WRITEPERFPROBE.cacheMisses
      WRITEPERFPROBE.cacheEvictions=service.adapter.cache.evictions-WRITEPERFPROBE.cacheEvictions
      WRITEPERFPROBE.End()
    END
  FI
RETURN(result)''')
    (out/'programapi.act').write_text(api)
    wire=original('blockwire.act').replace('USE EXEC\n','USE EXEC\nUSE WRITEPERFPROBE\n',1)
    wire=wire.replace('  EXEC.SendIO(EXEC.IORequest POINTER(request))','  WRITEPERFPROBE.Submitted(request)\n  EXEC.SendIO(EXEC.IORequest POINTER(request))')
    (out/'blockwire.act').write_text(wire)
    io=original('fswriteio.act').replace('USE EXEC\n','USE EXEC\nUSE WRITEPERFPROBE\n',1)
    io=io.replace('  LET status=BLOCKIO.BeginFetch(', '  IF WRITEPERFPROBE.active<>0 THEN WRITEPERFPROBE.logicalReads==+1 FI\n  LET status=BLOCKIO.BeginFetch(')
    marker='\nRETURN(1)\n\nPUBLIC PROC Zero('
    require(io.count(marker)==1,'Stale verified-write observer')
    io=io.replace(marker,'\n  WRITEPERFPROBE.Verified()\n'+marker)
    (out/'fswriteio.act').write_text(io)
    writer=original('fswrite.act').replace('USE EXEC\n','USE EXEC\nUSE WRITEPERFPROBE\n',1)
    writer=writer.replace('  done=0\n','  WRITEPERFPROBE.GroupBegin()\n  done=0\n',1)
    end='  IF okay<>0 AND service.work.error=0' if 'SDFSWRITE.Drain(service)' in writer else '  IF done>0 THEN\n'
    require(writer.count(end)==1,'Stale work-group end observer')
    writer=writer.replace(end,'  WRITEPERFPROBE.GroupEnd()\n'+end,1)
    (out/'fswrite.act').write_text(writer)
    mydos=original('mydoswrite.act').replace('USE FSTYPES\n','USE FSTYPES\nUSE WRITEPERFPROBE\n',1)
    mydos=mydos.replace('  high=state.data(sectorBytes-3)','  IF WRITEPERFPROBE.active<>0 THEN WRITEPERFPROBE.payloadVisits==+1 FI\n  high=state.data(sectorBytes-3)',1)
    (out/'mydoswrite.act').write_text(mydos)
    allocation=original('o65memory.act').replace('USE EXEC\n','USE EXEC\nUSE WRITEPERFPROBE\n',1)
    require(allocation.count('RETURN(Reserve(bytes,EXEC.MEMF_CLEAR))')==1,'Stale BSS allocation observer')
    allocation=allocation.replace('RETURN(Reserve(bytes,EXEC.MEMF_CLEAR))', '''  IF WRITEPERFPROBE.failAllocation<>0 AND bytes>=16384 THEN
    WRITEPERFPROBE.allocationFailed=1
    RETURN(NULL)
  FI
RETURN(Reserve(bytes,EXEC.MEMF_CLEAR))''',1)
    (out/'o65memory.act').write_text(allocation)
    shutil.copyfile(ROOT/'tests/programs/write_performance.act',out/'write_performance.act')


def source_image(folder, frozen):
    folder.mkdir(parents=True,exist_ok=True)
    tree=folder/'source';tree.mkdir(exist_ok=True)
    t=compiler(ROOT/'build/actionc')
    records={}
    for name,path in [('COPY512',frozen/'examples/commands/copy.act'),
                      ('COPY16',ROOT/'examples/commands/copy.act')]:
        records[name]=compile_command(t,path,tree/name)
        for suffix in ('options.json','profile.json'):
            (tree/(name+'.'+suffix)).rename(folder/(name+'.'+suffix))
    # Exact packaged primary bytes, plus a binary case covering three buffers.
    long=(ROOT/'build/development/write-performance/baseline/system.atr').read_bytes()
    audit=Audit(long);audit.sdfs()
    content=audit.files['LONG.TXT']
    (tree/'LONG.TXT').write_bytes(content)
    (tree/'BINARY.BIN').write_bytes(bytes((i*17+3)&255 for i in range(49159)))
    image=folder/'source.atr'
    sdfs_reference.make(image,tree,2880,256)
    return image,records


def run(out, source, filesystem, size, frozen=None, from_build=None, variants=(0,1),
        warmed=(False,True), overwrite=(False,True), binary=False, fast=False,
        load_failure=False, cache_blocks=None, split_row=False):
    out.mkdir(parents=True,exist_ok=True)
    require(not binary or not any(warmed),
            'Binary comparisons currently use cold source cases (--cold-create-only)')
    instrument(out,frozen)
    source_audit=Audit(source.read_bytes());source_audit.sdfs()
    selected='BINARY.BIN' if binary else 'LONG.TXT'
    content=source_audit.files[selected]
    mounts=[dict(alias='D1',unit=49,sectors=source_audit.image.count,sector_bytes=source_audit.image.size,format=2,profile=4),
            dict(alias='WORK',unit=56,sectors=720,sector_bytes=size,format=1 if filesystem=='mydos' else 2,profile=4,access='readwrite')]
    program=read_build(from_build) if from_build else build(compiler(ROOT/'build/actionc'),out/'write_performance.act',out,
                optimize=True,tasks=True,task_capacity=8,console_deferred=True,
                dos_mounts=mounts,system_mount='D1',
                image_data=[(0xeffd0,bytes([0xa5])*(16384+64)),(0x320000,bytes(8192))])
    if from_build:
        require(program['build']['source_sha256']==sha256(out/'write_performance.act'),
                'Changed benchmark source')
        for group in ('platform_inputs','task_inputs','console_inputs','banked_inputs'):
            for name,digest in program['build'].get(group,{}).items():
                require(sha256(ROOT/name)==digest,'Changed benchmark input: '+name)
        for path in out.glob('*.act'):
            require((from_build/path.name).exists() and sha256(path)==sha256(from_build/path.name),
                    'Changed benchmark observer/override: '+path.name)
    rows=[]
    with emulator(ROOT/'build/shell-paced-bridge',ROOT/'build/firmware/altirraos-816.rom',out,pin=PIN) as b:
        configuration={**PIN['configuration'],'diskemu':'generic56k','accuratedisk':not fast}
        for key,value in configuration.items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        machine=verify_machine(b,ROOT/'build/firmware/altirraos-816.rom',PIN)
        for variant in ((2,) if load_failure else variants):
            for warm in warmed:
                for existing in overwrite:
                    label=f'{512 if variant==0 else 16384}-{"warm" if warm else "cold"}-{"overwrite" if existing else "create"}'
                    folder=out/label;folder.mkdir(exist_ok=True)
                    tree=folder/'target';tree.mkdir(exist_ok=True)
                    (tree/'KEEP.BIN').write_bytes(bytes(range(256)))
                    extras={f'AAA{index}.BIN':b'' for index in range(4 if existing else 3)} if split_row else {}
                    for name,payload in extras.items():(tree/name).write_bytes(payload)
                    if existing:(tree/'COPY.BIN').write_bytes(content)
                    media=folder/'volume.atr'
                    if filesystem=='sdfs':sdfs_reference.make(media,tree,720,size)
                    else:make_mydos(media,tree,binary_names={'COPY.BIN','KEEP.BIN'},sector_bytes=size)
                    before_hash=sha256(media)
                    def before(bridge):
                        bridge.mount(0,str(source));bridge.mount(7,str(media))
                        if cache_blocks is not None:
                            boot=program['build']['memory']['boot_config']
                            bridge.memload(boot['address']+boot['abi']['fields']['cache_blocks'],
                                           cache_blocks.to_bytes(2,'little'))
                        bridge.memload(program['build']['task_storage']['BASE']+0x900,encode(mounts))
                        at=next(d['address'] for d in program['image']['data'] if '_WRITEPERFPROBE_TRACE_' in d['name'])
                        bridge.memload(at,(0x320000).to_bytes(3,'little'))
                        for name,value in [('variant',variant),('warm',int(warm))]:
                            at=next(d['address'] for d in program['image']['data'] if '_WRITEPERFORMANCE_'+name.upper()+'_' in d['name'])
                            bridge.poke(at,value)
                        at=next(d['address'] for d in program['image']['data'] if '_WRITEPERFORMANCE_ARGUMENTS_' in d['name'])
                        arguments=('SYS:'+selected+' WORK:COPY.BIN').encode()
                        bridge.memload(at,arguments+b'\0')
                        at=next(d['address'] for d in program['image']['data'] if '_WRITEPERFORMANCE_ARGUMENTBYTES_' in d['name'])
                        bridge.memload(at,len(arguments).to_bytes(2,'little'))
                    started=time.monotonic()
                    try:
                        runtime,_=execute(b,{**program,'output':folder},before_run=before,timeout=1200,frame_limit=60000)
                    except Exception as error:
                        storage=(program['output']/'sio-storage-action.inc').read_text()
                        diagnostic=dict(error=str(error),registers=b.regs(),
                                        state=list(b.memdump(0x800,64)),
                                        sio={name:list(b.memdump(int(address,16),2)) for name,address in
                                             re.findall(r'CONST (SD_\w+)=\$(\w+)',storage)})
                        (folder/'failure.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
                        raise
                    host_seconds=time.monotonic()-started
                    ownership(b,program,program['output'])
                    view={**program['image'],'data':[d for d in program['image']['data'] if '_WRITEPERFPROBE_' in d['name']]}
                    counts={name:int.from_bytes(bytes(data(b,view,name)),'little') for name in
                            ('startFrame','endFrame','maxGroupWrites','reads','writes','readBytes','writeBytes','logicalReads','payloadVisits','cacheHits','cacheMisses','cacheEvictions')}
                    for name in ('maxGroupRequests','maxGroupFrames'):
                        if any('_'+name.upper()+'_' in d['name'] for d in view['data']):
                            counts[name]=int.from_bytes(bytes(data(b,view,name)),'little')
                    verified=int.from_bytes(bytes(data(b,view,'verifiedWrites')),'little')
                    require(verified==counts['writes'],'Submitted Write did not complete successfully')
                    trace_count=int.from_bytes(bytes(data(b,view,'traceCount')),'little')
                    require(trace_count<2048,'Physical request trace overflow')
                    trace=b.memdump(0x320000,trace_count*4)
                    frames=(counts['endFrame']-counts['startFrame'])&65535
                    require(frames>0 or load_failure,'Missing measured interval')
                    time.sleep(3);b.regs();b._cmd_ok('EJECT drive=7')
                    audit=Audit(media.read_bytes());allocation=getattr(audit,filesystem)()
                    require(audit.files=={**extras,'KEEP.BIN':bytes(range(256)),'COPY.BIN':content},'Persisted benchmark bytes differ')
                    breakdown={}
                    for at in range(0,len(trace),4):
                        unit,command=trace[at:at+2]
                        sector=int.from_bytes(trace[at+2:at+4],'little')
                        owner=source_audit if unit==49 else audit
                        require(unit in (49,56),'Unexpected benchmark unit')
                        phase=physical_phase(owner,sector,'sdfs' if unit==49 else filesystem)
                        role='source' if unit==49 else 'target'
                        key=role+'-'+('read' if command==0x52 else 'write')
                        breakdown.setdefault(key,{})[phase]=breakdown.setdefault(key,{}).get(phase,0)+1
                    if load_failure:require(sha256(media)==before_hash,'Failed COPY load changed destination')
                    rows.append(dict(case=label,buffer_bytes=512 if variant==0 else 16384,warm_source=warm,overwrite=existing,
                                     guest_pal_frames=frames,guest_seconds=frames/50,
                                     effective_bytes_per_second=len(content)*50/frames if frames else None,
                                     load_failure=load_failure,
                                     host_seconds_including_boot=host_seconds,counts=counts,runtime=runtime,
                                     verified_writes=verified,physical_breakdown=breakdown,
                                     source_sha256=sha256(source),target_before_sha256=before_hash,target_after_sha256=sha256(media),allocation=allocation))
                    (out/'progress.json').write_text(json.dumps(rows,indent=2)+'\n')
                    print(label,frames,'frames',counts['reads'],'reads',counts['writes'],'writes',flush=True)
    return dict(status='pass',tier='development',rows=rows,build=program['build'],machine=machine,configuration=configuration,
                filesystem=filesystem,sector_bytes=size,bytes=len(content),baseline_sources=str(frozen) if frozen else None,
                cache_blocks_override=cache_blocks,
                split_directory_row=split_row,
                source_sha256=sha256(source),
                observer_inputs={p.name:sha256(p) for p in program['output'].glob('*.act')},
                bank_zero_delta=dict(fixed=0,per_task=0))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--source-image',type=Path)
    p.add_argument('--prepare-source',type=Path)
    p.add_argument('--frozen-sources',type=Path)
    p.add_argument('--from-build',type=Path)
    p.add_argument('--filesystem',choices=('mydos','sdfs'),default='sdfs')
    p.add_argument('--size',type=int,choices=(128,256),default=128)
    p.add_argument('--cold-create-only',action='store_true')
    p.add_argument('--create-only',action='store_true',help='Cold/warm source runs on fresh target media')
    p.add_argument('--binary',action='store_true')
    p.add_argument('--fast-media',action='store_true')
    p.add_argument('--load-failure',action='store_true')
    p.add_argument('--buffer',type=int,choices=(512,16384),help='Run one command artifact')
    p.add_argument('--cache-blocks',type=int)
    p.add_argument('--split-row',action='store_true',help='Place COPY entry across two 128-byte directory sectors')
    args=p.parse_args();result=dict(status='running');out=args.output.resolve();out.mkdir(parents=True,exist_ok=True)
    try:
        if args.prepare_source:
            image,records=source_image(args.prepare_source.resolve(),
                args.frozen_sources or ROOT/'build/development/write-performance/baseline/sources')
            result=dict(status='pass',image=str(image),sha256=sha256(image),commands=records)
        else:
            require(args.source_image is not None,'Need --source-image or --prepare-source')
            result=run(out,args.source_image.resolve(),args.filesystem,args.size,args.frozen_sources,
                       args.from_build,warmed=(False,) if args.cold_create_only else (False,True),
                       overwrite=(True,) if args.load_failure else (False,) if (args.cold_create_only or args.create_only) else (False,True),
                       binary=args.binary,fast=args.fast_media,load_failure=args.load_failure,
                       variants=(0,1) if args.buffer is None else (0 if args.buffer==512 else 1,),
                       cache_blocks=args.cache_blocks,split_row=args.split_row)
    except Exception as error:
        result.update(status='fail',error=str(error))
        raise
    finally:(out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
