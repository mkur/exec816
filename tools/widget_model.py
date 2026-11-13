"""Private shared Widget storage, checked against the emitted C layout."""
FIELDS=dict(id=0,window=2,opened=4,ready=6,actions=8,paints=12,message=16,
            work=32,tree=40,label=136)
SIZE=290
LAYOUT=[('Widget bytes',SIZE),*[(name,offset) for name,offset in FIELDS.items()]]
