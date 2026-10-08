"""Match passive presenter call/store markers against linked emitted bytes."""
import re
from native_program import require

def csites(p,foreign):
    targets=set('GemDrawingWidgetBatch GemWidgetText GemWidgetFill GemWidgetStipple WidgetDrawObject just_draw GemDrawingText GemDrawingTextClip GemBitmapTextClip GemBitmapText GemDrawingFill dev_glyph dev_fill_rect blit_mask blit_glyph blit_glyph_run glyph_record vbxe_widget_text_run _Mul16 _Mul32 _UDivMod16 _UDivMod32 _SDivMod16 _SDivMod32 VbxeOwnerSubmit VbxeOwnerRead VbxeOwnerWrite VbxeOwnerFence VbxeOwnerText VbxeOwnerTextFill VbxeBlitExtent DisplayCheck vram_win'.split())
    symbols=foreign['symbols'];sites={}
    for path in (p['output'].parent/'drawing').glob('*.lst'):
        if path.name=='link.lst':continue
        for section in path.read_text().split('.section ')[1:]:
            if not section.startswith('farcode,text'):continue
            calls=[(int(m[1],16),m[2]) for m in re.finditer(r'\\ ([0-9a-f]{6}) 22[.]{6}\s+jsl\s+long:(\w+)\s*$',section,re.M) if m[2] in targets and m[2] in symbols]
            if not calls:continue
            code={}
            for m in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',section):
                offset=int(m[1],16)
                for i in range(0,len(m[2]),2):code[offset+i//2]=m[2][i:i+2]
            require(set(code)==set(range(max(code)+1)),'Incomplete section '+str(path))
            for offset,name in calls:
                for i,value in enumerate(symbols[name].to_bytes(3,'little')):code[offset+1+i]=f'{value:02x}'
            pattern=b''.join(b'.' if code[i]=='..' else re.escape(bytes.fromhex(code[i])) for i in range(len(code)))
            locations=[s['address']+m.start() for s in foreign['segments'] if s['executable'] for m in re.finditer(pattern,bytes(s['bytes']),re.S)]
            public=re.search(r'\.public (\w+)',section)
            require(locations or public is None or public[1] not in symbols,'Missing linked section '+str(public))
            for base in locations:
                for offset,name in calls:
                    pc=base+offset
                    caller=re.search(r'\\ 000000\s+(\w+):',section)
                    sites['c_'+name+'_'+hex(pc)]=dict(entry=pc,returns=[pc+4],callee=name,caller=caller[1] if caller else 'outlined',listing=path.name)
    require(sites,'No C sites')
    return sites


def workpoints(p,foreign):
    """A16 immediately after a linked store publishes queued work."""
    result={};symbols=foreign['symbols']
    for path in (p['output'].parent/'drawing').glob('*gem-vbxe.lst'):
        for section in path.read_text().split('.section ')[1:]:
            if not section.startswith('farcode,text'):continue
            stores=[int(m[1],16) for m in re.finditer(r'\\ ([0-9a-f]{6}) 8f[.]{6}\s+sta\s+long:commandWork\s*$',section,re.M)]
            if not stores:continue
            code={}
            for m in re.finditer(r'\\ ([0-9a-f]{6}) ([0-9a-f.]+)\s+',section):
                offset=int(m[1],16)
                for i in range(0,len(m[2]),2):code[offset+i//2]=m[2][i:i+2]
            require(set(code)==set(range(max(code)+1)),'Incomplete work-store section')
            for offset in stores:
                for i,value in enumerate(symbols['commandWork'].to_bytes(3,'little')):
                    code[offset+1+i]=f'{value:02x}'
            pattern=b''.join(b'.' if code[i]=='..' else re.escape(bytes.fromhex(code[i])) for i in range(len(code)))
            locations=[s['address']+m.start() for s in foreign['segments'] if s['executable'] for m in re.finditer(pattern,bytes(s['bytes']),re.S)]
            require(len(locations)==1,'Ambiguous work-store marker')
            for offset in stores:result['list_work_'+hex(locations[0]+offset+4)]=locations[0]+offset+4
    require(result,'Missing list-work markers')
    return result
