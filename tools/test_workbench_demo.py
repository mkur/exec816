#!/usr/bin/env python3
"""Physical WB9 walkthrough of a clean extraction of the final boot ZIP."""
import argparse,hashlib,json,shutil,zipfile
from pathlib import Path
from types import SimpleNamespace
from native_program import ROOT,require,sha256
from test_demo import run
from test_shell_core import KEYS
from shell_session_walkthrough import Sessions
from console_model import read_cells
from workbench_interaction import FIELDS
from basic_build_model import FIELDS as JOB,STAGES


class Workbench(Sessions):
 def exercise(self,s):
  from desktop_mouse import schedule
  from desktop_menu_check import Menus
  from gem_applications import instances
  from generate_console import constants
  from generate_aes_server import expected_layout,layout
  from file_selector_model import FIELDS as SELECTOR,FORM_SELECTOR
  self.prepare(s);b=s.b;number=s.number;frames=s.frames;reach=s.rendezvous
  KEYS.update({'%':('5',True),'$':('4',True),'#':('3',True),',':('COMMA',False),'(':('9',True),')':('0',True)})
  at=lambda module,name:next(d['address'] for d in s.p['image']['data'] if '_'+module+'_'+name.upper()+'_' in d['name'])
  def move(x,y):
   old=[number(at('DESKINPUT',name),2) for name in ('cursorX','cursorY')]
   x,y=schedule(b,s.p,old,(x,y));reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('DESKINPUT','cursorX'),x,at('DESKINPUT','cursorY'),y));frames(2)
  def click(x,y):
   move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');frames(8);b._cmd_ok('MOUSE AT 2000 0 0 0');frames(12)
  def key(name,ctrl=False,shift=False):
   if ctrl:b._cmd_ok('KEY CTRL down')
   if shift:b._cmd_ok('KEY SHIFT down')
   require(b._cmd_ok('KEY '+name+' down')['raw_scan'],'Physical key required');frames(4);b._cmd_ok('KEY '+name+' up')
   if shift:b._cmd_ok('KEY SHIFT up')
   if ctrl:b._cmd_ok('KEY CTRL up')
   frames(4)
  def text(value):
   for char in value:
    name,shift=KEYS[char];key(name,shift=shift)
  menus=Menus(SimpleNamespace(p=s.p,b=b,number=number,frames=frames,rendezvous=reach,saved={'desktop_menu':{}}),click,move)
  def select(title):
   windows=menus.windows();row=next(i for i,w in enumerate(windows) if w['title']==title);target=windows[row]['id']
   if menus.focus()!=target:
    click(600,8);click(472,16+row*11);reach('dw($%x)=%d'%(menus.focus_address,target))
   frames(30)
  def cli(value,expected=None):
   select('Shell');previous=s.begin(value);s.ready(previous);s.result()
   raw=read_cells(s.far,s.saved['top'])
   if expected is not None:require(expected in raw,'Missing shell output: '+value)
   self.commands.append(dict(command=value,status=0));print('Packaged shell',value,flush=True);return raw
  live=s.p['build']['task_storage']['LIVE'];require(number(live,1)==6,'Changed standard desktop startup')
  cli('RUN C:BASIC.APP')
  found=next(item for item in instances(b,s.p,self.bundle/'bitmap-console') if item['name']=='basic')
  basic=found['symbols']['Basic'];job=found['symbols']['b'];d=basic+FIELDS['document']
  require(any(item['name']=='desktop' for item in instances(b,s.p,self.bundle/'bitmap-console')),'Desktop did not coexist with BASIC')
  reach('dw($%x)=1'%(basic+FIELDS['ready']));require(number(live,1)==7,'BASIC Task count')
  app=json.loads((self.bundle/'bitmap-console/apps/basic/app.json').read_text())
  foreign=json.loads((self.bundle/'bitmap-console/c-image.json').read_text());con=constants();storage=s.p['build']['memory']['console_storage']
  def source():
   pointer=number(d,4);gap=number(d+12,4);end=number(d+16,4)
   return s.far(pointer,gap)+s.far(pointer+end,32768-end)
  def replace(value):
   select('FastBasic');key('A',ctrl=True)
   reach('(dw($%x)=0)&(dw($%x)=%d)'%(basic+FIELDS['anchor'],basic+FIELDS['caret'],number(d+20,4)))
   reach('dw($%x)=0'%(basic+FIELDS['dirty']));frames(4)
   for char in value:
    edits=number(basic+FIELDS['edits'],2);name,shift=KEYS[char];key(name,shift=shift)
    reach('dw($%x)!=%d'%(basic+FIELDS['edits'],edits))
   require(source()==value.encode(),'Packaged source bytes differ')
  def output():
   unit=number(job+JOB['unit'],4);entry=storage['WINDOWS']+con['WINDOWS_ITEMS']+(unit&3)*con['WINDOW_SIZE']
   require(number(entry+con['WINDOW_UNIT'],4)==unit,'Stale output identity')
   return read_cells(s.far,number(entry+con['WINDOW_INSTANCE'],3))
  def contains(value):
   for _ in range(1200):
    raw=output()
    if value in raw:return raw
    frames()
   raise RuntimeError('Missing packaged output '+repr(value))
  def terminal(previous,cause=0):
   reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job+JOB['phase'],job+JOB['job'],job+JOB['job'],previous));frames(4)
   require(number(job+JOB['cause'],4)==cause,'Packaged job cause')
   self.commands.append(dict(job=number(job+JOB['job'],4),cause=cause));print('Packaged job',self.commands[-1],flush=True)
  def start(value,check=False):
   replace(value);previous=number(job+JOB['job'],4);key('RETURN',ctrl=True,shift=check);return previous
  def context():
   return next(number(foreign['symbols']['contexts']+4*i,4) for i in range(4)
    if number(foreign['symbols']['contexts']+4*i,4) and number(number(foreign['symbols']['contexts']+4*i,4)+layout()['Request']['fields']['global']+4,2)==number(basic,2))
  def choose(path,leaf):
   where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(20)
   selector=number(number(where,4)+FORM_SELECTOR,4);require(selector,'Missing packaged selector')
   def field(index,offset,value):
    obj=selector+index*24;click(number(selector+16,2)+number(obj+16,2)+12,number(selector+18,2)+number(obj+18,2)+8)
    old=s.far(selector+offset,128 if index==3 else 13).split(b'\0')[0]
    for _ in old:key('BACKSPACE')
    text(value)
   field(3,SELECTOR['path'],path);key('RETURN');frames(20);field(5,SELECTOR['file'],leaf);key('RETURN')
  select('FastBasic');key('O',ctrl=True);choose('WORK:*.BAS','HELLO.BAS')
  original=(ROOT/'examples/fastbasic/HELLO.BAS').read_bytes().replace(b'\r\n',b'\n').replace(b'\x9b',b'\n')
  reach('dw($%x)=%d'%(d+20,len(original)));frames(8)
  require(source()==original,'Packaged Open source bytes differ')
  self.commands.append(dict(open='WORK:HELLO.BAS',bytes=len(original)))
  previous=start('PRINT 1.25*2.0');terminal(previous);contains(b'2.5')
  require(number(basic+FIELDS['caret'],4)==14,'Packaged Run moved caret')
  previous=start('PRINT 1\n???',True);terminal(previous,306);require(number(basic+FIELDS['caret'],4)==9,'Packaged diagnostic location')
  previous=start('PRINT "FRESH"');terminal(previous);contains(b'FRESH')
  previous=start('PRINT "DECIMAL": INPUT A%: PRINT A%*2: GET K: PRINT K: REPEAT: UNTIL KEY(): GET K: PRINT K')
  reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));require(number(live,1)==8,'Sequential child Task count');contains(b'DECIMAL');select('FastBasic output')
  text('1.25');key('RETURN');contains(b'2.5');key('K');contains(b'107');key('Q');terminal(previous);contains(b'113')
  previous=start('DO: LOOP');reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));select('FastBasic');key('K',ctrl=True);terminal(previous,304)
  previous=start('INPUT A%');reach('dw($%x)=%d'%(job+JOB['phase'],STAGES['program']));select('FastBasic output');menus.close();terminal(previous,304)
  replace('PRINT "PACKAGED": PRINT 7*6');key('W',ctrl=True);choose('WORK:*.BAS','DEMO.BAS')
  where=basic+1495;reach('(dw($%x)=$6f53)&(dw($%x)=$7320)&(dw($%x)=$6465)'%(where,where+6,where+10))
  replace('PRINT "RELEASE": PRINT 42');previous=number(job+JOB['job'],4);key('B',ctrl=True);choose('WORK:*.COM','RELEASE.COM');terminal(previous)
  require(number(d+32,4)!=number(d+36,4),'Build marked unsaved source saved')
  select('FastBasic');key('Q',ctrl=True)
  where=context()+dict(expected_layout())['C context form'];reach('(dw($%x)|dw($%x))!=0'%(where,where+2));frames(15)
  tree=number(number(where,4),4);obj=tree+8*24;click(number(tree+16,2)+number(obj+16,2)+number(obj+20,2)//2,number(tree+18,2)+number(obj+18,2)+8)
  reach('db($%x)=6'%live)
  cli('JOBS');cli('WORK:RELEASE.COM',b'RELEASE');cli('ARC',b'filename is given.')
  cli('ECHO abc >WORK:ABC.TXT');cli('CD WORK:');self.md5=cli('MD5 ABC.TXT',b'MD5 (ABC.TXT)').decode('ascii','replace')
  cli('C:HELLO',b'Hello from disk!')
  s.saved['integration']=dict(workbench=True,application_sha256=app['sha256'],commands=self.commands,normal_desktop_preserved=True)
  s.save_screen(self.bundle/'workbench.png')
  s.save_screen(self.bundle/'boot-smoke.png')
  select('Shell')
  for char in 'EXIT':s.press(char)
  b._cmd_ok('KEY RETURN down');b.bp_clear_all()


def check(bundle,archive):
 from sdfs_reference import extract
 extracted=bundle/'workbench-extracted'
 if extracted.exists():shutil.rmtree(extracted)
 with zipfile.ZipFile(archive) as z:
  names=set(z.namelist());checks=z.read('exec816-demo/SHA256SUMS').decode().splitlines();verified={'exec816-demo/SHA256SUMS'}
  for line in checks:
   digest,name=line.split('  ',1);member='exec816-demo/'+name
   require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe package member')
   require(hashlib.sha256(z.read(member)).hexdigest()==digest,'Package checksum: '+name);verified.add(member)
  require(verified==names,'Incomplete package checksums');z.extractall(extracted)
 root=extracted/'exec816-demo';session=Workbench(bundle/'workbench',bundle)
 result=run(bundle,boot_smoke=True,distribution_root=root,integration=session)
 readback=bundle/'workbench-readback';extract(bundle/'work-walkthrough.atr',readback)
 require((readback/'DEMO.BAS').read_bytes()==b'PRINT "PACKAGED": PRINT 7*6','Packaged saved source bytes')
 require(hashlib.md5((readback/'ABC.TXT').read_bytes()).hexdigest() in session.md5.lower(),'Packaged MD5 digest')
 from build_fastbasic import profile
 release=readback/'RELEASE.COM';record=dict(status='pass',tier='development',qualification=False,
  zip_sha256=sha256(archive),release_sha256=sha256(release),profile=profile(release.read_bytes()),result=result)
 (bundle/'workbench-checks.json').write_text(json.dumps(record,indent=2)+'\n')
 return record


if __name__=='__main__':
 a=argparse.ArgumentParser(description=__doc__);a.add_argument('--bundle',type=Path,required=True);a.add_argument('--archive',type=Path,required=True);args=a.parse_args();check(args.bundle.resolve(),args.archive.resolve())
