#!/usr/bin/env python3
"""Production GEM terminal, matched Counter/disk load and physical input walk."""
import argparse
import hashlib
import json
import shutil
import struct
import zipfile
from pathlib import Path

import adapter_state as adapter
from console_model import read_cells
from desktop_menu_check import Menus
from desktop_mouse import schedule
from filesystem_audit import Audit
from gem_applications import MODELS,instances
from gem_first_observe import digit_pixels,progress
from gem_render_oracle import DESKTOP_PALETTE,font_bytes
from generate_console import constants
from native_program import ROOT,read_build,require,sha256,verify_machine
from os_boundary import emulator,run_to
from program_image_layout import FIELDS as IMAGE
from shell_inspect import address
from test_dos_stack import execute,ownership
from test_mouse_observe import BRIDGE,ROM,PIN
from test_shell_core import KEYS


class Session:
    def __init__(self,b,p,directory,out,report):
        self.b,self.p,self.directory,self.out,self.report=b,p,directory,out,report
        self.saved={'pointer':(320,120),'desktop_menu':{}}
        self.c=constants();self.far=b.memdump
        self.windows=p['build']['memory']['console_storage']['WINDOWS']
        self.provider=json.loads((directory/'c-image.json').read_text())['symbols']
        self.menus=Menus(self,self.click,self.move)

    def number(self,at,size=4):return int.from_bytes(self.far(at,size),'little')
    def at(self,name,index=0):return address(self.p['image'],name,session=index)
    def native(self,module,name):return address(self.p['image'],name,module)
    def index(self):return self.number(self.at('selectedSession'))-1
    def source(self,index):
        return self.number(self.windows+self.c['WINDOWS_ITEMS']+
            index*self.c['WINDOW_SIZE']+self.c['WINDOW_INSTANCE'],3)
    def route(self,index):
        return self.number(self.windows+self.c['WINDOWS_ITEMS']+
            index*self.c['WINDOW_SIZE']+self.c['WINDOW_ROUTE'])
    def rendezvous(self,condition,marker='native_nmi',timeout=240):
        b=self.b;pc=self.p['labels'][marker]
        condition=f'(@xpc=${pc:x})&({condition})'
        b.bp_clear_all();b.bp_set(pc,condition=condition)
        b.bp_set(self.p['labels']['done'],condition=adapter.STOPPED)
        original=b.regs
        def regs():
            result=original()
            require(not b.eval_expr(adapter.STOPPED),'Production guest stopped: '+hex(self.number(adapter.STATE,2)))
            return result
        b.regs=regs
        try:run_to(b,pc,30000,timeout,condition)
        finally:b.regs=original
    def frames(self,count=5):self.rendezvous('@frame>='+str(self.b.eval_expr('@frame')+count))
    def press(self,char):
        source=self.source(self.index())
        generation=source+self.c['INSTANCE_GENERATION']
        previous=self.number(generation)
        capture=self.p['build']['memory']['console_storage']['CAPTURE']+10
        captured=self.number(capture,2)
        name,shift=KEYS[char]
        if shift:self.b._cmd_ok('KEY SHIFT down')
        self.b._cmd_ok('KEY '+name+' down')
        self.rendezvous(f'dw(${capture:x})!={captured}',timeout=30)
        self.b._cmd_ok('KEY '+name+' up')
        if shift:self.b._cmd_ok('KEY SHIFT up')
        self.frames(3)
        if char!='\n':
            try:self.rendezvous(f'(dw(${generation:x})!={previous&65535})|'
                f'(dw(${generation+2:x})!={previous>>16})',timeout=30)
            except Exception:
                self.report['key_diagnostic']=dict(char=char,generation=previous,
                    captured_before=captured,captured_after=self.number(capture,2),
                    cells=read_cells(self.far,source).decode('latin1'))
                self.report['key_diagnostic']['ingress']={name:self.far(self.native('CONSOLEINGRESS',name),
                    672 if name=='packets' else 1).hex() for name in ('packets','count','head','tail')}
                self.report['key_diagnostic']['instance']=self.far(source,self.c['INSTANCE_SIZE']).hex()
                self.report['key_diagnostic']['capture']=self.far(capture-10,560).hex()
                self.report['key_diagnostic']['deferred']={name:self.far(self.native('DESKINPUT',name),
                    128 if name=='deferredKeys' else 1).hex() for name in ('deferredKeys','keyHead','keyCount','keyLost')}
                from generate_desktop import layout
                types=layout();service=self.number(self.native('DESKSTATE','service'),3)
                self.report['key_diagnostic']['windows']=[dict(id=self.number(service+types['Service']['fields']['windows']+n*types['Window']['size']),
                    keyRoute=self.number(service+types['Service']['fields']['windows']+n*types['Window']['size']+8)) for n in range(6)]
                print(self.report['key_diagnostic'],flush=True)
                raise
    def move(self,x,y):
        ax=self.native('DESKINPUT','cursorX');ay=self.native('DESKINPUT','cursorY')
        x,y=schedule(self.b,self.p,[self.number(ax,2),self.number(ay,2)],(x,y),settle_frames=25)
        self.rendezvous(f'(dw(${ax:x})={x})&(dw(${ay:x})={y})')
        self.saved['pointer']=(x,y)
    def click(self,x,y):
        self.move(x,y);self.b._cmd_ok('MOUSE AT 2000 0 0 1');self.frames(20)
        self.b._cmd_ok('MOUSE AT 2000 0 0 0');self.frames(50)
    def begin(self,text):
        index=self.index();before=(index,self.route(index))
        for char in text+'\n':self.press(char)
        return before
    def ready(self,before=None):
        index,route=before if before is not None else (self.index(),None)
        source=self.source(index)
        condition=f'(db(${source+self.c["INSTANCE_READREADY"]:x})=2)'
        if route is not None:
            at=self.windows+self.c['WINDOWS_ITEMS']+index*self.c['WINDOW_SIZE']+self.c['WINDOW_ROUTE']
            condition+=f'&(dw(${at:x})!={route&65535})'
        try:self.rendezvous(condition,timeout=240)
        except Exception:
            self.report['ready_diagnostic']=dict(index=index,route=self.route(index),previous=route,
                source=source,read_ready=self.number(source+self.c['INSTANCE_READREADY'],1),
                cells=read_cells(self.far,source).decode('latin1'),result=self.result(index))
            print(self.report['ready_diagnostic'],flush=True)
            raise
    def result(self,index=None):
        shell=self.number(self.at('shell',self.index() if index is None else index),3)
        return struct.unpack('<ii',self.far(shell+32,8))
    def command(self,text,expected=None,status=0):
        print('GEM production command:',text,flush=True)
        self.menus.select('Terminal')
        before=self.begin(text)
        if text=='NEWSHELL' or text.startswith('SESSION '):
            selected=self.at('selectedSession')
            target=before[0]+2 if text=='NEWSHELL' else int(text.split()[1])
            self.rendezvous(f'dw(${selected:x})={target}')
            self.ready()
            self.terminal_ready()
        else:self.ready(before)
        require(self.result(before[0])[0]==status,'Command result '+repr((text,self.result(before[0]))))
        if expected:require(expected in read_cells(self.far,self.source(self.index())),'Missing command output '+text)
        self.report.setdefault('commands',[]).append(dict(text=text,result=self.result(before[0])))
    def live(self):return self.number(self.p['build']['task_storage']['LIVE'],1)
    def terminal_ready(self):
        row=self.windows+self.c['WINDOWS_ITEMS']+self.index()*self.c['WINDOW_SIZE']
        slot=self.number(row+self.c['WINDOW_UNIT'])&3
        # Shell selection publishes before the terminal's asynchronous refresh.
        # Select stores this index after BindWindow returns; dirty clears after paint.
        state=self.number(self.terminal)
        self.rendezvous(f'(dw(${state+8:x})={slot})&(dw(${state+10:x})=0)')
    def close_extra_session(self):
        live=self.at('controllerLive')
        if self.number(live,1)<2:return
        self.command('SESSION 2')
        for char in 'EXIT':self.press(char)
        self.b._cmd_ok('KEY RETURN down')
        self.rendezvous(f'db(${live:x})=1')
        self.b._cmd_ok('KEY RETURN up')
        self.ready();self.terminal_ready();self.frames(40)
        self.report['extra_session_exited']=True
    def startup(self):
        from colour_desktop_model import FIELDS
        MODELS['terminal']=('GEMTerminal',0,18)
        children=self.provider['GEMDesktopChildren']
        self.rendezvous(f'dw(${children+8:x})!=0')
        apps=instances(self.b,self.p,self.directory)
        desktop=next(a for a in apps if a['name']=='desktop')
        terminal=next(a for a in apps if a['name']=='terminal')
        self.rendezvous(f'dw(${desktop["symbols"]["GEMDesk"]+FIELDS["ready"]:x})=1')
        pointer=terminal['symbols']['GEMTerminal']
        self.terminal=pointer
        self.rendezvous(f'(dw(${pointer:x})|db(${pointer+2:x}))!=0')
        state=self.number(pointer)
        self.rendezvous(f'(dw(${state+6:x})=1)&(dw(${state+14:x})!=0)')
        self.frames(120);self.menus.select('Terminal');self.frames(40)
    def counters(self,load):
        MODELS['gfcount']=('GEMCounter',12,38)
        return sorted(instances(self.b,self.p,load),key=lambda a:a['identity'])
    def counter_ready(self,load,count):
        for _ in range(300):
            apps=self.counters(load)
            if len(apps)==count and all(self.number(a['symbols']['GEMCounter']+12,2)==1 for a in apps):
                self.frames(60)
                return
            self.frames(5)
        raise RuntimeError('Counter startup did not finish')
    def sample(self,load,label):
        font=font_bytes(self.directory/'selected/src/vdi/font8x8.c')
        colours=[bytes((v&254)+(v>>7) for v in DESKTOP_PALETTE[i*3:i*3+3])[::-1] for i in range(16)]
        for attempt in range(100):
            clients=[];okay=True
            frame=self.b.rawscreen(str(self.out/(label+'.bgra')))
            raw=(self.out/(label+'.bgra')).read_bytes()
            for app in self.counters(load):
                at=app['symbols']['GEMCounter'];config=self.number(at)
                if self.number(at+12,2)!=1:continue
                count=self.number(at+14);paints=self.number(at+18)
                work=[self.number(at+38+i*2,2) for i in range(4)]
                ink=self.number(config+12,2);paper=self.number(config+14,2)
                digits=('%06d'%count).encode()
                want=b''.join(colours[ink if font[y*256+ch]&(128>>x) else paper]
                    for y in range(8) for ch in digits for x in range(8))
                actual=digit_pixels(raw,frame.stride,frame.width,frame.height,work[0]+64,work[1]+8)
                okay=okay and actual==want
                clients.append(dict(identity=app['identity'],base=app['base'],id=self.number(at+4,2),
                    window=self.number(at+8,2),count=count,paints=paints,work=work,
                    digits_sha256=hashlib.sha256(actual).hexdigest()))
            if len(clients)==2 and okay:
                result=dict(label=label,frame=self.b.eval_expr('@frame'),clock=self.b.eval_expr('@clk'),
                    live_tasks=self.live(),clients=clients,exact_digit_pixels=768)
                self.report.setdefault('samples',[]).append(result)
                return result
            self.frames(2)
        raise RuntimeError('No exact two-Counter frame '+label)
    def pointer(self,label):
        x=self.native('DESKINPUT','cursorX');y=self.native('DESKINPUT','cursorY')
        dirty=self.native('DESKINPUT','dirty');old=[self.number(x,2),self.number(y,2)]
        target=[min(639,old[0]+8),min(239,old[1]+8)]
        start=self.b.eval_expr('@clk');schedule(self.b,self.p,old,target)
        self.rendezvous(f'(dw(${x:x})={target[0]})&(dw(${y:x})={target[1]})','native_irq')
        captured=self.b.eval_expr('@clk')
        self.rendezvous(f'db(${dirty:x})=0','native_irq');presented=self.b.eval_expr('@clk')
        self.frames(1)
        item=dict(label=label,target=target,start=start,captured=captured,presented=presented,
            capture_ms=((captured-start)&0xffffffff)/1773447.5*1000,
            presentation_ms=((presented-start)&0xffffffff)/1773447.5*1000)
        self.report.setdefault('pointer',[]).append(item)
    def load_image(self):
        abi=json.loads((ROOT/'abi/process.json').read_text());fields={n:o for n,_,o in abi['record']}
        table=self.p['build']['memory']['process_storage']
        for i in range(table['CAPACITY']):
            row=table['BASE']+i*abi['record_bytes'];image=self.number(row+fields['image'],3)
            if not image or self.number(row+fields['state'],1)!=2:continue
            name=self.far(image+IMAGE['name'],24).split(b'\0')[0]
            if b'GFLOAD' in name.upper():return image
        return None
    def close_counter(self,title):
        from generate_desktop import layout
        from generate_layers import layout as layer_layout
        self.menus.select(title)
        window=next(w for w in self.menus.windows() if title==w['title'])
        types=layout();layers=layer_layout();service=self.menus.service;wf=types['Window']['fields']
        scene=service+types['Service']['fields']['scene']
        for slot in range(6):
            at=service+types['Service']['fields']['windows']+slot*types['Window']['size']
            if self.number(at+wf['id'])!=window['id']:continue
            layer=self.number(at+wf['layer'])
            for li in range(8):
                item=scene+layers['Scene']['fields']['items']+li*layers['Layer']['size']
                if self.number(item)==layer:
                    bounds=struct.unpack('<4h',self.far(item+layers['Layer']['fields']['bounds'],8))
                    self.click(bounds[0]+6,bounds[1]+5);self.frames(100)
                    return
        raise RuntimeError('No live Counter frame to close')
    def cancel_work(self,load):
        self.menus.select('Terminal')
        cancelled=self.begin('TEST:GFLOAD CANCEL')
        for _ in range(400):
            image=self.load_image()
            if image:break
            self.frames(3)
        require(image is not None,'Cancellation command did not load')
        descriptor=json.loads((load/'GFLOAD.profile.json').read_text())
        item=next(o for o in descriptor['objects'] if '_PROGRESS_' in o['name'])
        record=self.number(image+IMAGE[item['location']['section'].lower()],3)+item['location']['offset']
        self.rendezvous(f'(dw(${record:x})=2)&(db(${self.p["labels"]["SD_PHASE"]:x})>0)')
        self.b._cmd_ok('KEY BREAK down');self.frames(3)
        self.b._cmd_ok('KEY BREAK up');self.ready(cancelled)
        result=self.result(0)
        require(result==(5,304),'Cancelled read result: '+repr(result))
        self.report['physical_read_cancel']=dict(primary=result[0],read_error=result[1])

    def load_work(self,load):
        self.command('MOUNT TEST: DRIVE 8 FORMAT SPARTA READWRITE')
        self.command('RUN TEST:GFCOUNT.APP 1')
        self.counter_ready(load,1)
        self.command('NEWSHELL');self.rendezvous(f'dw(${self.at("selectedSession"):x})=2');self.ready()
        self.command('RUN TEST:GFCOUNT.APP 2')
        self.counter_ready(load,2)
        self.command('SESSION 1');self.rendezvous(f'dw(${self.at("selectedSession"):x})=1');self.ready()
        self.command('SYS:C/PANEL.APP',status=20)
        self.report['fifth_aes_client_rejected']=True
        self.menus.select('Counter A');self.menus.select('Counter B');self.move(620,232);self.frames(100)
        initial=self.sample(load,'load-ready')
        self.menus.select('Terminal')
        before=self.begin('TEST:GFLOAD')
        for _ in range(400):
            image=self.load_image()
            if image:break
            self.frames(3)
        require(image is not None,'Native disk command did not load')
        descriptor=json.loads((load/'GFLOAD.profile.json').read_text())
        item=next(o for o in descriptor['objects'] if '_PROGRESS_' in o['name'])
        record=self.number(image+IMAGE[item['location']['section'].lower()],3)+item['location']['offset']
        self.rendezvous(f'(dw(${record:x})=2)&(db(${self.p["labels"]["SD_PHASE"]:x})>0)')
        self.menus.select('Counter A');self.menus.select('Counter B');self.move(320,120)
        self.pointer('disk');self.move(620,232)
        during=self.sample(load,'load-during')
        self.report['disk_active_progress']=progress(initial,during)
        self.report['peak_tasks']=self.live()
        self.ready(before)
        require(self.result(0)[0]==0,'Four-pass disk command failed')
        self.frames(100);final=self.sample(load,'load-complete')
        self.report['progress']=progress(initial,final)
        self.report['offered_work']=dict(passes=4,read_bytes=65536,written_bytes=65536,
            buffer_bytes=16384,counter_body_sha256=sha256(ROOT/'examples/gem-counter/counter.c'))
        self.cancel_work(load)
        # Close through ordinary GUI messages; each shell collects its own job.
        for title in ('Counter A','Counter B'):
            self.close_counter(title)
        self.menus.select('Terminal');self.command('JOBS',b'finished')
        self.command('SESSION 2');self.command('JOBS',b'finished');self.command('SESSION 1')
        self.report['closed_counters']=True
        self.command('RUN TEST:GFCOUNT.APP 1');self.counter_ready(load,1)
        self.close_counter('Counter A');self.command('JOBS',b'finished')
        self.report['counter_relaunched']=True

    def qed(self,bundle):
        from qed_coexist_observe import ProductionEditor,current_offsets
        from qed_demo import mount_editor
        from prime_observer import process_record
        production=bundle/'qed-production'
        offsets=current_offsets(production,self.out/'qed-layout')
        mount_editor(self)
        self.command('RUN QED:QED.APP')
        identity=self.number(self.at('job'))
        editor=ProductionEditor(self,production,offsets,identity,self.out,self.report,0)
        editor.reach(f'(dw(${editor.sy["text_list"]:x})!=0)|(dw(${editor.sy["text_list"]+2:x})!=0)')
        editor.reach(f'dw(${editor.sy["QedStarting"]:x})=0')
        editor.command_idle();self.frames(80)
        editor.click(*editor.cell(0,0));editor.move(632,20)
        editor.loaded('gem-first-qed-empty',[b''])
        editor.key('A');editor.key('B')
        editor.check('gem-first-qed-edit',[b'ab'])
        title=next(w['title'] for w in self.menus.windows() if w['id']==self.menus.focus())
        self.menus.select('Terminal');self.command('ECHO qed-coexists',b'qed-coexists')
        self.menus.select(title);editor.move(632,20)
        editor.check('gem-first-qed-exposed',[b'ab'])
        editor.key('Q',ctrl=True);editor.form_open();editor.form_pixels('gem-first-qed-close')
        release=editor.alert(2,retiring=True)
        fields={n:o for n,_,o in json.loads((ROOT/'abi/process.json').read_text())['record']}
        row=process_record(self.far,self.p,identity)
        self.rendezvous(f'db(${row+fields["state"]:x})=4')
        release()
        self.menus.select('Terminal');self.command('JOBS',b'finished')
        self.report['qed_coexistence']=True


def bootstrap(b,p,bundle,extracted,report):
    boot=json.loads((bundle/'of816/of816.json').read_text())
    from test_of816 import check_loading_paused,check_loading_complete,check_boot_guards
    image=extracted/'Exec-of816.xex'
    require(sha256(image)==boot['xex_sha256'],'Changed extracted OF816 image')
    b.boot(str(image));b.bp_set(boot['labels']['of_start']);run_to(b,boot['labels']['of_start'],3000,90)
    check_loading_paused(b,boot,p);b.bp_clear_all();b._cmd_ok('KEY ALL up')
    b.bp_set(boot['labels']['of_autoboot']);run_to(b,boot['labels']['of_autoboot'],1000,30)
    b.bp_clear_all();start=b.eval_expr('@frame')
    b.bp_set(boot['labels']['of_handoff']);run_to(b,boot['labels']['of_handoff'],300,15)
    report['autoboot_frames']=b.eval_expr('@frame')-start
    require(249<=report['autoboot_frames']<=251,'Five-second autoboot changed')
    check_boot_guards(b,boot['layout']);settings=check_loading_paused(b,boot,p)
    b.bp_clear_all();b.bp_set(p['labels']['loader_start']);run_to(b,p['labels']['loader_start'],3000,90)
    check_loading_complete(b,boot,p,settings)
    b.bp_clear_all();b.bp_set(p['labels']['start']);run_to(b,p['labels']['start'],3000,90)
    b.bp_clear_all()


def run(directory,out,load=None,bundle=None,qed=False,sessions=False,cancel_only=False):
    require(not cancel_only or load is not None,'--cancel-only requires --load')
    out.mkdir(parents=True,exist_ok=True)
    p=read_build(bundle or directory/'program');original=p['output']
    report=dict(status='running',tier='development',qualification=False,
        xex_sha256=sha256(p['xex']),provider_sha256=sha256(directory/'c-image.json'))
    extracted=None
    if bundle:
        with zipfile.ZipFile(bundle/'exec816-demo.zip') as z:z.extractall(out/'extracted')
        extracted=out/'extracted/exec816-demo'
        manifest=json.loads((bundle/'demo-manifest.json').read_text())
        source=extracted/manifest['media'];report['zip_sha256']=sha256(bundle/'exec816-demo.zip')
    else:source=directory/'system.atr'
    shutil.copyfile(source,out/'system.atr')
    initial=Audit(source.read_bytes());initial.sdfs()
    report['initial_system_sha256']=sha256(source)
    if load:shutil.copyfile(load/'seed.atr',out/'load.atr')
    with emulator(BRIDGE,extracted/'altirraos-816.rom' if extracted else ROM,out,pin=PIN) as b:
        for key,value in PIN['configuration'].items():b.config(key,str(value).lower() if isinstance(value,bool) else value)
        report['machine']=verify_machine(b,extracted/'altirraos-816.rom' if extracted else ROM,PIN)
        b.mount(0,str(out/'system.atr'))
        if load:b.mount(7,str(out/'load.atr'))
        if qed:
            require(bundle is not None,'QED requires its production bundle')
            shutil.copyfile(bundle/'qed.atr',out/'qed.atr');b.mount(1,str(out/'qed.atr'))
        if bundle:bootstrap(b,p,bundle,extracted,report)
        def before(b):
            b._cmd_ok('KEY ALL up');b._cmd_ok('MOUSE ST')
            selected=address(p['image'],'selectedSession')
            b.bp_clear_all();b.bp_set(p['labels']['native_nmi'],condition=f'dw(${selected:x})=1')
            run_to(b,p['labels']['native_nmi'],12000,180,f'dw(${selected:x})=1')
            s=Session(b,p,directory,out,report);s.ready();s.startup()
            report['boot_tasks']=s.live();s.command('ECHO gem-first-ready',b'gem-first-ready')
            if load and cancel_only:
                s.command('MOUNT TEST: DRIVE 8 FORMAT SPARTA READWRITE')
                s.cancel_work(load)
            elif load:s.load_work(load)
            elif sessions:
                s.command('NEWSHELL');s.command('SESSION 1')
            if qed:s.qed(bundle)
            s.menus.select('Terminal')
            s.close_extra_session()
            for ch in 'EXIT':s.press(ch)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all()
        try:
            report['runtime'],_=execute(b,{**p,'output':out},before_run=before,
                timeout=300,frame_limit=20000,preloaded=bool(bundle))
            ownership(b,p,original);report['status']='runtime-pass'
        except Exception as error:
            report.update(status='fail',error=str(error),native_status=int.from_bytes(b.memdump(adapter.STATE,2),'little'))
            raise
        finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
        if load:b._cmd_ok('EJECT drive=7')
        b._cmd_ok('EJECT drive=0')
    try:
        final=Audit((out/'system.atr').read_bytes());allocation=final.sdfs()
        for name,payload in initial.files.items():
            if name.endswith('DESKTOP.CFG'):continue
            require(final.files.get(name)==payload,'Changed packaged input '+name)
        report['system_audit']=dict(status='pass',allocation=allocation,
            original_files_preserved=len(initial.files),sha256=sha256(out/'system.atr'))
        if load:
            audit=Audit((out/'load.atr').read_bytes());allocation=audit.sdfs()
            payload=(load/'media/LOAD.BIN').read_bytes()
            require(audit.files['LOAD.BIN']==audit.files['CANCEL.BIN']==payload,'Read inputs changed')
            if not cancel_only:
                require(audit.files['RESULT.BIN']==payload,'Persisted disk bytes differ')
            else:require('RESULT.BIN' not in audit.files,'Read cancellation created output')
            report['disk_audit']=dict(status='pass',allocation=allocation,sha256=sha256(out/'load.atr'))
        report['status']='pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    parser.add_argument('--load',type=Path)
    parser.add_argument('--bundle',type=Path)
    parser.add_argument('--qed',action='store_true')
    parser.add_argument('--cancel-only',action='store_true',help='Focused cold read cancellation; requires --load')
    parser.add_argument('--sessions',action='store_true',help='Focused two-session shutdown without disk load')
    a=parser.parse_args();run(a.build.resolve(),a.output.resolve(),
        a.load.resolve() if a.load else None,a.bundle.resolve() if a.bundle else None,a.qed,a.sessions,a.cancel_only)
