"""Physical WB7 interaction. Only keys/mouse are submitted; state is observed."""
import hashlib,json,time
from types import SimpleNamespace
from native_program import ROOT,read_build,require,verify_machine


def exercise(out):
    from os_boundary import emulator,run_to
    from test_mouse_observe import PIN,BRIDGE,ROM
    from test_dos_stack import execute,ownership
    from test_cooperative import data
    from desktop_mouse import schedule
    from desktop_menu_check import Menus
    from generate_console import constants
    from console_model import read_cells
    from stack_budget import stack_usage
    from gem_render_oracle import Raster,font_bytes,DESKTOP_PALETTE,PENS
    p=read_build(out/'program');app=json.loads((out/'app/app.json').read_text())
    con=constants();storage=p['build']['memory']['console_storage']
    at=lambda module,name:next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
    report=dict(status='running',tier='development',qualification=False,slice='WB7',cases=[],
        build=p['build'],reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as b:
            b._cmd_ok('MOUSE ST');b.config('diskemu','generic56k');b.mount(0,str(out/'system.atr'))
            report['machine']=verify_machine(b,ROM,PIN)
            number=lambda address,n=2:int.from_bytes(b.memdump(address,n),'little')
            def reach(condition):
                point=p['labels']['native_nmi'];condition='(@xpc=$%x)&(%s)'%(point,condition)
                b.bp_clear_all();b.bp_set(point,condition=condition)
                b.bp_set(p['labels']['done'],condition='dw($a00)!=$ffff')
                deadline=time.monotonic()+90;first=b.eval_expr('@frame');b.resume()
                while time.monotonic()<deadline:
                    if b.eval_expr('dw($a00)')!=65535:
                        b.pause();raise RuntimeError('Fixture terminated while waiting for '+condition)
                    regs=b.regs()
                    if int(regs['PC'].lstrip('$'),16)==point and b.eval_expr(condition):
                        b.pause();return
                    if b.eval_expr('@frame')-first>9000:break
                    time.sleep(0.01)
                b.pause();raise RuntimeError('Physical rendezvous timed out: '+condition)
            def frames(n=1):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
            def move(x,y):
                current=[number(at('DESKINPUT',name)) for name in ('cursorX','cursorY')]
                x,y=schedule(b,p,current,(x,y))
                reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),x,at('DESKINPUT','cursorY'),y));frames(2)
            def edge(button):b._cmd_ok('MOUSE AT 2000 0 0 '+str(button));frames(4)
            def click(x,y):move(x,y);edge(1);edge(0)
            def key(name):
                require(b._cmd_ok('KEY '+name+' down')['raw_scan'],'Physical key input required')
                frames(4);b._cmd_ok('KEY '+name+' up');frames(4)
            def before(bridge):
                root=storage['INSTANCE']
                for cycle in range(2):
                    reach('(dw($%x)=1)&(dw($%x)=%d)'%(at('CONSOLEWINDOWTEST','stage'),at('CONSOLEWINDOWTEST','cycle'),cycle))
                    if cycle==0:
                        rootMode=number(root+con['INSTANCE_CAPS'],1);rootCells=read_cells(b.memdump,root)
                    base=number(at('CONSOLEWINDOWTEST','appBase'),4)
                    print('Console window cycle',cycle,'base',hex(base),flush=True)
                    sy={name:base+address-(app['abi']['link_bank']<<16) for name,address in app['image']['symbols'].items() if name.startswith('CW')}
                    menus=Menus(SimpleNamespace(p=p,b=b,number=number,frames=frames,rendezvous=reach,saved={'desktop_menu':{}}),click,move)
                    def stage(round):
                        reach('(dw($%x)=%d)&(dw($%x)=2)'%(sy['CWRound'],round,sy['CWStage']))
                        print('Console window round',round,flush=True)
                    def instance():
                        unit=number(sy['CWUnit'],4)
                        entry=storage['WINDOWS']+con['WINDOWS_ITEMS']+(unit&3)*con['WINDOW_SIZE']
                        require(number(entry+con['WINDOW_UNIT'],4)==unit,'Console incarnation changed')
                        return number(entry+con['WINDOW_INSTANCE'],3)
                    def cells():return read_cells(b.memdump,instance())
                    def contains(text):
                        for _ in range(400):
                            value=cells()
                            if text in value:return value
                            frames()
                        (out/'cells-failure.bin').write_bytes(value)
                        raise RuntimeError('Output did not contain '+repr(text))
                    def pending():reach('db($%x)=2'%(instance()+con['INSTANCE_READREADY']))
                    def action(row):
                        click(160,6);click(176,16+row*11)
                        print('Console menu action',row,flush=True)
                    def pixels(label,x,y):
                        print('Console snapshot',label,flush=True)
                        move(630,230);frames(5)
                        raster=Raster(font_bytes(out/'selected/src/vdi/font8x8.c'))
                        rom=ROM.read_bytes()
                        for row,text in enumerate((b'OWNED'.ljust(64),b'NUMBER'.ljust(64))):
                            for column,ch in enumerate(text):
                                for dy in range(8):
                                    bits=rom[8192+(ch-32)*8+dy]
                                    for dx in range(8):raster.pixel(x+column*8+dx,y+row*8+dy,1 if bits&(128>>dx) else 0)
                        palette=bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE)
                        colors={hw:palette[pen*3:pen*3+3][::-1] for pen,hw in enumerate(PENS)}
                        wanted=b''.join(colors[raster.pixels[j*640+i]] for j in range(y,y+16) for i in range(x,x+512))
                        folder=out/label;folder.mkdir(exist_ok=True)
                        for _ in range(120):
                            frame=b.rawscreen(str(folder/'scanout.bgra'));raw=(folder/'scanout.bgra').read_bytes()
                            actual=b''.join(raw[j*frame.stride+64+i*4:j*frame.stride+64+i*4+3] for j in range(y,y+16) for i in range(x,x+512))
                            if actual==wanted:break
                            frames()
                        else:
                            (folder/'actual.bgr').write_bytes(actual);(folder/'expected.bgr').write_bytes(wanted)
                            b.screenshot(str(folder/'failure.png'));raise RuntimeError('Owned-console pixels: '+label)
                        report['cases'].append(dict(name=label,status='pass',sha256=hashlib.sha256(actual).hexdigest()))
                    stage(0);contains(b'NUMBER');pending()
                    peer=number(at('CONSOLEWINDOWTEST','peerProgress'),4)
                    menus.select('Console control');action(0)
                    reach('dw($%x)=1'%sy['CWSaves']);pending()
                    require(number(at('CONSOLEWINDOWTEST','peerProgress'),4)>peer,'GUI stopped peer during INPUT')
                    menus.select('Owned output');pixels(f'cycle-{cycle}-initial',64,32)
                    key('4');key('2');key('RETURN');contains(b'GET');pending();key('K')
                    contains(b'KEY');frames(12);key('Q');value=contains(b'BUSY')
                    rows=[value[i:i+64].rstrip() for i in range(0,1280,64)]
                    wanted=[b'OWNED',b'NUMBER',b'? 42',b'42',b'GET',b'107',b'KEY',b'113',b'BUSY']+[b'']*11
                    require(rows==wanted,'INPUT/GET/KEY bytes or duplicated key: '+repr(rows))
                    report.setdefault('transcripts',[]).append([row.decode('ascii','replace') for row in rows])
                    # Cover and expose completed output, then move its fixed frame.
                    menus.select('Console control');menus.select('Owned output')
                    pixels(f'cycle-{cycle}-exposed',64,32)
                    move(200,26);edge(1);move(224,50);edge(0);frames(40)
                    pixels(f'cycle-{cycle}-moved',88,56)
                    child=number(sy['CWChild'],4);menus.select('Console control')
                    require(menus.focus()!=next(w['id'] for w in menus.windows() if w['title']=='Owned output'),'Stop retained output focus')
                    start=b.eval_expr('@frame');action(1)
                    reach('(dw($%x)=0)&(dw($%x)=3)'%(sy['CWRound'],sy['CWStage']))
                    report.setdefault('stop_frames',[]).append(b.eval_expr('@frame')-start)
                    require(number(sy['CWChild'],4)==0,'Busy child did not retire')
                    require(number(instance()+con['INSTANCE_CAPS'],1)&0xe0==0x40,'FastBasic did not restore the owned mode')
                    menus.select('Owned output');pixels(f'cycle-{cycle}-completed',88,56)
                    require([cells()[i:i+64].rstrip() for i in range(0,1280,64)]==wanted,'Completion changed retained glyphs')
                    menus.select('Console control');action(0)
                    stage(1)
                    contains(b'WAITING');pending();menus.select('Console control');action(0)
                    reach('dw($%x)=3'%sy['CWSaves']);pending()
                    report['root_mode_preserved']=number(root+con['INSTANCE_CAPS'],1)==rootMode
                    report['root_cells_preserved']=read_cells(b.memdump,root)==rootCells
                    require(report['root_mode_preserved'] and report['root_cells_preserved'],'Owned console changed Shell state')
                    menus.select('Owned output');click(62,26)
                b.bp_clear_all()
            try:report['runtime'],_=execute(b,p,before_run=before,timeout=120,frame_limit=6000)
            finally:
                for name in ('checks','stage','cycle','primary','secondary','observedChecks','observedStage','observedSaves','observedStopped'):
                    report[name]=data(b,p['image'],name,True)
                if 'runtime' not in report:
                    base=number(at('CONSOLEWINDOWTEST','appBase'),4)
                    report['application_snapshot']={n:number(base+v-(app['abi']['link_bank']<<16),4 if n in ('CWUnit','CWChild') else 2) for n,v in app['image']['symbols'].items() if n in ('CWStage','CWRound','CWChecks','CWSaves','CWStopped','CWChild','CWUnit','CWFirstFailure')}
                    b.screenshot(str(out/'failure.png'))
            f=json.loads((out/'c-image.json').read_text())
            if 'CWABIChecks' in f['symbols']:
                report['abi_checks']=number(f['symbols']['CWABIChecks'])
                require(report['abi_checks']==20,'Incomplete raw/optimized console ABI checks')
            ownership(b,p,p['output']);report['stack_usage']=stack_usage(b,p['build']['memory'])
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error));raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
