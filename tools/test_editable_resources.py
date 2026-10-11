"""Independent classic RSC fixtures for writable TEDINFO admission."""
import struct


def cases():
    # Two OBJECTs, one TEDINFO, one tree pointer, then separately sized strings.
    object_at,ted_at,tree_at,text_at=36,84,112,116
    text=b'2B\0'+bytes(9);template=b'__-__\0';valid=b'9A\0'
    size=text_at+len(text)+len(template)+len(valid)
    header=[0,object_at,ted_at,0,0,0,text_at,0,0,tree_at,2,1,1,0,0,0,0,size]
    root=struct.pack('>hhhHHHIHHHH',-1,1,1,20,0,0,0x1170,0,0,20,10)
    field=struct.pack('>hhhHHHIHHHH',0,-1,-1,30,8|32,0,ted_at,1,1,8,2)
    ted=struct.pack('>IIIhhhhhhhh',text_at,text_at+12,text_at+18,3,0,0,0x1180,0,-1,12,6)
    payload=struct.pack('>18H',*header)+root+field+ted+struct.pack('>I',object_at)+text+template+valid
    result={'EDIT.RSC':payload}
    for name,capacity in [('EDCAP.RSC',129),('EDEXT.RSC',128)]:
        bad=bytearray(payload);struct.pack_into('>H',bad,ted_at+24,capacity);result[name]=bytes(bad)
    bad=bytearray(payload);bad[text_at:text_at+12]=b'x'*12;result['EDNUL.RSC']=bytes(bad)
    bad=bytearray(payload);struct.pack_into('>H',bad,36+24+6,26);result['EDTYPE.RSC']=bytes(bad)
    return result
