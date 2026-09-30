#!/usr/bin/env python3
"""Extend an independent fixture directory with deleted records, then have
Altirra validate and extract the result. Original file contents do not change.
"""
import hashlib,json,math,tempfile
from pathlib import Path
from make_sdfs_fixtures import Media,FIXTURES
import sdfs_reference as reference
from native_program import ROOT,require,sha256

def padded(raw):
    m=Media(raw);root=m.word(25);positions=m.entry(root,'MANY');entry=m.row(positions)
    start=int.from_bytes(entry[1:3],'little');maps,sectors=m.chain(start);sectors=[s for s in sectors if s]
    old=b''.join(bytes(m.raw[m.at(s):m.at(s)+m.size]) for s in sectors)
    length=int.from_bytes(old[3:6],'little');old=old[:length]
    require(length==301*23,'Unexpected source directory length')
    payload=bytearray(old[:-23]+(b'\x10'+bytes(22))*1110+old[-23:])
    payload[3:6]=len(payload).to_bytes(3,'little')
    bitmap=m.word(32);allocated=[]
    def allocate():
        for s in range(4,2001):
            at=m.at(bitmap+s//(m.size*8))+(s//8)%m.size;bit=0x80>>(s&7)
            if m.raw[at]&bit:
                m.raw[at]&=255^bit;allocated.append(s);return s
        raise ValueError('No free fixture sectors')
    capacity=(m.size-4)//2
    while len(sectors)<math.ceil(len(payload)/m.size):sectors.append(allocate())
    while len(maps)<math.ceil(len(sectors)/capacity):maps.append(allocate())
    for i,s in enumerate(sectors):m.raw[m.at(s):m.at(s)+m.size]=payload[i*m.size:(i+1)*m.size].ljust(m.size,b'\0')
    for i,s in enumerate(maps):
        at=m.at(s);m.raw[at:at+m.size]=bytes(m.size)
        m.put(at,maps[i+1] if i+1<len(maps) else 0);m.put(at+2,maps[i-1] if i else 0)
        for j,n in enumerate(sectors[i*capacity:(i+1)*capacity]):m.put(at+4+j*2,n)
    for at,value in zip(positions[3:6],len(payload).to_bytes(3,'little')):m.raw[at]=value
    m.put(29,m.word(29)-len(allocated))
    return bytes(m.raw),dict(directory=start,records=1411,live_entries=300,deleted_records=1110,last_ordinal=1409,length=len(payload),map_sectors=maps,data_sectors=sectors,allocated_sectors=allocated)

def produce(output):
    output.mkdir(parents=True,exist_ok=True);records=[]
    with tempfile.TemporaryDirectory() as temp:
        for size in (128,256):
            source=FIXTURES/f'sdfs-21-{size}.atr';expected_dir=Path(temp)/f'original-{size}'
            reference.extract(source,expected_dir)
            expected={p.relative_to(expected_dir).as_posix():p.read_bytes() for p in expected_dir.rglob('*') if p.is_file()}
            raw,mutation=padded(source.read_bytes());path=output/f'namespace-{size}.atr';path.write_bytes(raw)
            hashes=reference.verify(path,expected,Path(temp)/f'check-{size}')
            records.append(dict(image=path.name,sha256=sha256(path),source_sha256=sha256(source),sector_bytes=size,mutation=mutation,files=hashes))
    record=dict(schema_version=1,scope='Deleted-record insertion; independent Altirra allocation validation and complete byte extraction',producer_sha256=sha256(reference.reference()),fixtures=records)
    (output/'namespace-reference.json').write_text(json.dumps(record,indent=2)+'\n');return record
if __name__=='__main__':
    produce(FIXTURES)
