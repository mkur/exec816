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
  ADDRESS ARRAY assigns(4)
  LONGINT mountError
  BYTE mountSlot,mountStage
  BYTE ARRAY definitions(414)
  CARD defined,bootDefinitions,enabled
  BYTE bootCount,management
  BYTE ARRAY failureName(32)
  LONGCARD failureSectors
  CARD failureBytes
  BYTE failureBackend,failureUnit
  BYTE failureSource,failureReason
  BYTE ARRAY failureStatus(4),failurePercom(12)
]
