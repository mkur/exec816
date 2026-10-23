#!/usr/bin/env python3
"""Actual OF816 ZIP: shell source commands and unsaved-buffer interpreter UI."""
import argparse
import ast
import json
from pathlib import Path
from basic_build_model import FIELDS as JOB,RESIDENT_FIELDS
from workbench_interaction import FIELDS
from test_twelve_task_demo import TwelveTasks,check
from native_program import require,sha256
from gem_applications import instances
from shell_inspect import address as shell_address
from generate_aes_server import expected_layout,layout
from file_selector_model import FIELDS as SELECTOR,FORM_SELECTOR
from test_shell_core import KEYS

KEYS.update({'(':('9',True),')':('0',True),'$':('4',True),'%':('5',True),'+':('PLUS',False)})


def physical_keys():
    for node in ast.walk(ast.parse(Path(__file__).read_text())):
        if not isinstance(node,ast.Call):continue
        name=node.func.attr if isinstance(node.func,ast.Attribute) else node.func.id if isinstance(node.func,ast.Name) else ''
        if name not in ('start','replace','command','begin','choose','run'):continue
        for value in node.args:
            if isinstance(value,ast.Constant) and isinstance(value.value,str):
                require(all(char in KEYS for char in value.value),'Unmapped physical source key: '+repr(value.value))


class SourceInterpreter(TwelveTasks):
    def prepare(self,s):
        super().prepare(s)
        s.saved.setdefault('desktop_menu',{})
        original_regs,original_bp=s.b.regs,s.b.bp_set
        faults={s.p['labels'][name]:name for name in ('heap_fault','stack_overflow','arithmetic_fault')}
        reset=s.far(s.p['labels']['display_reset_required'],4)
        require(reset[0]==0x5c,'Unexpected display-reset veneer')
        faults[int.from_bytes(reset[1:4],'little')]='display_reset_required'
        def breakpoint(address,*args,**kwargs):
            value=original_bp(address,*args,**kwargs)
            if address==s.p['labels']['native_nmi']:
                for at in faults:original_bp(at,condition='@xpc=$%x'%at)
            return value
        def registers():
            value=original_regs();pc=int(value['PC'].lstrip('$'),16)
            if pc in faults and s.b.eval_expr('@xpc')==pc:
                from stack_budget import stack_usage
                returned=s.b.eval_expr('@ra');low=int(value['S'].lstrip('$'),16)
                candidates=[]
                for slot,pool in enumerate(s.p['build']['memory']['task_pools']):
                    for high in range(pool['stack_base']>>8,((pool['stack_base']+pool['stack_bytes'])>>8)+1):
                        pointer=(high<<8)|low
                        if pool['stack_base']<=pointer<pool['stack_base']+pool['stack_bytes'] and ((s.number(pointer+1,2)+1)&65535)==returned:
                            candidates.append(dict(slot=slot,stack=pointer,reason=s.number(pointer+4,2),caller=(s.number(pointer+3,1)<<16)|returned,bytes=s.far(pointer+1,32).hex()))
                diagnostic=dict(fault=faults[pc],registers=value,frame=s.b.eval_expr('@frame'),
                    native_a=s.b.eval_expr('@a'),return_address=returned,candidates=candidates,
                    stacks=stack_usage(s.b,s.p['build']['memory']))
                registry=shell_address(s.p['image'],'sessions')
                diagnostic['sessions']=[dict(identity=s.number(registry+i*330,4),
                    process=s.number(registry+i*330+318,4),state=s.number(registry+i*330+328,1),
                    close=s.number(registry+i*330+273,1),primary=s.number(registry+i*330+310,4),
                    secondary=s.number(registry+i*330+314,4)) for i in range(2)]
                try:s.b.state_save(str(self.bundle/'source-native-fault.altstate2'))
                except Exception as error:diagnostic['snapshot_error']=str(error)
                (self.bundle/'source-native-fault.json').write_text(json.dumps(diagnostic,indent=2)+'\n')
                raise RuntimeError('Native '+faults[pc]+': '+repr(value))
            return value
        s.b.regs=registers;s.b.bp_set=breakpoint

    def source_shell(self):
        if getattr(self,'diagnose',False):return
        self.command('FB WORK:CALC.BAS',b'3.75')
        self.command('FBI WORK:HELLO.BAS',b'42')
        self.command('FB "WORK:CALC.BAS"',b'3.75')
        self.command('CD WORK:')
        self.command('FBI HELLO.BAS',b'42')
        self.command('FB CALC.BAS',b'3.75')
        self.command('CD SYS:')
        self.command('ECHO 1.25 >RAM:NUM.TXT')
        self.command('FB WORK:DECIMAL.BAS <RAM:NUM.TXT >RAM:FLOAT.TXT')
        self.command('TYPE RAM:FLOAT.TXT',b'2.5')
        self.command('ECHO "GRAPHICS 0" >RAM:BAD.BAS')
        for command,cause in [('FB',115),('FBI',115),('FB WORK:MISSING.BAS',205),
                ('FB WORK:CALC.BAS EXTRA',115),('FB RAM:BAD.BAS',306)]:
            previous=self.s.begin(command);self.s.ready(previous)
            values=tuple(int.from_bytes(self.s.far(self.s.saved['shell']+off,4),'little',signed=True) for off in (32,36))
            require(values==(20,cause),repr((command,values)))
        self.s.saved['source_commands']=True

    def source_checks(self,**c):
        n,job,basic=c['n'],c['job'],c['basic']
        reach,key,frames,menus=c['reach'],c['key'],c['frames'],c['menus']
        app=next(v for v in instances(self.s.b,self.s.p,self.bundle/'bitmap-console') if v['name']=='basic')
        resident=app['symbols']['resident']
        def identity():return (n(resident+RESIDENT_FIELDS['image'],4),n(resident+RESIDENT_FIELDS['child'],4))
        held=identity();require(all(held),'No retained Image/Process')
        def same():require(identity()==held,repr(('Interpreter replaced',held,identity())))
        def contains(text):
            for _ in range(1200):
                if text in c['output']():return
                frames(3)
            raise RuntimeError('Missing retained output '+repr(text))
        def start(text):
            c['replace'](text)
            old=n(job+JOB['job'],4);key('RETURN',ctrl=True)
            return old
        def done(old,cause=0):
            reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],job+JOB['job'],old))
            require(n(job+JOB['cause'],4)==cause,repr(('Run',cause,n(job+JOB['cause'],4))))
            r=job+JOB['interpreterResult']
            require(n(r,2)==2 and n(r+2,2)==128,'Missing version-2 completion')
            require(n(r+4,4)==n(job+JOB['job'],4),'Stale result')
            require(n(job+8,2)==0 and n(job+10,2)==0,'Run reserved scratch')
            same()
        def run(text,answer=None,cause=0):
            old=start(text);done(old,cause)
            if answer:contains(answer)
        def menu(y):
            menus.select('FastBasic');c['click'](344,6);c['click'](360,y);frames(20)
        def form():
            symbols=json.loads((self.bundle/'bitmap-console/c-image.json').read_text())['symbols']
            context=next(v for v in (n(symbols['contexts']+4*i,4) for i in range(4))
                if v and n(v+layout()['Request']['fields']['global']+4,2)==n(basic,2))
            address=context+dict(expected_layout())['C context form']
            reach('(dw($%x)|dw($%x))!=0'%(address,address+2));frames(20)
            return n(n(address,4),4)
        def pending():
            unit=n(job+JOB['unit'],4);a=self.s.console
            windows=self.s.p['build']['memory']['console_storage']['WINDOWS']
            row=windows+a['WINDOWS_ITEMS']+(unit&3)*a['WINDOW_SIZE']
            console=n(row+a['WINDOW_INSTANCE'],3)
            reach('db($%x)=2'%(console+a['INSTANCE_READREADY']))

        # The pinned raw-key bridge has no PLUS alias; subtracting -1 increments.
        run('A=A-(-1):PRINT "COUNT";A',b'COUNT1')
        run('A=A-(-1):PRINT "COUNT";A',b'COUNT2')
        run('PRINT "EDIT";A:S$="STATE":DIM V(2) WORD:V(1)=42',b'EDIT2')
        run('DIM V(2) WORD:PRINT S$:PRINT "ARRAY";V(1)',b'ARRAY42')
        run('A=1:BOGUS',cause=306)
        run('PRINT "ERROR";A',b'ERROR2')
        old=start('A=77:PRINT "BUSY":DO:LOOP');contains(b'BUSY')
        menus.select('FastBasic');key('K',ctrl=True);done(old,304)
        run('PRINT "STOP";A:PRINT S$',b'STOP77')
        print('Retained Process, edits, arrays, parse error and Stop passed',flush=True)

        old=start('A=88:PRINT "RESTARTBUSY":DO:LOOP');contains(b'RESTARTBUSY');menu(82)
        reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],job+JOB['job'],old))
        require(n(job+JOB['cause'],4)==0,'Restart failed');same()
        run('A=A-(-1):PRINT "RESET";A',b'RESET1')
        print('Restart cleared BASIC state inside the same Process',flush=True)

        menu(60);reach('dw($%x)=0'%job)
        require(identity()==(0,0),'Mode change retained old engine')
        old=start('A=A-(-1):PRINT "INTEGER";A')
        reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],job+JOB['job'],old))
        held=identity();require(all(held),'Integer interpreter missing')
        require(n(job+JOB['cause'],4)==0,'Integer Run failed');contains(b'INTEGER1')
        run('A=A-(-1):PRINT "INTEGER";A',b'INTEGER2')
        old=start('INPUT Z');menus.select('FastBasic output');pending();menus.close();done(old,304)
        run('PRINT "INPUTSTOP";A',b'INPUTSTOP2')
        print('Mode switch, integer state and output-close cancellation passed',flush=True)

        c['replace']('PRINT 45');old=n(job+JOB['job'],4)
        key('RETURN',ctrl=True,shift=True)
        reach('(dw($%x)=0)&(dw($%x)!=0)&(dw($%x)!=%d)'%(job,job+JOB['job'],job+JOB['job'],old))
        require(n(job+JOB['cause'],4)==0,'Check beside idle interpreter failed');same()
        key('Q',ctrl=True)
        tree=form();obj=tree+9*24
        c['click'](n(tree+16,2)+n(obj+16,2)+n(obj+20,2)//2,
            n(tree+18,2)+n(obj+18,2)+8);frames(20);same()
        run('A=A-(-1):PRINT "CANCEL";A',b'CANCEL3')
        print('Check and canceled Quit preserved the interpreter',flush=True)
        start('INPUT Z');menus.select('FastBasic output');pending()
        self.s.saved['persistent_interpreter']=dict(process_retained=True,state_retained=True,
            edits=True,dim=True,parse_error=True,stop=True,restart=True,mode_change=True,
            input_stop=True,check=True,canceled_quit=True,final_quit=True)

    def source_after_quit(self):
        pass


if __name__=='__main__':
    physical_keys()
    a=argparse.ArgumentParser();a.add_argument('--bundle',type=Path,required=True);args=a.parse_args()
    bundle=args.bundle.resolve();record=check(bundle,SourceInterpreter)
    record['runner_sha256']=sha256(Path(__file__))
    filename='input-diagnostic-results.json' if args.diagnose_input else 'source-interpreter-results.json'
    (bundle/filename).write_text(json.dumps(record,indent=2)+'\n')
