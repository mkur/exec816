"""Independent cells, lexical pens, selection and caret for workbench snapshots."""
import hashlib
from native_program import ROOT,require
from gem_render_oracle import Raster,font_bytes,DESKTOP_PALETTE,PENS
from workbench_interaction import FIELDS


def picture(out,b,number,frames,move,base,source,label,lexical=(),visible=None):
    x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
    rows=number(base+FIELDS['rows']);columns=number(base+FIELDS['columns'])
    first=number(base+FIELDS['first']);left=number(base+FIELDS['left'])
    caret=number(base+FIELDS['caret'],4);anchor=number(base+FIELDS['anchor'],4)
    lines=source.split(b'\n');starts=[0]+[i+1 for i,c in enumerate(source) if c==10]
    r=Raster(font_bytes(ROOT/'build/fastbasic-workbench/wb0/selected/src/vdi/font8x8.c'))
    r.clip=(x,y,x+w-1,y+rows*8-1)
    for row in range(rows):
        logical=(visible[row] if row<len(visible) else len(lines)) if visible is not None else first+row
        text=lines[logical] if logical<len(lines) else b'';pens=[1]*len(text)
        for line,start,length,pen in lexical:
            if line==logical:pens[start:start+length]=[pen]*length
        cells=[]
        for c,pen in zip(text,pens):
            cells.extend([(32,pen)]*(8-len(cells)%8) if c==9 else [(c,pen)])
        cells=cells[left:left+columns];cells.extend([(32,1)]*(columns-len(cells)))
        for col,(c,pen) in enumerate(cells):
            r.text=pen;r.apply(8,(x+4+col*8,y+row*8+6),[c])
        if logical>=len(lines):continue
        lo,hi=sorted((anchor,caret));start=starts[logical];end=start+len(text)
        if lo<hi and lo<end+(logical+1<len(lines)) and hi>start:
            a=max(lo,start);z=min(hi,end)
            begin=len(source[start:a].expandtabs(8));finish=len(source[start:z].expandtabs(8))+(hi>end)
            l=x+4+max(0,begin-left)*8;right=x+3+min(columns,finish-left)*8
            if l<=right:r.fill=3;r.apply(11,(l,y+row*8+7,right,y+row*8+7))
        if logical==source[:caret].count(b'\n'):
            col=len(source[start:caret].expandtabs(8))
            if left<=col<left+columns:
                r.fill=1;r.apply(11,(x+4+(col-left)*8,y+row*8,x+4+(col-left)*8,y+row*8+7))
    rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
    colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
    wanted=b''.join(colors[r.pixels[j*640+i]] for j in range(y,y+rows*8) for i in range(x,x+w))
    folder=out/label;folder.mkdir(exist_ok=True);move(630,230);frames(3)
    for _ in range(120):
        frame=b.rawscreen(str(folder/'scanout.bgra'));raw=(folder/'scanout.bgra').read_bytes()
        region=b''.join(raw[j*frame.stride+64+x*4:j*frame.stride+64+(x+w)*4] for j in range(y,y+rows*8))
        actual=b''.join(region[i:i+3] for i in range(0,len(region),4))
        if actual==wanted:return dict(name=label,status='pass',sha256=hashlib.sha256(actual).hexdigest())
        frames()
    (folder/'expected.bgr').write_bytes(wanted);(folder/'actual.bgr').write_bytes(actual)
    b.screenshot(str(folder/'failure.png'));require(False,'Workbench lexical/fold pixels differ: '+label)
