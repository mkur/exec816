; APT helpers operate on the one controller buffer; no table cache is retained.
LONGCARD FUNC TableLong(BYTE POINTER bytes CARD offset)

RETURN(LONGCARD(bytes(offset)) OR (LONGCARD(bytes(offset+1)) LSH 8)
    OR (LONGCARD(bytes(offset+2)) LSH 16) OR (LONGCARD(bytes(offset+3)) LSH 24))
; Publish only supported active DOS mappings with bounded physical extents.
BYTE FUNC PartitionEntry(BYTE number BYTE POINTER entry LONGCARD low,high)
  CARD offset,id
  LONGCARD start,count

  LET partition=UnitAt(number)
  IF entry(0)=0 OR (entry(0) & $80)<>0 OR entry(1)<>0
      OR (entry(12) & $40)=0 THEN
    RETURN(1)
  FI
  IF (entry(0) & $0f)<>3 THEN
    RETURN(1)
  FI
  id=CARD(entry(10)) OR (CARD(entry(11)) LSH 8)
  start=TableLong(entry,2)
  count=TableLong(entry,6)
  offset=CARD(entry(14)) OR (CARD(entry(15)) LSH 8)
  IF id=0 OR id=$ffff OR start=0 OR start<low OR start>=high
      OR count=0 OR count>high-start OR LONGCARD(offset)>=count THEN
    RETURN(0)
  FI
  partition.number=number
  partition.bytes=512
  partition.start=start+LONGCARD(offset)
  partition.physical=count-LONGCARD(offset)
  partition.sectors=partition.physical
  partition.flags=entry(12) & $80
  IF (entry(0) & $30)<>0 OR (entry(12) & $3f)<>0 OR entry(13)<>0 THEN
    partition.flags=$80
  FI
  partition.reserved=entry(0) & $40
  partition.offset=offset
  partition.enabled=1

RETURN(1)

; Include a metadata leader in exclusion checks without exposing it as data.
LONGCARD FUNC ExtentStart(Partition POINTER partition)

RETURN(partition.start-LONGCARD(partition.offset)-LONGCARD(partition.reserved<>0))

; Decode the low-byte table variant in place before parsing 16-byte entries.
BYTE FUNC ReadTable(LONGCARD sector BYTE even)
  CARD index

  LET error=ReadPhysical(sector)
  LET c=Control()
  IF error<>0 THEN
    c.error=error
    RETURN(0)
  FI
  IF even<>0 THEN
    FOR index=0 TO 255 DO
      c.buffer(index)=c.buffer(index LSH 1)
    OD
  FI

RETURN(1)

; Discover only fifteen mapping slots, with at most sixteen linked headers.
BYTE FUNC DiscoverPartitions()
  LONGCARD low,high,sector,previous,next,count
  LONGCARD ARRAY visited(16)
  BYTE even,headerOffset,nextOffset,previousOffset,number,links,index,entries,limit
  CARD position
  BYTE POINTER header

  LET c=Control()
  low=0
  high=c.physical
  IF ReadTable(0,0)=0 THEN
    RETURN(0)
  FI
  even=0
  IF (c.buffer(0) & $80)<>0 AND c.buffer(2)=$41
      AND c.buffer(4)=$50 AND c.buffer(6)=$54 THEN
    even=1
  ELSEIF c.buffer(1)<>$41 OR c.buffer(2)<>$50 OR c.buffer(3)<>$54 THEN
    IF c.buffer(510)<>$55 OR c.buffer(511)<>$aa THEN
      RETURN(0)
    FI
    ; One protective $7F container; addresses in its APT remain absolute.
    FOR index=0 TO 3 DO
      position=446+CARD(index)*16
      IF c.buffer(position+4)=$7f THEN
        IF low<>0 THEN
          RETURN(0)
        FI
        low=TableLong(c.buffer,position+8)
        count=TableLong(c.buffer,position+12)
        IF low=0 OR low>=c.physical OR count=0 OR count>c.physical-low THEN
          RETURN(0)
        FI
        high=low+count
      FI
    OD
    IF low=0 OR ReadTable(low,0)=0 THEN
      RETURN(0)
    FI
    IF (c.buffer(0) & $80)<>0 THEN
      even=1
    FI
  FI
  sector=low
  previous=0
  previousOffset=0
  headerOffset=0
  number=1
  links=0
  WHILE number<=15 DO
    IF links>=16 OR sector<low OR sector>=high THEN
      RETURN(0)
    FI
    IF links<>0 THEN
      FOR index=0 TO links-1 DO
        IF visited(index)=sector THEN
          RETURN(0)
        FI
      OD
    FI
    visited(links)=sector
    links==+1
    IF ReadTable(sector,even)=0 THEN
      RETURN(0)
    FI
    limit=32
    IF even<>0 THEN
      limit=16
    FI
    IF headerOffset>=limit THEN
      RETURN(0)
    FI
    position=CARD(headerOffset)*16
    header=c.buffer+SIZE(position)
    entries=header(5)
    IF entries<2 OR entries>limit-headerOffset THEN
      RETURN(0)
    FI
    IF links=1 THEN
      IF header(1)<>$41 OR header(2)<>$50 OR header(3)<>$54
          OR (header(0) & $6f)<>0 THEN RETURN(0) FI
    ELSEIF (header(1)<>0 OR header(2)<>0 OR header(3)<>0)
        AND (header(1)<>$41 OR header(2)<>$50 OR header(3)<>$54) THEN RETURN(0)
    FI
    IF TableLong(header,12)<>previous OR header(7)<>previousOffset THEN
      RETURN(0)
    FI
    next=TableLong(header,8)
    nextOffset=header(6)
    IF nextOffset>=limit THEN
      RETURN(0)
    FI
    FOR index=1 TO entries-1 DO
      IF number<=15 THEN
        IF PartitionEntry(number,header+SIZE(CARD(index)*16),low,high)=0 THEN
          RETURN(0)
        FI
        number==+1
      FI
    OD
    IF number<=15 AND next=0 THEN
      RETURN(0)
    FI
    previous=sector
    previousOffset=headerOffset
    sector=next
    headerOffset=nextOffset
  OD
  ; Reject mapped data overlapping a visited table sector or another mapping.
  FOR number=1 TO 15 DO
    BEGIN
      LET a=UnitAt(number)
      IF a.enabled<>0 THEN
        FOR index=0 TO links-1 DO
          IF visited(index)>=ExtentStart(a)
              AND visited(index)<a.start+a.physical THEN RETURN(0) FI
        OD
        IF number<15 THEN
          FOR index=number+1 TO 15 DO
            BEGIN
              LET b=UnitAt(index)
              IF b.enabled<>0 AND ExtentStart(a)<b.start+b.physical
                  AND ExtentStart(b)<a.start+a.physical THEN RETURN(0) FI
            END
          OD
        FI
      FI
    END
  OD

RETURN(1)
