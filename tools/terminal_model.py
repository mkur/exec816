"""Private terminal observations checked by an emitted C layout probe."""
SIZE=5853
SESSION_SIZE=1316
FIELDS=dict(paints=14,work=18,sessions=306,replies=5704,wake=5708,wakeBit=5846,directoryWatch=5847,metadataDirty=5851,retry=5852)
SESSION_FIELDS=dict(damageRows=20,width=24,column=28,mode=32,cells=36)
LAYOUT=[('Terminal bytes',SIZE)]+[('Terminal '+n,v) for n,v in FIELDS.items()]+[
    ('Terminal session bytes',SESSION_SIZE)]+[('Terminal session '+n,v) for n,v in SESSION_FIELDS.items()]
