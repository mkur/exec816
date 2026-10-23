"""Wrap the canonical combined XEX in an independently located boot reader."""
import hashlib
import json
from pathlib import Path
import struct

from build_bootable_atr import compile_reader,check_layout,phase_budget

ROOT=Path(__file__).resolve().parents[1]
ABI=json.loads((ROOT/'abi/boot-sio.json').read_text())
INPUTS=('abi/boot-sio.json','tools/build_boot_fast.py','tools/build_bootable_atr.py',
        'platform/altirraos/disk-boot-reader.s','platform/altirraos/boot-xex.inc',
        'platform/altirraos/boot-takeover.inc','platform/altirraos/boot-sio.inc',
        'platform/altirraos/boot-sio-policy.inc')


def segment(address,data):
    return struct.pack('<HH',address,address+len(data)-1)+data


def wrap(canonical,target,output,monitor,policy='auto',loader_address=0x6f00,native_divisor=8,callbacks=None,options=None):
    canonical,target,output=map(Path,(canonical,target,output))
    if native_divisor not in (8,40):raise ValueError('Unsupported native handoff divisor')
    if callbacks is not None and len(callbacks)>3:raise ValueError('Too many local callbacks')
    raw=canonical.read_bytes()
    check_layout(canonical,monitor)
    if policy not in ABI['policies']:raise ValueError('Invalid boot SIO policy')
    r=compile_reader(output,fast=True,backend=1,options=options)
    labels=r['disk-boot-reader.s']['labels']
    reader=bytearray((output/'disk-boot-reader.bin').read_bytes())
    prefix=b'\xff\xff'+segment(loader_address,bytes([0x4c])+struct.pack('<H',loader_address))
    prefix+=segment(0x2e0,struct.pack('<H',loader_address))
    descriptor_offset=len(prefix)+4+labels['take_descriptor']-ABI['reader_address']
    payload_offset=len(prefix)+4+len(reader)+6
    if len(raw)+payload_offset>0xffffff:raise ValueError('Wrapped XEX exceeds 24-bit file size')
    descriptor=bytearray(ABI['descriptor']['size']);f=ABI['descriptor']['fields']
    descriptor[:4]=ABI['descriptor']['magic'].encode()
    descriptor[4:8]=bytes([ABI['version'],ABI['policies'][policy],1,native_divisor])
    for name,value in [('payload_offset',payload_offset),('payload_size',len(raw)),('descriptor_offset',descriptor_offset)]:
        descriptor[f[name]:f[name]+3]=value.to_bytes(3,'little')
    descriptor[f['identity']:f['identity']+16]=hashlib.sha256(raw).digest()[:16]
    struct.pack_into('<H',descriptor,f['monitor_entry'],monitor['labels']['of_start'] if monitor else 0)
    for i,address in enumerate(monitor.get('local_callbacks',[]) if monitor else (callbacks or [])):
        struct.pack_into('<H',descriptor,f['local_callbacks']+2*i,address)
    start=labels['take_descriptor']-ABI['reader_address']
    reader[start:start+len(descriptor)]=descriptor
    prefix+=segment(ABI['reader_address'],reader)+segment(0x2e2,struct.pack('<H',labels['reader_start']))
    assert len(prefix)==payload_offset==ABI['prefix_bytes']
    target.write_bytes(prefix+raw)
    result=dict(format=ABI['format'],policy=policy,canonical_sha256=hashlib.sha256(raw).hexdigest(),
                xex_sha256=hashlib.sha256(target.read_bytes()).hexdigest(),canonical_bytes=len(raw),
                prefix_bytes=len(prefix),descriptor=descriptor.hex(),descriptor_offset=descriptor_offset,
                labels=labels,used_bytes=labels['reader_end']-ABI['reader_address']+ABI['guard_bytes'],
                reserved_bytes=ABI['reader_bytes'],memory=phase_budget(monitor) if monitor else None,
                inputs={n:hashlib.sha256((ROOT/n).read_bytes()).hexdigest() for n in INPUTS})
    (output/'boot-sio.json').write_text(json.dumps(result,indent=2)+'\n')
    return result
