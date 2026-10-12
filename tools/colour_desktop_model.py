"""Private desktop observation offsets, checked by an emitted C layout probe."""
SIZE=2128
FIELDS=dict(ready=8,folders=10,active=22,source=26,popup=30,stock=34,bar=38,
    tree=758,icons=974,children=1212,result=1224,message=1232,work=1248,
    input=1256,output=1278,mx=1392,my=1394,mb=1396,ks=1398,kr=1400,br=1402,
    down=1404,armed=1406,clicks=1408,selected=1410,installed=1412,quit=1414,
    launches=1416,paints=1420,status=1424,copy=1489,associations=1493,
    saved=1629,savedCount=2049,mouse=2051,defaultIcons=2053,defaultSort=2055,
    settingsLoaded=2057,error=2059,publishedStatus=2063)
COPY_SIZE=17174
COPY_FIELDS=dict(owner=0,input=4,output=8,copied=12,error=16,replacing=20,
    source=22,target=278,temporary=534,buffer=790)
LAYOUT=[('Desktop size',SIZE)]+[('Desktop '+n,v) for n,v in FIELDS.items()]+[
    ('Copy size',COPY_SIZE)]+[('Copy '+n,v) for n,v in COPY_FIELDS.items()]
