"""Private dialog-demo observations checked against emitted C constants."""
FIELDS=dict(ready=8,phase=10,accepted=12,paints=16,interruptions=20,work=40,
    home=184,text=812,path=848,file=976,directory=989,selection=1029,fileButton=1069,fileResult=1071)
LAYOUT=[('Dialog size',1073)]+[('Dialog '+name,offset) for name,offset in FIELDS.items()]
