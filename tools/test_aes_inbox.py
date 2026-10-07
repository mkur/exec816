"""Private emitted presenter producer for bounded application input transport."""
from library_paths import read_source
from native_program import ROOT, require


def producer(out, symbols):
    source = '''MODULE AESINBOXPROBE
USE EXEC
USE AESSTATE
USE AESTYPES
USE AESGUI
USE AESINBOX
USE HEAPCORE
AESTYPES.InputRecord sample

PUBLIC PROC Pump()
  CARD index
  BYTE accepted

  LET command=CARD POINTER($COMMAND)
  IF command^=0 THEN
    RETURN
  FI

  LET identity=LONGCARD POINTER($CLIENT)
  LET source=CARD POINTER($SOURCE)
  LET count=CARD POINTER($COUNT)
  LET total=CARD POINTER($ACCEPTED)
  LET eligible=CARD POINTER($ELIGIBLE)
  LET buttons=CARD POINTER($BUTTONS)
  LET acknowledgement=LONGCARD POINTER($ACK)
  LET service=AESSTATE.Get()
  LET client=AESSTATE.Find(service,identity^)
  IF client=NULL THEN
    HEAPCORE.Abort($fcc0)
  FI

  CASE command^ OF
  WHEN 1 THEN
    IF AESGUI.Open(service,client,7)=0 THEN
      HEAPCORE.Abort($fcc1)
    FI

  WHEN 2 THEN
    total^=0
    FOR index=0 TO count^-1 DO
      sample.x=INT(index)
      sample.y=-INT(index)
      sample.buttons=buttons^
      sample.qualifiers=2
      sample.key=INT($100+index)
      accepted=AESINBOX.Publish(client,source^,@sample)
      total^==+CARD(accepted)
    OD

  WHEN 3 THEN
    AESINBOX.Snapshot(client,@sample,eligible^)

  WHEN 4 THEN
    AESINBOX.Lost(client,source^)

  WHEN 5 THEN
    AESGUI.Close(client)

  WHEN 6 THEN
    client.endpoint.input.keyHead=250
    client.endpoint.input.keyTail=250

  WHEN 7 THEN
    client.endpoint.input.keyEpoch=$ffffffff
  ESAC

  EXEC.Forbid()
  command^=0
  EXEC.Signal(client.lease.task,acknowledgement^)
  EXEC.Permit()

RETURN
ENDMODULE
'''
    for name in ('Command', 'Client', 'Source', 'Count', 'Accepted', 'Eligible', 'Buttons', 'Ack'):
        source = source.replace('$'+name.upper(), f'${symbols["AESInput"+name]:x}')
    (out/'aesinboxprobe.act').write_text(source)
    host = read_source(ROOT/'lib/aes/aeshost.act').replace('USE AESCORE', 'USE AESCORE\nUSE AESINBOXPROBE')
    needle = '  changed=service.directory.changed<>0'
    require(host.count(needle) == 1, 'Input producer wake boundary changed')
    (out/'aeshost.act').write_text(host.replace(needle, '  AESINBOXPROBE.Pump()\n'+needle))
