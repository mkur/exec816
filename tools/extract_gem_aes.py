"""Hash-checked AES function extraction followed by explicit hosted patches."""
import ast
import json
import re
from pathlib import Path
from native_program import ROOT, command, require, sha256

PORT = ROOT/'ports/gem4xe/aes'


def alert_icons(source):
    """Encode the pinned 32x32 masks as (row, left, width) black fill runs."""
    tree=ast.parse(source)
    masks=next(ast.literal_eval(node.value) for node in tree.body
        if isinstance(node,ast.Assign) and any(isinstance(t,ast.Name) and
            t.id=='ALERT_ICONS' for t in node.targets))
    runs=[];offsets=[0]
    for name in ('NOTE','QUEST','STOP'):
        words=masks[name]
        require(len(words)==64,'Alert mask must have 32 rows')
        for y in range(32):
            bits=(words[y*2]<<16)|words[y*2+1];x=0
            while x<32:
                if not (bits & (1<<(31-x))):x+=1;continue
                left=x
                while x<32 and bits & (1<<(31-x)):x+=1
                runs.extend((y,left,x-left))
        offsets.append(len(runs))
    return offsets,runs


def extract(output, upstream=None):
    output=Path(output);output.mkdir(parents=True,exist_ok=True)
    upstream=Path(upstream or ROOT/'build/gem-vdi/upstream')
    pin=json.loads((PORT/'inputs.json').read_text())
    for name,digest in pin['files'].items():
        require(sha256(upstream/name)==digest,'Changed AES donor: '+name)
    offsets,runs=alert_icons((upstream/'tools/gemdata.py').read_text())
    (output/'alert-icons.h').write_text(
        '/* Generated from pinned GEM4XE tools/gemdata.py; EmuTOS GPLv2 artwork. */\n'+
        'static const UWORD AlertIconOffsets[]={'+','.join(map(str,offsets))+'};\n'+
        'static const UBYTE AlertIconRuns[]={\n'+
        ''.join(','.join(map(str,runs[n:n+24]))+',\n' for n in range(0,len(runs),24))+'};\n')
    selection=json.loads((PORT/'selection.json').read_text())
    selected={}
    for name,spec in selection['outputs'].items():
        require(spec['source'] in pin['files'],'Unpinned AES input')
        source=(upstream/spec['source']).read_text();parts=[]
        for function in spec['functions']:
            match=re.search(r'^(?:static )?\w[\w *]*\b'+function+r'\(',source,re.M)
            require(match is not None,'Missing donor function: '+function)
            end=re.search(r'^}',source[match.start():],re.M)
            require(end is not None,'Missing function end')
            parts.append(source[match.start():match.start()+end.end()]+'\n')
        (output/name).write_text('#include "aes-hosted.h"\n\n'+'\n'.join(parts))
        selected[name]=sha256(output/name)
    patches=sorted((PORT/'patches').glob('*.patch'))
    for patch in patches:command(['patch','-p1','-F','0','-t','-i',patch],cwd=output)
    source=(upstream/'src/aes/aes.h').read_text()
    header=source[source.index('typedef struct {'):source.index('/* evnt_multi')]
    header += source[source.index('/* TEDINFO,'):source.index('/* BITBLK,')]
    header += '\n#define TE_LEFT 0\n#define TE_RIGHT 1\n#define TE_CNTR 2\n'
    (output/'aes-objects.h').write_text('#ifndef HOSTED_AES_OBJECTS_H\n#define HOSTED_AES_OBJECTS_H\n'+header+'\n#endif\n')
    for name in ('COPYING','COPYING.LIB'):(output/name).write_bytes((upstream/name).read_bytes())
    record=dict(revision=pin['revision'],inputs=pin['files'],selected=selected,
        patches={p.name:sha256(p) for p in patches},
        adapted={p.name:sha256(p) for p in output.iterdir() if p.suffix in ('.c','.h')})
    (output/'extraction.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
