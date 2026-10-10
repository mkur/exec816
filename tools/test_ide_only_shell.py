"""IDE-only shell startup, assigns and command admission through emitted code."""
import argparse,json
from pathlib import Path
from native_program import ROOT,compiler,require
from make_data_disk import make
from build_ide_media import write
from test_ideplus import PIN,ide_emulator
from test_shell_core import run
from test_shell_startup_scripts import Startup

class IDEStartup(Startup):
    system_mount='SYSTEM'
    sio_enabled=False
    mount_primary=False
    capture_only=True
    def __init__(self):
        super().__init__('normal','sdfs',{})
        self.mounts=[dict(alias='SYSTEM',device='ideplus.device',unit=1,profile=0,
                          sectors=1440,sector_bytes=512,format=2),
                     dict(alias='WORK',device='ideplus.device',unit=2,profile=0,
                          sectors=1440,sector_bytes=512,format=2,access='readwrite')]
    def instrument(self,out):
        super().instrument(out)
        p=out/'shell_core.act';s=p.read_text().replace('USE FSBOOT','USE FSBOOT\nUSE IDEPLUSDRIVER',1)
        s=s.replace('  Check(FSBOOT.Stop()<>0 AND EXEC.AvailMem(0)=before)',
            '  Check(FSBOOT.Stop()<>0)\n  IDEPLUSDRIVER.Stop()\n  Check(EXEC.AvailMem(0)=before)')
        p.write_text(s)
    def prepare(self,t,out,mode,size):
        super().prepare(t,out,mode,size)
        self.files=make(out/'volume.atr',out/'files',binary_names={'C/'+name for name in self.commands},
                        sector_bytes=512,sectors=1440)
        make(out/'work.atr',out/'workspace',sector_bytes=512,sectors=1440)
        self.mapping=write(out/'ideplus.img',out/'volume.atr',out/'work.atr')
        self.directory=b'SYSTEM:SUB\n'
        self.assigns=b'C: -> SYSTEM:C\nS: -> SYSTEM:S\n'
    def environment(self,out):return ide_emulator(out,out/'ideplus.img',writable=True)
    def mount_extra(self,b,out):pass
    def startup_output(self,p):
        s=p['build']['exec_build']['strings']
        return ('\n'+s['banner']+s['slots']+s['stackChecks']+'console.device: ready\n'+s['mountStart']+
                s['systemReady']+': ready, read-only'+s['otherMountsReady']+'\n\n').encode()+self.output
    def exercise(self,c):
        c.command('DEVICES',b'DEVICE          STATE\nconsole.device  ready\ntimer.device    ready\nideplus.device  ready\n')
        c.command('ASSIGN',self.assigns)
        c.command('CD',self.directory)
        c.command('PATH',b'Current directory\nC:\n')
        c.command('C:HELLO',b'Hello from disk!\n')
        c.command('ECHO recovered',b'recovered\n')
        c.check_screen('ide-startup')

if __name__=='__main__':
    a=argparse.ArgumentParser();a.add_argument('--reuse',action='store_true');a.add_argument('--output',type=Path,default=ROOT/'build/development/ide-only/id2');v=a.parse_args()
    r=run(compiler(ROOT/'build/actionc',release=True),v.output,'opt',size=512,external=IDEStartup(),
          pin=PIN,bridge_build=ROOT/'build/mouse-bridge',reuse=v.reuse)
    (v.output/'results.json').write_text(json.dumps(r,indent=2)+'\n')
    print('IDE-only shell startup passed',flush=True)
