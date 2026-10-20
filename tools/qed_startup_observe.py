"""Read-only QED startup observations and physical Close/Quit stimuli."""
import hashlib,json,struct
import adapter_state as adapter
from generate_aes_server import ABI,layout,expected_layout
from native_program import ROOT,require
from os_boundary import run_to
from desktop_mouse import schedule


def interact(bridge,program,app,record,owner):
    def address(name):
        return next(d['address'] for d in program['image']['data']
                    if d['name'].startswith('M_CPROCESSTEST_'+name.upper()+'_'))
    def get(at,size=2):return int.from_bytes(bridge.memdump(at,size),'little')
    def reach(condition):
        bridge.bp_clear_all();bridge.bp_set(program['labels']['native_irq'],condition=condition)
        bridge.bp_set(program['labels']['done'],condition=adapter.STOPPED)
        original=bridge.regs
        def regs():
            value=original()
            if int(value['PC'].lstrip('$'),16)==program['labels']['done']:
                require(not bridge.eval_expr(adapter.STOPPED),
                    'QED stopped before interaction: status='+hex(bridge.peek16(adapter.STATE))+
                    ', checks='+str(get(address('checks')))+', primary='+str(get(address('lastPrimary'),4)))
            return value
        bridge.regs=regs
        try:run_to(bridge,program['labels']['native_irq'],condition=condition,timeout=180,frame_limit=12000)
        finally:bridge.regs=original
    def frames(count):reach('@frame>='+str(bridge.eval_expr('@frame')+count))
    if not record.get('qed_startup'):
        bridge._cmd_ok('MOUSE ST');bridge._cmd_ok('KEY ALL up')
    if get(address('cycle'))==3:
        record.setdefault('qed_startup',[]).append(dict(cycle=3,action='supervisor RequestStop',process=owner['identity']))
        return
    reach('dw($%x)=dw($%x)+1'%(address('phase'),address('cycle')))
    cycle=get(address('cycle'));frames(80)
    print('QED window ready, cycle',cycle,flush=True)
    delta=owner['image_base']-(app['abi']['link_bank']<<16)
    symbols={name:at+delta for name,at in app['image']['symbols'].items()}
    require(get(symbols['menu'],4)!=0 and get(symbols['strings'],4)!=0,'QED did not retain its actual resource')
    require(get(symbols['font_wcell'])==8 and get(symbols['font_hcell'])==8,'QED did not select the fixed font')
    outer=[int.from_bytes(bridge.memdump(address(name),2),'little',signed=True)
           for name in ('windowX','windowY','windowW','windowH')]
    snapshot=dict(cycle=cycle,process=owner['identity'],outer=outer,menu_objects=get(address('menuObjects')),
        resource_pointer=get(symbols['menu'],4),fixed_font=[8,8])
    resident=json.loads((program['output'].parent/'c-image.json').read_text())['symbols']
    process_layout=json.loads((ROOT/'abi/process.json').read_text())
    task=owner['record']+next(f[2] for f in process_layout['record'] if f[0]=='task')
    request=layout()['Request']['fields'];view=layout()['WindowView']['fields']
    contexts=[]
    for i in range(ABI['constants']['CONTEXTS']):
        context=get(resident['contexts']+i*4,4)
        if context and get(context+request['owner'],3)==task:contexts.append(context)
    require(len(contexts)==1,'QED has no unique native context')
    views=contexts[0]+dict(expected_layout())['C context views']
    shown=[get(views+i*4,4) for i in range(ABI['constants']['WINDOWS'])
           if get(views+i*4,4) and get(get(views+i*4,4)+view['shown'])]
    require(len(shown)==1,'QED did not open exactly one native window')
    snapshot['work']=list(struct.unpack('<4h',bridge.memdump(shown[0]+view['work'],8)))
    snapshot['native_view']=shown[0]
    snapshot['heap']=list(struct.unpack('<4I',bridge.memdump(symbols['totals'],16)))
    require(get(symbols['vdi_handle'])==get(symbols['cf_vdi_handle'])==2,'QED did not borrow CFLIB workstation')
    from gem_render_oracle import DESKTOP_PALETTE
    screen_path=program['output'].parent/('qed-'+str(cycle)+'.bgra')
    screen=bridge.rawscreen(str(screen_path));pixels=screen_path.read_bytes()
    background=bytes((n&254)+(n>>7) for n in DESKTOP_PALETTE[:3])[::-1]
    input_at=lambda name:next(d['address'] for d in program['image']['data']
                             if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    pointer=[get(input_at('cursorX')),get(input_at('cursorY'))]
    left,top,right,bottom=snapshot['work'];checked=0
    for y in range(top,bottom):
        for x in range(left,right):
            # The blinking insertion caret and presenter-owned pointer are dynamic.
            if x<left+4 and y<top+8:continue
            if pointer[0]<=x<pointer[0]+16 and pointer[1]<=y<pointer[1]+16:continue
            at=y*screen.stride+64+x*4
            require(pixels[at:at+3]==background,'QED empty-document pixel '+str((x,y)))
            checked+=1
    snapshot['pixels']=dict(checked=checked,sha256=hashlib.sha256(pixels).hexdigest(),
        assertion='Native empty work area uses background pen zero; dynamic caret/pointer excluded')
    bridge.screenshot(str(program['output'].parent/('qed-'+str(cycle)+'.png')))
    record.setdefault('qed_startup',[]).append(snapshot)
    if cycle==1:
        bridge._cmd_ok('KEY CTRL down');bridge._cmd_ok('KEY Q down');frames(3)
        bridge._cmd_ok('KEY Q up');bridge._cmd_ok('KEY CTRL up')
        snapshot['action']='physical Ctrl+Q'
    else:
        # Observe the active cursor; positioning sends ordinary physical phases.
        at=lambda name:next(d['address'] for d in program['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        position=[get(at('cursorX')),get(at('cursorY'))]
        position=schedule(bridge,program,position,(outer[0]+6,outer[1]+5))
        reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),position[0],at('cursorY'),position[1]))
        print('QED physical closer position',position,flush=True)
        bridge._cmd_ok('MOUSE AT 2000 0 0 1');frames(15)
        bridge._cmd_ok('MOUSE AT 2000 0 0 0')
        snapshot['action']='physical window Close'
    print('QED action delivered:',snapshot['action'],flush=True)
