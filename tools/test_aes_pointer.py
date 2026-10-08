"""Normalized presenter injection through the production classification path."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    desktop = read_source(ROOT/'lib/desktop/deskinput.act')
    assert desktop.endswith('ENDMODULE\n')
    desktop = desktop[:-len('ENDMODULE\n')]+'''
; Fixture-only entry at the fresh normalized-capture boundary.
PUBLIC PROC Inject(INPUT.Event POINTER captured)

  A816MEMORY.Move(BYTE POINTER(@sample),BYTE POINTER(captured),INPUT.EVENT_BYTES)
  Fresh()
  AESMOUSE.Refresh()

RETURN
ENDMODULE
'''
    (out/'deskinput.act').write_text(desktop)
    source = '''MODULE AESPOINTERPROBE
USE EXEC
USE INPUT
USE AESSTATE
USE DESKINPUT
USE DESKCORE
USE DESKSTATE
INPUT.Event captured

PUBLIC PROC Pump()
  BYTE handled

  LET command=CARD POINTER($COMMAND)
  IF command^=0 THEN
    RETURN
  FI

  LET identity=LONGCARD POINTER($CLIENT)
  LET x=INT POINTER($X)
  LET y=INT POINTER($Y)
  LET buttons=CARD POINTER($BUTTONS)
  LET qualifiers=CARD POINTER($QUALIFIERS)
  LET kind=BYTE POINTER($KIND)
  LET acknowledgement=LONGCARD POINTER($ACK)
  LET client=AESSTATE.Find(AESSTATE.Get(),identity^)
  captured.x=x^
  captured.y=y^
  captured.buttons=buttons^
  captured.qualifiers=qualifiers^
  captured.kind=kind^
  IF command^=3 THEN
    captured.route=client.window.keyRoute
    captured.kind=INPUT.EVENT_CANCEL
    captured.code=INPUT.CANCEL_BREAK
    handled=DESKINPUT.Key(@captured)
  ELSE
    DESKINPUT.Inject(@captured)
  FI

  IF command^=2 THEN
    captured.buttons=0
    DESKINPUT.Inject(@captured)
  FI

  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,acknowledgement^)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for name in ('Command', 'Client', 'X', 'Y', 'Buttons', 'Qualifiers', 'Kind', 'Ack'):
        source = source.replace('$'+name.upper(), f'${symbols["AESPointer"+name]:x}')
    (out/'aespointerprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE', 'USE AESCORE\nUSE AESPOINTERPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Pointer producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESPOINTERPROBE.Pump()\n'+needle))
