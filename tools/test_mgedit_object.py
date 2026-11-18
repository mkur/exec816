#!/usr/bin/env python3
"""Exercise the loaded G_EDIT fixture on the pinned GEM provider."""
import argparse
import json
from pathlib import Path

import adapter_state as adapter
from build_c_program import build as application
from build_gem_desktop import build_desktop
from c_program import ABI
from desktop_mouse import coordinates
from gem_render_oracle import DESKTOP_PALETTE, PENS, Raster, font_bytes
from generate_aes_server import ABI as AES_ABI, expected_layout, layout
from generate_tasks import constants as task_constants
from make_data_disk import make
from measure_mgview import expected
from native_program import ROOT, read_build, require, sha256, verify_machine
from os_boundary import emulator, run_to
from test_dos_stack import execute, ownership
from test_mouse_observe import BRIDGE, PIN, ROM


def run(out, reuse=False, loss=False):
    if reuse:
        program = read_build(out/'program')
        app = json.loads((out/'app/app.json').read_text())
        peer = json.loads((out/'peer/app.json').read_text())
    else:
        app = application(out/'app',[ROOT/'tests/programs/mgedit_object.c'],minimum_stack=2560)
        peer = application(out/'peer',[ROOT/'tests/programs/mgedit_peer.c'],
            minimum_stack=ABI['stack_floor_bytes'])
        program = build_desktop(out,source=ROOT/'tests/programs/c_mgedit.act',
            build_applications=False,program_output=out/'program',release_compiler=True,
            system_mount='D1',task_capacity=12,dos_mounts=[dict(alias='D1',unit=49,sectors=2880,
                sector_bytes=256,profile=4,format=2)])
    media = out/'media'
    media.mkdir(exist_ok=True)
    for group,name,image in (('app','EDITOBJ.APP',app),('peer','PEER.APP',peer)):
        payload=out/group/'program.app'
        require(image['abi']==ABI and sha256(payload)==image['sha256'],f'Stale {name}')
        (media/name).write_bytes(payload.read_bytes())
    make(out/'system.atr',media,filesystem='sdfs',sector_bytes=256,sectors=2880,
         binary_names={'EDITOBJ.APP','PEER.APP'})

    font = font_bytes(out/'selected/src/vdi/font8x8.c')
    colours = [None]*16
    for pen,hardware in enumerate(PENS):
        colours[hardware] = bytes((b&254)+(b>>7) for b in DESKTOP_PALETTE[pen*3:pen*3+3])[::-1]
    white,black,fill = (colours[PENS[pen]] for pen in (0,1,2))
    cells = {name: next(d['address'] for d in program['image']['data']
                        if f'_CMGEDITTEST_{name.upper()}_' in d['name'])
             for name in ('round','base','checks','peerBase')}
    resident=json.loads((out/'c-image.json').read_text())['symbols']
    context_layout=dict(expected_layout())
    wire=layout()
    pointer=[next(d['address'] for d in program['image']['data']
                  if f'_DESKINPUT_CURSOR{axis}_' in d['name']) for axis in ('X','Y')]
    record = dict(tier='development',status='running',app_bytes=app['bytes'],
                  abi=ABI['version'],pictures=[],drags=[])
    try:
        with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
            for key,value in PIN['configuration'].items():
                bridge.config(key,str(value).lower() if isinstance(value,bool) else value)
            bridge.mount(0,str(out/'system.atr'))
            record['machine'] = verify_machine(bridge,ROM,PIN)

            def reach(condition, frame_limit=8000):
                marker = program['labels']['native_cop']
                condition = f'(@xpc=${marker:x})&({condition})'
                bridge.bp_clear_all()
                bridge.bp_set(marker,condition=condition)
                stops = {program['labels'][name]: name for name in
                         ('heap_fault','stack_overflow','arithmetic_fault','done')}
                for stop in stops:
                    bridge.bp_set(stop)
                original = bridge.regs

                def regs():
                    state = original()
                    pc = bridge.eval_expr('@xpc')
                    if pc in stops:
                        record['stop'] = dict(name=stops[pc],checks=number(cells['checks']),
                                              round=number(cells['round']),registers=state)
                        raise RuntimeError(f'Edit object fixture reached {stops[pc]} before {condition}')
                    return state

                bridge.regs = regs
                try:
                    run_to(bridge,marker,condition=condition,timeout=120,frame_limit=frame_limit)
                finally:
                    bridge.regs = original

            def number(address, size=2):
                return int.from_bytes(bridge.memdump(address,size),'little')

            def frames(count):
                reach(f'@frame>={bridge.eval_expr("@frame")+count}')

            def move(x,y,acceptable):
                off = {'build': {'desktop_mouse': {'profile': 'off'}}}
                for _ in range(24):
                    current=[number(a) for a in pointer]
                    if acceptable(*current): return
                    _,steps=coordinates(off,current,(x,y))
                    dx,dy=(max(-8,min(8,step))*16 for step in steps)
                    bridge._cmd_ok(f'MOUSE AT 2000 {dx} {dy} -1')
                    frames(10)
                current=[number(a) for a in pointer]
                require(acceptable(*current),
                        f'Mouse did not reach ({x},{y}) from {current}')

            def editor_context():
                contexts = bridge.memdump(resident['contexts'],AES_ABI['constants']['CONTEXTS']*4)
                for end in range(4,len(contexts)+1,4):
                    context=int.from_bytes(contexts[end-4:end],'little')
                    if context and number(context+context_layout['C context multiline'],4):
                        return context
                raise RuntimeError('Missing edit object application context')

            def editor_inbox(context):
                request=wire['Request']['fields']
                endpoint=wire['Endpoint']
                directory=number(context+request['directory'],3)
                identity=number(context+request['client'],4)
                end=directory+wire['Directory']['fields']['endpoints']
                for i in range(AES_ABI['constants']['CLIENTS']):
                    row=end+i*endpoint['size']
                    if number(row+endpoint['fields']['id'],4)==identity:
                        return number(row+endpoint['fields']['input'],3)
                raise RuntimeError('Missing edit input inbox')

            def manager_wait(addr):
                reach(f'dw(${addr("phase"):x})=13')
                context=editor_context()
                directory=number(context+wire['Request']['fields']['directory'],3)
                manager=number(directory+wire['Directory']['fields']['owner'],3)
                tc=task_constants()
                control=number(manager+tc['TASK_TC_EXECPRIVATE'],3)
                reason=control+tc['TCB_WAITREASON']
                # After release, uncaptured motion queues manager work as it
                # normally would. Keep this one UPDATE level until observed.
                bridge._cmd_ok('MOUSE AT 2000 32 0 -1')
                reach(f'db(${reason:x})={tc["WAIT_SEMAPHORE"]}')
                tail=editor_inbox(context)+wire['InputInbox']['fields']['keyTail']
                previous=number(tail,1)
                bridge._cmd_ok('KEY A down')
                reach(f'db(${tail:x})!={previous}')
                bridge._cmd_ok('KEY A up')
                require(number(reason,1)==tc['WAIT_SEMAPHORE'],
                        'Manager left native UPDATE wait before editor released it')
                record['manager_wait']='physical key published during native UPDATE wait'
                bridge.poke16(addr('proceed'),13)

            def drag(addr, peer_progress, stage, loss):
                reach(f'dw(${addr("phase"):x})={stage}')
                x,y,width,height=(number(addr('work')+2*i) for i in range(4))
                move(x+24,y+height-12,lambda px,py:x+2<=px<x+width-2 and y+2<=py<y+height-8)
                # Settle uncaptured positioning before pressing. Retrying with
                # another edge would also release a press still in flight.
                frames(24)
                bridge._cmd_ok('MOUSE AT 2000 0 0 1')
                reach(f'dw(${addr("dragActive"):x})={stage}',frame_limit=180)
                context=editor_context()
                update=context+context_layout['C context updateDepth']
                progress=number(peer_progress)
                move(number(pointer[0]),y+height+24,
                     lambda px,py:x+2<=px<x+width-2 and py>=y+height+8)
                frames(16)
                require(number(update)==1,'Drag lost its UPDATE owner before release')
                advanced=(number(peer_progress)-progress)&65535
                require(advanced>0,'Peer stalled during drag UPDATE')
                if loss:
                    flag=editor_inbox(context)+wire['InputInbox']['fields']['loss']
                    bridge.poke16(flag,number(flag)|AES_ABI['constants']['MU_BUTTON'])
                    bridge._cmd_ok('MOUSE AT 2000 32 0 -1')
                    reach(f'dw(${addr("dragDone"):x})={stage}')
                    bridge._cmd_ok('MOUSE AT 2000 0 0 0')
                    frames(4)
                else:
                    bridge._cmd_ok('MOUSE AT 2000 0 0 0')
                    reach(f'dw(${addr("dragDone"):x})={stage}')
                require(number(addr('dragStatus'))==(AES_ABI['constants']['INPUT_LOST'] if loss else 0),
                        'Unexpected drag completion')
                record['drags'].append(dict(peer_ticks=advanced,update_held=True,loss=loss))

            def picture(addr, label, phase):
                def rect(name):
                    return [number(addr(name)+i*2) for i in range(4)]

                work = rect('work')
                x,y,width,height = work
                content = (b'Ax\n\tB\nSecond\nThird\nFourth\n' if phase==2
                           else b'A\tB\nSecond\nThird\nFourth\n')
                if phase<6:
                    expected_pixels = expected(font,work,content,0)
                else:
                    lines = [f'{i:02d} abcdefghijklmnopqrstuvwxyz-0123456789'.encode()
                             for i in range(16)]
                    top = number(addr('scrollTop'),4)
                    left = number(addr('scrollLeft'))
                    model = Raster(font)
                    model.clip=(x,y,x+width-1,y+height-1)
                    for row,line in enumerate(lines[top:top+height//8]):
                        model.apply(8,[x-left,y+row*8+6],list(line))
                    expected_pixels = b''.join(colours[model.pixels[row*640+col]]
                        for row in range(y,y+height) for col in range(x,x+width))
                covered = phase==3
                if covered:
                    ox,oy,ow,oh = rect('coverBounds')
                    cx,cy,cw,ch = rect('coverWork')
                    # The frame projects a two-pixel physical shadow.
                    ow += 2
                    oh += 2
                path = out/(label+'.bgra')
                frame = bridge.rawscreen(str(path))
                pixels = path.read_bytes()
                checked = 0
                for row in range(height):
                    for column in range(width):
                        px,py = x+column,y+row
                        dest = (px+16)*4+py*frame.stride
                        source = (column+row*width)*3
                        wanted = expected_pixels[source:source+3]
                        if phase in (3,4):
                            inverted = row<32
                        elif phase<6:
                            top = 8 if phase==2 else 0
                            inverted = column==0 and top<=row<top+8
                        else:
                            inverted = False
                        if inverted:
                            wanted = black if wanted==white else white
                        if covered and ox<=px<ox+ow and oy<=py<oy+oh:
                            if not (cx<=px<cx+cw and cy<=py<cy+ch):
                                continue
                            wanted = fill
                        require(pixels[dest:dest+3]==wanted,
                                f'{label} pixel {px},{py} {pixels[dest:dest+3].hex()} != {wanted.hex()}')
                        checked += 1
                record['pictures'].append(dict(name=label,checked=checked))

            def before(_):
                bridge._cmd_ok('MOUSE ST')
                for cycle in (1,2):
                    reach(f'(dw(${cells["round"]:x})={cycle})&(dw(${cells["checks"]:x})>={5+4*(cycle-1)})')
                    base = number(cells['base'],4)-(ABI['link_bank'] << 16)
                    pulse = number(cells['peerBase'],4)-(ABI['link_bank'] << 16)
                    peer_progress=pulse+peer['image']['symbols']['peerProgress']

                    def addr(name):
                        return base+app['image']['symbols'][name]

                    for phase in range(1,11):
                        reach(f'(dw(${cells["round"]:x})={cycle})&(dw(${addr("phase"):x})={phase})')
                        frames(2)
                        picture(addr,f'{cycle}-{phase}',phase)
                        if phase==10:
                            bridge.poke16(addr('dragMode'),(2 if loss else 1) if cycle==1 else 0)
                        bridge.poke16(addr('proceed'),phase)
                    if cycle==1:
                        try:
                            drag(addr,peer_progress,11,loss)
                            if not loss:
                                manager_wait(addr)
                                drag(addr,peer_progress,14,False)
                        except Exception:
                            record['drag_failure']={name:number(addr(name)) for name in
                                                     ('phase','dragStatus','dragActive','dragDone')}
                            record['pointer']=[number(a) for a in pointer]
                            record['native_status']=number(adapter.STATE)
                            raise
                    reach(f'dw(${addr("phase"):x})=12')
                    bridge.poke16(addr('proceed'),12)
                reach(f'dw(${cells["checks"]:x})>=12')
                bridge.poke16(pulse+peer['image']['symbols']['peerStop'],1)
                bridge.bp_clear_all()

            record['runtime'],_ = execute(bridge,program,before_run=before,timeout=180,frame_limit=16000)
            ownership(bridge,program,program['output'])
            record['checks'] = number(cells['checks'])
            require(record['checks']==16,'Incomplete edit object lifecycle')
        record['status']='pass'
    except Exception as error:
        record.update(status='fail',error=str(error))
        raise
    finally:
        name='loss' if loss else 'release'
        (out/f'results-{name}.json').write_text(json.dumps(record,indent=2)+'\n')
    return record


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--loss',action='store_true',help='Inject loss into the physical drag')
    args = parser.parse_args()
    run(args.output.resolve(),args.reuse,args.loss)
