"""Private selector observation offsets checked against emitted C layouts."""
FIELDS=dict(tree=0,ted=744,entries=1304,scan=1308,info=1328,indices=1588,
    path=2100,file=2228,title=2241,directory=2272,mask=2400,requested=2528,
    filter=2656,savedName=2784,labels=2892,status=3148,count=3228,first=3230,
    visible=3232,selected=3234,valid=3236,loading=3238,result=3240)
for name in FIELDS:
    if FIELDS[name]>FIELDS['scan']: FIELDS[name]+=18
SIZE=3260
FORM_SELECTOR=379
FORM_ALERT=FORM_SELECTOR-4
LAYOUT=[('Selector size',SIZE),('Form size',383),('Form selector',FORM_SELECTOR)]+[
    ('Selector '+name,offset) for name,offset in FIELDS.items()]+[
    ('FSEL_CANCEL',0),('FSEL_OK',1),('fsel_input pointer',4),('fsel_exinput pointer',4)]
