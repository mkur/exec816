; Root turns presenter events into its own bounded ordinary control messages.
; Each close has a separate lane, so a pending CREATE/SELECT cannot block it.
ShellSessionMessage ARRAY tabRequests(4)
DESKTYPES.TabSnapshot tabSnapshot
DESKTYPES.Event tabEvent
LONGCARD tabSelection
BYTE tabBusy

BYTE FUNC ShellTabReply(ShellSessionMessage POINTER request)
  BYTE index

  IF request.message.mn_Node.ln_Type<>EXEC.NT_REPLYMSG THEN
    RETURN(0)
  FI

  FOR index=0 TO 3 DO
    IF request=@tabRequests(index) THEN
      tabBusy=tabBusy & (BYTE(1 LSH index) XOR $ff)
      RETURN(1)
    FI
  OD

RETURN(0)

PROC ShellTabRequest(BYTE index,operation LONGCARD identity)

  IF (tabBusy & BYTE(1 LSH index))<>0 THEN
    RETURN
  FI

  LET request=@tabRequests(index)
  request.operation=operation
  request.session=identity
  request.payload=BYTE POINTER(c"SYS:")
  request.capacity=SESSION_PATH_BYTES
  request.message.mn_Node.ln_Type=EXEC.NT_MESSAGE
  request.message.mn_ReplyPort=shellRequests
  request.message.mn_Length=SHELLSESSIONMESSAGE_SIZE
  tabBusy=tabBusy OR BYTE(1 LSH index)
  EXEC.PutMsg(shellRequests,@request.message)

RETURN

PROC ShellTabsStep()
  BYTE index,changed
  ShellSession POINTER session

  IF DESKSTATE.Enabled()=0 THEN
    RETURN
  FI

  IF DESKBOOT.TakeEvent(@tabEvent)<>0 THEN
    CASE tabEvent.kind OF
    WHEN DESKTYPES.EVENT_TAB_NEW THEN
      IF controllerLive<SESSION_CAPACITY THEN
        ShellTabRequest(0,SESSION_CREATE,0)
      FI

    WHEN DESKTYPES.EVENT_TAB_SELECT THEN
      tabSelection=tabEvent.route

    WHEN DESKTYPES.EVENT_TAB_CLOSE THEN
      session=ShellSessionFind(tabEvent.route)
      IF session<>NULL THEN
        index=0
        IF session=@sessions(1) THEN
          index=1
        FI
        ShellTabRequest(index+2,SESSION_CLOSE,tabEvent.route)
      FI
    ESAC
  FI

  IF tabSelection<>0 AND (tabBusy & 2)=0 AND selectionRequest=NULL THEN
    session=ShellSessionFind(tabSelection)
    IF session<>NULL AND session.state=SESSION_STATE_READY THEN
      ShellTabRequest(1,SESSION_SELECT,tabSelection)
    FI
    tabSelection=0
  FI

  FOR index=0 TO SESSION_CAPACITY-1 DO
    BEGIN
      LET entry=@tabSnapshot.entries(index)
      session=@sessions(index)
      entry.identity=0
      entry.state=0
      entry.selected=0
      entry.busy=0
      IF session.state<>SESSION_STATE_FREE THEN
        entry.identity=session.control.identity
        entry.state=session.state
        entry.selected=entry.identity=selectedSession
        entry.busy=desktopPending<>0 AND desktopTarget=entry.identity
      FI
    END
  OD

  tabSnapshot.newEnabled=controllerLive<SESSION_CAPACITY AND (tabBusy & 1)=0
  changed=DESKBOOT.SetTabs(@tabSnapshot)

RETURN
