; Timing workloads share the existing four-task serial fixture.
ADDRESS ARRAY fragments(24)
LONGCARD heapBefore,heapAfter,heapAllocations,heapQueries,heapClears
CARD fragmentCount

PROC HeapRequire(BYTE condition)

  IF condition=0 THEN
    HEAPCORE.Abort($ff72)
  FI

RETURN

PROC HeapPrepare()
  CARD index
  BYTE POINTER p

  heapBefore=EXEC.AvailMem(0)
  IF workload=6 THEN
    FOR index=0 TO 23 DO
      p=EXEC.AllocMem(257,0)
      HeapRequire(p<>BYTE POINTER(0))
      p^=$a5
      p(256)=$5a
      fragments(index)=ADDRESS(p)
    OD

    FOR index=0 TO 22 STEP 2 DO
      EXEC.FreeMem(BYTE POINTER(fragments(index)),257)
      fragments(index)=0
    OD

    fragmentCount=13
  FI

RETURN

PROC HeapAllocateStep()
  BYTE POINTER p

  p=EXEC.AllocMem(257,0)
  HeapRequire(p<>BYTE POINTER(0))
  p^=$39
  p(256)=$73
  EXEC.FreeMem(p,257)
  IF pumpSent<byteCount THEN
    heapAllocations==+1
  FI

RETURN

PROC HeapFragmentStep()
  BYTE POINTER p,q
  LONGCARD largest

  p=EXEC.AllocMem(513,0)
  q=EXEC.AllocMem(LONGCARD($10001),EXEC.MEMF_LINEAR)
  HeapRequire(p<>BYTE POINTER(0) AND q<>BYTE POINTER(0))
  p^=$39
  q(SIZE($10000))=$73
  largest=EXEC.AvailMem(EXEC.MEMF_LARGEST)
  HeapRequire(largest>0 AND largest<=LONGCARD($10000))
  largest=EXEC.AvailMem(EXEC.MEMF_LARGEST OR EXEC.MEMF_LINEAR)
  HeapRequire(largest>LONGCARD($10000))
  EXEC.FreeMem(p,513)
  EXEC.FreeMem(q,LONGCARD($10001))
  IF pumpSent<byteCount THEN
    heapQueries==+1
  FI

RETURN

PROC HeapClearStep()
  BYTE POINTER p

  p=EXEC.AllocVec(LONGCARD($20001),EXEC.MEMF_LINEAR OR EXEC.MEMF_CLEAR)
  HeapRequire(p<>BYTE POINTER(0))
  HeapRequire(p^=0 AND p(SIZE($10000))=0 AND p(SIZE($20000))=0)
  p^=$d7
  p(SIZE($20000))=$7d
  EXEC.FreeVec(p)
  IF pumpSent<byteCount THEN
    heapClears==+1
  FI

RETURN

PROC HeapFinish()
  CARD index
  BYTE POINTER p

  IF workload=6 THEN
    FOR index=1 TO 23 STEP 2 DO
      p=BYTE POINTER(fragments(index))
      HeapRequire(p^=$a5 AND p(256)=$5a)
      EXEC.FreeMem(p,257)
    OD
  FI

  heapAfter=EXEC.AvailMem(0)
  HeapRequire(heapAfter=heapBefore)

RETURN
