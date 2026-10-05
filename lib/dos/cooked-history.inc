; Optional fixed storage belongs to the cooked session, not inherited wrappers.
PROC FreeHistory(Session POINTER state)

  IF state.history<>NULL THEN
    EXEC.FreeMem(BYTE POINTER(state.history),HISTORY_SIZE)
    state.history=NULL
  FI

RETURN

PROC ResetHistory(Session POINTER state)

  IF state.history<>NULL THEN
    state.history.selected=0
    state.history.draftLength=0
    state.history.draftCursor=0
  FI

RETURN

BYTE POINTER FUNC HistorySlot(History POINTER history BYTE index)

RETURN(@history.entries(CARD(index)*LINE_BYTES))

; Remember one valid Return submission. Blank and adjacent duplicate lines do
; not evict an entry; slots hold original text, before LF or shell parsing.
PROC Remember(Session POINTER state)
  CARD index
  BYTE nonblank,equal,previous

  LET history=state.history
  IF history=NULL THEN
    RETURN
  FI

  IF history.enabled=0 OR state.length=0 THEN
    RETURN
  FI

  nonblank=0
  FOR index=0 TO state.length-1 DO
    IF state.line(index)<>ASCII.SPACE THEN
      nonblank=1
    FI
  OD

  IF nonblank=0 THEN
    RETURN
  FI

  IF history.count<>0 THEN
    previous=IF history.next=0 THEN HISTORY_SLOTS-1 ELSE history.next-1 FI
    BEGIN
      LET old=HistorySlot(history,previous)
      equal=old(state.length)=ASCII.NUL
      FOR index=0 TO state.length-1 DO
        IF old(index)<>state.line(index) THEN
          equal=0
        FI
      OD

      IF equal<>0 THEN
        RETURN
      FI
    END
  FI

  LET target=HistorySlot(history,history.next)
  A816MEMORY.Move(target,state.line,SIZE(state.length))
  target(state.length)=ASCII.NUL
  history.next==+1
  IF history.next=HISTORY_SLOTS THEN
    history.next=0
  FI

  IF history.count<HISTORY_SLOTS THEN
    history.count==+1
  FI

RETURN

; Browsing copies into the live line. Only the draft retains its cursor;
; recalled entries start at EOF and editing them never changes the ring.
BYTE FUNC Recall(Session POINTER state BYTE older)
  BYTE index
  CARD length
  BYTE POINTER source

  LET history=state.history
  IF history=NULL THEN
    RETURN(0)
  FI

  IF history.enabled=0 OR history.count=0 THEN
    RETURN(0)
  FI

  IF older<>0 THEN
    IF history.selected=history.count THEN
      RETURN(0)
    FI

    IF history.selected=0 THEN
      A816MEMORY.Move(history.draft,state.line,SIZE(state.length))
      history.draft(state.length)=ASCII.NUL
      history.draftLength=state.length
      history.draftCursor=state.cursor
    FI

    history.selected==+1
  ELSE
    IF history.selected=0 THEN
      RETURN(0)
    FI

    history.selected==-1
  FI

  IF history.selected=0 THEN
    length=history.draftLength
    source=history.draft
    state.cursor=history.draftCursor
  ELSE
    index=BYTE((CARD(history.next)+HISTORY_SLOTS
        -CARD(history.selected)) MOD HISTORY_SLOTS)
    source=HistorySlot(history,index)
    length=0
    WHILE length<LINE_BYTES-1 AND source(length)<>ASCII.NUL DO
      length==+1
    OD

    state.cursor=length
  FI

  A816MEMORY.Move(state.line,source,SIZE(length))
  state.length=length
  state.appendEcho=0

RETURN(1)
