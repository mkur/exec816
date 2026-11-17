"""Passive text preparation/painting costs on the cached MGVIEW fixture."""
from collections import defaultdict
import re

from console_turn_profile import Timeline,analyze_events
from g4bench_trace import calls
from mgview_frame_trace import partition
from native_program import require
from sio_transaction_trace import read_events


GROUPS={
    'text_entry':'v_gtext',
    'text_setup_and_loop':'VDI_text',
    'input_conversion':'text_input_conversion',
    'visibility_clipping':'VDI_paint',
    'damage_preparation':'text_damage_preparation',
    'damage_reporting':'ExecAESChanged',
    'draw_admission':'GemDrawingBorrow drawing_borrow DisplayEnter DisplayLeave',
    'glyph_preparation':'GemVdiPaint',
    'glyph_adapter':'vbxe_text_run',
    'driver_text':'VBXE_text_run',
    'command_encoding_and_upload':'_VbxeTextUpload _VbxeUpload',
    'queue':'drain fence_owner',
    'fences':'VbxeOwnerFence',
}


def linked_section(image,listing,name):
    """Resolve the emitted local function, rather than a same-named data symbol."""
    sections=[s for s in listing.split('.section ')[1:] if s.startswith('farcode,text')
              and re.search(r'\\ 000000\s+'+re.escape(name)+':',s)]
    require(len(sections)==1,'Missing/ambiguous local C function: '+name)
    section=sections[0];code={}
    for m in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',section):
        offset=int(m[1],16)
        for i in range(0,len(m[2]),2):code[offset+i//2]=m[2][i:i+2]
    require(code and set(code)==set(range(max(code)+1)),'Incomplete local C listing')
    pattern=b''.join(b'.' if code[i]=='..' else re.escape(bytes.fromhex(code[i])) for i in range(len(code)))
    matches=[s['address']+m.start() for s in image['segments'] if s['executable']
             for m in re.finditer(pattern,bytes(s['bytes']),re.S)]
    require(len(matches)==1,'Missing/ambiguous linked local function: '+name)
    return matches[0],section


def source_point(section,source):
    require(section.count(source)==1,'Missing/ambiguous text source boundary: '+source)
    tail=section[section.index(source):]
    match=re.search(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',tail)
    require(match is not None,'Missing emitted source boundary: '+source)
    return int(match[1],16)


def definition(cache,foreign):
    entries={foreign['symbols'][n]:n for n in GROUPS['text_entry'].split()}
    for group,names in GROUPS.items():
        if group in ('text_setup_and_loop','input_conversion','visibility_clipping',
                     'damage_preparation','driver_text'):continue
        for n in names.split():
            require(n in foreign['symbols'],'Missing text trace routine: '+n)
            entries[foreign['symbols'][n]]=n
    listing=(cache/'drawing/24-vdi.lst').read_text()
    text,section=linked_section(foreign,listing,'text')
    paint,_=linked_section(foreign,listing,'paint')
    driver,_=linked_section(foreign,(cache/'drawing/2-vbxe.lst').read_text(),'text_run')
    entries.update({text:'VDI_text',paint:'VDI_paint',driver:'VBXE_text_run'})
    points={text+source_point(section,'count=0;'):'convert_begin',
            text+source_point(section,'if (!count) break;'):'convert_end',
            text+source_point(section,'if (at>origin) changed'):'damage_begin'}
    return dict(entries=entries,points=points,pcs=sorted(set(entries)|set(points)))


def analyze(out,definition,audit):
    events=read_events(out/'emulator.log',kinds={'cpu'})
    interrupts={definition['timeline']['points'][n] for n in ('native_irq','native_nmi')}
    while events and int(events[-1][1][4],16) in interrupts:events.pop()
    profile=analyze_events(events,definition['timeline'],include_segments=True)
    selected=definition['text'];dp=audit['samples'][0]['viewer_dp']
    timeline=Timeline(profile['segments'],dp)
    rows,unfinished=calls(events,selected['entries'],set(definition['returns']),dp,
                          set(definition['exits']))
    kinds={n:group for group,names in GROUPS.items() for n in names.split()}
    result=[]
    for sample in audit['samples']:
        text=next(r for r in sample['spans'] if r['kind']=='v_gtext')
        start,end=text['start'],text['end']
        spans=[dict(r,**timeline.measure(r['start'],r['end'])) for r in rows
               if start<=r['start']<r['end']<=end]
        body=next(r for r in spans if r['kind']=='VDI_text')
        pending=None;damage=None;conversion=[]
        for tick,event in events:
            if not start<=tick<end or int(event[9],16)!=dp:continue
            name=selected['points'].get(int(event[4],16))
            if name=='convert_begin':
                require(pending is None,'Overlapping text input conversion');pending=tick
            elif name=='convert_end':
                require(pending is not None,'Unstarted text input conversion')
                conversion.append(dict(kind='text_input_conversion',start=pending,end=tick))
                pending=None
            elif name=='damage_begin':damage=tick
        require(pending is None and conversion and damage is not None,'Incomplete text stages')
        stages=conversion+[dict(kind='text_damage_preparation',start=damage,end=body['end'])]
        for s in stages:s.update(timeline.measure(s['start'],s['end']))
        functions=defaultdict(list)
        for r in spans:functions[r['kind']].append(r)
        result.append(dict(action=sample['action'],measured=timeline.measure(start,end),
            exclusive_cpu_ms=partition(spans+stages,timeline,start,end,kinds),
            routines={n:dict(calls=len(v),charged_cpu_ms=sum(r['charged_cpu_ms'] for r in v))
                      for n,v in functions.items()},stages=stages,spans=spans))
    return dict(samples=result,unfinished_calls=unfinished,
        scope='Exclusive Task CPU by innermost routine/source interval; native interrupts and other Tasks excluded. Source intervals follow emitted PCs, including their loop control.')
