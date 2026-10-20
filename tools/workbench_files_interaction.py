"""WB3: physical Open/Save/Save As and dirty decisions on a RAM volume."""
import argparse,json
from pathlib import Path
from native_program import ROOT,build,compiler,require,sha256,read_build,verify_machine
from workbench_interaction import FIELDS,LAYOUT


def prepare(out,provider):
    from build_c_program import build as application
    from build_bitmap_console import prepare as launcher
    from c_program import binding
    from make_data_disk import make
    from generate_memory import PROFILE
    from generate_mouse_acceleration import metadata
    out.mkdir(parents=True,exist_ok=True)
    sources=[ROOT/'examples/gem-basic'/n for n in ('main.c','basic.c','editor.c','document.c','files.c','file-ui.c','assist.c','assist-ui.c')]
    app=application(out/'app',sources+[ROOT/'c/calypsi/file-list.c'],probes=[(ROOT/'tests/programs/basic_editor_layout.c',LAYOUT)])
    media=out/'media';media.mkdir(exist_ok=True)
    (media/'BASIC.APP').write_bytes((out/'app/program.app').read_bytes())
    make(out/'system.atr',media,binary_names={'BASIC.APP'},filesystem='sdfs',sector_bytes=256,sectors=2880)
    foreign=json.loads(provider.read_text())
    for path,digest in foreign['provenance']['source_inputs'].items():require(sha256(ROOT/path)==digest,'Changed provider: '+path)
    binding(foreign,out);(out/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    source=launcher(ROOT/'tests/programs/basic_files_interaction.act',out,foreign,desktop=True,aes=True)
    profile=json.loads(PROFILE.read_text());profile['image_data_bytes']=8192
    memory=out/'fixture-memory.json';memory.write_text(json.dumps(profile,indent=2)+'\n')
    p=build(compiler(ROOT/'build/actionc',release=True),source,out/'program',tasks=True,task_capacity=8,
        foreign_image=foreign,console_deferred=True,memory_profile=memory,system_mount='D1',
        dos_mounts=[dict(alias='D1',unit=49,sectors=2880,sector_bytes=256,profile=4,format=2),dict(alias='RAM',format=3)],
        sdx=True,sdx_drive_a='RAM:',stack_checks=True)
    p['build']['desktop_mouse']=metadata(None);(p['output']/'build.json').write_text(json.dumps(p['build'],indent=2)+'\n')


def exercise(out,assistance=False):
    from os_boundary import emulator,run_to
    from test_mouse_observe import PIN,BRIDGE,ROM
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    from desktop_mouse import schedule
    from test_shell_core import KEYS
    KEYS["'"]=('7',True)
    from generate_aes_server import expected_layout,layout
    from file_selector_model import FIELDS as S,FORM_SELECTOR
    from desktop_menu_check import Menus
    from types import SimpleNamespace
    p=read_build(out/'program');app=json.loads((out/'app/app.json').read_text())
    foreign=json.loads((out/'c-image.json').read_text())
    at=lambda n:next(d['address'] for d in p['image']['data'] if '_BASICFILEINTERACTION_'+n.upper()+'_' in d['name'])
    cursor=lambda n:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+n.upper()+'_' in d['name'])
    report=dict(status='running',slice='WB4' if assistance else 'WB3',tier='development',qualification=False,cases=[],application=app['sha256'],
        runner_sha256=sha256(Path(__file__)),reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'))
            report['machine']=verify_machine(b,ROM,PIN)
            number=lambda a,n=2:int.from_bytes(b.memdump(a,n),'little')
            def reach(condition):
                marker=p['labels']['native_nmi'];condition='(@xpc=$%x)&(%s)'%(marker,condition)
                b.bp_clear_all();b.bp_set(marker,condition=condition);b.bp_set(p['labels']['done'],condition='dw($a00)!=$ffff')
                run_to(b,marker,condition=condition,timeout=180,frame_limit=9000)
            def frames(n=1):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def move(x,y):
                x,y=schedule(b,p,[number(cursor(n)) for n in ('cursorX','cursorY')],(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(cursor('cursorX'),x,cursor('cursorY'),y));frames(2)
            def edge(v):b._cmd_ok('MOUSE AT 2000 0 0 '+str(v));frames(8)
            def click(x,y):move(x,y);edge(1);edge(0);frames(12)
            def key(name,ctrl=False,shift=False):
                if ctrl:b._cmd_ok('KEY CTRL down')
                if shift:b._cmd_ok('KEY SHIFT down')
                b._cmd_ok('KEY '+name+' down');frames(4);b._cmd_ok('KEY '+name+' up')
                if shift:b._cmd_ok('KEY SHIFT up')
                if ctrl:b._cmd_ok('KEY CTRL up')
                frames(4)
            def text(value):
                for c in value:
                    n,s=KEYS[c];key(n,shift=s)
            def before(bridge):
                reach('dw($%x)=1'%at('stage'))
                base=number(at('appBase'),4)+app['image']['symbols']['Basic']-(app['abi']['link_bank']<<16)
                reach('dw($%x)=1'%(base+FIELDS['ready']));frames(30)
                menus=Menus(SimpleNamespace(p=p,b=b,number=number,frames=frames,rendezvous=reach,saved={'desktop_menu':{}}),click,move)
                menus.select('FastBasic');d=base+FIELDS['document']
                def typed_source(value):
                    for c in value:
                        edits=number(base+FIELDS['edits']);start=b.eval_expr('@frame')
                        n,s=KEYS[c];key(n,shift=s)
                        reach('dw($%x)!=%d'%(base+FIELDS['edits'],edits))
                        report.setdefault('typing_frames',[]).append(b.eval_expr('@frame')-start)
                def source(wanted,label):
                    reach('dw($%x)=0'%(base+FIELDS['dirty']))
                    ptr=number(d,4);gap=number(d+12,4);end=number(d+16,4);n=number(d+20,4)
                    actual=b.memdump(ptr,gap)+b.memdump(ptr+end,32768-end)
                    if actual!=wanted:
                        report['failure_source']=dict(label=label,actual=actual.decode('ascii','replace'),expected=wanted.decode('ascii','replace'),caret=number(base+FIELDS['caret'],4),status=b.memdump(base+FIELDS['edits']-81,81).split(b'\0')[0].decode('ascii','replace'))
                    require(actual==wanted and n==len(wanted),'Source differs: '+label)
                    b.screenshot(str(out/(label+'.png')));report['cases'].append(dict(name=label,bytes=n,status='pass'))
                def context():
                    for i in range(4):
                        c=number(foreign['symbols']['contexts']+4*i,4)
                        if c and number(c+layout()['Request']['fields']['global']+4)==number(base):return c
                    raise RuntimeError('No BASIC AES context')
                def form():return number(context()+dict(expected_layout())['C context form'],4)
                def dialog(choice):
                    where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
                    tree=number(form(),4);obj=tree+(choice+6)*24
                    click(number(tree+16)+number(obj+16)+number(obj+20)//2,number(tree+18)+number(obj+18)+8)
                def choose(name=None):
                    where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(30)
                    selector=number(form()+FORM_SELECTOR,4);require(selector,'Missing source selector')
                    if name is None:key('ESC');return
                    def field(index,offset,value):
                        obj=selector+index*24
                        click(number(selector+16)+number(obj+16)+12,number(selector+18)+number(obj+18)+8)
                        old=b.memdump(selector+offset,128 if index==3 else 13).split(b'\0')[0]
                        for _ in old:key('BACKSPACE')
                        text(value)
                    field(3,S['path'],'RAM:*.BAS');key('RETURN');frames(30)
                    field(5,S['file'],name);key('RETURN')
                def clean():reach('(dw($%x)=dw($%x))&(dw($%x)=0)'%(d+32,d+36,base+FIELDS['dirty']))
                typed_source('PRINT 7\n');key('S',ctrl=True);choose('EDITOR.BAS');clean();source(b'PRINT 7\n','save-new-atascii')
                typed_source('PRINT 8\n');key('N',ctrl=True);dialog(3);source(b'PRINT 7\nPRINT 8\n','new-cancel')
                key('N',ctrl=True);dialog(1);reach('dw($%x)=0'%(d+20));source(b'','new-after-save')
                key('O',ctrl=True);choose('EDITOR.BAS');reach('dw($%x)=16'%(d+20));source(b'PRINT 7\nPRINT 8\n','open-saved')
                key('A',ctrl=True);typed_source('PRINT 9\n');key('O',ctrl=True);dialog(2);choose();source(b'PRINT 9\n','discard-open-selector-cancel')
                key('W',ctrl=True);choose('SECOND.BAS');clean();source(b'PRINT 9\n','save-as')
                key('N',ctrl=True);reach('dw($%x)=0'%(d+20));key('O',ctrl=True);choose('SECOND.BAS')
                reach('dw($%x)=8'%(d+20));source(b'PRINT 9\n','open-save-as')
                if assistance:
                    from workbench_pixels import picture
                    def visual(wanted,label,lexical=(),visible=None):
                        source(wanted,label)
                        report['cases'].append(picture(out,b,number,frames,move,base,wanted,label,lexical,visible))
                    def search_field(index,value):
                        where=context()+dict(expected_layout())['C context form']
                        reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
                        tree=number(form(),4);obj=tree+index*24;ted=number(obj+12,4);data_pointer=number(ted,4)
                        old=b.memdump(data_pointer,81).split(b'\0')[0]
                        click(number(tree+16)+number(obj+16)+8,number(tree+18)+number(obj+18)+8)
                        for _ in old:key('BACKSPACE')
                        text(value)
                    def search_button(index):
                        tree=number(form(),4);obj=tree+index*24
                        click(number(tree+16)+number(obj+16)+number(obj+20)//2,number(tree+18)+number(obj+18)+8)
                    def navigate(down):
                        key('ESC',ctrl=True,shift=True);key('ASTERISK',ctrl=True);key('ASTERISK',ctrl=True)
                        for _ in range(down):key('EQUALS',ctrl=True)
                        key('RETURN');frames(25)
                    key('F',ctrl=True);search_field(2,'PRINT');search_button(5)
                    reach('(dw($%x)=5)&(dw($%x)=0)'%(base+FIELDS['caret'],base+FIELDS['anchor']))
                    visual(b'PRINT 9\n','find-selected',[(0,0,5,4)])
                    key('R',ctrl=True);search_field(4,'?');search_button(6)
                    reach('dw($%x)=4'%(d+20));visual(b'? 9\n','replace-all')
                    key('Z',ctrl=True);visual(b'PRINT 9\n','undo-replace',[(0,0,5,4)])
                    key('A',ctrl=True);typed_source('PRINT "IF REM" \' ENDPROC\n')
                    visual(b'PRINT "IF REM" \' ENDPROC\n','lexical-string-comment',[(0,0,5,4),(0,6,8,2),(0,15,9,3)])
                    key('A',ctrl=True);typed_source('PROC A\n  PRINT 1\nENDPROC\nPROC AB\n  PRINT 2\nENDPROC\n')
                    wanted=b'PROC A\n  PRINT 1\n  ENDPROC\n  PROC AB\n    PRINT 2\n    ENDPROC\n    '
                    colors=[(0,0,4,4),(1,2,5,4),(2,2,7,4),(3,2,4,4),(4,4,5,4),(5,4,7,4)]
                    visual(wanted,'automatic-indent',colors)
                    navigate(2);reach('dw($%x)=27'%(base+FIELDS['caret']))
                    generation=number(d+32,4);navigate(3)
                    require(number(d+32,4)==generation,'Folding changed source generation')
                    visual(wanted,'folded-procedure',colors,[0,1,2,3,6])
                    key('A',ctrl=True);visual(wanted,'folded-selection',colors,[0,1,2,3,6])
                    navigate(2);navigate(3);visual(wanted,'unfolded-procedure',colors)
                    key('Q',ctrl=True);dialog(2)
                else:key('Q',ctrl=True)
                b.bp_clear_all()
            runtime,_=execute(b,p,before_run=before,timeout=300,frame_limit=15000)
            ownership(b,p,p['output']);report.update(status='pass',runtime=runtime,checks=data(b,p['image'],'checks',True),
                peer_progress=data(b,p['image'],'peerProgress',True))
    except BaseException as error:report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--provider',type=Path,default=ROOT/'build/fastbasic-workbench/wb0/c-image.json')
    parser.add_argument('--from-build',action='store_true');parser.add_argument('--assistance',action='store_true');a=parser.parse_args()
    if not a.from_build:prepare(a.output.resolve(),a.provider.resolve())
    exercise(a.output.resolve(),a.assistance)
