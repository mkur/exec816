#!/usr/bin/env python3
"""Relink supplied QED objects with the user's pinned Calypsi installation."""
import argparse
import json
import shutil
from pathlib import Path

from build_c_program import verify_relocations
from calypsi_image import read_image
from c_program import ABI, pack
from native_program import command, require, sha256


COMPONENTS=dict(qed='source/qed/',cflib='source/cflib/',native='native/',
    bindings='exec816/c/',runtime='runtime-source/',exec='exec816/lib/',
    gem='third-party/gem-',calculator='third-party/calc/',g4bench='third-party/g4bench/',
    **{'actionc-runtime':'third-party/actionc-runtime/'})


def material(directory):
    record=json.loads((directory/'source-material.json').read_text())
    require(record['schema_version']==1 and record['abi']==ABI,'Unsupported QED relink material')
    for name,digest in record['files'].items():
        path=Path(name)
        require(not path.is_absolute() and '..' not in path.parts,'Invalid QED material path')
        require((directory/path).is_file() and sha256(directory/path)==digest,'Missing/changed QED material: '+name)
    require(set(record['components'])==set(COMPONENTS) and
            set(record.get('component_sources',{}))==set(COMPONENTS),'Incomplete QED source component inventory')
    for component,prefix in COMPONENTS.items():
        paths=record['component_sources'][component]
        require(paths and all(n in record['files'] and n.startswith(prefix) for n in paths),
                'Missing QED component source: '+component)
    inventory=json.loads((directory/'link-inventory.json').read_text())
    require(inventory['status']=='pass' and inventory['app_sha256']==record['app_sha256'],
            'Source link inventory differs from QED')
    for name,digest in record['application_sources'].items():
        require(record['files'].get(name)==digest,'Missing compiled QED source: '+name)
    for name,row in inventory['native_files'].items():
        require(record['files'].get('native/'+Path(name).name)==row['sha256'],
                'Missing inventoried native QED source: '+name)
    for unit in inventory['link_units']:
        if unit['component']!='runtime' or ':' not in unit['source']:
            require('objects/'+unit['object'] in record['objects'],'Missing retained QED object: '+unit['object'])
    require(record['objects'] and record['cflib_objects'] and record['source_revision'] and
            'exec816/c/calypsi/layout.scm' in record['files'],'Incomplete QED relink material')
    require(all(o in record['files'] for o in record['objects']) and
            all(o in record['objects'] and s in record['files'] for o,s in record['cflib_objects'].items()),
            'Incomplete QED library/object mapping')
    return record


def relink(directory,output,replace=None):
    directory,output=directory.resolve(),output.resolve()
    record=material(directory);output.mkdir(parents=True,exist_ok=True)
    tools={}
    for name,expected in record['tools'].items():
        path=Path(shutil.which(name) or '/missing')
        require(path.is_file() and sha256(path)==expected['sha256'],'Install the pinned Calypsi '+name)
        tools[name]=dict(path=str(path),sha256=sha256(path))
    prefix=Path(tools['ln65816']['path']).resolve().parent.parent
    runtime=prefix/'lib/clib-lc-hd.a'
    require(runtime.is_file() and sha256(runtime)==record['runtime_sha256'],'Changed Calypsi runtime archive')
    objects=[directory/n for n in record['objects']]
    replacement=None
    if replace:
        object_name,source=replace
        require(object_name in record['cflib_objects'],'Replacement must name a retained CF-Lib object')
        replacement=output/Path(object_name).name
        includes=[directory/'exec816/c/include',directory/'exec816/platform/altirraos',
                  directory/'native',directory/'source/qed/src',directory/'source/cflib',prefix/'src/lib']
        command([tools['cc65816']['path'],'--code-model=large','--data-model=huge','-O2',
                 *record['compiler_options'],'-c',*[v for p in includes for v in ('-I',p)],
                 '--list-file',replacement.with_suffix('.lst'),'-o',replacement,Path(source).resolve()])
        require(sha256(replacement)!=record['files'][object_name],'Replacement object did not change')
        objects[record['objects'].index(object_name)]=replacement
    layout=directory/'exec816/c/calypsi/layout.scm'
    command([tools['ln65816']['path'],'--hosted','--program-root','main','--program-start','main',
        '--root-symbol','__exec_image_info','--rtattr','printf=nofloat','--no-data-init-table-section',
        '--no-automatic-placement-rules','--list-file',output/'link.lst','-o',output/'program.elf',*objects,layout])
    image=read_image(output/'program.elf')
    image['provenance'].update(tools=tools,runtime_attributes={'printf':'nofloat'},
        link_objects=[str(p) for p in objects],analysis_only=False)
    # This script lives in the supplied Exec tree; its standard relocation verifier
    # uses that same linker layout and exhausts all permitted application banks.
    relocations,banks=verify_relocations(output,image)
    payload,app=pack(image,relocations,record['minimum_stack_bytes'])
    (output/'program.app').write_bytes(payload)
    if not replacement:require(sha256(output/'program.app')==record['app_sha256'],'Relink differs from production QED')
    else:require(sha256(output/'program.app')!=record['app_sha256'],'Replacement did not change a retained routine')
    result=dict(status='pass',tier='development',qualification=False,
        app_sha256=sha256(output/'program.app'),original_app_sha256=record['app_sha256'],
        source_material_sha256=sha256(directory/'source-material.json'),verified_banks=banks,
        replacement=dict(object=replace[0],source_sha256=sha256(Path(replace[1])),
                         object_sha256=sha256(replacement)) if replace else None)
    (output/'relink-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--material',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--replace-cflib',nargs=2,metavar=('OBJECT','SOURCE'))
    a=p.parse_args();relink(a.material,a.output,a.replace_cflib)
