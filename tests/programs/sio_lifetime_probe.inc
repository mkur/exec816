; Test-only rendezvous at fully published lifecycle states, with the worker's
; lifetime lease still held. Wait deliberately lets a peer attempt removal.
PROC LifecycleCheckpoint(BYTE wanted)
  BYTE POINTER checkpoint
  LONGCARD bits

  checkpoint=BYTE POINTER(ADDRESS(SIO_STATE+90))
  IF checkpoint^=wanted THEN
    checkpoint^=wanted+1
    bits=EXEC.Wait(1)
  FI

RETURN
