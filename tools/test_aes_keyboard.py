"""Presenter routing fixture: normalized capture carries its original route."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    source = '''MODULE AESKEYPROBE
USE EXEC
USE INPUT
USE AESSTATE
USE DESKINPUT
USE DESKCORE
USE DESKSTATE
INPUT.Event captured
LONGCARD savedRoute

PUBLIC PROC Pump()
  BYTE handled

  LET command=CARD POINTER($COMMAND)
  IF command^=0 THEN
    RETURN
  FI

  LET identity=LONGCARD POINTER($CLIENT)
  LET code=CARD POINTER($CODE)
  LET kind=BYTE POINTER($KIND)
  LET route=LONGCARD POINTER($ROUTE)
  LET acknowledgement=LONGCARD POINTER($ACK)
  LET client=AESSTATE.Find(AESSTATE.Get(),identity^)
  IF command^=1 THEN
    savedRoute=client.window.keyRoute
    route^=savedRoute
  ELSEIF command^=4 THEN
    DESKCORE.Focus(DESKSTATE.Get(),client.window.id)
  ELSE
    captured.route=IF command^=3 THEN savedRoute ELSE client.window.keyRoute FI
    captured.kind=kind^
    captured.code=code^
    captured.qualifiers=(code^ RSH 6) & 3
    handled=DESKINPUT.Key(@captured)
  FI

  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,acknowledgement^)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for name in ('Command', 'Client', 'Code', 'Kind', 'Route', 'Ack'):
        source = source.replace('$'+name.upper(), f'${symbols["AESInput"+name]:x}')
    (out/'aeskeyprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE', 'USE AESCORE\nUSE AESKEYPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Keyboard producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESKEYPROBE.Pump()\n'+needle))


def physical(b, p, foreign, report):
    from desktop_mouse import schedule
    from os_boundary import run_to
    sy = foreign['symbols']

    def reach(condition):
        b.bp_clear_all()
        b.bp_set(p['labels']['native_irq'], condition=condition)
        run_to(b, p['labels']['native_irq'], condition=condition,
               timeout=120, frame_limit=6000)

    def frames(n):
        reach('@frame>=%d' % (b.eval_expr('@frame')+n))

    b._cmd_ok('MOUSE ST')
    reach('dw($%x)=1' % sy['AESPhysical'])
    b._cmd_ok('KEY CTRL down')
    b._cmd_ok('KEY C down')
    frames(3)
    b._cmd_ok('KEY C up')
    b._cmd_ok('KEY CTRL up')
    frames(3)
    b._cmd_ok('KEY BREAK down')
    frames(3)
    b._cmd_ok('KEY BREAK up')
    frames(3)
    # A title gesture owns BREAK; it must not also reach the GEM inbox.
    at = lambda name: next(d['address'] for d in p['image']['data']
                           if '_DESKINPUT_'+name.upper()+'_' in d['name'])
    position = [int.from_bytes(b.memdump(at(name), 2), 'little')
                for name in ('cursorX', 'cursorY')]
    target = schedule(b, p, position, (100, 46))
    reach('(dw($%x)=%d)&(dw($%x)=%d)' %
          (at('cursorX'), target[0], at('cursorY'), target[1]))
    frames(8)
    b._cmd_ok('MOUSE AT 2000 0 0 1')
    frames(8)
    b._cmd_ok('KEY BREAK down')
    frames(3)
    b._cmd_ok('KEY BREAK up')
    b._cmd_ok('MOUSE AT 2000 0 0 0')
    frames(8)
    b.poke16(sy['AESPhysicalGo'], 1)
    b.bp_clear_all()
    report['physical_keys'] = ['Ctrl-C through unfiltered AES route',
                              'BREAK to GEM Escape', 'title gesture consumes BREAK']
