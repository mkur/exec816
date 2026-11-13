"""Common external Widget decoder for the 65816 and 68000 targets."""
from widget_model import FIELDS,SIZE


def widget_state(raw,byteorder):
    if len(raw)!=SIZE:raise ValueError('Incomplete Widget model')
    result={key:int.from_bytes(raw[offset:offset+(4 if key in ('actions','paints') else 2)],
                              byteorder,signed=key=='window')
            for key,offset in FIELDS.items() if key in ('id','window','opened','ready','actions','paints')}
    result['work']=[int.from_bytes(raw[FIELDS['work']+i:FIELDS['work']+i+2],byteorder,signed=True)
                    for i in (0,2,4,6)]
    result['label']=raw[FIELDS['label']:FIELDS['label']+16].split(b'\0')[0].decode('ascii')
    result['selected']=int.from_bytes(raw[FIELDS['tree']+2*24+10:FIELDS['tree']+2*24+12],byteorder)&1
    return result
