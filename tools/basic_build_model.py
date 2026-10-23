"""Private workbench observation offsets, checked by emitted C layout."""
SIZE=2543
FIELDS=dict(phase=0,job=20,child=28,unit=32,caret=44,cause=92,
    compilerResult=100,programResult=108,diagnostic=116,interpreterResult=340,
    window=468,source=470,target=610)
RESIDENT_FIELDS=dict(image=0,child=4,channel=12,request=32)
LAYOUT=[('Build job size',SIZE)]+[('Build '+n,v) for n,v in FIELDS.items()]+[('Interpreter session size',86)]+[('Interpreter '+n,v) for n,v in RESIDENT_FIELDS.items()]
STAGES=dict(choose=1,reserve=2,retry_names=3,snapshot=4,write_source=5,close_source=6,
    load_compiler=7,compiler=8,diagnostic=9,load_program=10,program=11,read_binary=12,publish=13,retire=14,
    prepare_run=15,load_interpreter=16,wait_interpreter=17,close_interpreter=18)
