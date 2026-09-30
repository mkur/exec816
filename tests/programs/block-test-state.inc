TYPE TestState=[
  CARD calls
  BYTE fault,pad
  BLOCKTYPES.Adapter POINTER adapter
  BYTE pad2
  BLOCKTYPES.Volume POINTER volume
  PROC POINTER probe()
]
