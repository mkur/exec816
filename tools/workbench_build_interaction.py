"""Physical WB9 keys/mouse; model memory is observed, never changed."""
import ast,json,time,os
from pathlib import Path
from types import SimpleNamespace
from native_program import ROOT,read_build,require,sha256,verify_machine
from workbench_interaction import FIELDS
from basic_build_model import FIELDS as JOB,STAGES

def exercise(out,scenario=None):
 from os_boundary import emulator
 from test_mouse_observe import PIN,BRIDGE,ROM
 from test_dos_stack import execute,ownership
 from test_cooperative import data
 from desktop_mouse import schedule
 from desktop_menu_check import Menus
 from test_shell_core import KEYS
 KEYS.update({'%':('5',True),'$':('4',True),'#':('3',True),',':('COMMA',False),'(':('9',True),')':('0',True)})
 for call in ast.walk(ast.parse(Path(__file__).read_text())):
  if isinstance(call,ast.Call) and isinstance(call.func,ast.Name) and call.func.id in ('replace','run_source','choose','text'):
   for argument in call.args:
    if isinstance(argument,ast.Constant) and isinstance(argument.value,str):
     require(all(char in KEYS for char in argument.value),'Unmapped physical key in '+repr(argument.value))
 from generate_console import constants
 from console_model import read_cells
 from generate_aes_server import expected_layout,layout
 from file_selector_model import FIELDS as S,FORM_SELECTOR
 from stack_budget import stack_usage
 p=read_build(out/'program');app=json.loads((out/'app/app.json').read_text());foreign=json.loads((out/'c-image.json').read_text())
 at=lambda module,name:next(d['address'] for d in p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
 report=dict(status='running',tier='development',qualification=False,slice='WB9',cases=[],build=p['build'],application=app['sha256'])
 con=constants();storage=p['build']['memory']['console_storage']
 try:
  with emulator(BRIDGE,ROM,out,pin=PIN) as bridge:
   bridge._cmd_ok('MOUSE ST');bridge.config('diskemu','generic56k');bridge.mount(0,str(out/'system.atr'))
   report['machine']=verify_machine(bridge,ROM,PIN)
   number=lambda address,n=2:int.from_bytes(bridge.memdump(address,n),'little')
   def reach(condition):
    point=p['labels']['native_nmi'];condition='(@xpc=$%x)&(%s)'%(point,condition)
    bridge.bp_clear_all();bridge.bp_set(point,condition=condition);bridge.bp_set(p['labels']['done'],condition='dw($a00)!=$ffff')
    deadline=time.monotonic()+90;first=bridge.eval_expr('@frame');bridge.resume()
    while time.monotonic()<deadline:
     if bridge.eval_expr('dw($a00)')!=65535:
      bridge.pause();raise RuntimeError('Fixture terminated while waiting for '+condition)
     regs=bridge.regs()
     if int(regs['PC'].lstrip('$'),16)==point and bridge.eval_expr(condition):bridge.pause();return
     if bridge.eval_expr('@frame')-first>9000:break
     time.sleep(.01)
    bridge.pause();raise RuntimeError('Physical rendezvous timed out: '+condition)
   def frames(n=1):reach('@frame>=%d'%(bridge.eval_expr('@frame')+n))
   def move(x,y):
    old=[number(at('DESKINPUT',n)) for n in ('cursorX','cursorY')];x,y=schedule(bridge,p,old,(x,y))
    reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),x,at('DESKINPUT','cursorY'),y));frames(2)
   def edge(v):bridge._cmd_ok('MOUSE AT 2000 0 0 '+str(v));frames(4)
   def click(x,y):move(x,y);edge(1);edge(0)
   def key(name,ctrl=False,shift=False):
    if ctrl:bridge._cmd_ok('KEY CTRL down')
    if shift:bridge._cmd_ok('KEY SHIFT down')
    bridge._cmd_ok('KEY '+name+' down');frames(4);bridge._cmd_ok('KEY '+name+' up')
    if shift:bridge._cmd_ok('KEY SHIFT up')
    if ctrl:bridge._cmd_ok('KEY CTRL up')
    frames(4)
   def text(value):
    for ch in value:
     name,shift=KEYS[ch];key(name,shift=shift)
   current={}
   def before(_):
    for cycle in range(2):
     reach('(dw($%x)=1)&(dw($%x)=%d)'%(at('BASICBUILDINTERACTION','stage'),at('BASICBUILDINTERACTION','cycle'),cycle))
     base=number(at('BASICBUILDINTERACTION','appBase'),4);origin=app['abi']['link_bank']<<16
     basic=base+app['image']['symbols']['Basic']-origin;job=base+app['image']['symbols']['b']-origin
     current.update(base=base,basic=basic,job=job)
     d=basic+FIELDS['document'];sourceWindow=number(basic+4)
     reach('dw($%x)=1'%(basic+FIELDS['ready']));frames(25)
     print('Workbench cycle',cycle,'base',hex(base),flush=True)
     menus=Menus(SimpleNamespace(p=p,b=bridge,number=number,frames=frames,rendezvous=reach,saved={'desktop_menu':{}}),click,move)
     def select(title):
      windows=menus.windows();row=next(i for i,w in enumerate(windows) if w['title']==title);target=windows[row]['id']
      if menus.focus()==target:return
      click(600,8);click(472,16+row*11);reach('dw($%x)=%d'%(menus.focus_address,target));frames(30)
     def observed():
      ptr=number(d,4);gap=number(d+12,4);end=number(d+16,4)
      return bridge.memdump(ptr,gap)+bridge.memdump(ptr+end,32768-end)
     def replace(value):
      select('FastBasic');key('A',ctrl=True)
      reach('(dw($%x)=0)&(dw($%x)=%d)'%(basic+FIELDS['anchor'],basic+FIELDS['caret'],number(d+20,4)))
      reach('dw($%x)=0'%(basic+FIELDS['dirty']));frames(4)
      for char in value:
       edits=number(basic+FIELDS['edits']);name,shift=KEYS[char]
       key(name,shift=shift);reach('dw($%x)!=%d'%(basic+FIELDS['edits'],edits))
      reach('dw($%x)=%d'%(d+20,len(value)))
      require(observed()==value.encode(),'Physical source bytes')
     def cells():
      unit=number(job+JOB['unit'],4);require(unit,'No owned output console')
      entry=storage['WINDOWS']+con['WINDOWS_ITEMS']+(unit&3)*con['WINDOW_SIZE']
      require(number(entry+con['WINDOW_UNIT'],4)==unit,'Stale console incarnation')
      return read_cells(bridge.memdump,number(entry+con['WINDOW_INSTANCE'],3))
     def contains(value):
      for _ in range(1200):
       raw=cells()
       if value in raw:return raw
       frames()
      raise RuntimeError('Output missing '+repr(value)+'; '+repr(raw))
     def action(row):
      # Program title follows File/Edit/Navigate in the application menu.
      select('FastBasic');click(344,6);click(360,16+row*11);frames(20)
     def terminal(previous,label):
      reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job+JOB['phase'],job+JOB['job'],job+JOB['job'],previous))
      frames(4)
      report['cases'].append(dict(name=f'{cycle}-{label}',status='pass',job=number(job+JOB['job'],4),cause=number(job+JOB['cause'],4)))
      print('Workbench terminal',label,'cause',number(job+JOB['cause'],4),flush=True)
     def run_source(value,variant):
      replace(value);caret=number(basic+FIELDS['caret'],4);anchor=number(basic+FIELDS['anchor'],4)
      viewport=(number(basic+FIELDS['first']),number(basic+FIELDS['left']))
      previous=number(job+JOB['job'],4)
      key('RETURN',ctrl=True)
      states=[]
      while number(job+JOB['phase']):
       phase=number(job+JOB['phase']);states.append(phase)
       reach('dw($%x)!=%d'%(job+JOB['phase'],phase))
      report.setdefault('states',[]).append(states)
      terminal(previous,variant+'-unsaved-run')
      require(number(job+JOB['cause'],4)==0,'Unsuccessful '+variant+' Run')
      require(observed()==value.encode(),'Run changed source')
      require((number(basic+FIELDS['caret'],4),number(basic+FIELDS['anchor'],4))==(caret,anchor),'Run moved caret/selection')
      require((number(basic+FIELDS['first']),number(basic+FIELDS['left']))==viewport,'Run moved viewport')
      report.setdefault('transcripts',[]).append(cells().decode('ascii','replace'))
     def context():
      for i in range(4):
       c=number(foreign['symbols']['contexts']+4*i,4)
       if c and number(c+layout()['Request']['fields']['global']+4)==number(basic):return c
      raise RuntimeError('No BASIC AES context')
     def dialog(choice):
      where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
      tree=number(number(where,4),4);obj=tree+(choice+6)*24
      click(number(tree+16)+number(obj+16)+number(obj+20)//2,number(tree+18)+number(obj+18)+8)
     def choose(path,leaf):
      where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(20)
      form=number(where,4);selector=number(form+FORM_SELECTOR,4);require(selector,'Missing selector')
      def field(index,offset,value):
       obj=selector+index*24;click(number(selector+16)+number(obj+16)+12,number(selector+18)+number(obj+18)+8)
       old=bridge.memdump(selector+offset,128 if index==3 else 13).split(b'\0')[0]
       for _ in old:key('BACKSPACE')
       text(value)
      field(3,S['path'],path);key('RETURN');frames(20)
      field(5,S['file'],leaf);key('RETURN')
     def saved():
      reach('(dw($%x)=dw($%x))&(dw($%x)=0)'%(d+32,d+36,basic+FIELDS['dirty']));frames(10)
      where=basic+1495
      reach('(dw($%x)=$6f53)&(dw($%x)=$7320)&(dw($%x)=$6465)'%(where,where+6,where+10))
     if scenario is not None:
      scenario(dict(locals(),output=out));continue
     run_source('PRINT "FLOAT": PRINT 1.25*2.0','fp');contains(b'FLOAT');contains(b'2.5')
     replace('PRINT "DECIMAL": INPUT A%: PRINT A%*2')
     previous=number(job+JOB['job'],4);key('RETURN',ctrl=True)
     reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));contains(b'DECIMAL');select('FastBasic output')
     text('1.25');key('RETURN');terminal(previous,'decimal-input')
     require(number(job+JOB['cause'],4)==0,'Decimal INPUT failed');contains(b'2.5')
     action(4)
     run_source('PRINT "INTEGER": PRINT 7*6','integer');contains(b'INTEGER');contains(b'42')
     replace('PRINT 1\n???');previous=number(job+JOB['job'],4);key('RETURN',ctrl=True,shift=True);terminal(previous,'syntax-check')
     require(number(job+JOB['cause'],4)==306,'Syntax cause')
     require(number(basic+FIELDS['caret'],4)==9,'Diagnostic did not select exact second-line byte')
     replace('PROC A\n???\nENDPROC');frames(30)
     click(272,6);click(260,38);frames(25)
     from workbench_pixels import picture
     report['cases'].append(picture(out,bridge,number,frames,move,basic,b'PROC A\n???\nENDPROC',f'{cycle}-folded-diagnostic-source',[(0,0,4,4)],visible=[0]))
     previous=number(job+JOB['job'],4);key('RETURN',ctrl=True,shift=True);terminal(previous,'folded-syntax-check')
     require(number(job+JOB['cause'],4)==306 and number(basic+FIELDS['caret'],4)==8,'Folded diagnostic location')
     report['cases'].append(picture(out,bridge,number,frames,move,basic,b'PROC A\n???\nENDPROC',f'{cycle}-revealed-diagnostic',[(0,0,4,4),(2,0,7,4)]))
     replace('PRINT "FIXED"');previous=number(job+JOB['job'],4);key('RETURN',ctrl=True,shift=True);terminal(previous,'fixed-check')
     require(number(job+JOB['cause'],4)==0,'Fixed Check failed')
     replace('PRINT "NUMBER": INPUT N: PRINT N: PRINT "GET": GET K: PRINT K: PRINT "KEY": REPEAT: UNTIL KEY(): GET K: PRINT K')
     previous=number(job+JOB['job'],4);key('RETURN',ctrl=True)
     reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));contains(b'NUMBER');select('FastBasic output')
     key('4');key('2');key('RETURN');contains(b'GET');key('K');contains(b'KEY');key('Q');terminal(previous,'interactive-run')
     require(number(job+JOB['cause'],4)==0,'Interactive Run failed')
     raw=cells();require(b'? 42' in raw and b'107' in raw and b'113' in raw,'INPUT/GET/KEY transcript')
     report.setdefault('transcripts',[]).append(raw.decode('ascii','replace'))
     replace('DO: LOOP');previous=number(job+JOB['job'],4);key('RETURN',ctrl=True)
     reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));select('FastBasic')
     first=bridge.eval_expr('@frame');key('K',ctrl=True);terminal(previous,'busy-stop')
     report.setdefault('stop_frames',[]).append(bridge.eval_expr('@frame')-first)
     require(number(job+JOB['cause'],4)==304,'Stop cause')
     replace('PRINT "WAIT": INPUT N: OPEN #1,4,0,"REL.TXT": INPUT #1,S$: CLOSE #1: PRINT S$')
     key('W',ctrl=True);choose('RAM:PROJECT/*.BAS','REL.BAS');saved()
     previous=number(job+JOB['job'],4);key('RETURN',ctrl=True)
     reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));contains(b'WAIT')
     select('FastBasic');key('W',ctrl=True);choose('RAM:OTHER/*.BAS','AFTER.BAS');saved()
     select('FastBasic output');key('0');key('RETURN');terminal(previous,'captured-project-directory')
     require(number(job+JOB['cause'],4)==0,'Relative file failed');contains(b'PROJECTVALUE')
     replace('PRINT "STANDALONE"');previous=number(job+JOB['job'],4);key('B',ctrl=True)
     choose('RAM:*.COM','RELEASE.COM');terminal(previous,'standalone-build')
     require(number(job+JOB['cause'],4)==0,'Build failed')
     require(observed()==b'PRINT "STANDALONE"','Build changed source')
     select('FastBasic');key('Q',ctrl=True)
     # Source is deliberately unsaved; Discard follows exact child retirement.
     dialog(2)
    bridge.bp_clear_all()
   try:report['runtime'],_=execute(bridge,p,before_run=before,timeout=120,frame_limit=6000)
   finally:
    report['root']={n:data(bridge,p['image'],n,True) for n in ('checks','stage','cycle','primary','secondary')}
    report['stack_usage']=stack_usage(bridge,p['build']['memory'])
    if 'runtime' not in report and current:
     report['controller_trace']={n:number(current['base']+address-(app['abi']['link_bank']<<16),4) for n,address in app['image']['symbols'].items() if (n.startswith('BuildProbe') and n!='BuildProbeSpec') or n.startswith('Workbench') or n in ('FixtureHeld','FixtureCompleted','FixtureRecovered','FixtureReady','FixtureFinished','FixtureChecks','FixtureMaxTurnTicks','FixtureRecoveryShown')}
     if 'BuildProbeSpec' in app['image']['symbols']:
      report['start_spec']=bridge.memdump(current['base']+app['image']['symbols']['BuildProbeSpec']-(app['abi']['link_bank']<<16),24).hex()
      report['arguments']=bridge.memdump(current['job']+JOB['source']+51,80).split(b'\0')[0].decode('ascii','replace')
     report['compiler_result']=bridge.memdump(current['job']+JOB['compilerResult'],8).hex()
     report['program_result']=bridge.memdump(current['job']+JOB['programResult'],8).hex()
     report['diagnostic']=bridge.memdump(current['job']+JOB['diagnostic'],224).hex()
     report['status_text']=bridge.memdump(current['basic']+1495,81).split(b'\0')[0].decode('ascii','replace')
     report['scratch']={n:bridge.memdump(current['job']+JOB['source']+17*i,17).split(b'\0')[0].decode('ascii','replace') for i,n in enumerate(('source','command','diagnostics'))}
     report['snapshot']={n:number(current['job']+offset,4 if n in ('job','child','unit','cause') else 2) for n,offset in JOB.items() if n in ('phase','job','child','unit','window','cause')}
     report['editor']=dict(caret=number(current['basic']+FIELDS['caret'],4),bytes=number(current['basic']+FIELDS['document']+20,4))
     bridge.screenshot(str(out/'failure.png'))
   ownership(bridge,p,p['output']);report['stack_usage']=stack_usage(bridge,p['build']['memory'])
  report['status']='pass'
 except Exception as e:report.update(status='fail',error=str(e));raise
 finally:(out/'results.json').write_text(json.dumps(report,indent=2)+'\n')
 return report
