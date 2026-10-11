"""Matched loaded COPY on fresh IDE media, with physical ATA phase counts.

The frozen comparison is an explicit development-only source snapshot. It is
never a production compatibility path and uses the same pinned compiler/ROM.
"""
import argparse
import importlib.util
import json
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


def frozen_module(path):
    spec=importlib.util.spec_from_file_location('frozen_'+path.stem,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module


def prepare(out,frozen=None):
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
    program_source=out/'write_performance.act'
    program_source.write_text(program_source.read_text().replace('$efff0','$2dfff0'))
    tree=out/'source';tree.mkdir(exist_ok=True)
    command=tree/'COPY16'
    compile_command(t,ROOT/'examples/commands/copy.act',command)
    for suffix in ('options.json','profile.json'):(tree/('COPY16.'+suffix)).rename(out/('COPY16.'+suffix))
    content=(ROOT/'examples/demo-disk/LONG.TXT').read_bytes()
    (tree/'LONG.TXT').write_bytes(content)
    target=out/'target';target.mkdir(exist_ok=True);(target/'KEEP.BIN').write_bytes(bytes(range(256)))
    size=256 if frozen else 512
    sectors=2880 if frozen else 1440
    make(out/'system.atr',tree,binary_names=['COPY16','LONG.TXT'],sector_bytes=size,sectors=sectors)
    make(out/'work.atr',target,binary_names=['KEEP.BIN'],sector_bytes=size,sectors=sectors)
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


def run(out,frozen=None,from_build=None,warm=False):
    out.mkdir(parents=True,exist_ok=True)
    if from_build:
        require(frozen is None,'Choose a retained build or frozen sources')
        p=read_build(from_build)
        require(p['build']['optimize'],'Performance requires optimized code')
        import shutil
        for name in ('system.atr','work.atr','manifest.bin'):
            shutil.copyfile(from_build/name,out/name)
        mapping=write(out/'ideplus.img',out/'system.atr',out/'work.atr')
        wire=None
        content=(ROOT/'examples/demo-disk/LONG.TXT').read_bytes()
        size=512
        tree=from_build/'source'
        command=tree/'COPY16'
    else:
        p,wire,mapping,content,size,command,tree=prepare(out,frozen)
    with ide_emulator(out,out/'ideplus.img',writable=True) as b:
        def before(b):
            if wire is not None:
                b.memload(p['build']['task_storage']['BASE']+0x900,wire)
            for field,value in [('WARM',bytes([warm])),('VARIANT',b'\1'),('ARGUMENTS',b'SYS:LONG.TXT WORK:COPY.BIN\0'),('ARGUMENTBYTES',len(b'SYS:LONG.TXT WORK:COPY.BIN').to_bytes(2,'little'))]:
                address=next(d['address'] for d in p['image']['data'] if '_WRITEPERFORMANCE_'+field+'_' in d['name'])
                b.memload(address,value)
        runtime,_=execute(b,{**p,'output':out},before_run=before,timeout=300,frame_limit=15000)
        clean_ownership(b,p,out)
        view={**p['image'],'data':[d for d in p['image']['data'] if '_WRITEPERFPROBE_' in d['name']]}
        counts={name:int.from_bytes(bytes(data(b,view,name)),'little') for name in ('startFrame','endFrame','ataReads','ataWrites','ataFlushes','prepReads','verifyReads','completedWrites','cacheHits','cacheMisses','cacheEvictions')}
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
    result['warm_source']=warm
    result['retained_build']=str(from_build) if from_build else None
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n')
    print('IDE loaded COPY:',size,frames,'frames',counts,flush=True)
    return result

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--output',type=Path,required=True);a.add_argument('--frozen-sources',type=Path)
    a.add_argument('--from-build',type=Path);a.add_argument('--warm-source',action='store_true')
    v=a.parse_args();run(v.output,v.frozen_sources,v.from_build,v.warm_source)
