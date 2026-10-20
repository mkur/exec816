"""Physical multi-session walkthrough against an unchanged packaged image."""
from pathlib import Path

from console_model import read_cells
from generate_console import glyphs
from generate_dos import ABI as DOS_ABI
from native_program import require
from shell_inspect import address, process_slot


class Sessions:
    def __init__(self, out, bundle):
        self.out, self.bundle = Path(out), Path(bundle)
        self.commands, self.screens, self.peaks = [], [], []

    def prepare(self, s):
        self.s=s
        self.c=s.console
        self.windows=s.p['build']['memory']['console_storage']['WINDOWS']
        self.selected=address(s.p['image'],'selectedSession')
        self.live=address(s.p['image'],'controllerLive')
        self.bitmap=s.manifest.get('bitmap',False)
        self.prime=not s.manifest.get('shell_only',False)
        self.bind(1)

    def exercise(self, s):
        self.prepare(s)
        self.command('CD WORK:')
        self.command('ALIAS HI "ECHO first"')
        self.command('PATH CLEAR')
        self.command('SESSIONS',b'* 1 ready')
        s.begin('NEWSHELL')
        self.wait_selected(2)
        self.bind(2);s.ready()
        self.screen('second-ready')
        self.command('CD',b'WORK:')
        self.command('PATH',b'C:')
        self.command('HI',error=205)
        self.command('NEWSHELL',error=103)
        self.command('SESSION 0',error=115)
        self.command('SESSION 4294967296',error=115)
        self.command('SESSION 4294967295',error=205)
        self.command('SESSIONS >WORK:SESS.TXT')
        self.command('TYPE WORK:SESS.TXT',b'* 2 ready')
        self.command('ECHO shared >WORK:SHARED.TXT')
        self.command('ASSIGN X: WORK:')
        if self.prime:
            before=s.ledger()
            self.command('CAT SYS:LONG.TXT | WC',error=103)
            require(s.ledger()==before,'Rejected second pipeline retained owned resources')
            require(s.number(s.p['build']['task_storage']['LIVE'],1)==7,
                    'Two shells plus prime did not recover seven live Tasks')
        self.command('HELLO',b'Hello from disk!')
        if self.prime:
            self.command('RUN PRIMES >CON:')
            # Pane admission from a shell on a different unit fails.
            s.frames(10)
            self.command('JOBS')
            require(s.number(self.windows+self.c['WINDOWS_PANE'])!=0,
                    'The second session replaced the first prime pane')
        self.command('ECHO "NEWSHELL >WORK:BAD" >WORK:SCRIPT')
        self.command('EXECUTE WORK:SCRIPT',error=209)
        self.command('TYPE WORK:BAD',error=205)
        self.command('RUN NEWSHELL',error=115)
        self.command('NEWSHELL | WC',error=115)
        self.command('CD SYS:')

        # Chord is physical and releases both modifiers; TAB remains completion.
        for ch in 'echo second':s.press(ch)
        s.press('\x02')
        draft=self.draft()
        self.chord(1)
        self.command('HI',b'first')
        self.command('TYPE X:SHARED.TXT',b'shared')
        self.command('CD',b'WORK:')
        self.command('PATH')
        for ch in 'echo first':s.press(ch)
        first_draft=self.draft()
        self.chord(2)
        require(self.draft()==draft,'Second draft/caret changed while hidden')
        s.press('z');s.press('\n');s.ready();s.result()
        require(b'seconzd' in self.screen('midline-draft'), 'Modifiers remained held or caret moved')
        # A fresh history has only this session's lines, never HI or PATH CLEAR.
        s.press('\x10')
        require(self.draft()[0]==b'echo seconzd','History crossed session boundaries')
        s.press('\x15')
        for ch in 'NEW':s.press(ch)
        s.press('\t');s.ready()
        require(self.draft()[0]==b'NEWSHELL ','TAB did not complete in second shell')
        s.press('\x15')
        self.chord(1)
        require(self.draft()==first_draft,'First draft changed while hidden')
        s.press('\x15')
        self.command('PATH RESET')
        self.command('CD SYS:')

        # Disk wait in one shell leaves the other prompt and completion live.
        route=s.begin('CAT SYS:LONG.TXT >NIL:')
        active_tasks=8 if self.prime else 7
        s.rendezvous(f'db(${s.p["build"]["task_storage"]["LIVE"]:x})={active_tasks}')
        self.peaks.append(active_tasks)
        self.wait_disk()
        self.chord(2)
        for ch in 'SESS':s.press(ch)
        s.press('\t');s.ready()
        require(self.draft()[0].startswith(b'SESSION'),'Completion stalled during peer disk I/O')
        s.press('\x15')
        self.command('ECHO active-peer',b'active-peer')
        self.chord(1)
        s.press('\x03');s.ready(route);s.result(304)
        if self.prime:
            self.command('JOBS')
            job=s.number(address(s.p['image'],'job',session=0))
            self.command(f'BREAK {job}')
            s.frames(10);self.command('JOBS')
            require(s.number(s.p['build']['task_storage']['LIVE'],1)==6,
                    'Stopping prime did not release its Task')
        self.chord(2)
        route=s.begin('CAT SYS:LONG.TXT | WC')
        scope=s.saved['scope']
        s.rendezvous(f'(db(${s.p["build"]["task_storage"]["LIVE"]:x})=8)&(db(${scope+54:x})=1)')
        self.peaks.append(8)
        s.press('\x03');s.ready(route);s.result(304)
        require(s.number(s.p['build']['task_storage']['LIVE'],1)==6,
                'Two-shell pipeline did not recover its slots')

        # EXIT closes only the selected shell; the survivor gets focus first.
        s.begin('EXIT')
        self.wait_selected(1);self.bind(1);s.ready()
        s.rendezvous(f'db(${self.live:x})=1')
        self.command('SESSION 2',error=205)
        s.begin('NEWSHELL')
        self.wait_selected(3);self.bind(3);s.ready()
        self.command('SESSIONS',b'* 3 ready')
        self.command('ECHO recreated',b'recreated')
        s.begin('SESSION 1')
        self.wait_selected(1);self.bind(1);s.ready()
        s.begin('EXIT')
        self.wait_selected(3);self.bind(3);s.ready()
        s.rendezvous(f'db(${self.live:x})=1')
        s.begin('NEWSHELL')
        self.wait_selected(4);self.bind(4);s.ready()
        require(self.unit==0,'Vacant permanent unit zero was not reused')
        require(b'first' not in read_cells(s.far,s.saved['top']), 'Unit zero retained an old transcript')
        self.command('ECHO unit-zero-reused',b'unit-zero-reused')
        s.begin('EXIT')
        self.wait_selected(3);self.bind(3);s.ready()
        s.rendezvous(f'db(${self.live:x})=1')
        self.command('ECHO survivor',b'survivor')
        s.save_screen(self.bundle/'boot-smoke.png')
        (self.out/'sessions.png').write_bytes((self.bundle/'boot-smoke.png').read_bytes())
        for ch in 'EXIT':s.press(ch)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()

    def wait_disk(self):
        s=self.s
        scope_field=self.entry+self.c['WINDOW_SCOPE']
        # The bound foreground route must already belong to the command. Keys
        # captured before handoff correctly retire with their old generation.
        s.rendezvous(f'(dw(${scope_field:x})!={s.saved["scope"]&65535})|(db(${scope_field+2:x})!={s.saved["scope"]>>16})')
        child=s.number(scope_field,3)
        s.rendezvous(f'(db(${child+21:x})=3)&(dw(dw(${child+27:x})+db(${child+29:x})*65536+22)=82)')

    def wait_selected(self, identity):
        self.s.rendezvous(f'dw(${self.selected:x})={identity}')

    def bind(self, identity):
        s,c=self.s,self.c
        index=next(i for i in range(2) if (control:=s.number(address(s.p['image'],'control',session=i),3))
                   and s.number(control)==identity)
        slot=process_slot(s.b,s.p,identity)
        dos=s.p['build']['memory']['dos_storage']['BASE']+16*slot
        scope=s.number(s.number(dos,3)+83,3)
        entries=[self.windows+c['WINDOWS_ITEMS']+i*c['WINDOW_SIZE'] for i in range(4)]
        fields={name:offset for name,_,offset in DOS_ABI['foreground']['fields']}
        unit=s.number(scope+fields['unit'])
        entry=next(e for e in entries if s.number(e+c['WINDOW_STATE'],1) and s.number(e+c['WINDOW_UNIT'])==unit)
        s.saved.update(shell=s.number(address(s.p['image'],'shell',session=index),3),
                       dos_slot=dos,scope=scope,top=s.number(entry+c['WINDOW_INSTANCE'],3),
                       topView=s.number(entry+c['WINDOW_VIEW'],3))
        self.entry=entry
        self.unit=unit
        self.identity=identity

    def draft(self):
        s=self.s
        handle=s.number(s.saved['shell'],3)
        cooked=s.number(handle+16,3)
        f={name:offset for name,_,offset in DOS_ABI['cooked']['session']['fields']}
        return s.far(cooked+f['line'],s.number(cooked+f['length'],2)),s.number(cooked+f['cursor'],2)

    def chord(self, target):
        s=self.s
        for key in ('CTRL','SHIFT','SPACE'):s.b._cmd_ok(f'KEY {key} down')
        self.wait_selected(target)
        for key in ('SPACE','SHIFT','CTRL'):s.b._cmd_ok(f'KEY {key} up')
        s.frames(3);self.bind(target)
        self.screen('chord-'+str(target))

    def command(self, text, expected=None, error=0):
        s=self.s
        print('Session',self.identity,'command:',text,flush=True)
        previous=s.begin(text);s.ready(previous);s.result(error)
        cells=self.screen(text)
        if expected is not None:
            require(expected in cells,'Missing session output: '+text)
        self.commands.append(dict(session=self.identity,command=text,error=error))
        return cells

    def screen(self, label):
        s,c=self.s,self.c
        waits=[f'db(${self.windows+c["WINDOWS_PRESENTING"]:x})=0']
        visible=[]
        for slot in range(4):
            entry=self.windows+c['WINDOWS_ITEMS']+slot*c['WINDOW_SIZE']
            if s.number(entry+c['WINDOW_STATE'],1)!=c['WIN_LIVE']:continue
            view=s.number(entry+c['WINDOW_VIEW'],3)
            if not s.number(view+c['PRESENTATION_VISIBLE'],1):continue
            instance=s.number(entry+c['WINDOW_INSTANCE'],3)
            waits.extend([f'db(${instance+c["INSTANCE_DIRTYROWS"]:x})=0',
                          f'db(${instance+c["INSTANCE_OPERATION"]:x})={c["OP_IDLE"]}',
                          f'dw(${instance+c["INSTANCE_WRITE"]:x})=0',
                          f'db(${instance+c["INSTANCE_WRITE"]+2:x})=0',
                          f'db(${view+c["PRESENTATION_SCROLLSTATE"]:x})=0',
                          f'dw(${view+c["PRESENTATION_PRESENTEDGENERATION"]:x})=dw(${instance+c["INSTANCE_GENERATION"]:x})',
                          f'dw(${view+c["PRESENTATION_PRESENTEDGENERATION"]+2:x})=dw(${instance+c["INSTANCE_GENERATION"]+2:x})',
                          f'dw(${view+c["PRESENTATION_INDEX"]:x})=dw(${instance+c["INSTANCE_LINESTART"]:x})+dw(${instance+c["INSTANCE_COLUMN"]:x})'])
            visible.append((instance,view))
        s.rendezvous('&'.join('('+item+')' for item in waits))
        if self.bitmap:
            from gem_render_oracle import Raster,font_bytes
            from bitmap_console_oracle import Terminal
            from test_gem_interactive import pixels
            s.frames(2)
            raster=Raster(font_bytes(self.bundle/s.manifest['font_source']))
        expected=bytearray(2400 if self.bitmap else 960)
        display_width=80 if self.bitmap else 40
        for instance,view in visible:
            cells=read_cells(s.far,instance)
            width=s.number(instance+c['INSTANCE_WIDTH'],2)
            left=s.number(view+c['PRESENTATION_LEFT'],2)
            top=s.number(view+c['PRESENTATION_TOP'],2)
            caret=s.number(view+c['PRESENTATION_PREVIOUSCURSOR'],2)
            on=s.number(view+c['PRESENTATION_CURSORON'],1)
            if self.bitmap:
                terminal=Terminal(width,len(cells)//width)
                terminal.cells[:]=cells
                terminal.row,terminal.column=divmod(caret,width)
                terminal.paint(raster,left,top,caret=on)
            else:
                for i,value in enumerate(cells):
                    expected[(top+i//width)*display_width+left+i%width]=glyphs()[value]^(128 if on and i==caret else 0)
        if self.bitmap:
            folder=self.out/f'pixels-{len(self.screens)}';folder.mkdir(exist_ok=True)
            pixels(s.b,folder,raster.packed())
        else:
            actual=s.far(s.saved['screen'],960)
            if actual!=expected:
                import json
                self.out.mkdir(parents=True,exist_ok=True)
                (self.out/'screen-difference.json').write_text(json.dumps(dict(label=label,
                    instances=[dict(instance=instance,view=view,
                        dirty=s.number(instance+c['INSTANCE_DIRTYROWS'],1),
                        writing=s.number(instance+c['INSTANCE_WRITE'],3),
                        generation=s.number(instance+c['INSTANCE_GENERATION'],4),
                        presented=s.number(view+c['PRESENTATION_PRESENTEDGENERATION'],4))
                               for instance,view in visible],
                    differences=[dict(index=i,actual=a,expected=e) for i,(a,e) in
                                 enumerate(zip(actual,expected)) if a!=e]),indent=2)+'\n')
            require(actual==expected,'Physical session cells/caret differ: '+label)
        self.screens.append(dict(session=self.identity,label=label,frame=s.b.eval_expr('@frame')))
        return read_cells(s.far,s.saved['top'])


class DiskSwitch(Sessions):
    def exercise(self,s):
        self.prepare(s)
        s.begin('NEWSHELL');self.wait_selected(2);self.bind(2);s.ready()
        s.begin('SESSION 1');self.wait_selected(1);self.bind(1);s.ready()
        previous=s.begin('CAT SYS:LONG.TXT >NIL:')
        self.wait_disk()
        for key in ('CTRL','SHIFT','SPACE'):s.b._cmd_ok(f'KEY {key} down')
        s.frames(30)
        for key in ('SPACE','SHIFT','CTRL'):s.b._cmd_ok(f'KEY {key} up')
        selected=s.number(self.selected)
        print('Disk chord selected',selected,'window route',s.number(self.entry+self.c['WINDOW_ROUTE']),flush=True)
        if selected!=2:
            registry=address(s.p['image'],'sessions')
            print('Registry',s.far(registry,660).hex(),flush=True)
        require(selected==2,'Physical disk-wait chord did not select peer')
        self.bind(2);self.command('ECHO peer',b'peer')
        self.chord(1);s.press('\x03');s.ready(previous);s.result(304)
        s.begin('EXIT');self.wait_selected(2);self.bind(2);s.ready()
        self.command('ECHO survivor',b'survivor')
        s.save_screen(self.bundle/'boot-smoke.png')
        for ch in 'EXIT':s.press(ch)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()


class Inherited(Sessions):
    def exercise(self,s):
        self.prepare(s)
        s.begin('NEWSHELL');self.wait_selected(2);self.bind(2);s.ready()
        self.command('ECHO inherited >RAM:INPUT.TXT')
        self.command('TYPE <RAM:INPUT.TXT',b'inherited')
        self.command('CAT <RAM:INPUT.TXT',b'inherited')
        baseline=s.ledger()
        previous=s.begin('CAT')
        client=s.number(s.saved['scope']+3,3)
        condition=f'(db(${s.saved["top"]+51:x})=2)&(db(${client+86:x})=1)'
        s.rendezvous(condition)
        self.chord(1);self.command('ECHO reader-peer',b'reader-peer')
        self.chord(2)
        for char in '↑program\tdata\n':s.press(char)
        s.rendezvous(condition);s.press('\x04')
        s.rendezvous(f'db(${client+86:x})=0')
        s.ready(previous);s.result()
        require(s.ledger()==baseline,'Inherited input retained owned objects')
        require(b'program' in self.screen('inherited-input'),'Missing inherited input output')
        s.press('\x10');require(self.draft()[0]==b'CAT','Program input entered shell history')
        s.press('\x0e');require(self.draft()[0]==b'','Inherited EOF changed the shell draft')
        self.chord(1)
        s.begin('EXIT');self.wait_selected(2);self.bind(2);s.ready()
        self.command('PRIMES PASSES 1',error=212)
        self.command('ECHO inherited-survivor',b'inherited-survivor')
        s.save_screen(self.bundle/'boot-smoke.png')
        (self.out/'sessions.png').write_bytes((self.bundle/'boot-smoke.png').read_bytes())
        for ch in 'EXIT':s.press(ch)
        s.b._cmd_ok('KEY RETURN down');s.b.bp_clear_all()
