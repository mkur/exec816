#!/usr/bin/env python3
"""WB0: unchanged normal desktop startup, IDE/child capacity and refusal."""
import argparse,json,re,zipfile
from pathlib import Path
from native_program import require,sha256
from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances,symbols


class Baseline:
    interrupt_marker='native_nmi'
    def __init__(self,case='all'):self.case=case
    def exercise(self,s):
        try:self.check(s)
        except BaseException:
            s.b.screenshot(str(s.p['output']/'workbench-baseline-failure.png'))
            raise
    def check(self,s):
        b=s.b;directory=s.p['output']/'bitmap-console'
        def at(name):return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            x,y=schedule(b,s.p,current,(x,y));s.saved['pointer']=[x,y]
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));s.frames(3)
        def click(x,y):
            move(x,y)
            for edge in (1,0):b._cmd_ok('MOUSE AT 2000 0 0 '+str(edge));s.frames(25)
            s.frames(60)
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        live=s.p['build']['task_storage']['LIVE'];menus.select('Shell')
        baseline_tasks=s.number(live,1)
        require(baseline_tasks==6,'Normal startup no longer leaves two Task slots')
        cases=[]
        def memory():
            text=s.command('MEM').decode('ascii')
            return [int(v) for v in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',text)][-4:]
        def free_extents():
            storage=s.p['build']['memory']['heap_storage'];result=[]
            head=s.number(storage['BASE'],3)
            while head!=storage['BASE']+3:
                require(storage['HEADERS']<=head<storage['HEADERS']+storage['CAPACITY']*32,'Invalid heap region observer')
                chunk=s.number(head+14,3)
                while chunk:
                    raw=b.memdump(chunk,8);size=int.from_bytes(raw[4:8],'little')
                    result.append([chunk,chunk+size]);chunk=int.from_bytes(raw[:3],'little')
                head=s.number(head,3)
            return sorted(result)
        def launch(name):
            menus.select('Shell');old=s.begin('RUN C:'+name+'.APP');s.ready(old);s.result()
            matches=[i for i in instances(b,s.p,directory) if i['name']==name.lower()]
            require(matches,'Missing running '+name)
            item=matches[-1];model='Basic' if name=='BASIC' else 'GEMCounter'
            ready=8 if name=='BASIC' else 12
            s.rendezvous('dw($%x)=1'%(item['symbols'][model]+ready));s.frames(80)
            return item
        shell=next(w['id'] for w in menus.windows() if w['title']=='Shell')
        if self.case!='capacity':
            start=b.eval_expr('@frame');app=launch('BASIC')
            open_frames=b.eval_expr('@frame')-start
            require(s.number(live,1)==7,'IDE did not use one ordinary Task slot')
            shell=next(w['id'] for w in menus.windows() if w['title']=='Shell')
            menus.key('TAB',ctrl=True)
            s.rendezvous('dw($%x)=%d'%(menus.focus_address,shell))
            s.command('ECHO "PRINT 7" >RAM:WB0.BAS')
            s.command('C:FBCI.COM RAM:WB0.BAS RAM:WB0.COM',b'Compiled')
            s.command('RAM:WB0.COM',b'7')
            require(s.number(live,1)==7,'Compiler/program left a Task behind beside IDE')
            require(s.number(app['symbols']['Basic']+8,2)==1,'Compiler disturbed IDE state')
            menus.select('FastBasic');move(630,230);s.cells('wb0-normal-window');menus.close()
            menus.select('Shell');s.command('MEM');s.frames(80)
            require(s.number(live,1)==baseline_tasks,'IDE close did not restore Task capacity')
            baseline=memory();owners=s.ledger()
            cases.append(dict(name='normal IDE and compiler/program',status='pass',open_frames=open_frames,
                              baseline_tasks=baseline_tasks,IDE_tasks=7,peak_with_child=8))
            (s.p['output']/'workbench-normal-progress.json').write_text(json.dumps(dict(
                tier='development',status='partial',cases=cases,package_sha256=sha256(s.p['output']/'exec816-demo.zip'),
                test_sha256=sha256(Path(__file__))),indent=2)+'\n')
        else:
            baseline=memory();owners=s.ledger()
        if self.case=='coexist':
            s.saved['integration']=dict(profile='fastbasic-workbench-WB0-coexist',cases=cases,baseline_heap=baseline)
            s.save_screen(s.p['output']/'boot-smoke.png')
            for character in 'EXIT':s.press(character)
            b._cmd_ok('KEY RETURN down');b.bp_clear_all();return
        before_free=free_extents()
        # The desktop owns these launches; the Shell's one background-job
        # record remains free, so refusal exercises Task admission itself.
        def desktop_launch(row,name,ready):
            menus.select('SYS:');click(296,8);click(304,28+row*11)
            matches=[]
            for attempt in range(40):
                s.frames(50)
                matches=[i for i in instances(b,s.p,directory) if i['name']==name]
                if matches:break
            require(len(matches)==1,'Desktop did not launch '+name)
            model='GEMPanel' if name=='panel' else 'GEMCounter'
            s.rendezvous('dw($%x)=1'%(matches[0]['symbols'][model]+ready))
            painted=14 if name=='panel' else 18
            s.rendezvous('dw($%x)>0'%(matches[0]['symbols'][model]+painted))
            s.frames(100)
        cold=memory()
        desktop_launch(4,'counter',12)
        menus.close();s.frames(100)
        s.rendezvous('db($%x)=%d'%(live,baseline_tasks))
        menus.select('Shell');baseline=memory();owners=s.ledger()
        warm_bytes=cold[0]-baseline[0]
        require(warm_bytes==368,'Unexpected desktop path/timer warm allocation: '+str(warm_bytes))
        before_free=free_extents()
        for row,name,ready in ((1,'panel',8),(4,'counter',12)):
            desktop_launch(row,name,ready)
        menus.key('TAB',ctrl=True)
        s.rendezvous('dw($%x)=%d'%(menus.focus_address,shell))
        require(s.number(live,1)==8,'Capacity fixture did not fill normal slots')
        before=memory();held=s.ledger()
        s.command('RUN C:BASIC.APP',error=103)
        require(memory()==before and s.ledger()==held,'Refused IDE retained Image or resources')
        for title in ('Control Panel','Counter'):menus.select(title);menus.close();s.frames(100)
        menus.select('Shell');s.command('MEM');s.frames(100)
        recovered=memory();recovered_owners=s.ledger();after_free=free_extents()
        if recovered!=baseline or recovered_owners!=owners:
            added=[]
            for lo,hi in before_free:
                segments=[(lo,hi)]
                for a,z in after_free:
                    segments=[piece for x,y in segments for piece in
                        ([(x,y)] if y<=a or x>=z else ([(x,a)] if x<a else [])+([(z,y)] if y>z else []))]
                for x,y in segments:
                    added.append(dict(address=x,bytes=y-x,head=b.memdump(x,min(256,y-x)).hex()))
            (s.p['output']/'workbench-heap-difference.json').write_text(json.dumps(dict(
                baseline=baseline,recovered=recovered,before_owners=owners,after_owners=recovered_owners,
                before_free=before_free,after_free=after_free,newly_occupied=added),indent=2)+'\n')
        require(recovered==baseline and recovered_owners==owners,'Capacity recovery leaked resources')
        app=launch('BASIC');menus.select('FastBasic');menus.close()
        menus.select('Shell');s.command('MEM');s.frames(80)
        require(memory()==baseline and s.ledger()==owners,'Relaunch/close leaked resources')
        cases.append(dict(name='normal refusal, recovery, relaunch',status='pass',error=103,heap_return=True))
        s.saved['integration']=dict(profile='fastbasic-workbench-WB0',cases=cases,
            baseline_heap=baseline,reserved_bank_zero_delta=dict(fixed=0,root_kernel=0,per_public_task=[0]*8,idle=0))
        s.save_screen(s.p['output']/'boot-smoke.png')
        for character in 'EXIT':s.press(character)
        b._cmd_ok('KEY RETURN down');b.bp_clear_all()


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',type=Path,required=True)
    p.add_argument('--case',choices=('all','coexist','capacity'),default='all')
    a=p.parse_args();out=a.bundle.resolve()
    with zipfile.ZipFile(out/'exec816-demo.zip') as z:z.extractall(out/'extracted')
    from test_demo import run
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',
               integration=Baseline(a.case),profile_commands=False)
    (out/('workbench-'+a.case+'-results.json')).write_text(json.dumps(result,indent=2)+'\n')
