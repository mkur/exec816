"""Private sample observation layout, verified against emitted C."""
SIZE=240
FIELDS=dict(ready=6,scrolls=8,shifts=12,roundtrips=16,running=20,left=22,first=24,work=26)
LAYOUT=[('Raster sample size',SIZE),*[(name,offset) for name,offset in FIELDS.items()]]
