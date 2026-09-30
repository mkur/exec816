; All system heap calls run in the existing guarded policy activation. Native
; wrappers supply a read-only packet on the caller's bank-zero stack.

; Recognize the public system-memory service family.
BYTE FUNC MemoryService(BYTE service)

RETURN(service=H_SERVICE_ALLOC_MEM OR service=H_SERVICE_FREE_MEM
      OR (service>=H_SERVICE_ALLOC_VEC AND service<=H_SERVICE_TYPE_OF_MEM))

; Require the complete memory-call packet to fit the caller's stack.
BYTE FUNC MemoryPacket(TaskControl POINTER ctx CARD saved BYTE service)
  CARD bytes

  LET base=SavedWord(saved,T_FRAME_X)
  bytes=8
  IF service=H_SERVICE_FREE_VEC OR service=H_SERVICE_TYPE_OF_MEM THEN
    bytes=3
  FI

  IF service=H_SERVICE_AVAIL_MEM THEN
    bytes=4
  FI

  IF base<ctx.stackFloor OR base>ctx.stackTop THEN
    RETURN(0)
  FI

RETURN(bytes<=ctx.stackTop-base+1)

; Decode a checked memory request and publish its result in the saved frame.
CARD FUNC MemoryCall(TaskControl POINTER ctx CARD saved BYTE service)
  HeapAllocArgs POINTER allocation
  HeapFreeArgs POINTER release
  HeapPointerArgs POINTER pointerArgs
  HeapQueryArgs POINTER query

  IF MemoryPacket(ctx,saved,service)=0 THEN
    RETURN(T_FAULT)
  FI

  LET packet=ArgumentPointer(saved)
  CASE service OF
  WHEN H_SERVICE_ALLOC_MEM,H_SERVICE_ALLOC_VEC THEN
    allocation=HeapAllocArgs POINTER(packet)
    IF service=H_SERVICE_ALLOC_MEM THEN
      MaskResult(saved,LONGCARD(ADDRESS(HEAPPOLICY.Reserve(allocation.bytes,
          allocation.flags))))

    ELSE
      MaskResult(saved,LONGCARD(ADDRESS(HEAPPOLICY.ReserveVector(allocation.bytes,
          allocation.flags))))
    FI

  WHEN H_SERVICE_FREE_MEM THEN
    release=HeapFreeArgs POINTER(packet)
    HEAPPOLICY.Free(release.block,release.bytes)

  WHEN H_SERVICE_FREE_VEC THEN
    pointerArgs=HeapPointerArgs POINTER(packet)
    HEAPPOLICY.FreeVector(pointerArgs.block)

  WHEN H_SERVICE_AVAIL_MEM THEN
    query=HeapQueryArgs POINTER(packet)
    MaskResult(saved,HEAPPOLICY.Avail(query.flags))

  WHEN H_SERVICE_TYPE_OF_MEM THEN
    pointerArgs=HeapPointerArgs POINTER(packet)
    MaskResult(saved,HEAPPOLICY.MemoryType(pointerArgs.block))
  ESAC

RETURN(saved)
