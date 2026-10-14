"""Private desktop observation offsets, checked by an emitted C layout probe."""
SIZE=2128
FIELDS=dict(ready=8,folders=10,active=22,source=26,popup=30,stock=34,bar=38,
    tree=758,icons=974,children=1212,result=1224,message=1232,work=1248,
    input=1256,output=1278,mx=1392,my=1394,mb=1396,ks=1398,kr=1400,br=1402,
    down=1404,armed=1406,clicks=1408,selected=1410,installed=1412,quit=1414,
    launches=1416,paints=1420,status=1424,job=1489,associations=1493,
    saved=1629,savedCount=2049,mouse=2051,defaultIcons=2053,defaultSort=2055,
    settingsLoaded=2057,error=2059,publishedStatus=2063)
for name in FIELDS:
    if FIELDS[name]>FIELDS['bar']:FIELDS[name]+=48
SIZE+=48
for name in FIELDS:
    if FIELDS[name]>FIELDS['icons']:FIELDS[name]+=28
SIZE+=28
FIELDS["drag"]=SIZE
DRAG_SIZE=148
DRAG_FIELDS=dict(phase=0,source=2,target=4,entry=6,pressX=8,pressY=10,lastX=12,lastY=14,hover=16,held=18,destination=20)
SIZE+=DRAG_SIZE
# One additional desktop OBJECT and CICONBLK for RAM:.
for name in FIELDS:
    if FIELDS[name]>FIELDS['tree']:FIELDS[name]+=24
for name in FIELDS:
    if FIELDS[name]>FIELDS['icons']:FIELDS[name]+=38
SIZE+=62
# About adds one menu OBJECT; the remaining model stays application-owned.
for name in FIELDS:
    if FIELDS[name]>FIELDS['bar']:FIELDS[name]+=24
SIZE+=24
ICONS=8
JOB_SIZE=974
JOB_FIELDS=dict(owner=0,input=4,output=8,copied=12,error=16,cleanupError=20,
    operation=24,state=26,index=28,total=30,completed=32,skipped=34,replacing=36,
    temporaryOwned=38,keepComplete=40,pending=42,source=74,target=330,temporary=586,
    destination=842,buffer=970)
LAYOUT=[('Desktop size',SIZE)]+[('Desktop '+n,v) for n,v in FIELDS.items()]+[
    ('Job size',JOB_SIZE)]+[('Job '+n,v) for n,v in JOB_FIELDS.items()]

LAYOUT+=[("Drag size",DRAG_SIZE)]+[("Drag "+n,v) for n,v in DRAG_FIELDS.items()]
