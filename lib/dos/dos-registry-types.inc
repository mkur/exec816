; Private fixed upper-kernel service state. The Task uses admitted kernel
; storage; application Task records and tc_UserData are not borrowed.
PUBLIC TYPE DosRegistry=[
  BYTE ARRAY task(62)
  ADDRESS entry
  BYTE POINTER worker,runtime
  BYTE state,stop
  LONGCARD mask,generation
  ADDRESS config
  BYTE count
  LONGINT error
  BYTE cancelSignal,cancelReady
  BYTE POINTER cancelHead
]
