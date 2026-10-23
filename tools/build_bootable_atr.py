#!/usr/bin/env python3
"""Build a single SDFS disk booting the unchanged combined OF816/kernel XEX."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile

from make_data_disk import make
from sector_images import ATRImage
import sdfs_reference

ROOT = Path(__file__).resolve().parents[1]
ABI_PATH = ROOT/'abi/boot-atr.json'
ABI = json.loads(ABI_PATH.read_text())
SOURCES = ('disk-boot-first.s', 'disk-boot-reader.s')
SIO_ABI=json.loads((ROOT/'abi/boot-sio.json').read_text())


def require(ok, message):
    if not ok:
        raise ValueError(message)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def compile_reader(output,fast=False,backend=0,options=None):
    output.mkdir(parents=True, exist_ok=True)
    constants = {name.upper(): value for name, value in ABI.items() if type(value) is int}
    constants.update({'LOC_'+name.upper(): value for name, value in ABI['locator_fields'].items()})
    (output/'boot-atr.inc').write_text(''.join(f'{k} = ${v:x}\n' for k,v in constants.items()))
    definitions=dict(DEADLINE_FRAMES=SIO_ABI['deadline_frames'],RESYNC_ATTEMPTS=SIO_ABI['resync_attempts'],
                     DESC_SIZE=SIO_ABI['descriptor']['size'],VERSION=SIO_ABI['version'],
                     PREFIX_READER_OFFSET=SIO_ABI['prefix_reader_offset'],PREFIX_BYTES=SIO_ABI['prefix_bytes'])
    definitions.update({'DESC_'+k.upper():v for k,v in SIO_ABI['descriptor']['fields'].items()})
    (output/'boot-sio-defs.inc').write_text('; Generated from abi/boot-sio.json.\n'+''.join(f'BS_{k} = {v}\n' for k,v in definitions.items()))
    records = {}
    for name, address, size in zip(SOURCES, (ABI['boot_address'], ABI['reader_address']),
                                  (ABI['boot_bytes'], ABI['reader_bytes'])):
        prefix = output/Path(name).stem
        prefix.with_suffix('.cfg').write_text(
            f'MEMORY {{ RAM: start=${address:x}, size=${size:x}, file=%O; }}\n'
            'SEGMENTS { CODE: load=RAM, type=rw, align=$100; }\n')
        subprocess.run(['ca65', '-D',f'BOOT_FAST={int(fast)}','-D',f'BOOT_BACKEND={backend}',*[a for k,v in (options or {}).items() for a in ('-D',f'{k}={v}')], '-I', str(output), '-I', str(ROOT/'platform/altirraos'), '-o', str(prefix.with_suffix('.o')),
                        '-l', str(prefix.with_suffix('.lst')),
                        str(ROOT/'platform/altirraos'/name)], check=True)
        subprocess.run(['ld65', '-C', str(prefix.with_suffix('.cfg')),
                        '-o', str(prefix.with_suffix('.bin')), '-Ln', str(prefix.with_suffix('.lbl')),
                        str(prefix.with_suffix('.o'))], check=True)
        records[name] = dict(bytes=prefix.with_suffix('.bin').stat().st_size,
            sha256=digest(prefix.with_suffix('.bin')),
            labels={parts[2].lstrip('.'): int(parts[1],16)
                    for line in prefix.with_suffix('.lbl').read_text().splitlines()
                    if len(parts := line.split()) == 3})
        require(records[name]['bytes']==size, 'Boot image does not fill its declared reservation')
    require(records[SOURCES[0]]['labels']['first_start']==ABI['boot_entry'] and
            records[SOURCES[1]]['labels']['reader_start']==ABI['reader_entry'], 'Boot entry moved')
    return records


class Volume:
    """Address boot mutations through documented SDFS maps; verify independently."""
    def __init__(self, raw):
        self.image = ATRImage(raw)
        require(self.image.size==256, 'Boot requires SDFS/256')

    def chain(self, first):
        maps, data = [], []
        previous = 0
        while first:
            require(first not in maps, 'Cyclic SDFS map')
            page = self.image.sector(first)
            require(int.from_bytes(page[2:4],'little')==previous, 'Bad SDFS backlink')
            maps.append(first)
            data.extend(int.from_bytes(page[i:i+2],'little') for i in range(4,256,2))
            previous, first = first, int.from_bytes(page[:2],'little')
        return maps, data

    def entry(self, name):
        root = int.from_bytes(self.image.sector(1)[9:11],'little')
        _, sectors = self.chain(root)
        raw = b''.join(self.image.sector(n) for n in sectors if n)
        length = int.from_bytes(raw[3:6],'little')
        base, _, ext = name.partition('.')
        key = (base.ljust(8)+ext.ljust(3)).encode('ascii')
        for at in range(23,length,23):
            row = raw[at:at+23]
            if row[0]&0x18==8 and row[6:17]==key:
                positions = [self.image.offset(sectors[i//256])+i%256 for i in range(at,at+23)]
                return row, positions
        raise ValueError('Missing boot file: '+name)


def check_layout(xex, monitor=None):
    """Build-time admission proves the reader and callbacks survive every write."""
    data = Path(xex).read_bytes()
    require(data[:2]==b'\xff\xff', 'Expected XEX marker')
    low, high = ABI['reader_address'], ABI['reader_address']+ABI['reader_bytes']
    at, count = 2, 0
    while at<len(data):
        require(at+2<=len(data), 'Truncated XEX header')
        start=struct.unpack_from('<H',data,at)[0];at+=2
        if start==65535:continue
        require(at+2<=len(data), 'Truncated XEX header')
        end=struct.unpack_from('<H',data,at)[0];at+=2
        require(start<=end and at+end-start+1<=len(data), 'Truncated XEX payload')
        require(end<low or start>=high, 'XEX overwrites live disk reader')
        require((0x2e0<=start<=end<=0x2e3) or
                (0xa00<=start<=end<0x4000) or (0x6000<=start<=end<0x8000),
                'XEX destination outside admitted boot spans')
        at+=end-start+1; count+=1
    require(count>0,'Empty XEX has no native entry')
    if monitor:
        layout = monitor['layout']
        for start,end in ((layout['OF_STACK']-16,layout['OF_STACK']+1552),
                          (layout['OF_DP'],layout['OF_DP']+256),
                          (layout['OF_ADAPTER']-16,layout['OF_ADAPTER']+1552)):
            require(end<=low or start>=high, 'OF816 overwrites live disk reader')
    return count


def phase_budget(monitor):
    """Count the union, including padding and guards, rather than just code."""
    if monitor is None:
        return dict(reader_claim_bytes=ABI['reader_bytes'],first_stage_claim_bytes=ABI['boot_bytes'])
    memory=json.loads((Path(monitor['exec_build'])/'memory.json').read_text())
    def occupied(rows):
        return {a for row in rows for a in range(row['address'],row['address']+row['size'])}
    loading=occupied(memory['phase_reservations']['loading'])
    runtime=occupied(memory['phase_reservations']['runtime'])
    first=set(range(ABI['boot_address'],ABI['boot_address']+ABI['boot_bytes']))
    reader=set(range(ABI['reader_address'],ABI['reader_address']+ABI['reader_bytes']))
    require((first|reader) <= runtime,'Boot reader would enlarge runtime reservations')
    borrowed=[]
    for i,pool in enumerate(memory['task_pools']):
        span=set(range(pool['stack_base']-16,pool['stack_base']+pool['stack_bytes']+16))
        if reader & span:borrowed.append(dict(slot=i,bytes=len(reader & span),runtime_delta=0))
    return dict(native_loading_union=len(loading),disk_loading_union=len(loading|reader),
        loading_union_delta=len(reader-loading),first_stage_union_delta=len(first-loading),
        runtime_union_delta=0,reader_claim_bytes=len(reader),first_stage_claim_bytes=len(first),
        borrowed_public_stacks=borrowed,native_budget=memory['bank_zero_budget'])


def build(image, source, xex, output, monitor=None,boot_sio="standard"):
    image, source, xex, output = map(Path,(image,source,xex,output))
    options=dict(BOOT_POLICY=int(boot_sio=='auto'),BOOT_NATIVE_DIVISOR=40)
    if monitor:
        options.update(BOOT_NATIVE_DIVISOR=8,BOOT_LOCAL0=monitor['layout']['EXEC_LOADER'],
                       BOOT_LOCAL1=monitor['labels']['of_load'],BOOT_LOCAL2=monitor.get('local_loader_init',0))
        # EXEC_LOADER is RUNAD; generated callbacks are recorded by build_of816.
        for i,address in enumerate(monitor.get('local_callbacks',[])):options['BOOT_LOCAL'+str(i)]=address
    records = compile_reader(output,fast=True,options=options)
    segments = check_layout(xex,monitor)
    with tempfile.TemporaryDirectory(prefix='exec816-boot-media-') as temporary:
        staging = Path(temporary)/'source'
        shutil.copytree(source,staging)
        shutil.copyfile(xex,staging/'EXEC816.XEX')
        shutil.copyfile(output/'disk-boot-reader.bin',staging/'BOOT.LDR')
        binary_names = {p.relative_to(staging).as_posix() for p in staging.rglob('*') if p.is_file()}
        expected = make(image,staging,binary_names=binary_names,sector_bytes=256,
                        sectors=ABI['sectors'],label='EXEC816')
        volume = Volume(image.read_bytes())
        row, _ = volume.entry('BOOT.LDR')
        maps, pointers = volume.chain(int.from_bytes(row[1:3],'little'))
        sectors = pointers[:ABI['reader_bytes']//256]
        require(len(sectors)==32 and sectors==list(range(sectors[0],sectors[0]+32)),
                'BOOT.LDR allocation is not contiguous')
        require(int.from_bytes(row[3:6],'little')==ABI['reader_bytes'], 'Reader file length changed')
        for name in ('BOOT.LDR','EXEC816.XEX'):
            _, positions = volume.entry(name)
            volume.image.data[positions[0]] |= 1
        header = bytearray(volume.image.sector(1))
        boot = bytearray((output/'disk-boot-first.bin').read_bytes())
        boot[:40] = header[:40]
        # The disk loader never returns to DOSINI. Warm reset must cold-start
        # instead of invoking a discarded DOS/first-stage address.
        struct.pack_into('<BBHH',boot,0,0,3,ABI['boot_address'],0xe477)
        boot[6:9] = bytes([0x4c])+struct.pack('<H',ABI['boot_entry'])
        locator = struct.pack('<4sHHHH',ABI['locator_magic'].encode(),sectors[0],len(sectors),
                              ABI['reader_address'],ABI['reader_entry'])
        begin = ABI['locator_offset']; boot[begin:begin+len(locator)] = locator
        for sector in range(1,4):
            at = volume.image.offset(sector)
            volume.image.data[at:at+128] = boot[(sector-1)*128:sector*128]
        image.write_bytes(volume.image.data)
        sdfs_reference.verify(image,expected,Path(temporary)/'verified')
    proof = json.loads(image.with_suffix('.verification.json').read_text())
    proof['media_sha256'] = digest(image)
    proof['verification'] += '; boot code/locator and protected boot files patched, then independently revalidated'
    image.with_suffix('.verification.json').write_text(json.dumps(proof,indent=2)+'\n')
    report = dict(format=ABI['format'],status='built',abi=ABI,reader=records,segments=segments,
        image_sha256=digest(image),xex_sha256=digest(xex),bytes=image.stat().st_size,
        boot_file_sectors=sectors,boot_file_maps=maps,
        boot_sio=boot_sio,reader_used_bytes=records[SOURCES[1]]['labels']['reader_end']-ABI['reader_address']+ABI['guard_bytes'],
        free_sectors=int.from_bytes(volume.image.sector(1)[13:15],'little'),
        inputs={str(p.relative_to(ROOT)):digest(p) for p in
                (ABI_PATH,ROOT/'abi/boot-sio.json',Path(__file__),*(ROOT/'platform/altirraos'/n for n in (*SOURCES,'boot-xex.inc','boot-sio.inc','boot-sio-policy.inc','boot-takeover.inc')))},
        reserved_bank_zero_delta=dict(fixed=0,root=0,kernel=0,per_task=0,idle=0),
        boot_phase_budget=phase_budget(monitor),
        boot_only_claims=[dict(address=ABI['boot_address'],bytes=ABI['boot_bytes'],
                               retirement='before XEX reader starts'),
                          dict(address=ABI['reader_address'],bytes=ABI['reader_bytes'],
                               retirement='before native Task initialization')])
    (output/'boot-atr.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image',type=Path,required=True)
    parser.add_argument('--source',type=Path,required=True)
    parser.add_argument('--xex',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    report=build(args.image,args.source,args.xex,args.output)
    print(f'{args.image}: bootable SDFS, {report["free_sectors"]} free sectors')
