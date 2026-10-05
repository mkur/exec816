; Shared command policy; all filesystem operations use checked COMMAND imports.
USE COMMAND
USE ASCII

; Required arguments can still contain an explicitly quoted empty name.
BYTE FUNC CommandName(ADDRESS value)

  IF value=0 THEN
    COMMAND.SetIoErr(COMMAND.ERROR_REQUIRED_ARG_MISSING)
    RETURN(0)
  FI

  LET name=BYTE POINTER(value)
  IF name(0)=ASCII.NUL THEN
    COMMAND.SetIoErr(COMMAND.ERROR_INVALID_COMPONENT_NAME)
    RETURN(0)
  FI

RETURN(1)

; Mutations start only after validation and the ordinary command BREAK check.
BYTE FUNC CommandReady()

  IF COMMAND.BreakPending()<>0 THEN
    COMMAND.SetIoErr(COMMAND.ERROR_BREAK)
    RETURN(0)
  FI

RETURN(1)
