"""Check named loaded Tasks through the packaged desktop and shell."""
import re
from gem_applications import instances
from native_program import require


def exercise(s,click,desk_menu,menus):
    directory=s.p['output']/'bitmap-console'
    def apps():return instances(s.b,s.p,directory)
    def tasks(expected,absent=()):
        menus.select('Shell');s.command('CLS')
        screen=s.command('TASKS',b'DESKTOP.APP')
        require(b'(unnamed)' not in screen,'Unnamed Task in packaged desktop')
        for name in expected:require(name in screen,'Missing Task name: '+repr(name))
        for name in absent:require(name not in screen,'Retired Task remains: '+repr(name))
        return screen.decode('ascii')

    initial=tasks((b'shell',b'dos.filesystem',b'sio.device',b'console.device'))
    menus.select('SYS:');desk_menu(4)
    for _ in range(60):
        found=[a for a in apps() if a['name']=='counter']
        if found:break
        s.frames(20)
    require(found,'Counter did not launch')
    counter=found[0]['symbols']['GEMCounter']
    s.rendezvous('dw($%x)=1'%(counter+12));s.frames(100)
    menus.select('Shell')
    s.command('RUN TICK')
    started=s.command('JOBS')
    jobs=re.findall(rb'Job (\d+) running',started)
    require(jobs,'JOBS did not report the running Process identity')
    running=tasks((b'COUNTER.APP',b'TICK'))
    s.save_screen(s.p['output']/'named-tasks.png')
    s.command('BREAK '+jobs[-1].decode('ascii'));s.frames(200)
    menus.select('Counter')
    x,y=[s.number(counter+38+i*2,2) for i in range(2)]
    click(x,y-8)
    for _ in range(60):
        if not any(a['name']=='counter' for a in apps()):break
        s.frames(20)
    require(not any(a['name']=='counter' for a in apps()),'Counter not collected')
    final=tasks((),(b'COUNTER.APP',b'TICK'))
    return dict(initial=initial,running=running,after_collection=final,
                gui_names=True,native_name=True,retirement=True)
