; Preserve complete source/result records for the host's independent coverage
; oracle, including the unchanged target on overflow and aliased cut storage.
PROC RegionBatches()
  CARD index,count
  BYTE POINTER input,output
  LAYERTYPES.Rect POINTER cut

  count=CARD POINTER($d4000)^
  input=BYTE POINTER($d4002)
  output=BYTE POINTER($e8010)
  FOR index=0 TO count-1 DO
    A816MEMORY.Move(BYTE POINTER(first),input,LAYERTYPES.REGION_SIZE)
    A816MEMORY.Fill(BYTE POINTER(second),$a5,LAYERTYPES.REGION_SIZE)
    cut=LAYERTYPES.Rect POINTER(input+LAYERTYPES.REGION_SIZE)
    IF input(LAYERTYPES.REGION_SIZE+LAYERTYPES.RECT_SIZE)<>0 THEN
      REGIONS.Copy(cut,@second.rects(0))
      cut=@second.rects(0)
    FI
    Require(REGIONS.Subtract(first,cut,second)
        =input(LAYERTYPES.REGION_SIZE+LAYERTYPES.RECT_SIZE+1))
    A816MEMORY.Move(output,BYTE POINTER(first),LAYERTYPES.REGION_SIZE)
    A816MEMORY.Move(output+LAYERTYPES.REGION_SIZE,
        BYTE POINTER(second),LAYERTYPES.REGION_SIZE)
    input==+LAYERTYPES.REGION_SIZE+LAYERTYPES.RECT_SIZE+2
    output==+LAYERTYPES.REGION_SIZE*2
  OD

RETURN
