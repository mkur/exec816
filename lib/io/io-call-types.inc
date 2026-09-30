; Guarded packets use the current compiler's native argument offsets.
TYPE IOOpenArgs=[
  BYTE POINTER name
  LONGCARD unit
  IORequest POINTER request
  LONGCARD flags
]

TYPE IOPointerArgs=[IORequest POINTER request]
TYPE IOResident=[
  CARD opens
  BYTE unit
]

TYPE IOQueue=[
  EXECLISTS.List pending
  IORequest POINTER active
  BYTE phase
  BYTE cancelled
  TaskControl POINTER worker
  LONGCARD mask
]
