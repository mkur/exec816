; Match one directory entry against a bounded final-component pattern.
BYTE FUNC PatternUpper(BYTE value)

RETURN(IF value>='a AND value<='z THEN value-32 ELSE value FI)

BYTE FUNC PatternMatch(CSTRING pattern,name)
  CARD at,position,star,retry

  at=0
  position=0
  star=$ffff
  retry=0
  WHILE name(position)<>ASCII.NUL DO
    IF pattern(at)='* THEN
      star=at
      at==+1
      retry=position
    ELSEIF pattern(at)='? OR (pattern(at)<>ASCII.NUL AND
        PatternUpper(pattern(at))=PatternUpper(name(position))) THEN
      at==+1
      position==+1
    ELSEIF star<>$ffff THEN
      retry==+1
      position=retry
      at=star+1
    ELSE
      RETURN(0)
    FI
  OD

  WHILE pattern(at)='* DO
    at==+1
  OD

RETURN(BYTE(pattern(at)=ASCII.NUL))
