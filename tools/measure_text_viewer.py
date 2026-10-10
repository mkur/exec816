#!/usr/bin/env python3
"""Bounded physical-input measurements on the unchanged OF816 viewer package."""
import argparse
import json
import math
import os
import re
import zipfile
from pathlib import Path

from desktop_menu_check import Menus
from desktop_mouse import schedule
from gem_applications import instances, symbols
from native_program import require, sha256
from generate_aes_server import layout
from sio_transaction_trace import BASE_HZ
from test_demo import run
from text_model import FIELDS as F, LOAD_PHASE


def distribution(values):
    ordered = sorted(values)
    return dict(count=len(values), median=ordered[len(ordered)//2] if len(ordered)%2 else
                (ordered[len(ordered)//2-1]+ordered[len(ordered)//2])/2,
                p95=ordered[math.ceil(len(ordered)*.95)-1], maximum=ordered[-1])


class ViewerMeasurement:
    def __init__(self, count, panel=True):
        self.count, self.panel = count, panel
        self.record = dict(samples=[], panel=[], milestones='IRQ-sampled software state; scanout excluded')

    def exercise(self, s):
        directory = s.p['output']/'bitmap-console'
        shared = json.loads((directory/'c-image.json').read_text())['symbols']
        panel_symbols = symbols(s.b,s.p,directory,'panel',s.number(shared['GEMDesktopChildren'],4))
        panel = panel_symbols['GEMPanel']
        panel_task=next(x['task'] for x in instances(s.b,s.p,directory) if x['name']=='panel')
        fields=layout()['Request']['fields']
        contexts=[s.number(shared['contexts']+i*4,4) for i in range(4)]
        context=next(c for c in contexts if c and s.number(c+fields['owner'],3)==panel_task)
        receiving=s.number(context+fields['receiving'],3)
        event_mask=1<<s.number(receiving+12,1)
        counter = symbols(s.b,s.p,directory,'counter',s.number(shared['GEMDesktopChildren']+4,4))['GEMCounter']
        def at(name):
            return next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
        def move(x,y):
            current=[s.number(at(n),2) for n in ('cursorX','cursorY')]
            target=schedule(s.b,s.p,current,(x,y));s.saved['pointer']=target
            s.rendezvous('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),target[0],at('cursorY'),target[1]))
        def click(x,y):
            move(x,y);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(6)
            s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(40)
        def clock(): return s.b.eval_expr('@clk')
        def panel_idle(actions):
            # Wait on the inbox belongs to evnt_multi. UPDATE/RPC waits use
            # different signals, so they cannot masquerade as paint completion.
            s.rendezvous('(dw($%x)!=%d)&(db($%x)=4)&(dw($%x)=%d)&(dw($%x)=%d)'%
                (panel+10,actions&65535,panel_task+12,panel_task+20,event_mask&65535,
                 panel_task+22,event_mask>>16))
        def key(name,shift=False):
            cursor=name in ('UP','DOWN')
            if cursor:
                s.b._cmd_ok('KEY CTRL down')
                name='MINUS' if name=='UP' else 'EQUALS'
            if shift:s.b._cmd_ok('KEY SHIFT down')
            s.b._cmd_ok('KEY '+name+' down');s.frames(3);s.b._cmd_ok('KEY '+name+' up')
            if shift:s.b._cmd_ok('KEY SHIFT up')
            if cursor:s.b._cmd_ok('KEY CTRL up')
        def memory():
            screen=s.command('MEM').decode('ascii')
            return [int(v) for v in re.findall(r'(?:ordinary|linear) (?:total|largest) +(\d+)',screen)][-4:]
        s.saved['desktop_menu']={};menus=Menus(s,click,move)
        menus.select('Files');menus.close();menus.select('Shell')
        owners=s.ledger();baseline=memory()
        old=s.begin('RUN C:TEXT.APP SYS:STORY.TXT');s.ready(old);s.result()
        identity=s.number(s.at('job'),4)
        app=next(x for x in instances(s.b,s.p,directory) if x['identity']==identity and x['name']=='text')
        a=app['symbols']['GEMText'];n=lambda name,size=2:s.number(a+F[name],size)
        self.record['app']=app
        self.record['start_load_observation']=clock()
        if os.environ.get('EXEC816_LATENCY_PCS'):s.b.profile_start()
        def settled():
            s.rendezvous('(dw($%x)=1)&(dw($%x)=0)&(dw($%x)=0)'%
                         (a+F['ready'],a+F['load']+LOAD_PHASE,a+F['dirty']))
        settled();self.record['load_settled_observation']=clock()
        s.frames(80)
        menus.select('STORY.TXT');move(630,230);s.cells('performance-initial')
        start_count=s.number(counter+14,4)
        def checkpoint():
            (s.p['output']/'text-performance-samples.json').write_text(json.dumps(self.record,indent=2)+'\n')
        for operation in ('page','line'):
            for i in range(self.count):
                settled();s.frames(6)
                first=n('first');paints=n('paints',4)
                row=dict(operation=operation,index=i,start=clock(),first=first,paints=paints)
                # A short physical key pulse; the queued key remains durable.
                key('SPACE' if operation=='page' else ('DOWN' if i%2==0 else 'UP'),shift=operation=='page' and i%2==1)
                s.rendezvous('dw($%x)!=%d'%(a+F['first'],first));row['model']=clock()
                s.rendezvous('dw($%x)!=%d'%(a+F['paints'],paints&65535));row['first_band']=clock()
                settled();row['complete']=clock();row['final_first']=n('first')
                expected=first+(n('rows') if operation=='page' else 1)*(1 if i%2==0 else -1)
                require(row['final_first']==expected,'Unexpected scroll result')
                row['paint_bands']=n('paints',4)-paints
                for label,end in [('model','model'),('first_band','first_band'),('complete','complete')]:
                    row[label+'_ms']=((row[end]-row['start'])&0xffffffff)*1000/BASE_HZ
                self.record['samples'].append(row);checkpoint()
                print(operation,i,round(row['complete_ms'],3),'ms',flush=True)
            s.frames(60);s.cells('performance-'+operation)
        # A top-boundary key must not repaint.
        before=n('paints',4);key('UP');s.frames(30)
        require(n('first')==0 and n('paints',4)==before,'No-op scroll repainted')
        def panel_action(i):
            click(96,40);settled();s.frames(30);move(568,176)
            first=n('first');actions=s.number(panel+10,4)
            key('SPACE',shift=i%2==1);s.frames(3)
            row=dict(index=i,offered_frame=s.b.eval_expr('@frame'),start=clock(),
                     viewer_dirty=n('dirty'),viewer_first=n('first'))
            s.b._cmd_ok('MOUSE AT 2000 0 0 1')
            # Raising an inactive GEM window is a separate transaction.
            # Wait for its focus acknowledgment before offering a button.
            s.b._cmd_ok('MOUSE AT %d 0 0 0'%(2000+round(.04*BASE_HZ)))
            target=next(w['id'] for w in menus.windows() if w['title']=='GEM Control Panel')
            s.rendezvous('dw($%x)=%d'%(menus.focus_address,target))
            s.frames(3);row['gesture']=clock();row['gesture_dirty']=n('dirty')
            s.b._cmd_ok('MOUSE AT 2000 0 0 1')
            s.b._cmd_ok('MOUSE AT %d 0 0 0'%(2000+round(.08*BASE_HZ)))
            panel_idle(actions);row['paint']=clock()
            s.frames(30);settled()
            require(s.number(panel+10,4)==actions+1,'Panel missed or duplicated activation')
            row.update(paint_ms=((row['paint']-row['start'])&0xffffffff)*1000/BASE_HZ,
                       button_paint_ms=((row['paint']-row['gesture'])&0xffffffff)*1000/BASE_HZ,
                       scope='Fixed-offset raise; focus acknowledgment then an 80 ms button gesture; completed inbox wait after synchronous drawing')
            return row
        if self.panel:
            # Offer the raise six PAL frames after a page key.
            for i in range(self.count):
                row=panel_action(i)
                self.record['panel'].append(row);checkpoint()
                print('panel',i,round(row['paint_ms'],3),'ms',flush=True)
            move(630,230);s.frames(60);s.cells('performance-panel-overlap')
        # New model damage must repair bands already drawn for the old page.
        menus.select('STORY.TXT');settled();move(630,230);s.frames(20)
        key('SPACE');s.frames(3)
        require(n('first')==n('rows') and n('dirty'),'Missing in-flight repaint')
        key('SPACE',shift=True);settled();s.frames(60)
        require(n('first')==0,'Mid-repaint model change was lost')
        s.cells('performance-model-replaced');self.record['model_replaced_during_paint']=True
        if self.panel:
            # One additional bounded case with real disk/console work. Report
            # it individually; it is not another percentile cohort.
            menus.select('Shell');cat=s.begin('CAT LONG.TXT')
            menus.select('STORY.TXT')
            running=s.number(s.saved['top']+51,1)!=2 or s.number(s.saved['scope']+54,1)!=0
            require(running,'Shell workload finished before loaded input')
            self.record['shell_loaded_panel']=panel_action(0)
            # Bound the offered stream instead of waiting for a full LONG.TXT
            # repaint behind several windows. BREAK follows normal shell routing.
            menus.select('Shell')
            window=s.p['build']['memory']['console_storage']['WINDOWS']+s.console['WINDOWS_ITEMS']
            foreground=s.number(window+s.console['WINDOW_SCOPE'],3)
            cancelled=foreground not in (0,s.saved['scope']);started=clock()
            if cancelled:s.press('\x03')
            s.ready(cat);s.result(304 if cancelled else 0)
            self.record['shell_loaded_panel'].update(cancelled=cancelled,
                retire_ms=((clock()-started)&0xffffffff)*1000/BASE_HZ)
            move(630,230);s.frames(60);s.cells('performance-shell-load')
        require(s.number(counter+14,4)>start_count,'Counter stopped during repaint workload')
        menus.select('STORY.TXT');menus.close()
        s.rendezvous('db($%x)=3'%(s.at('job')+12));s.frames(80);menus.select('Shell')
        require(s.ledger()==owners and memory()==baseline,'Viewer measurement retained resources')
        self.record.update(counter_progress=True,heap_return=True,no_op=True)
        checkpoint();s.save_screen(s.p['output']/'boot-smoke.png')
        for char in 'EXIT':s.press(char)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


def measure(out,count,observe=False,panel=True):
    out=out.resolve()
    (out/'measurement-observer.py').write_text(Path(__file__).read_text())
    with zipfile.ZipFile(out/'exec816-demo.zip') as archive:
        archive.extractall(out/'extracted')
    definition=None
    if observe:
        from text_performance_trace import prepare
        definition=prepare(out)
        os.environ['EXEC816_LATENCY_PCS']=','.join(f'{pc:x}' for pc in definition['pcs'])
        os.environ.pop('EXEC816_MASK_TRACE',None)
    integration=ViewerMeasurement(count,panel)
    result=run(out,boot_smoke=True,distribution_root=out/'extracted/exec816-demo',integration=integration,profile_commands=False)
    result.update(scope='Physical text page/line and Panel feedback during viewer repaint',
                  qualification=False,zip_sha256=sha256(out/'exec816-demo.zip'),text_performance=integration.record)
    result['ordinary_stack_headroom_pass']=all(result['gem_stacks'][str(i)]['remaining_above_floor']>=128 for i in range(1,6))
    require(result['ordinary_stack_headroom_pass'],'Ordinary Task stack margin below 128 bytes')
    for operation in ('page','line'):
        samples=[r for r in integration.record['samples'] if r['operation']==operation]
        integration.record[operation+'_distribution']={k:distribution([r[k+'_ms'] for r in samples]) for k in ('model','first_band','complete')}
    if integration.record['panel']:
        integration.record['panel_distribution']={k:distribution([r[k+'_ms'] for r in integration.record['panel']]) for k in ('paint','button_paint')}
    (out/'text-performance-functional.json').write_text(json.dumps(result,indent=2)+'\n')
    if definition:
        from text_performance_trace import analyze
        result['breakdown']=analyze(out,definition,integration.record)
    (out/'text-performance-results.json').write_text(json.dumps(result,indent=2)+'\n')
    return result


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bundle',type=Path,required=True)
    parser.add_argument('--count',type=int,default=10)
    parser.add_argument('--observe',action='store_true')
    parser.add_argument('--no-panel',action='store_true')
    args=parser.parse_args();require(args.count>0 and args.count%2==0,'Use a positive even count')
    measure(args.bundle,args.count,args.observe,not args.no_panel)
