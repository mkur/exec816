; Internal system policy. Every caller holds E816_SWITCHING; IRQ/NMI never
; touches these lists. CLEAR is performed by the later caller-side wrapper.
INCLUDE "heap-call-types.inc"

CONST LONGCARD MAX_VECTOR_BYTES=$fffffff0

; Reject unsupported flags and mutually exclusive placement/query requests.
BYTE FUNC FlagsValid(LONGCARD flags BYTE query)
  LONGCARD allowed

  allowed=LONGCARD($80110019)
  IF query<>0 THEN
    allowed=allowed OR LONGCARD($000a0000)
  FI

  IF (flags & (allowed XOR SYS.MAXLONGCARD))<>0 THEN
    RETURN(0)
  FI

  IF (flags & H_FLAG_BANK0)<>0 THEN
    IF (flags & (H_FLAG_UPPER+H_FLAG_LINEAR))<>0 THEN
      RETURN(0)
    FI
  FI

  IF (flags & (H_FLAG_LARGEST+H_FLAG_TOTAL))=LONGCARD(
      H_FLAG_LARGEST+H_FLAG_TOTAL) THEN
    RETURN(0)
  FI

RETURN(1)

; Check the descriptor address before reading it, then bounded list links and
; predecessor consistency. Only reserved descriptor slots can be system nodes.
PROC Descriptor(EXECLISTS.Node POINTER node CARD count)

  IF LONGCARD(ADDRESS(node))<LONGCARD(HS_HEADERS) THEN
    HEAPCORE.Abort(H_ERROR_CORRUPT)
  FI

  LET offset=LONGCARD(ADDRESS(node))-LONGCARD(HS_HEADERS)
  IF (offset & 31)<>0 OR offset>=(LONGCARD(count) LSH 5) THEN
    HEAPCORE.Abort(H_ERROR_CORRUPT)
  FI

RETURN

; Validate the published descriptor list before applying system heap policy.
PUBLIC PROC ValidateRegions()
  HeapState POINTER state
  EXECLISTS.Node POINTER node,previous
  CARD count

  state=GetState()
  IF state.ready<>1 OR state.count>HS_CAPACITY THEN
    HEAPCORE.Abort(H_ERROR_CORRUPT)
  FI

  node=state.regions.lh_Head
  previous=EXECLISTS.Node POINTER(@state.regions.lh_Head)
  LET tail=EXECLISTS.Node POINTER(@state.regions.lh_Tail)
  count=0
  WHILE node<>tail DO
    IF count>=state.count THEN
      HEAPCORE.Abort(H_ERROR_CORRUPT)
    FI

    Descriptor(node,state.count)
    IF node.ln_Pred<>previous OR node.ln_Type<>H_NT_MEMORY THEN
      HEAPCORE.Abort(H_ERROR_CORRUPT)
    FI

    previous=node
    node=node.ln_Succ
    count==+1
  OD

  IF count<>state.count OR state.regions.lh_TailPred<>previous THEN
    HEAPCORE.Abort(H_ERROR_CORRUPT)
  FI

  IF state.regions.lh_Tail<>NULL THEN
    HEAPCORE.Abort(H_ERROR_CORRUPT)
  FI

RETURN

; Select a region by requested attributes; ordinary allocations use upper RAM.
BYTE FUNC Matches(HEAPCORE.MemHeader POINTER pool LONGCARD flags)
  CARD required

  required=CARD(flags & LONGCARD($19))
  IF (required & H_FLAG_BANK0)=0 THEN
    required=required OR H_FLAG_UPPER
  FI

RETURN((pool.mh_Attributes & required)=required)

; Find a matching region and reserve storage with the requested bank policy.
PUBLIC BYTE POINTER FUNC Reserve(LONGCARD byteSize LONGCARD flags)
  HeapState POINTER state
  EXECLISTS.Node POINTER node
  HEAPCORE.MemHeader POINTER pool
  BYTE POINTER result

  IF FlagsValid(flags,0)=0 OR HEAPCORE.Rounded(byteSize)=0 THEN
    RETURN(NULL)
  FI

  LET contained=(flags & H_FLAG_LINEAR)=0
  IF contained<>0 AND byteSize>LONGCARD(H_BANK_BYTES) THEN
    RETURN(NULL)
  FI

  ValidateRegions()
  state=GetState()
  node=state.regions.lh_Head
  LET tail=EXECLISTS.Node POINTER(@state.regions.lh_Tail)
  WHILE node<>tail DO
    pool=HEAPCORE.MemHeader POINTER(node)
    IF Matches(pool,flags)<>0 THEN
      result=HEAPCORE.Reserve(pool,byteSize,contained)
      IF result<>NULL THEN
        RETURN(result)
      FI
    FI

    node=node.ln_Succ
  OD

RETURN(NULL)

; Find the validated region containing an address, or return NULL.
HEAPCORE.MemHeader POINTER FUNC Locate(BYTE POINTER location)
  HeapState POINTER state
  EXECLISTS.Node POINTER node
  HEAPCORE.MemHeader POINTER pool

  ValidateRegions()
  state=GetState()
  node=state.regions.lh_Head
  LET tail=EXECLISTS.Node POINTER(@state.regions.lh_Tail)
  LET base=LONGCARD(ADDRESS(location))
  WHILE node<>tail DO
    pool=HEAPCORE.MemHeader POINTER(node)
    HEAPCORE.Bounds(pool)
    IF base>=LONGCARD(ADDRESS(pool.mh_Lower)) AND base<pool.mh_Upper THEN
      RETURN(pool)
    FI

    node=node.ln_Succ
  OD

RETURN(NULL)

; Validate a system allocation's extent before returning it to its region.
PUBLIC PROC Free(BYTE POINTER memoryBlock LONGCARD byteSize)

  IF byteSize=0 THEN
    RETURN
  FI

  LET base=LONGCARD(ADDRESS(memoryBlock))
  LET bytes=HEAPCORE.Rounded(byteSize)
  IF base=0 OR (base & (H_ALIGNMENT-1))<>0 OR bytes=0 THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  LET pool=Locate(memoryBlock)
  IF pool=NULL THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  IF bytes>pool.mh_Upper-base THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  HEAPCORE.Deallocate(pool,memoryBlock,bytes)

RETURN

; Report matching free, total or largest memory using the allocation policy.
PUBLIC LONGCARD FUNC Avail(LONGCARD flags)
  HeapState POINTER state
  EXECLISTS.Node POINTER node
  HEAPCORE.MemHeader POINTER pool
  LONGCARD total,value

  IF FlagsValid(flags,1)=0 THEN
    RETURN(0)
  FI

  ValidateRegions()
  state=GetState()
  node=state.regions.lh_Head
  LET tail=EXECLISTS.Node POINTER(@state.regions.lh_Tail)
  total=0
  WHILE node<>tail DO
    pool=HEAPCORE.MemHeader POINTER(node)
    IF Matches(pool,flags)<>0 THEN
      HEAPCORE.Bounds(pool)
      IF (flags & H_FLAG_TOTAL)<>0 THEN
        value=pool.mh_Upper-LONGCARD(ADDRESS(pool.mh_Lower))

      ELSE
        IF (flags & H_FLAG_LARGEST)<>0 THEN
          value=HEAPCORE.Largest(pool,(flags & H_FLAG_LINEAR)=0)

        ELSE
          value=pool.mh_Free
        FI
      FI

      IF (flags & H_FLAG_LARGEST)<>0 THEN
        IF value>total THEN
          total=value
        FI

      ELSE
        total==+value
      FI
    FI

    node=node.ln_Succ
  OD

RETURN(total)

; Report the containing region's attributes, or zero outside the heap.
PUBLIC LONGCARD FUNC MemoryType(BYTE POINTER location)

  LET pool=Locate(location)
  IF pool=NULL THEN
    RETURN(0)
  FI

RETURN(LONGCARD(pool.mh_Attributes))

; Include the private vector prefix without overflowing the allocation size.
LONGCARD FUNC VectorBytes(LONGCARD requested)

  LET bytes=HEAPCORE.Rounded(requested)
  IF bytes=0 OR bytes>MAX_VECTOR_BYTES THEN
    RETURN(0)
  FI

RETURN(bytes+H_VECPREFIX_BYTES)

; Reserve backing storage for a vector; its wrapper initializes the prefix.
PUBLIC BYTE POINTER FUNC ReserveVector(LONGCARD byteSize LONGCARD flags)

  LET bytes=VectorBytes(byteSize)
  IF bytes=0 THEN
    RETURN(NULL)
  FI

RETURN(Reserve(bytes,flags))

; Validate the entire vector prefix and backing extent before releasing it.
PUBLIC PROC FreeVector(BYTE POINTER memoryBlock)
  VecPrefix POINTER prefix
  LONGCARD base

  IF memoryBlock=NULL THEN
    RETURN
  FI

  base=LONGCARD(ADDRESS(memoryBlock))
  IF base<H_VECPREFIX_BYTES OR (base & (H_ALIGNMENT-1))<>0 THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  base==-H_VECPREFIX_BYTES
  LET pool=Locate(BYTE POINTER(ADDRESS(base)))
  IF pool=NULL THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  ; Bounds and entire prefix extent precede every prefix read.
  IF pool.mh_Upper-base<H_VECPREFIX_BYTES THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  prefix=VecPrefix POINTER(ADDRESS(base))
  LET backing=VectorBytes(prefix.requested)
  IF backing=0 OR backing<>prefix.backing THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  IF backing>pool.mh_Upper-base THEN
    HEAPCORE.Abort(H_ERROR_POINTER)
  FI

  HEAPCORE.Deallocate(pool,BYTE POINTER(ADDRESS(base)),backing)

RETURN
