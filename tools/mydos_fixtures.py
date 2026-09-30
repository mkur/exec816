"""Host ATR containers and independent known-content fixture oracle.

Expected bytes come from producer jobs and original MyDOS CIO read-back, not
from this chain extractor or the new Action! parser. Extraction cross-checks
those known bytes and records original directory fields for metadata tests.
"""
import hashlib,json
from pathlib import Path
from native_program import ROOT,require,sha256
FIXTURES=ROOT/'tests/fixtures/mydos'

class Image:
    def __init__(self,data):
        self.data=bytearray(data)
        require(len(data)>=16 and data[:2]==b'\x96\x02','Not an ATR')
        self.size=int.from_bytes(data[4:6],'little')
        require(self.size in (128,256),'Unsupported sector size')
        require(len(data)-16==16*(int.from_bytes(data[2:4],'little')+(int.from_bytes(data[6:8],'little')<<16)),'ATR length mismatch')
        require((len(data)-16-384)%self.size==0,'Incomplete ATR sector')
        self.count=3+(len(data)-16-384)//self.size
    def offset(self,sector):
        require(1<=sector<=self.count,'Out-of-range fixture sector')
        return 16+(sector-1)*128 if sector<=3 else 16+384+(sector-4)*self.size
    def sector(self,sector):
        at=self.offset(sector);return bytes(self.data[at:at+(128 if sector<=3 else self.size)])
    def entries(self,directory=361):
        for ordinal in range(64):
            e=self.sector(directory+ordinal//8)[16*(ordinal%8):16*(ordinal%8+1)]
            if not e[0]:break
            if e[0]&0x81:continue
            name=e[5:13].decode('ascii').rstrip()+(('.'+e[13:16].decode('ascii').rstrip()) if e[13:16]!=b'   ' else '')
            yield dict(name=name,flags=e[0],count=int.from_bytes(e[1:3],'little'),start=int.from_bytes(e[3:5],'little'),ordinal=ordinal,parent=directory)
    def walk(self,directory=361,prefix=''):
        for entry in self.entries(directory):
            entry['path']=prefix+entry['name'];yield entry
            if entry['flags']&16:yield from self.walk(entry['start'],entry['path']+'/')
    def file(self,entry):
        sector=entry['start'];seen=[];payload=bytearray()
        while sector:
            require(sector not in seen and len(seen)<self.count,'Cyclic oracle input')
            seen.append(sector);data=self.sector(sector);high,low,used=data[-3:]
            require(used<=len(data)-3,'Bad oracle payload count')
            if not entry['flags']&4:require(high>>2==entry['ordinal'],'Bad oracle ordinal')
            sector=((high if entry['flags']&4 else high&3)<<8)|low;payload+=data[:used]
        require(len(seen)==entry['count'],'Original directory/chain count disagreement')
        return bytes(payload),seen

def publish():
    from mydos_producer import ORIGINAL_URL,ORIGINAL_SHA256
    volumes=[]
    for size in (128,256):
        directory=ROOT/f'build/dos-slice5/producer{size}'
        producer=json.loads((directory/'results.json').read_text())
        require(producer['status']=='pass','Original MyDOS did not finish read-back')
        source=directory/'volume.atr';require(sha256(source)==producer['media_sha256'],'Changed producer output')
        target=FIXTURES/f'mydos450-{size}.atr';target.write_bytes(source.read_bytes())
        image=Image(target.read_bytes());entries=list(image.walk());files=[]
        jobs={j['name'][3:].replace(':','/'):j for j in producer['jobs'] if j['op']==3}
        for entry in entries:
            if entry['flags']&16:continue
            data,chain=image.file(entry);job=jobs[entry['path']]
            expected=bytes((i&255)^job['seed'] for i in range(job['size']))
            require(data==expected,'Original read-back/oracle mismatch: '+entry['path'])
            files.append(dict(entry,bytes=len(data),sha256=hashlib.sha256(data).hexdigest(),seed=job['seed'],chain=chain))
        require(len(list(image.entries()))==64,'Producer did not fill root directory')
        volumes.append(dict(path=str(target.relative_to(ROOT)),sha256=sha256(target),sector_bytes=size,sectors=image.count,vtoc=image.sector(360)[:10].hex(),entries=entries,files=files,producer=producer))
    manifest=dict(schema_version=1,producer_version='MyDOS 4.50',original_url=ORIGINAL_URL,original_sha256=ORIGINAL_SHA256,source_reference=dict(url='https://atariwiki.org/wiki/attach/MyDOS/Mydos451.zip',sha256='ca9a6ef43d6e12c44c965faf31ec092001c15c2eefcff2c45a62faea1ffb5724',scope='Authors’ 4.51 format source used by design; the executable fixture producer is pinned separately at 4.50'),oracle='Every file written and read back byte-for-byte through original MyDOS CIO. Expected bytes/lengths are the producer jobs; host extraction independently agrees.',producer_tool_sha256=sha256(ROOT/'tools/mydos_producer.py'),volumes=volumes)
    (FIXTURES/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');return manifest
if __name__=='__main__':
    publish();print('Original MyDOS fixtures and independent expected contents verified')
