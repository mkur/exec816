"""Host-only metadata fixture edits on an independently produced SDFS disk."""
from filesystem_audit import Audit, word
from sector_images import ATRImage


def attributes(path, values):
    original=path.read_bytes()
    before=Audit(original);before.sdfs()
    image=ATRImage(original)
    page=word(image.sector(1),9);sectors=[];seen=set()
    while page:
        assert page not in seen
        seen.add(page)
        data=image.sector(page)
        sectors.extend(word(data,i) for i in range(4,image.size,2) if word(data,i))
        page=word(data,0)
    directory=b''.join(image.sector(s) for s in sectors)
    length=int.from_bytes(directory[3:6],'little')
    changed={}
    for offset in range(23,length,23):
        row=directory[offset:offset+23]
        name=row[6:14].decode().rstrip()
        suffix=row[14:17].decode().rstrip()
        if suffix:name+='.'+suffix
        if name in values:
            assert values[name]&~7==0 and row[0]&0xf8==8
            at=image.offset(sectors[offset//image.size])+offset%image.size
            image.data[at]=(row[0]&~7)|values[name]
            changed[name]=image.data[at]
    assert changed.keys()==values.keys(),changed
    after=Audit(bytes(image.data));after.sdfs()
    assert after.files==before.files
    path.write_bytes(image.data)
    return changed
