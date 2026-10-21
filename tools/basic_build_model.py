"""Private workbench observation offsets, checked by emitted C layout."""
SIZE=2415
FIELDS=dict(phase=0,job=20,child=28,unit=32,caret=44,cause=92,
    compilerResult=100,programResult=108,diagnostic=116,window=340,source=342,target=482)
LAYOUT=[('Build job size',SIZE)]+[('Build '+n,v) for n,v in FIELDS.items()]
STAGES=dict(choose=1,reserve=2,retry_names=3,snapshot=4,write_source=5,close_source=6,
    load_compiler=7,compiler=8,diagnostic=9,load_program=10,program=11,read_binary=12,publish=13,retire=14)
