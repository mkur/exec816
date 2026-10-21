#!/usr/bin/env python3
"""Real WB9 controller with fixture-only phase holds and physical Stop/Quit."""
import argparse,json,re
from pathlib import Path
from native_program import ROOT,require,sha256
import test_fastbasic_build


def prepare(out,provider,app_only=False,scope='all'):
 import build_c_program
 out.mkdir(parents=True,exist_ok=True)
 from build_command import compile_command
 from native_program import compiler
 hold=out/'hold.act';hold.write_text('MODULE HOLD\nUSE COMMAND\nLONGINT FUNC Main()\n\n  WHILE COMMAND.BreakPending()=0 DO\n    COMMAND.Yield()\n  OD\n  COMMAND.SetIoErr(COMMAND.ERROR_BREAK)\n\nRETURN(COMMAND.RETURN_ERROR)\nENDMODULE\n')
 compile_command(compiler(ROOT/'build/actionc',release=True),hold,out/'native/HOLD',True)
 source=ROOT/'examples/gem-basic/build.c';text=source.read_text()
 text=re.sub(r'#include "([^"]+)"',lambda m:'#include "'+str((source.parent/m[1]).resolve())+'"',text)
 text=text.replace('static struct BasicBuildJob b;','struct BasicBuildJob b;')
 text=text.replace('static struct BasicFileJob publication;','struct BasicFileJob publication;')
 text=text.replace('void BasicBuildStep(', 'void FixtureActualStep(')
 text=text.replace('fsel_exinput(', 'FixtureSelect(')
 text='WORD FixtureSelect(char *,char *,WORD *,const char *);\n'+text
 # Prototype follows the Exec types, rather than assuming host C widths.
 text=text.replace('WORD FixtureSelect(char *,char *,WORD *,const char *);\n','')
 text=text.replace('enum { CHOOSE=', 'WORD FixtureSelect(char *,char *,WORD *,const char *);\nLONG FixtureDelete(const char *);\nenum { CHOOSE=')
 text=text.replace('DeleteFile(', 'FixtureDelete(')
 controller=out/'controller-fixture.c';controller.write_text(text)
 main_source=ROOT/'examples/gem-basic/main.c'
 main_text=main_source.read_text().replace('#include "editor.h"','#include "'+str(main_source.parent/'editor.h')+'"\nvoid FixtureCleanup(void);')
 main_text=main_text.replace('    BasicDocumentDispose(', '    FixtureCleanup();\n    BasicDocumentDispose(')
 main=out/'main-fixture.c';main.write_text(main_text)
 first,limit={'all':(0,24),'stop':(0,11),'quit':(11,24)}[scope]
 cases_source=ROOT/'tests/programs/basic_build_cancel.c';cases_text=cases_source.read_text()
 cases_text=re.sub(r'#include "([^"]+)"',lambda m:'#include "'+str((cases_source.parent/m[1]).resolve())+'"',cases_text)
 cases=out/'cases-fixture.c';cases.write_text(f'#define FIXTURE_FIRST {first}\n#define FIXTURE_LIMIT {limit}\n'+cases_text)
 (out/'fixture-scope.json').write_text(json.dumps(dict(first=first,limit=limit,scope=scope))+'\n')
 original=build_c_program.build
 def application(output,sources,**kwargs):
  return original(output,[controller if p==source else main if p==main_source else p for p in sources]+[cases],**kwargs)
 build_c_program.build=application
 control=out/'fbcancelcontrol.act'
 control.write_text('MODULE FBCANCELCONTROL\nPUBLIC BYTE holding\nENDMODULE\n')
 service=(ROOT/'lib/dos/fbservice.act').read_text().replace('USE EXEC\n','USE EXEC\nUSE FBCANCELCONTROL\n')
 service=service.replace('  BYTE mode\n','  BYTE mode\n  CARD fixtureWrites\n')
 service=service.replace('  result=0\n','  fixtureWrites=0\n  result=0\n')
 service=service.replace('      ; The bridge has retired the guest activation before this checkpoint.', '''      ; Fixture holds only after guest activation has retired.
      IF (state.diagnosticJob & $ff)=128
          AND SDXSTATE.ReadWord(state.guest.bank,state.diagnostic)=2 THEN
        FBCANCELCONTROL.holding=128
        WHILE DOS.BreakPending()=0 DO
          EXEC.Yield()
        OD
        FBCANCELCONTROL.holding=0
        cause=DOS.ERROR_BREAK
      FI''')
 service=service.replace('      FBFILES.Call(state,frame)', '''      IF (state.diagnosticJob & $ff)=240
          AND SDXSTATE.ReadWord(state.guest.bank,state.diagnostic)=3
          AND state.guest.bank(832+CARD(frame(SDXABI.FRAME_X))+2)=11 THEN
        fixtureWrites==+1
        IF fixtureWrites=2 THEN
          FBCANCELCONTROL.holding=240
          WHILE DOS.BreakPending()=0 DO
            EXEC.Yield()
          OD
          FBCANCELCONTROL.holding=0
          cause=DOS.ERROR_BREAK
        FI
      FI
      IF cause=0 THEN
        FBFILES.Call(state,frame)
      FI''')
 (out/'fbservice.act').write_text(service)
 try:test_fastbasic_build.prepare(out,provider,app_only,fixture=ROOT/'tests/programs/basic_build_cancel.act',extra_media={'C/HOLD':(out/'native/HOLD').read_bytes()},minimum_stack=1312)
 finally:build_c_program.build=original
 (out/'fixture-overrides.json').write_text(json.dumps({str(p.relative_to(ROOT)):sha256(p) for p in (controller,main,cases,control,out/'fbservice.act',hold,ROOT/'tests/programs/basic_build_cancel.c',ROOT/'tests/programs/basic_build_cancel.act')},indent=2)+'\n')


def replay(v):
 b=v['bridge'];app=v['app'] if 'app' in v else json.loads((v['out']/'app/app.json').read_text())
 base=v['base'];origin=app['abi']['link_bank']<<16
 field=lambda name:base+app['image']['symbols'][name]-origin
 number,reach,key,frames,select=[v[n] for n in ('number','reach','key','frames','select')]
 scope=json.loads((v['output']/'fixture-scope.json').read_text())
 first,limit=scope['first'],scope['limit']
 v['report']['fixture_overrides']=json.loads((v['output']/'fixture-overrides.json').read_text())
 def wait(name,value):
  a=field(name);checks=field('FixtureChecks')
  reach('((dw($%x)=%d)&(dw($%x)=0))|(dw($%x)>=$fff0)'%(a,value,a+2,checks))
  require(number(checks,4)<0xfff0,'Cancellation fixture assertion '+hex(number(checks,4)))
 def dialog(choice):
  from generate_aes_server import layout,expected_layout
  basic=v['basic'];foreign=v['foreign']
  context=next(number(foreign['symbols']['contexts']+4*i,4) for i in range(4)
    if number(foreign['symbols']['contexts']+4*i,4) and
    number(number(foreign['symbols']['contexts']+4*i,4)+layout()['Request']['fields']['global']+4)==number(basic))
  where=context+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
  tree=number(number(where,4),4);obj=tree+(choice+6)*24
  v['click'](number(tree+16)+number(obj+16)+number(obj+20)//2,number(tree+18)+number(obj+18)+8)
 if v['cycle']:
  wait('FixtureHeld',first+1);select('FastBasic');key('K',ctrl=True)
  wait('FixtureCompleted',first+1);wait('FixtureReady',first+1);key('RETURN',ctrl=True);wait('FixtureRecovered',first+1)
  wait('FixtureHeld',first+2);select('FastBasic');key('Q',ctrl=True)
  reach('dw($%x)=0'%v['job']);dialog(2)
  v['report']['cases'].append(dict(name='warm-reload-stop-run-quit',status='pass'))
  return
 for index in range(first,min(limit,22)):
  wait('FixtureHeld',index+1)
  target=(4,5,7,8,8,10,11,11,14,12,13)[index%11]
  if index%11 in (3,4):
   address=v['at']('FBCANCELCONTROL','holding');reach('db($%x)=%d'%(address,128 if index%11==3 else 240))
  if index%11==7:
   # Wait for the actual blocking cooked read, then close or Stop it physically.
   v['contains'](b'INPUT')
   frames(20)
  select('FastBasic');frames(30)
  key('Q' if index>=11 else 'K',ctrl=True)
  if index>=11:
   reach('dw($%x)=0'%v['job']);dialog(3)
  wait('FixtureCompleted',index+1)
  wait('FixtureReady',index+1);key('RETURN',ctrl=True)
  wait('FixtureRecovered',index+1)
  require(number(field('FixtureChecks'),4)<0xfffd,'Fixture assertion')
  v['report']['cases'].append(dict(name='%s-phase-%d'%('Quit' if index>=11 else 'Stop',target),status='pass',fresh_run=True))
  print('Cancellation',v['cycle'],index,target,flush=True)
 if limit==24:
  wait('FixtureCompleted',23);wait('FixtureReady',23);key('RETURN',ctrl=True)
  wait('FixtureRecovered',23)
  v['report']['cases'].append(dict(name='failed-task-admission',status='pass',cause=103,fresh_run=True))
  wait('FixtureCompleted',24);wait('FixtureRecoveryShown',1)
  v['contains'](b'.BAS');wait('FixtureReady',24);select('FastBasic');key('RETURN',ctrl=True)
  wait('FixtureRecovered',24)
  v['report']['cases'].append(dict(name='scratch-cleanup-warning',status='pass',cause=0,warning=205,recovery_path=True,fresh_run=True))
 wait('FixtureFinished',1)
 maximum=number(field('FixtureMaxTurnTicks'),4)
 require(maximum<=120,'Controller turn exceeds WB2 development budget')
 v['report'].setdefault('latencies',[]).append(dict(maximum_controller_turn_ticks=maximum,budget_ticks=120,clock='PAL VBLANK',scope='Instrumented real controller, excluding fixture holds'))
 select('FastBasic');key('Q',ctrl=True);dialog(2)


if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--output',type=Path,required=True);a.add_argument('--provider',type=Path,default=ROOT/'build/fastbasic-workbench/wb9-provider/c-image.json');a.add_argument('--from-build',action='store_true');a.add_argument('--build-only',action='store_true');a.add_argument('--app-only',action='store_true');a.add_argument('--scope',choices=('all','stop','quit'),default='all');args=a.parse_args();out=args.output.resolve()
 if not args.from_build:prepare(out,args.provider.resolve(),args.app_only,args.scope)
 if not args.build_only:
  from workbench_build_interaction import exercise
  exercise(out,replay)
