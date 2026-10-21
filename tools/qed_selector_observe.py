"""Physical checks of QED's adapter over the real native file selector."""
import json,struct
from native_program import ROOT,require
from qed_editing_observe import Editor
from generate_aes_server import ABI,layout,expected_layout
from file_selector_model import FORM_SELECTOR,FIELDS as F
from desktop_mouse import schedule

class SelectorProbe(Editor):
    def __init__(self,b,p,app,record,owner):
        self.b,self.p,self.app,self.record,self.owner=b,p,app,record,owner
        delta=owner['image_base']-(app['abi']['link_bank']<<16)
        self.sy={n:v+delta for n,v in app['image']['symbols'].items()}
        self.provider=json.loads((p['output'].parent/'c-image.json').read_text())['symbols']
        self.task=owner['record']+next(f[2] for f in json.loads((ROOT/'abi/process.json').read_text())['record'] if f[0]=='task')
        self.owner_offset=layout()['Request']['fields']['owner']
        self.contexts=lambda:[self.get(self.provider['contexts']+i*4,4) for i in range(ABI['constants']['CONTEXTS'])]
    def selector(self):return self.get(self.form()+FORM_SELECTOR,4)
    def phase(self,n):
        print('QED selector phase',n,flush=True)
        self.reach('dw($%x)=%d'%(self.sy['QedSelectorPhase'],n))
        c=self.context()+dict(expected_layout())['C context form']
        self.reach('(dw($%x)!=0)|(dw($%x)!=0)'%(c,c+2))
        at=self.form()+FORM_SELECTOR
        self.reach('(dw($%x)!=0)|(dw($%x)!=0)'%(at,at+2))
        self.reach('dw($%x)=1'%(self.selector()+F['valid']));self.frames(20)
    def key(self,name,shift=False):
        if shift:self.b._cmd_ok('KEY SHIFT down')
        self.b._cmd_ok('KEY '+name+' down');self.frames(3);self.b._cmd_ok('KEY '+name+' up')
        if shift:self.b._cmd_ok('KEY SHIFT up')
        self.frames(15)
    def xy(self,index):
        at=self.selector();root=struct.unpack('<hhhHHHI4h',self.b.memdump(at,24))
        obj=struct.unpack('<hhhHHHI4h',self.b.memdump(at+24*index,24))
        return root[7]+obj[7]+obj[9]//2,root[8]+obj[8]+obj[10]//2

def interact(b,p,app,record,owner):
    s=SelectorProbe(b,p,app,record,owner);b._cmd_ok('MOUSE ST');b._cmd_ok('KEY ALL up')
    s.phase(1);s.click(*s.xy(5))
    for key in ('D','A','T','A','PERIOD','T','X','T'):s.key(key,shift=key!='PERIOD')
    require(s.b.memdump(s.selector()+F['file'],13).split(b'\0')[0]==b'DATA.TXT','Selector filename edit')
    s.key('RETURN');s.phase(2);s.key('ESC');s.phase(3)
    s.move(100,29);s.b._cmd_ok('MOUSE AT 2000 0 0 1');s.frames(15)
    s.move(108,29);s.b._cmd_ok('MOUSE AT 2000 0 0 0');s.frames(20)
    s.phase(4);s.key('ESC')
    record.setdefault('qed_selector',[]).append(dict(identity=owner['identity'],
        executed=['accepted native selection','Escape cancellation','move interruption',
                  'exact deferred WM_MOVED consumed once','selector reuse after interruption']))
