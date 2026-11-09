#!/usr/bin/env python3
"""Physical GemARC and BASIC walks on the exact extracted demo ZIP."""
import argparse,hashlib,json,shutil,subprocess,zipfile
from pathlib import Path
from native_program import ROOT,require,sha256
from test_demo import run
from test_workbench_demo import Workbench
from test_shell_core import KEYS
from filesystem_audit import Audit


class Archives(Workbench):
 def exercise(self,s):
  from desktop_mouse import schedule
  from desktop_menu_check import Menus
  from gem_applications import instances
  from generate_aes_server import expected_layout,layout
  from file_selector_model import FIELDS as SELECTOR,FORM_SELECTOR,FORM_ALERT
  self.prepare(s);b=s.b;number=s.number;frames=s.frames;reach=s.rendezvous
  at=lambda name:next(d['address'] for d in s.p['image']['data'] if '_DESKINPUT_'+name.upper()+'_' in d['name'])
  def move(x,y):
   old=[number(at(name),2) for name in ('cursorX','cursorY')]
   x,y=schedule(b,s.p,old,(x,y));reach('(dw($%x)=%d)&(dw($%x)=%d)'%(at('cursorX'),x,at('cursorY'),y));frames(3)
  def click(x,y):
   move(x,y);b._cmd_ok('MOUSE AT 2000 0 0 1');frames(12);b._cmd_ok('MOUSE AT 2000 0 0 0');frames(30)
  s.saved['desktop_menu']={};menus=Menus(s,click,move)
  def key(name,ctrl=False,shift=False):
   if ctrl:b._cmd_ok('KEY CTRL down')
   if shift:b._cmd_ok('KEY SHIFT down')
   require(b._cmd_ok('KEY '+name+' down')['raw_scan'],'Physical key required');frames(4);b._cmd_ok('KEY '+name+' up')
   if shift:b._cmd_ok('KEY SHIFT up')
   if ctrl:b._cmd_ok('KEY CTRL up')
   frames(5)
  def text(value):
   for char in value:
    name,shift=KEYS[char];key(name,shift=shift)
  def cli(value):
   menus.select('Shell');old=s.begin(value);s.ready(old);s.result();frames(20)
  directory=self.bundle/'bitmap-console'
  cli('ECHO archive-original >WORK:PORT.TXT')
  cli('COPY C:BASIC.APP WORK:BIG.DAT')
  cli('RUN C:GEMARC.APP "WORK:SAMPLE.ARC"')
  found=next(row for row in instances(b,s.p,directory) if row['name']=='gemarc');sy=found['symbols']
  reach('dw($%x)=2'%sy['nlist']);menus.select('GemARC')
  resident=json.loads((directory/'c-image.json').read_text())['symbols']
  def context():
   return next(value for i in range(4) if (value:=number(resident['contexts']+4*i,4)) and
       number(value+layout()['Request']['fields']['owner'],3)==found['task'])
  def form():return number(context()+dict(expected_layout())['C context form'],4)
  def wait_form(selector=False,alert=False):
   for _ in range(1000):
    value=form()
    if value and (not selector or number(value+FORM_SELECTOR,4)) and (not alert or number(value+FORM_ALERT,4)):return value
    frames(10)
   raise RuntimeError('GemARC did not open expected form')
  def choose(path,leaf):
   current=wait_form(selector=True);frames(25);selector=number(current+FORM_SELECTOR,4)
   def field(index,offset,value):
    obj=selector+index*24;click(number(selector+16,2)+number(obj+16,2)+12,number(selector+18,2)+number(obj+18,2)+8)
    old=s.far(selector+offset,128 if index==3 else 13).split(b'\0')[0]
    for _ in old:key('BACKSPACE')
    text(value)
   field(3,SELECTOR['path'],path);key('RETURN');frames(30);field(5,SELECTOR['file'],leaf);key('RETURN')
  def alert():
   wait_form(alert=True);key('RETURN');frames(30)
  pointer=number(sy['list'],4)
  click(number(sy['wx'],2)+12,number(sy['wy'],2)+number(sy['hchar'],2)+3)
  require(number(pointer+14,1)==1,'Physical member click did not select')
  key('A',ctrl=True);frames(15)
  require(number(pointer+14,1) and number(pointer+33+14,1),'Select All did not select both members')
  key('E',ctrl=True);choose('WORK:*.*','OUT.DAT');alert()
  key('N',ctrl=True);choose('WORK:*.ARC','PORT.ARC');reach('dw($%x)=0'%sy['nlist']);frames(30)
  key('I',ctrl=True);choose('WORK:*.TXT','PORT.TXT');alert();reach('dw($%x)=1'%sy['nlist'])
  key('Q',ctrl=True)
  for _ in range(1000):
   if not any(row['name']=='gemarc' for row in instances(b,s.p,directory)):break
   frames(10)
  else:raise RuntimeError('GemARC did not retire')
  cli('ECHO archive-replacement >WORK:PORT.TXT')
  cli('RUN C:GEMARC.APP WORK:PORT.ARC');found=next(row for row in instances(b,s.p,directory) if row['name']=='gemarc');sy=found['symbols']
  reach('dw($%x)=1'%sy['nlist']);menus.select('GemARC')
  key('I',ctrl=True);choose('WORK:*.TXT','PORT.TXT');alert();reach('dw($%x)=1'%sy['nlist'])
  # Interrupt actual disk work through captured physical input.
  key('I',ctrl=True);choose('WORK:*.DAT','BIG.DAT')
  reach('(dw($%x)!=0)&(db($%x)!=0)'%(sy['working'],sy['recovery']))
  key('ESC');reach('dw($%x)=0'%sy['working']);frames(80)
  require(number(sy['nlist'],2)==1,'Cancelled Add changed the member list')
  # Keep the editor and a computing Process live beside the archive window.
  from qed_demo import mount_editor
  menus.select('Shell');mount_editor(s)
  cli('RUN QED:QED.APP');cli('RUN PRIMES >CON:')
  prime=number(s.at('job'),4);frames(100)
  require(any(row['name']=='gemarc' for row in instances(b,s.p,directory)),'Peer launch lost GemARC')
  menus.select('Untitled');key('Q',ctrl=True);frames(80)
  cli('BREAK '+str(prime));menus.select('GemARC')
  key('I',ctrl=True);choose('WORK:*.DAT','BIG.DAT')
  reach('(dw($%x)!=0)&(db($%x)!=0)'%(sy['working'],sy['recovery']))
  menus.close();frames(100);menus.select('Shell')
  s.saved['gemarc']=dict(physical_selection=True,select_all=True,extraction=True,
      create=True,add=True,replace=True,repeated_launch=True,
      cancel_during_io=True,close_during_io=True,qed_and_computing_coexistence=True)
  print('Packaged GemARC create/add/replace/extract passed',flush=True)
  super().exercise(s)


def check(bundle):
 extracted=bundle/'gemarc-extracted'
 require(not extracted.exists(),'Use a fresh extracted GemARC walkthrough')
 archive=bundle/'exec816-demo.zip'
 with zipfile.ZipFile(archive) as z:
  expected={'exec816-demo/SHA256SUMS'}
  for line in z.read('exec816-demo/SHA256SUMS').decode().splitlines():
   digest,name=line.split('  ',1);member='exec816-demo/'+name
   require(not Path(name).is_absolute() and '..' not in Path(name).parts,'Unsafe package path')
   require(hashlib.sha256(z.read(member)).hexdigest()==digest,'Changed packaged file: '+name);expected.add(member)
  require(expected==set(z.namelist()),'Incomplete package checksum list');z.extractall(extracted)
 session=Archives(bundle/'gemarc-walk',bundle)
 manifest=json.loads((bundle/'demo-manifest.json').read_text());combined=bool(manifest.get('bootable_atr'))
 options={};boot=None
 if combined:
  from test_bootable_atr import DiskBoot
  boot=DiskBoot(bundle);options['bootstrap']=boot
 result=run(bundle,boot_smoke=True,distribution_root=extracted/'exec816-demo',integration=session,**options)
 media=extracted/'exec816-demo'/manifest['media'] if combined else bundle/'work-walkthrough.atr'
 audit=Audit(media.read_bytes());allocation=audit.sdfs()
 files={name.removeprefix('WORK/'):payload for name,payload in audit.files.items() if not combined or name.startswith('WORK/')}
 require(files['DEMO.BAS']==b'PRINT "PACKAGED": PRINT 7*6','BASIC saved source differs')
 require(hashlib.md5(files['ABC.TXT']).hexdigest() in session.md5.lower(),'MD5 persisted-byte oracle differs')
 require(files['EXTRACT.TXT']==b'ARC extraction works through Exec816 SDX.\n','Extracted bytes differ')
 require(files['EMPTY.TXT']==b'','Empty extraction differs')
 target=bundle/'gemarc-readback';target.mkdir(exist_ok=True)
 (target/'PORT.ARC').write_bytes(files['PORT.ARC'])
 subprocess.run([shutil.which('unar'),'-q','-f','-o',str(target),str(target/'PORT.ARC')],check=True)
 members=list(target.rglob('PORT.TXT'));require(len(members)==1 and members[0].read_bytes()==b'archive-replacement\n','Independent new-archive bytes differ')
 result.update(qualification=False,tier='development',zip_sha256=sha256(archive),
     gemarc=session.s.saved['gemarc'],allocation=allocation,atr_boot=boot.report if boot else None,
     scope='Exact extracted ZIP: physical GemARC, BASIC save/run, MD5/ARC, OF816 cold boot and clean EXIT')
 (bundle/'gemarc-demo-results.json').write_text(json.dumps(result,indent=2)+'\n');return result


if __name__=='__main__':
 parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--bundle',type=Path,required=True)
 check(parser.parse_args().bundle.resolve())
