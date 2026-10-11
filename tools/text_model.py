"""Private viewer offsets, checked against emitted C constants."""
FIELDS=dict(ready=8,first=10,rows=12,columns=14,dirty=24,work=32,document=416,
    load=558,path=975,file=1103,status=1500,paints=1662,loads=1666,interruptions=1670)
SIZE=1678
LOAD_PHASE=410
LAYOUT=[('TextApp size',SIZE),('TextDocument size',142),('TextLoad size',417)]+[
    ('TextApp '+key,value) for key,value in FIELDS.items()]+[('TextLoad phase',LOAD_PHASE)]
