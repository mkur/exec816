#!/usr/bin/env python3
"""Build the retained QED graph, with explicit analysis or executable output."""
import argparse,json,re,struct
from pathlib import Path

from analysis_artifact import MARKER
from build_c_program import verify_relocations
from c_program import ABI,import_assembly,pack,shape
from calypsi_build import emit
from generate_qed_compat import generate,TARGET
from native_program import ROOT,require,sha256
from prepare_qed import PORT,prepare


def selected():
    selection=json.loads((PORT/'native-selection.json').read_text())
    pin=json.loads((PORT/'inputs.json').read_text())
    expected={(source['id'],name) for source in pin['sources'] for name in source['files']
        if name.endswith('.c') and ((source['id']=='qed' and name.startswith('src/')) or
                                   (source['id']=='cflib' and '/' not in name))}
    rows=selection['units']+selection['excluded']
    actual=[(r['origin'],r['path']) for r in rows]
    require(len(actual)==len(set(actual)) and set(actual)==expected,
            'QED selection must account for every pinned source exactly once')
    return selection


def object_symbols(path):
    raw=path.read_bytes();header=struct.unpack_from('<HHIIIIIHHHHHH',raw,16)
    rows=[struct.unpack_from('<IIIIIIIIII',raw,header[5]+i*header[10]) for i in range(header[11])]
    result={}
    for row in rows:
        if row[1]!=2:continue
        strings=rows[row[6]];names=raw[strings[4]:strings[4]+strings[5]]
        for at in range(row[4],row[4]+row[5],16):
            name,value,size,info,other,section=struct.unpack_from('<IIIBBH',raw,at)
            if name:result[names[name:].split(b'\0',1)[0].decode()]=dict(
                section=section,binding=info>>4,kind=info&15,size=size)
    return result


def units_from_listing(path):
    """Actual retained sections, including selected archive members and helpers."""
    text=path.read_text()
    pattern=r'^\s*\d+\s+(.+?)\s+(-|\S+\.a)\n((?:\s+(?:>|#)[^\n]*\n)+)'
    return [dict(source=m[1].strip(),archive=None if m[2]=='-' else m[2],
        sections={name:int(size,16) for name,size in
        re.findall(r'>\s+(\w+)\s+([0-9a-f]+)',m[3])}) for m in re.finditer(pattern,text,re.M)]


def build(output,provider,executable=False):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    for name in ('program.app','app.json'):(output/name).unlink(missing_ok=True)
    selection=selected();inputs=prepare(output/'inputs');native=PORT/'native'
    provider=Path(provider).resolve();resident=json.loads(provider.read_text())
    require(resident['provenance']['c_program_provider']['abi']==ABI['version'],
            'QED layout needs a matching current C provider')
    provider_code=sum(len(s['bytes']) for s in resident['segments'] if s['executable'])
    provider_tables=sum(len(s['bytes']) for s in resident['segments'] if
        s['address']>>16 in resident['provenance']['readonly_table_banks'])
    provider_data=sum(len(s['bytes']) for s in resident['segments'] if s['writable'])+sum(
        s['size'] for s in resident['zero_fill'])
    caps=selection['resident_provider_allowances']
    require(provider_code+caps['code_bytes']<=3*65536 and provider_tables+caps['table_bytes']<=65536
            and provider_data+caps['data_bss_bytes']<=65536,'Provider and explicit allowances exceed its layout')
    reference=ROOT/'build/gem-vdi/upstream/src/app/gem.h'
    require(TARGET.read_text()==generate(reference),'Stale private QED GEM declarations')
    catalog=json.loads((PORT/'analysis-bindings.json').read_text())['bindings']
    require(len({b['name'] for b in catalog})==len(catalog),'Duplicate analysis binding')
    require(all(b.get('status','pending') in ('pending','adapted','implemented') for b in catalog),
            'Unknown QED binding disposition')
    header=(native/'qed-gem-extra.h').read_text()
    pending=[b for b in catalog if b.get('status','pending')=='pending']
    require(not executable or not pending,'Executable QED still has analysis bindings')
    for b in pending:
        require(b['declaration'] in header and b['name'].startswith(('appl_','graf_','objc_','v_','vs','vq','vr')),
                'Analysis binding must be an explicit later GEM interface: '+b['name'])
    traps=output/'analysis-traps.c'
    traps.write_text('#include "qed-native.h"\nconst char __exec_analysis_only[]="'+MARKER.decode()+'";\n'+
        '\n'.join(b['declaration'][:-1]+'{for(;;){}}' for b in pending)+'\n')
    sources=[output/'inputs/source'/u['origin']/u['path'] for u in selection['units']]
    sources += [native/name for name in selection['native_sources']]+([] if executable else [traps])
    definitions={str(p):['-D'+d for d in selection['defines']]+
        ['-Werror=implicit-function-declaration']+selection['compiler_options']+
        (['--char-is-unsigned'] if '/source/qed/' in str(p) or p.parent==native else [])
        for p in sources}
    imports=output/'imports.s';imports.write_text(import_assembly())
    roots=[] if executable else ['__exec_analysis_only']
    image=emit(output,sources,[imports,ROOT/'c/calypsi/image-info.s'],(),roots=roots,
        includes=[native,output/'inputs/source/qed/src',output/'inputs/source/cflib'],
        definitions=definitions,runtime_attributes={'printf':'nofloat'})
    # A complete real link is mandatory. Essential runtime helpers cannot enter the catalog.
    require(not {'exit','_Stub_exit','_Stub_assert','_Exit'} & set(image['symbols']),
            'Retained QED closure contains a board termination dependency')
    image['provenance']['analysis_only']=not executable
    require(not any(b['name'] in image['symbols'] for b in catalog if b.get('status')=='adapted'),
            'An adapted donor GEM dependency is still linked')
    callers={b['name']:[] for b in catalog}
    for number,source in enumerate(sources):
        symbols=object_symbols(output/(str(number)+'-'+source.stem+'.o'))
        for name in callers:
            if name in symbols and symbols[name]['section']==0:callers[name].append(str(source))
    bindings=[dict(b,linked=b['name'] in image['symbols'],callers=callers[b['name']]) for b in catalog]
    relocations,banks=verify_relocations(output,image,roots=roots)
    segments=shape(image,ABI['link_bank']);span=max(s['offset']+s['size'] for s in segments)
    code=sum(len(s['bytes']) for s in image['segments'] if s['executable'])
    initialized=sum(len(s['bytes']) for s in image['segments'] if not s['executable'])
    bss=sum(s['size'] for s in image['zero_fill'])
    imports_count=sum(n in image['symbols'] for n in ABI['imports'])
    serialized=ABI['header_bytes']+16*len(segments)+8*imports_count+4*len(relocations)+code+initialized
    allowance=selection['private_allowances']
    require(code+allowance['code_bytes']<=3*65536,'QED code plus allowance exceeds three code banks')
    require(initialized+bss+allowance['data_bss_bytes']<=65536,'QED data plus allowance exceeds its bank')
    require(serialized+sum(allowance.values())+selection['container_metadata_allowance_bytes']<=ABI['file_limit'],'QED serialized size plus allowance exceeds file cap')
    # Test the direct packer boundary, independently of any filename or sidecar.
    if executable:
        payload,app=pack(image,relocations,selection['minimum_stack_bytes'])
        (output/'program.app').write_bytes(payload)
        app.update(abi=ABI,bytes=len(payload),sha256=sha256(output/'program.app'),
            verified_banks=banks,image=image,inputs={str(p):sha256(p) for p in sources})
        (output/'app.json').write_text(json.dumps(app,indent=2)+'\n')
    else:
        try:pack(image,relocations)
        except RuntimeError as error:require('Analysis-only' in str(error),'Unexpected packaging failure')
        else:raise RuntimeError('Analysis artifact escaped packaging rejection')
    linked_units=units_from_listing(output/'link.lst')
    accounted=sum(sum(u['sections'].values()) for u in linked_units)
    require(accounted==code+initialized+bss+16+image['provenance']['dp_workspace_bytes'],
            'Link summary does not account for all loaded and virtual bytes')
    record=dict(schema_version=1,status='executable-development' if executable else 'analysis-only',tier='development',inputs=inputs,
        selection=selection,bindings=bindings,analysis_bindings=[b['name'] for b in pending],abi=ABI,verified_banks=banks,
        complete_link=True,unresolved_essential_helpers=[],
        image=image,link_units=linked_units,link_summary_reconciled_bytes=accounted,
        layout=dict(code_bytes=code,initialized_bytes=initialized,bss_bytes=bss,
            import_thunk_bytes=4*imports_count,span_bytes=span,
            image_holes_bytes=span-code-initialized-bss,
            serialized_bytes_if_executable=serialized,relocation_count=len(relocations),
            heap_alignment_backing_bytes=(span+65535+3)//4*4,
            future_full_profile_backing_bytes=(ABI['span_limit']+65535+3)//4*4,
            private_allowances=allowance,container_metadata_allowance_bytes=selection['container_metadata_allowance_bytes'],
            resident_provider_allowances=selection['resident_provider_allowances']),
        resident_provider=dict(path=str(provider),sha256=sha256(provider),code_bytes=provider_code,
            table_bytes=provider_tables,data_bss_bytes=provider_data,allowances=caps),
        elf_sha256=sha256(output/'program.elf'),
        build_inputs={str(p):sha256(p) for p in [*sources,PORT/'native-selection.json',PORT/'analysis-bindings.json',reference]},
        bank_zero_delta=selection['bank_zero_delta'])
    if not executable:record['analysis_elf_sha256']=record['elf_sha256']
    if executable:record['app']=dict(path=str(output/'program.app'),sha256=app['sha256'],bytes=app['bytes'],minimum_stack_bytes=selection['minimum_stack_bytes'])
    (output/'layout.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--provider',type=Path,required=True)
    parser.add_argument('--executable',action='store_true');args=parser.parse_args()
    result=build(args.output,args.provider,args.executable)
    print('QED',result['status'],result['layout'])
