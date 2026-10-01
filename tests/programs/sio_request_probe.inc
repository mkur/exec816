INCLUDE "../../lib/exec/adapter-state.inc"
; Test-only wait for a real VBI at partial claim/reply publication. The caller
; holds Forbid, not I; no Wait/Sleep may release that exclusion here.
PROC RequestCheckpoint(BYTE wanted)
  BYTE POINTER checkpoint
  CARD POINTER clock
  CARD before

  checkpoint=BYTE POINTER(ADDRESS(SIO_STATE+90))
  IF checkpoint^=wanted THEN
    clock=CARD POINTER(ASTATE_VBI_COUNT)
    before=clock^
    checkpoint^=wanted+1
    WHILE clock^=before DO
    OD
  FI

RETURN
