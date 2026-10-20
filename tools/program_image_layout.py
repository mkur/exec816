"""Derive development observer offsets from the authoritative native Image type."""
import re
from native_program import ROOT,require


def layout(text=None):
    if text is None:text=(ROOT/'lib/dos/programimage.act').read_text()
    text=text.replace('\r\n','\n').replace('\r','\n')
    match=re.search(r'PUBLIC TYPE Image=\[\n(.*?)\n\]',text,re.S)
    require(match is not None,'Missing native Image type')
    constants={name:int(value) for name,value in re.findall(r'PUBLIC CONST (\w+)=(\d+)',text)}
    types={'LONGINT FUNC POINTER':(3,1),'PROC POINTER':(3,1),'BYTE POINTER':(3,1),
           'LONGCARD':(4,2),'ADDRESS':(3,1),'CARD':(2,2),'BYTE':(1,1)}
    cursor=0;alignment=1;fields={}
    for line in match[1].splitlines():
        line=line.strip()
        array=re.fullmatch(r'BYTE ARRAY (\w+)\((\w+)\)',line)
        if array:
            size=int(array[2]) if array[2].isdigit() else constants[array[2]]
            names=[array[1]];align=1
        else:
            kind=next((t for t in types if line.startswith(t+' ')),None)
            require(kind is not None,'Unsupported Image field: '+line)
            size,align=types[kind]
            names=re.sub(r'\(.*\)','',line[len(kind):]).strip().split(',')
        alignment=max(alignment,align)
        for name in names:
            require(re.fullmatch(r'\w+',name) is not None,'Unsupported Image declaration: '+line)
            cursor=(cursor+align-1)//align*align
            fields[name]=dict(offset=cursor,size=size);cursor+=size
    return dict(size=(cursor+alignment-1)//alignment*alignment,fields=fields)


LAYOUT=layout()
FIELDS={name:field['offset'] for name,field in LAYOUT['fields'].items()}
