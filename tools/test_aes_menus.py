"""Fixture-only menu selection entry, absent from production link roots."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    source = '''MODULE AESMENUPROBE
USE EXEC
USE AESSTATE
USE AESTYPES
USE AESGUI
USE AESLOCKS
USE AESMENU

PUBLIC PROC Pump()
  BYTE accepted

  LET command=CARD POINTER($COMMAND)
  IF command^=0 OR AESLOCKS.NativeReady()=0 THEN
    RETURN
  FI
  LET identity=LONGCARD POINTER($CLIENT)
  LET service=AESSTATE.Get()
  LET client=AESSTATE.Find(service,identity^)
  accepted=0
  IF command^=1 THEN
    accepted=AESGUI.Select(service,client,3,6,5)
  ELSEIF command^=2 THEN
    AESGUI.Post(service,client,AESTYPES.GUI_CLOSED,0,0,0,0)
  FI
  LET result=CARD POINTER($RESULT)
  result^=CARD(accepted)
  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,LONGCARD(1) LSH client.endpoint.port.mp_SigBit)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for key, symbol in (('COMMAND', 'AESMenuCommand'), ('CLIENT', 'AESMenuClient'),
                        ('RESULT', 'AESMenuResult')):
        source = source.replace('$'+key, f'${symbols[symbol]:x}')
    (out/'aesmenuprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE',
        'USE AESCORE\nUSE AESMENUPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Menu producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESMENUPROBE.Pump()\n'+needle))
