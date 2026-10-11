"""Matched loaded COPY on fresh IDE media, with physical ATA phase counts.

The frozen comparison is an explicit development-only source snapshot. It is
never a production compatibility path and uses the same pinned compiler/ROM.
"""
import argparse
import importlib.util
import json
import os
from contextlib import contextmanager
from pathlib import Path

from native_program import ROOT,build,compiler,execute,require,sha256,read_build
from test_ideplus import PIN,ide_emulator
from test_heap_api import clean_ownership
from test_cooperative import data
from measure_write_performance import instrument
from library_paths import read_source,library_file
from build_command import compile_command
from filesystem_audit import Audit
from make_data_disk import make
from build_ide_media import write


@contextmanager
def driver_observer(program, enabled):
    """Passive full-bank PCs; no guest counters or debugger pauses."""
    if not enabled:
        yield None
        return
    from measure_sector_copy import instructions_for
    phases={}
    address='ADDRESSRANGE' if any(r['name'].startswith('M_IDEPLUSDRIVER_ADDRESSRANGE_') for r in program['image']['routines']) else 'ADDRESSSECTOR'
    for module,name in (('IDEPLUSDRIVER','RUNREQUEST'),('IDEPLUSDRIVER','READY'),
                        ('IDEPLUSDRIVER',address),('BLOCKWIRE','EXCHANGE')):
        routine,instructions,_,_=instructions_for(program,'M_'+module+'_'+name+'_')
        mapping=dict(consume=routine['address'],native_nmi=program['labels']['native_nmi'],native_irq=program['labels']['native_irq'])
        mapping.update({f'return{i}':item['pc'] for i,item in enumerate(x for x in instructions if x['text']=='RTL')})
        phases[name.lower()]=mapping
    for name in ('read','write'):
        phases['pio_'+name]=dict(consume=program['labels']['ideplus_'+name+'_words'],
                                return0=program['labels']['ideplus_'+name+'_words_end']-1,
                                native_nmi=program['labels']['native_nmi'],native_irq=program['labels']['native_irq'])
    boundary={name:next(r['address'] for r in program['image']['routines'] if r['name'].startswith('M_WRITEPERFPROBE_'+name.upper()+'_')) for name in ('begin','end')}
    pcs=set(boundary.values())|{pc for mapping in phases.values() for pc in mapping.values()}
    keys=('EXEC816_LATENCY_TRACE','EXEC816_LATENCY_PCS')
    previous={key:os.environ.get(key) for key in keys}
    try:
        os.environ['EXEC816_LATENCY_TRACE']='1'
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in sorted(pcs))
        yield (phases,boundary)
    finally:
        for key,value in previous.items():
            if value is None:os.environ.pop(key,None)
            else:os.environ[key]=value


def phase_summary(out, observer):
    from measure_sector_copy import samples, summarize
    from sio_transaction_trace import read_events
    phases,boundary=observer
    events=read_events(out/'emulator.log')
    start=next(t for t,e in events if e[0]=='cpu' and int(e[4],16)==boundary['begin'])
    finish=next(t for t,e in events if t>start and e[0]=='cpu' and int(e[4],16)==boundary['end'])
    selected=[row for row in events if start<=row[0]<=finish]
    result={}
    for name,mapping in phases.items():
        rows=samples(selected,mapping)
        stats=summarize(rows)
        result[name]=dict(**stats,estimated_uninterrupted_total_us=len(rows)*stats['uninterrupted_us']['total']['mean_us'])
    return result


def frozen_module(path):
    spec=importlib.util.spec_from_file_location('frozen_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(out,frozen=None,open_bytes=0,count_comparisons=False,validation_source=None):
    out.mkdir(parents=True,exist_ok=True)
    t=compiler(ROOT/'build/actionc',release=True)
    instrument(out,frozen)
    probe=(out/'writeperfprobe.act').read_text()
    probe=probe.replace('PUBLIC BYTE armed,active,finished','PUBLIC BYTE armed,active,finished\nPUBLIC LONGCARD ataReads,ataWrites,ataFlushes,prepReads,verifyReads')
    # Count only ATA commands in the measured source-open to target-close interval.
    probe=probe.replace('ENDMODULE', '''PUBLIC PROC ATA(BYTE command)

  IF active<>0 THEN
    IF command=$20 THEN
      ataReads==+1
    ELSEIF command=$30 THEN
      ataWrites==+1
    ELSEIF command=$e7 THEN
      ataFlushes==+1
    FI
  FI

RETURN

PUBLIC PROC Reading(BYTE preparation)

  IF active<>0 THEN
    IF preparation<>0 THEN
      prepReads==+1
    ELSE
      verifyReads==+1
    FI
  FI

RETURN

ENDMODULE''')
    # The generic SIO-only request observer is unnecessary in this IDE run.
    a=probe.index('PUBLIC PROC Submitted(');z=probe.index('PUBLIC PROC Completed()',a)
    probe=probe[:a]+'''PUBLIC PROC Submitted(EXEC.IOStdReq POINTER request)

RETURN

'''+probe[z:]
    if count_comparisons:
        probe=probe.replace('PUBLIC BYTE armed,active,finished','PUBLIC BYTE armed,active,finished\nPUBLIC LONGCARD comparisons')
    (out/'writeperfprobe.act').write_text(probe)
    driver=out/'ideplusdriver.act'
    original=read_source(frozen/'lib/io/ideplusdriver.act' if frozen else library_file('ideplusdriver.act'))
    import re
    def include(match):
        path=Path(match[1])
        return path.read_text() if path.is_file() else match[0]
    original=re.sub(r'^INCLUDE "([^"\n]+)"$',include,original,flags=re.M)
    original=original.replace('USE IDEPLUS\n','USE IDEPLUS\nUSE WRITEPERFPROBE\n',1)
    commands=re.findall(r'IDEPLUSNATIVE.WriteRegister\(IDEPLUS.REG_COMMAND,IDEPLUS.(ATA_READ|ATA_WRITE|ATA_FLUSH)\)',original)
    require(sorted(commands)==['ATA_FLUSH','ATA_READ','ATA_WRITE'],'Changed ATA command sites')
    original=re.sub(r'(?m)^( +)(IDEPLUSNATIVE.WriteRegister\(IDEPLUS.REG_COMMAND,IDEPLUS.(ATA_READ|ATA_WRITE|ATA_FLUSH)\))',r'\1WRITEPERFPROBE.ATA(IDEPLUS.\3)\n\1\2',original)
    start=original.index('BYTE FUNC WriteLogical(')
    finish=original.index('PROC RunRequest(',start)
    writing=original[start:finish]
    require(writing.count('  error=ReadPhysical(sector)')==(2 if frozen else 0),'Changed write read phases')
    if frozen:
        writing=writing.replace('  error=ReadPhysical(sector)','  WRITEPERFPROBE.Reading(1)\n  error=ReadPhysical(sector)',1)
        last=writing.rfind('  error=ReadPhysical(sector)')
        writing=writing[:last]+'  WRITEPERFPROBE.Reading(0)\n'+writing[last:]
    original=original[:start]+writing+original[finish:]
    driver.write_text(original)
    if count_comparisons:
        source=read_source(validation_source or library_file('sdfswrite.act'),
                           {p.name:p for p in (ROOT/'lib').rglob('*.inc')})
        source=source.replace('USE FSTYPES\n','USE FSTYPES\nUSE WRITEPERFPROBE\n',1)
        if '        IF SDFS.Word(state.map,other)=sector THEN' in source:
            source=source.replace('        IF SDFS.Word(state.map,other)=sector THEN',
                '        WRITEPERFPROBE.comparisons==+1\n        IF SDFS.Word(state.map,other)=sector THEN',1)
        else:
            for marker in ('    IF value>=refs(child) THEN','    IF refs(index-1)=refs(index) THEN'):
                require(source.count(marker)==1,'Changed sort comparison site')
                source=source.replace(marker,'    WRITEPERFPROBE.comparisons==+1\n'+marker,1)
            marker='    IF child+1<count AND refs(child)<refs(child+1) THEN'
            require(source.count(marker)==1,'Changed heap-child comparison site')
            source=source.replace(marker,'    IF child+1<count THEN\n      WRITEPERFPROBE.comparisons==+1\n    FI\n'+marker,1)
        (out/'sdfswrite.act').write_text(source)
    program_source=out/'write_performance.act'
    program_source.write_text(program_source.read_text().replace('$efff0','$2dfff0'))
    if open_bytes:
        program_source.write_text(f'''MODULE WRITEROPEN
USE EXEC
USE DOS
USE DOSCORE
USE FSTYPES
USE FSBOOT
USE BLOCKIO
USE WRITEPERFPROBE
USE HEAPCORE
INCLUDE "{ROOT}/lib/exec/exec-abi.inc"
VOLATILE CARD clock=E816_VBI_COUNT
VOLATILE CARD gateway=E816_GATE_COUNT
CARD openFrames,openCalls

PROC Main()

  IF FSBOOT.Ensure()=0 THEN
    HEAPCORE.Abort($fc01)
  FI

  LET registry=DOSCORE.GetRegistry()
  LET service=FSTYPES.Service POINTER(registry.runtime)
  BLOCKIO.Invalidate(service.adapter)
  WRITEPERFPROBE.Begin()
  LET handle=DOS.Open(BYTE POINTER(c"WORK:COPY.BIN"),DOS.MODE_READWRITE)
  openFrames=clock-WRITEPERFPROBE.startFrame
  openCalls=gateway-WRITEPERFPROBE.kernelCalls
  IF handle=NULL THEN
    HEAPCORE.Abort($fc02)
  FI

  IF DOS.Close(handle)=0 THEN
    HEAPCORE.Abort($fc03)
  FI

  WRITEPERFPROBE.End()
  IF DOS.ReleaseContext()=0 THEN
    HEAPCORE.Abort($fc04)
  FI

RETURN

ENDMODULE
''')
    tree=out/'source';tree.mkdir(exist_ok=True)
    command=tree/'COPY16'
    compile_command(t,ROOT/'examples/commands/copy.act',command)
    for suffix in ('options.json','profile.json'):(tree/('COPY16.'+suffix)).rename(out/('COPY16.'+suffix))
    content=(ROOT/'examples/demo-disk/LONG.TXT').read_bytes()
    (tree/'LONG.TXT').write_bytes(content)
    if open_bytes:
        content=bytes((i*17+3)&255 for i in range(open_bytes))
    target=out/'target';target.mkdir(exist_ok=True);(target/'KEEP.BIN').write_bytes(bytes(range(256)))
    if open_bytes:
        (target/'COPY.BIN').write_bytes(content)
    size=256 if frozen else 512
    sectors=2880 if frozen else 1440
    make(out/'system.atr',tree,binary_names=['COPY16','LONG.TXT'],sector_bytes=size,sectors=sectors)
    make(out/'work.atr',target,binary_names=['KEEP.BIN','COPY.BIN'],sector_bytes=size,sectors=sectors)
    mounts=[dict(alias='SYSTEM',device='ideplus.device',unit=1,profile=0,format=2,sectors=sectors,sector_bytes=size),
            dict(alias='WORK',device='ideplus.device',unit=2,profile=0,format=2,sectors=sectors,sector_bytes=size,access='readwrite')]
    if frozen:
        legacy_media=frozen_module(frozen/'tools/ideplus_media.py')
        legacy_builder=frozen_module(frozen/'tools/build_ide_media.py')
        legacy_builder.put_sector=legacy_media.put_sector
        legacy_builder.filesystem_atr=legacy_media.filesystem_atr
        mapping=legacy_builder.write(out/'ideplus.img',out/'system.atr',out/'work.atr')
        wire=frozen_module(frozen/'tools/generate_dos_mounts.py').encode(mounts)
    else:
        mapping=write(out/'ideplus.img',out/'system.atr',out/'work.atr')
        from generate_dos_mounts import encode
        wire=encode(mounts)
    # Runtime wire geometry selects the snapshot layout without retaining a
    # legacy profile in the current generator or production driver.
    compile_mounts=[{**m,'sectors':1440,'sector_bytes':512} for m in mounts]
    profile=json.loads((ROOT/'platform/altirraos/memory-4m.json').read_text());profile['image_data_bytes']=4352
    (out/'profile.json').write_text(json.dumps(profile))
    p=build(t,out/'write_performance.act',out,optimize=True,tasks=True,task_capacity=8,console_deferred=True,system_mount='SYSTEM',dos_mounts=compile_mounts,memory_profile=out/'profile.json',image_data=[(0x2dffd0,bytes([0xa5])*(16384+64)),(0x320000,bytes(8192))])
    return p,wire,mapping,content,size,command,tree


def run(out,frozen=None,from_build=None,warm=False,open_bytes=0,count_comparisons=False,validation_source=None,driver_timing=False):
    require(not count_comparisons or (open_bytes and from_build is None), 'Count comparisons in a fresh Open probe')
    require(validation_source is None or count_comparisons, 'Source overrides are comparison-count probes only')
    require(0 <= open_bytes <= 524288, 'Invalid selected-file size')
    require(not open_bytes or not (frozen or warm), 'Open timing uses current cold media')
    out.mkdir(parents=True,exist_ok=True)
    if from_build:
        require(frozen is None,'Choose a retained build or frozen sources')
        p=read_build(from_build)
        require(p['build']['optimize'],'Performance requires optimized code')
        import shutil
        for name in ('system.atr','work.atr','manifest.bin'):
            shutil.copyfile(from_build/name,out/name)
        if open_bytes:
            require(any('_WRITEROPEN_OPENFRAMES_' in d['name'] for d in p['image']['data']), 'Retained image is not an Open probe')
            target=out/'target';target.mkdir(exist_ok=True)
            (target/'KEEP.BIN').write_bytes(bytes(range(256)))
            (target/'COPY.BIN').write_bytes(bytes((i*17+3)&255 for i in range(open_bytes)))
            make(out/'work.atr',target,binary_names=['KEEP.BIN','COPY.BIN'],sector_bytes=512,sectors=1440)
        mapping=write(out/'ideplus.img',out/'system.atr',out/'work.atr')
        wire=None
        content=bytes((i*17+3)&255 for i in range(open_bytes)) if open_bytes else (ROOT/'examples/demo-disk/LONG.TXT').read_bytes()
        size=512
        tree=from_build/'source'
        command=tree/'COPY16'
    else:
        p,wire,mapping,content,size,command,tree=prepare(out,frozen,open_bytes,count_comparisons,validation_source)
    with driver_observer(p,driver_timing) as observer, ide_emulator(out,out/'ideplus.img',writable=True) as b:
        def before(b):
            if driver_timing:
                b.profile_start()
            if wire is not None:
                b.memload(p['build']['task_storage']['BASE']+0x900,wire)
            if open_bytes:
                return
            for field,value in [('WARM',bytes([warm])),('VARIANT',b'\1'),('ARGUMENTS',b'SYS:LONG.TXT WORK:COPY.BIN\0'),('ARGUMENTBYTES',len(b'SYS:LONG.TXT WORK:COPY.BIN').to_bytes(2,'little'))]:
                address=next(d['address'] for d in p['image']['data'] if '_WRITEPERFORMANCE_'+field+'_' in d['name'])
                b.memload(address,value)
        runtime,_=execute(b,{**p,'output':out},before_run=before,timeout=300,frame_limit=15000)
        if driver_timing:
            b.profile_stop()
        clean_ownership(b,p,out)
        view={**p['image'],'data':[d for d in p['image']['data'] if '_WRITEPERFPROBE_' in d['name']]}
        counts={name:int.from_bytes(bytes(data(b,view,name)),'little') for name in ('startFrame','endFrame','ataReads','ataWrites','ataFlushes','prepReads','verifyReads','completedWrites','cacheHits','cacheMisses','cacheEvictions','logicalReads')}
        if open_bytes:
            counts['openFrames']=int.from_bytes(bytes(data(b,p['image'],'openFrames')),'little')
            counts['openCalls']=int.from_bytes(bytes(data(b,p['image'],'openCalls')),'little')
        if count_comparisons:
            counts['comparisons']=int.from_bytes(bytes(data(b,view,'comparisons')),'little')
        for name in ('kernelCalls','taskSwitches'):
            if any('_'+name.upper()+'_' in d['name'] for d in view['data']):
                counts[name]=int.from_bytes(bytes(data(b,view,name)),'little')
    media=out/'ideplus.img'
    if frozen:
        restored=frozen_module(frozen/'tools/ideplus_media.py').filesystem_atr(media.read_bytes(),mapping['partitions'][1],(out/'work.atr').read_bytes())
    else:
        from ideplus_media import filesystem_atr
        restored=filesystem_atr(media.read_bytes(),mapping['partitions'][1],(out/'work.atr').read_bytes())
    audit=Audit(restored);allocation=audit.sdfs()
    require(audit.files=={'KEEP.BIN':bytes(range(256)),'COPY.BIN':content},'COPY persistence differs')
    require(counts['completedWrites']==counts['ataWrites'],'A write did not complete')
    require(counts['verifyReads']==(counts['ataWrites'] if frozen else 0),'Verification phase count differs')
    require(counts['prepReads']==(counts['ataWrites'] if frozen else 0),'Preparation phase count differs')
    frames=(counts['endFrame']-counts['startFrame'])&65535
    result=dict(status='pass',tier='development',snapshot=str(frozen) if frozen else None,build=p['build'],pin=PIN,counts=counts,guest_frames=frames,guest_seconds=frames/50,bytes=len(content),source_sha256=sha256(tree/'LONG.TXT'),command_sha256=sha256(command),sector_bytes=size,cache_blocks=p['build']['memory']['boot_config']['cache_blocks'],allocation=allocation,runtime=runtime)
    result['observer_inputs']={p.name:sha256(p) for p in out.glob('*.act')}
    result['observer_sha256']=sha256(Path(__file__))
    result['timing_valid']=not count_comparisons
    result['validation_source']=str(validation_source) if validation_source else None
    result['workload']='writable-open-close' if open_bytes else 'loaded-copy'
    result['selected_file_bytes']=open_bytes
    result['warm_source']=warm
    result['retained_build']=str(from_build) if from_build else None
    if observer:
        result['driver_phases']=phase_summary(out,observer)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('IDE writable Open/Close:' if open_bytes else 'IDE loaded COPY:',size,frames,'frames',counts,flush=True)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--frozen-sources',type=Path)
    a.add_argument('--from-build',type=Path);a.add_argument('--warm-source',action='store_true');a.add_argument('--open-bytes',type=int,default=0);a.add_argument('--count-comparisons',action='store_true');a.add_argument('--validation-source',type=Path)
    a.add_argument('--driver-timing',action='store_true')
    v=a.parse_args();run(v.output,v.frozen_sources,v.from_build,v.warm_source,v.open_bytes,v.count_comparisons,v.validation_source,v.driver_timing)
