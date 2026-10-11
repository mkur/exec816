"""Physical caller-local file selector and its real bounded directory scans."""
from native_program import ROOT,require
from file_selector_model import FIELDS as F,FORM_SELECTOR

def media(out,bridge):
    from make_data_disk import make
    source=out/'media';(source/'DOCS').mkdir(parents=True,exist_ok=True);(source/'MANY').mkdir(exist_ok=True)
    for name,content in [('A.TXT',b'hello'),('B.BIN',b'bin'),('README',b'read'),('DOCS/NOTE.TXT',b'note')]:
        (source/name).write_bytes(content)
    for i in range(257):(source/'MANY'/f'A{i:03}.TXT').write_bytes(b'x')
    make(out/'selector.atr',source,filesystem='sdfs',sector_bytes=128,sectors=720)
    bridge.mount(0,str(out/'selector.atr'))

def physical(b,p,foreign,report):
    from os_boundary import run_to
    from desktop_mouse import schedule
    from generate_aes_server import expected_layout
    from test_shell_core import KEYS
    from gem_render_oracle import Raster,font_bytes,PENS,PALETTE
    from file_selector_oracle import paint
    import adapter_state as adapter
    sy=foreign['symbols'];position=[320,120];context_offset=dict(expected_layout())['C context form']
    def get(at,size=2):return int.from_bytes(b.memdump(at,size),'little')
    def reach(condition):
        b.bp_clear_all();b.bp_set(p['labels']['native_irq'],condition=condition)
        b.bp_set(p['labels']['done'],condition=adapter.STOPPED)
        try:run_to(b,p['labels']['native_irq'],condition=condition,timeout=120,frame_limit=6000)
        except Exception:
            from stack_budget import stack_usage
            report['failure_phase']=[get(sy['AESFilePhase']+i*2) for i in range(2)]
            report['failure_adapter']=b.memdump(adapter.STATE,64).hex()
            report['failure_stacks']=stack_usage(b,p['build']['memory'])
            c=get(sy['AESFileContext'],4);session=get(c+context_offset,4)
            report['failure_form']=b.memdump(session,319).hex() if session else None
            a=get(session+FORM_SELECTOR,4) if session else 0
            if a:
                report['failure_selector']={name:get(a+F[name]) for name in ('count','first','visible','selected','valid','loading','result')}
                report['failure_scan']=b.memdump(a+F['scan'],20).hex()
                report['failure_status']=b.memdump(a+F['status'],80).split(b'\0')[0].decode('ascii')
            raise
        require(get(sy['AESFailures'])==0,'Selector target assertion '+str(get(sy['AESFirstFailure'])))
    def frames(n=12):reach('@frame>=%d'%(b.eval_expr('@frame')+n))
    def context(who=0):return get(sy['AESFileContext']+who*4,4)
    def selector(who=0):
        c=context(who);session=get(c+context_offset,4)
        require(session!=0,'No active selector session')
        return get(session+FORM_SELECTOR,4)
    def phase(n,valid=True):
        print('Selector phase',n,flush=True)
        reach('(dw($%x)=%d)|(dw($%x)!=0)'%(sy['AESFilePhase'],n,sy['AESFailures']))
        frames(100)
        if valid:reach('dw($%x)=1'%(selector()+F['valid']))
        else:reach('(dw($%x)=0)&(db($%x)!=0)'%(selector()+F['loading'],selector()+F['status']))
        frames(30)
    def text(name,who=0):return b.memdump(selector(who)+F[name],128).split(b'\0')[0].decode('ascii')
    at=lambda name:next(d['address'] for d in p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    def move(x,y):
        nonlocal position
        position=schedule(b,p,position,(x,y));reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),position[0],at('cursorY'),position[1]))
    def edge(down):b._cmd_ok('MOUSE AT 2000 0 0 '+str(down));frames(20)
    def click(x,y):move(x,y);edge(1);edge(0)
    def key(name,shift=False):
        if shift:b._cmd_ok('KEY SHIFT down')
        b._cmd_ok('KEY '+name+' down');frames(3);b._cmd_ok('KEY '+name+' up')
        if shift:b._cmd_ok('KEY SHIFT up')
        frames(20)
    def xy(i,who=0):
        a=selector(who);o=a+i*24
        return get(a+16)+get(o+16)+get(o+20)//2,get(a+18)+get(o+18)+get(o+22)//2
    def fill(name,value):
        for _ in range(len(text(name))):key('BACKSPACE')
        for ch in value:key(*KEYS[ch])
        require(text(name)==value,'Selector edit '+name+': '+repr(text(name)))
    report['selector_pixels']=[]
    def pixels(name):
        move(628,232);frames(40)
        r=Raster(font_bytes(p['output'].parent/'selected/src/vdi/font8x8.c'))
        x,y,w,h=paint(b,context(),r)
        target=p['output'].parent/('selector-'+name+'.bgra');capture=b.rawscreen(str(target));actual=target.read_bytes()
        rgb=bytes((v&254)+(v>>7) for v in PALETTE)
        colors={hw:rgb[i*3:i*3+3][::-1] for i,hw in enumerate(PENS)}
        for yy in range(y,y+h):
            for xx in range(x,x+w):
                off=yy*capture.stride+(xx+16)*4
                require(actual[off:off+3]==colors[r.pixels[yy*640+xx]],f'Selector {name} pixel {xx},{yy}')
        report['selector_pixels'].append(dict(name=name,pixels=w*h))
    b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    phase(1);require(get(sy['AESFilePhase']+2)==1,'Independent selector peer missing')
    require(text('mask')=='*.TXT' and text('mask',1)=='*.BIN','Selectors share filter state')
    require(get(selector()+F['count'])==3,'Directories must survive filename filtering')
    pixels('initial')
    a=selector(1);click(get(a+16)+32,get(a+18)-8);frames(40);key('ESC')
    reach('dw($%x)=90'%(sy['AESFilePhase']+2));frames(60)
    pixels('exposed')
    move(*xy(14));edge(1);move(620,220);edge(0)
    require(get(sy['AESFilePhase'])==1,'Outside release accepted Cancel')
    move(*xy(14));edge(1);key('ESC');edge(0)
    require(get(sy['AESFilePhase'])==1,'Escape accepted an armed Cancel')
    endpoint=get(context()+dict(expected_layout())['Request size']+20,4)
    inbox=get(endpoint+36,3)
    move(*xy(14));edge(1);b.poke16(inbox+14,2);key('A');edge(0)
    require(get(sy['AESFilePhase'])==1,'Input loss accepted Cancel')
    click(*xy(5));fill('file','new.txt')
    a=selector();move(get(a+16)+330,get(a+18)+140);edge(1);key('RETURN')
    # The old host's held gesture excludes a new UPDATE until release. Release
    # after entry, before waiting for the new directory to finish painting.
    reach('dw($%x)=2'%sy['AESFilePhase']);edge(0)
    phase(2);a=selector();require(get(a+F['count'])==256 and get(a+F['visible'])==3,'Compact capacity/rows')
    require(get(sy['AESFilePhase'])==2,'Held-entry release activated a control')
    require(text('status')=='First 256 only','Missing truncation status')
    click(*xy(9));click(*xy(11));require(get(selector()+F['first'])==4,'Line/page scroll')
    click(*xy(16));require(text('file')=='A005.TXT','Scrolled row selected wrong name')
    pixels('scrolled');click(*xy(13))
    phase(3,False);require(text('status')=='Cannot open dir','Missing path error: '+text('status'))
    click(*xy(3));fill('path','D1:*.TXT');key('RETURN');frames(100)
    require(get(selector()+F['valid'])==1,'Corrected directory did not load')
    reads=get(sy['AESFileReads'],4)
    click(*xy(3));fill('path','D1:*.BIN');key('RETURN');frames(60)
    require(get(sy['AESFileReads'],4)==reads,'Changing the filter performed directory I/O')
    click(*xy(3));fill('path','D1:*.TXT');key('RETURN');frames(60)
    require(get(sy['AESFileReads'],4)==reads,'Restoring the filter performed directory I/O')
    click(*xy(16));frames(100);require(text('path')=='D1:DOCS/*.TXT','Directory navigation')
    click(*xy(6));frames(100);require(text('path')=='D1:*.TXT','Parent navigation')
    # Return in Path selects a row; restore the intended candidate for Cancel.
    click(*xy(5));fill('file','OLD.TXT');key('ESC')
    phase(4);a=selector();x,y=get(a+16),get(a+18)
    move(x+64,y-8);edge(1);move(x+80,y+4);edge(0);frames(60)
    pixels('moved');a=selector();click(get(a+16),get(a+18)-8)
    # Intercept Loading early, before waiting for a completed snapshot.
    reach('dw($%x)=5'%sy['AESFilePhase'])
    reach('dw($%x)!=0'%(context()+context_offset+2))
    session=get(context()+context_offset,4)
    reach('dw($%x)!=0'%(session+FORM_SELECTOR+2))
    a=selector();reach('(dw($%x)=1)&(dw($%x)=3)'%(a+F['loading'],inbox+12));key('ESC')
    phase(6);a=selector();x,y=get(a+16),get(a+18)
    move(x+48,y-8);edge(1);move(x+56,y);edge(0)
    phase(7);a=selector();click(get(a+16),get(a+18)-8)
    phase(8,False);frames(100)
    require(text('status')=='Read failed' and get(selector()+F['count'])==0 and not get(selector()+F['valid']),
        'Partial read failure retained an overwritten snapshot')
    if 'AESFileABI' in sy:
        require(text('title')=='012345678901234567890123456789','Custom title bound')
        key('ESC');phase(9)
        require(text('title')=='File selector' and text('path')=='SYS:*.*','Default path/caption')
        key('ESC');phase(10)
        require(len(text('path'))==127 and text('file')=='EIGHTCHR.TXT','Public buffer limits')
        pixels('boundary-path')
        key('ESC');phase(11,False)
        require(text('status')=='Invalid path','Unsupported GEMDOS syntax silently translated')
        report['standard_bindings']=dict(named=True,aespb=True,context_arrays=True,limits=True,canaries=True)
    # The last caller can finish and restore the OS before another native IRQ.
    # Let execute observe its completion breakpoint, not a later frame count.
    b._cmd_ok('KEY ESC down')
    report['physical_selector']=dict(two_callers=True,editing=True,save_candidate=True,
        compact=True,scrolling=True,truncation=True,path_correction=True,cancel=True,
        movement=True,temporary_close=True,cancel_loading=True,
        outside_release=True,input_loss=True,held_entry=True,borrowed_policy_order=True)
    b.bp_clear_all()
