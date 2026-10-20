"""Physical editor fixture using the checked, unchanged WB0 GEM provider."""
import json
import hashlib
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,read_build,verify_machine

FIELDS=dict(ready=8,work=166,document=178,caret=224,anchor=228,first=232,left=234,
            rows=236,columns=238,dirty=244,edits=856,paintTurns=860)
LAYOUT=[('BasicApp size',178),('BasicDocument size',46),('BasicEditor size',864)]+[
    ('Basic '+n,FIELDS[n]) for n in ('ready','work','document','caret','anchor','first','left','rows','columns','dirty','edits','paintTurns')]


def build_editor(out,provider):
    from build_c_program import build as application
    from build_bitmap_console import prepare
    from c_program import binding
    from make_data_disk import make
    from generate_memory import PROFILE
    from generate_mouse_acceleration import metadata
    out.mkdir(parents=True,exist_ok=True)
    app=application(out/'app',[ROOT/'examples/gem-basic'/n for n in ('main.c','basic.c','editor.c','document.c','files.c','file-ui.c')]+[ROOT/'c/calypsi/file-list.c'],
        probes=[(ROOT/'tests/programs/basic_editor_layout.c',LAYOUT)])
    maximum=application(out/'maximum',[ROOT/'tests/programs/basic_maximum.c']+[ROOT/'examples/gem-basic'/n for n in ('basic.c','editor.c','document.c','files.c','file-ui.c')]+[ROOT/'c/calypsi/file-list.c'])
    application(out/'counter',[ROOT/'examples/gem-counter'/n for n in ('main.c','counter.c')])
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'COUNTER.APP').write_bytes((out/'counter/program.app').read_bytes())
    (media/'BMAX.APP').write_bytes((out/'maximum/program.app').read_bytes())
    (media/'BASIC.APP').write_bytes((out/'app/program.app').read_bytes())
    make(out/'system.atr',media,binary_names={'BASIC.APP','BMAX.APP','COUNTER.APP'},filesystem='sdfs',sector_bytes=256,sectors=2880)
    foreign=json.loads(provider.read_text())
    for path,digest in foreign['provenance']['source_inputs'].items():
        require(sha256(ROOT/path)==digest,'Changed provider input: '+path)
    require('BasicEditorRun' not in foreign['symbols'],'Resident editor body')
    binding(foreign,out)
    (out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    launcher=prepare(ROOT/'tests/programs/basic_interaction.act',out,foreign,desktop=True,aes=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),launcher,out/'program',tasks=True,task_capacity=8,
        foreign_image=foreign,console_deferred=True,memory_profile=memory,system_mount='D1',
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2)],
        sdx=True,sdx_drive_a='RAM:',stack_checks=True)
    p['build']['desktop_mouse']=metadata(None)
    (p['output']/'build.json').write_text(json.dumps(p['build'],indent=2)+'\n')
    return p,app


def exercise(out):
    from os_boundary import emulator,run_to
    from test_mouse_observe import PIN,BRIDGE,ROM
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    from desktop_mouse import schedule
    from gem_render_oracle import Raster,font_bytes,DESKTOP_PALETTE,PENS
    from test_shell_core import KEYS
    from stack_budget import stack_usage
    p=read_build(out/'program');app=json.loads((out/'app/app.json').read_text())
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_BASICINTERACTION_'+name.upper()+'_' in d['name'])
    cursor=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    report=dict(status='running',slice='WB2',tier='development',qualification=False,cases=[],latencies=[],
        build=p['build'],application={k:app[k] for k in ('bytes','sha256','span','verified_banks')},
        reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'))
            report['machine']=verify_machine(b,ROM,PIN)
            number=lambda where,n=2:int.from_bytes(b.memdump(where,n),'little')
            def reach(condition):
                marker=p['labels']['native_nmi'];condition='(@xpc=$%x)&(%s)'%(marker,condition)
                b.bp_clear_all();b.bp_set(marker,condition=condition)
                b.bp_set(p['labels']['done'],condition='dw($a00)!=$ffff')
                run_to(b,marker,condition=condition,timeout=180,frame_limit=9000)
            def frames(n=1):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def move(x,y):
                current=[number(cursor(n)) for n in ('cursorX','cursorY')]
                x,y=schedule(b,p,current,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(cursor('cursorX'),x,cursor('cursorY'),y));frames(2)
            def edge(value):b._cmd_ok('MOUSE AT 2000 0 0 '+str(value));frames(5)
            def click(x,y):move(x,y);edge(1);edge(0)
            def key(name,ctrl=False,shift=False):
                if ctrl:b._cmd_ok('KEY CTRL down')
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                if ctrl:b._cmd_ok('KEY CTRL up')
                frames(3)
            from types import SimpleNamespace
            from desktop_menu_check import Menus
            def before(bridge):
                for round in range(3):
                    reach('(dw($%x)=1)&(dw($%x)=%d)'%(at('stage'),at('round'),round))
                    menus=Menus(SimpleNamespace(p=p,b=b,number=number,frames=frames,rendezvous=reach,
                        saved={'desktop_menu':{}}),click,move)
                    current=app if round<2 else json.loads((out/'maximum/app.json').read_text())
                    base=number(at('appBase'),4)+current['image']['symbols']['Basic']-(current['abi']['link_bank']<<16)
                    def settled():
                        reach('(dw($%x)=1)&(dw($%x)=0)&(dw($%x)>0)'%
                            (base+FIELDS['ready'],base+FIELDS['dirty'],base+FIELDS['paintTurns']))
                    def model(expected):
                        settled();d=base+FIELDS['document'];ptr=number(d,4);gap=number(d+12,4);end=number(d+16,4)
                        count=number(d+20,4);lines=number(d+44)
                        source=b.memdump(ptr,gap)+b.memdump(ptr+end,32768-end)
                        if source!=expected or count!=len(expected):
                            (out/'source-actual.bin').write_bytes(source);(out/'source-expected.bin').write_bytes(expected)
                            report['failure_model']=dict(bytes=count,expected=len(expected),caret=number(base+FIELDS['caret'],4),
                                anchor=number(base+FIELDS['anchor'],4),edits=number(base+FIELDS['edits'],4),
                                focus=menus.focus(),windows=menus.windows())
                            raise RuntimeError('Physical editor bytes differ; see source-actual.bin/source-expected.bin')
                        starts=[0]+[i+1 for i,c in enumerate(expected) if c==10]
                        offsets=b.memdump(number(d+8,4),(len(starts)+1)*4)
                        require(lines==len(starts) and offsets==b''.join(i.to_bytes(4,'little') for i in starts+[len(expected)]),
                                'Physical editor line offsets')
                    def picture(label,expected):
                        model(expected);move(630,230);frames(2)
                        x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
                        rows=number(base+FIELDS['rows']);columns=number(base+FIELDS['columns'])
                        first=number(base+FIELDS['first']);left=number(base+FIELDS['left'])
                        caret=number(base+FIELDS['caret'],4);anchor=number(base+FIELDS['anchor'],4)
                        starts=[0]+[i+1 for i,c in enumerate(expected) if c==10]
                        r=Raster(font_bytes(ROOT/'build/fastbasic-workbench/wb0/selected/src/vdi/font8x8.c'))
                        r.clip=(x,y,x+w-1,y+rows*8-1)
                        for row in range(rows):
                            line=first+row
                            text=expected.split(b'\n')[line] if line<len(starts) else b''
                            visible=text.expandtabs(8)[left:left+columns].ljust(columns)
                            r.apply(8,(x+4,y+row*8+6),visible)
                            if line>=len(starts):continue
                            lo,hi=sorted((anchor,caret));lineStart=starts[line]
                            lineEnd=starts[line+1] if line+1<len(starts) else len(expected)
                            if lo<hi and lo<lineEnd and hi>lineStart:
                                a=max(lo,lineStart);z=min(hi,lineEnd)
                                if z>lineStart and expected[z-1:z]==b'\n':z-=1
                                colA=len(expected[lineStart:a].expandtabs(8));colZ=len(expected[lineStart:z].expandtabs(8))+(hi>z)
                                l=x+4+max(0,colA-left)*8;rr=x+3+min(columns,colZ-left)*8
                                if l<=rr:r.fill=3;r.apply(11,(l,y+row*8+7,rr,y+row*8+7))
                            if line==expected[:caret].count(b'\n'):
                                col=len(expected[lineStart:caret].expandtabs(8))
                                if left<=col<left+columns:
                                    r.fill=1;r.apply(11,(x+4+(col-left)*8,y+row*8,x+4+(col-left)*8,y+row*8+7))
                        rgb=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
                        colors={hw:rgb[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                        wanted=b''.join(colors[r.pixels[j*640+i]] for j in range(y,y+rows*8) for i in range(x,x+w))
                        folder=out/label;folder.mkdir(exist_ok=True)
                        for attempt in range(100):
                            frame=b.rawscreen(str(folder/'scanout.bgra'));raw=(folder/'scanout.bgra').read_bytes()
                            region=b''.join(raw[j*frame.stride+64+x*4:j*frame.stride+64+(x+w)*4] for j in range(y,y+rows*8))
                            actual=b''.join(region[i:i+3] for i in range(0,len(region),4))
                            if actual==wanted:break
                            frames()
                        else:
                            (folder/'expected.bgr').write_bytes(wanted);(folder/'actual.bgr').write_bytes(actual)
                            mismatch=[i//3 for i in range(0,len(actual),3) if actual[i:i+3]!=wanted[i:i+3]]
                            (folder/'difference.json').write_text(json.dumps(dict(work=[x,y,w,h],rows=rows,columns=columns,
                                first=first,left=left,caret=caret,anchor=anchor,pixels=len(mismatch),
                                first_differences=[[x+i%w,y+i//w] for i in mismatch[:20]]),indent=2)+'\n')
                            b.screenshot(str(folder/'failure.png'));raise RuntimeError('Editor pixels differ: '+label)
                        report['cases'].append(dict(name=label,status='pass',sha256=hashlib.sha256(actual).hexdigest()))
                    def type_text(text):
                        for c in text:
                            name,shift=KEYS[c];key(name,shift=shift)
                    if round==0:
                        counter=json.loads((out/'counter/app.json').read_text())
                        cb=number(at('counterBase'),4)+counter['image']['symbols']['GEMCounter']-(counter['abi']['link_bank']<<16)
                        reach('dw($%x)=1'%(cb+12));frames(20)
                        menus.select('FastBasic');frames(20)
                    settled();menus.select('FastBasic');model(b'' if round<2 else (b'a'*255+b'\n')*127+b'a'*255);move(630,230)
                    if round==0:
                        type_text('hello\tworld\nsecond');picture('typed-tabs',b'hello\tworld\nsecond')
                        x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
                        move(x+4+8*8,y+3);edge(1);move(x+4+13*8,y+3);edge(0)
                        model(b'hello\tworld\nsecond')
                        require(sorted((number(base+FIELDS['caret'],4),number(base+FIELDS['anchor'],4)))==[6,11],
                                'Physical drag selection')
                        key('X');picture('selection-replaced',b'hello\tx\nsecond')
                        key('Z',ctrl=True);picture('undo-selection',b'hello\tworld\nsecond')
                        key('Y',ctrl=True);model(b'hello\tx\nsecond')
                        key('ESC',ctrl=True,shift=True);key('ASTERISK',ctrl=True)
                        key('EQUALS',ctrl=True);key('RETURN');frames(30)
                        picture('keyboard-menu-undo',b'hello\tworld\nsecond')
                        key('Y',ctrl=True)
                        saved=[number(base+FIELDS[n],4) for n in ('caret','anchor')]
                        peer=number(cb+14,4);menus.select('Counter');frames(30)
                        require(number(cb+14,4)>peer,'Covered editor stopped Counter')
                        menus.select('FastBasic');frames(30)
                        require([number(base+FIELDS[n],4) for n in ('caret','anchor')]==saved,'Focus changed selection')
                        picture('focus-cover-exposure',b'hello\tx\nsecond')
                        key('A',ctrl=True);type_text('1234567890'*8);picture('horizontal-pan',b'1234567890'*8)
                        require(number(base+FIELDS['left'])>0,'Caret did not pan horizontally')
                        # Resize through the physical size gadget to a non-cell height.
                        x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
                        move(x+w+8,y+h+5);edge(1);move(x+224,y+145);edge(0);frames(30)
                        picture('resized-partial-row',b'1234567890'*8)
                        x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
                        move(x+w+8,y+h+5);edge(1);move(x+40,y+40);edge(0);frames(30)
                        require(number(base+FIELDS['work']+4)>=288 and number(base+FIELDS['work']+6)>=128,'Editor minimum work area')
                        picture('minimum-size',b'1234567890'*8)
                    elif round==1:
                        start=b.eval_expr('@frame');type_text('again');picture('fresh-relaunch',b'again')
                        report['latencies'].append(dict(name='five-character edit to scanout',frames=b.eval_expr('@frame')-start))
                    else:
                        key('ASTERISK',ctrl=True)
                        report['maximum_navigation']=dict(caret=number(base+FIELDS['caret'],4),focus=menus.focus(),windows=menus.windows())
                        require(number(base+FIELDS['caret'],4)==1,'Physical cursor-right did not reach byte one')
                        peer=number(at('peerProgress'),4);start=b.eval_expr('@frame')
                        prior=number(base+FIELDS['edits'],4)
                        key('BACKSPACE');reach('dw($%x)>%d'%(base+FIELDS['edits'],prior))
                        picture('maximum-gap-delete',b'a'*254+b'\n'+(b'a'*255+b'\n')*126+b'a'*255)
                        elapsed=b.eval_expr('@frame')-start;progress=number(at('peerProgress'),4)-peer
                        require(elapsed<=120 and progress>0,'Maximum edit exceeded 120 PAL frames or starved peer')
                        report['latencies'].append(dict(name='32767-byte document, one-byte gap moved 32766 bytes, delete to scanout',
                            frames=elapsed,milliseconds=elapsed*20,budget_frames=120,peer_progress=progress))
                        key('X');picture('maximum-size-restored',b'x'+b'a'*254+b'\n'+(b'a'*255+b'\n')*126+b'a'*255)
                    x,y,w,h=[number(base+FIELDS['work']+i*2) for i in range(4)]
                    changed=number(base+FIELDS['document']+32,4)!=number(base+FIELDS['document']+36,4)
                    click(x,y-6)
                    if changed:
                        from generate_aes_server import expected_layout,layout
                        foreign=json.loads((out/'c-image.json').read_text());context=0
                        for slot in range(4):
                            candidate=number(foreign['symbols']['contexts']+4*slot,4)
                            if candidate and number(candidate+layout()['Request']['fields']['global']+4)==number(base):context=candidate
                        require(context,'No editor context for dirty decision')
                        where=context+dict(expected_layout())['C context form']
                        reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(10)
                        tree=number(number(where,4),4);button=tree+8*24
                        click(number(tree+16)+number(button+16)+number(button+20)//2,number(tree+18)+number(button+18)+8)
                    reach('dw($%x)=2'%at('stage'))
                    b.memload(at('gate'),(round+1).to_bytes(2,'little'))
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=240,frame_limit=12000)
            ownership(b,p,p['output'])
            report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                peer_progress=data(b,p['image'],'peerProgress',True),stack_usage=stack_usage(b,p['build']['memory']))
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--provider',type=Path,default=ROOT/'build/fastbasic-workbench/wb0/c-image.json')
    parser.add_argument('--from-build',action='store_true');parser.add_argument('--build-only',action='store_true')
    args=parser.parse_args()
    if not args.from_build:build_editor(args.output.resolve(),args.provider.resolve())
    if not args.build_only:exercise(args.output.resolve())
