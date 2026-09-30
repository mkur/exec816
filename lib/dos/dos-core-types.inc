; Private upper-RAM side entry. Sixteen reserved bytes per execution slot.
PUBLIC TYPE DosSlot=[
  BYTE POINTER context
  EXEC.Task POINTER owner
  LONGINT error
  BYTE active
  BYTE POINTER objects
]
