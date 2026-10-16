"""Scanner observation offsets, checked in the emitted Browser layout probe."""
SIZE=38
FIELDS=dict(error=16,batch=20,buffered=24,next=26,terminal=28,currentSize=32,currentFlags=36)
LAYOUT=[("FileScan size",SIZE)]+[("FileScan "+name,offset) for name,offset in FIELDS.items()]
