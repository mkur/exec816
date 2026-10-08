"""Exercise range ownership and the XEX wire format independently of emission."""
import copy
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from generate_memory import layout, generate, CONFIG, PROFILE
from banked_image import extents, manifest, package, validate_extents


def segments(blob):
    if blob[:2] != b'\xff\xff':
        raise ValueError('Bad XEX magic')
    at = 2
    while at < len(blob):
        if at + 4 > len(blob):
            raise ValueError('Short XEX header')
        start, end = struct.unpack_from('<HH', blob, at)
        at += 4
        if end < start or at + end-start+1 > len(blob):
            raise ValueError('Short/invalid XEX segment')
        data = blob[at:at+end-start+1]
        at += len(data)
        yield start, data


def model(blob, memory, expected, every=False):
    """Model only the callback contract; no calls to the packer's chunker."""
    c = memory['constants']
    ram = {}
    index, offset, initialized, init = 0, 0, False, False
    count = int.from_bytes(expected[8:10], 'little')
    descriptors = expected[32+c['TABLE_BYTES']:]
    def read(at, n):
        return bytes(ram.get(a, 0) for a in range(at, at+n))
    for address, data in segments(blob):
        ram.update((address+i, byte) for i,byte in enumerate(data))
        trigger = address == 0x02e2
        init = init or trigger
        if not (trigger or (every and init)):
            continue
        if not initialized:
            if read(c['MANIFEST'], len(expected)) != expected:
                raise ValueError('Manifest mismatch')
            initialized = True
        k, pos, n, flags, reserved = struct.unpack('<HHHBB', read(c['STAGE'], 8))
        if not n:
            continue
        if k != index or pos != offset or k >= count or reserved or n > c['CHUNK']:
            raise ValueError('Bad staging sequence')
        entry = descriptors[k*8:k*8+8]
        base = int.from_bytes(entry[:3], 'little')
        length = int.from_bytes(entry[4:6], 'little')
        if flags != entry[3] or pos + n > length:
            raise ValueError('Bad staging extent')
        payload = bytes(n) if flags == 1 else read(c['PAYLOAD'], n)
        ram.update((base+pos+i, byte) for i,byte in enumerate(payload))
        offset += n
        if offset == length:
            index += 1
            offset = 0
        ram[c['STAGE']+4] = ram[c['STAGE']+5] = 0
    if not initialized or index != count or offset:
        raise ValueError('Incomplete image')
    return ram


class BankedPackageTests(unittest.TestCase):
    def test_disk_component_is_reserved_and_cleared_without_cartridge_payload(self):
        image = {'entry':0x10000, 'segments':[
            {'address':0x10000,'bytes':[0x6b],'executable':True},
            {'address':0xc0000,'bytes':[0xa7]*65536,'executable':True,'deferred':True},
            {'address':0xd0000,'bytes':[0x59]*200,'executable':False,'deferred':True}],
            'zero_fill':[{'address':0xd00c8,'size':80}]}
        blob, head, spans = self.make(image)
        ram = model(blob,self.memory,head)
        self.assertEqual(bytes(ram[0xc0000+i] for i in range(65536+280)),bytes(65536+280))
        self.assertLess(len(blob),4096)
        for bank in (12,13):
            self.assertEqual(head[32+bank*4:36+bank*4],bytes([2,0,2,0]))
        self.assertEqual(image['segments'][1]['bytes'][0],0xa7)
        image['entry']=0xc0000
        with self.assertRaisesRegex(ValueError,'Entry outside executable'):
            manifest(image,self.memory)

    def test_adjacent_routines_share_extents_without_merging_gaps_or_data(self):
        image = {'segments':[
            {'address':0x10000+i, 'bytes':[i], 'executable':True} for i in range(80)],
            'zero_fill':[]}
        image['segments'] += [
            {'address':0x10051,'bytes':[0xaa],'executable':True},
            {'address':0x10052,'bytes':[0xbb],'executable':False},
            {'address':0x10053,'bytes':[0xcc],'executable':True}]
        spans = extents(image,layout())
        self.assertEqual([(a,p,n,f) for a,p,n,f,_ in spans], [
            (0x10000,bytes(range(80)),80,2),(0x10051,b'\xaa',1,2),
            (0x10052,b'\xbb',1,0),(0x10053,b'\xcc',1,2)])

    def test_many_data_objects_roundtrip_without_growing_manifest(self):
        image = {'entry':0x10000, 'segments':[
            {'address':0x10000,'bytes':[0x6b],'executable':True},
            *[{'address':0x20000+i,'bytes':[i],'executable':False} for i in range(80)]],
            'zero_fill':[{'address':0x20050+i,'size':1} for i in range(80)]}
        image['segments'].append({'address':0x200a1,'bytes':[0xee],'executable':False})
        blob,head,spans=self.make(image)
        self.assertEqual(len(spans),4)
        for every in (False,True):
            ram=model(blob,self.memory,head,every)
            self.assertEqual(bytes(ram[0x20000+i] for i in range(160)),bytes(range(80))+bytes(80))
            self.assertNotIn(0x200a0,ram)
            self.assertEqual(ram[0x200a1],0xee)
        # Merging does not hide an invalid source region or cross a kind boundary.
        for size in (0,-1,True):
            bad=copy.deepcopy(image);bad['zero_fill'].append({'address':0x200a0,'size':size})
            with self.subTest(size=size),self.assertRaises(ValueError):extents(bad,self.memory)

    def test_empty_code_cannot_disappear_when_adjacent_regions_merge(self):
        image = {'segments':[
            {'address':0x10000,'bytes':[0x6b],'executable':True},
            {'address':0x10001,'bytes':[],'executable':True}], 'zero_fill':[]}
        with self.assertRaisesRegex(ValueError, 'Empty'):
            extents(image,layout())

    def setUp(self):
        self.memory = layout()
        self.image = {'entry':0x10000, 'segments':[
            {'address':0x10000, 'bytes':[0x6b], 'executable':True},
            {'address':0x1fffd, 'bytes':[7,9,11,13,15,17], 'executable':False},
            {'address':0x18000, 'bytes':[65,155], 'executable':False}],
            'zero_fill':[{'address':0x20003, 'size':65533}]}

    def make(self, image=None, memory=None):
        memory = memory or self.memory
        head, spans = manifest(image or self.image, memory)
        blob = package(b'\x4c\0\x68', head, spans, memory,
                       {'loader_start':0x6800,'loader_init':0x6840}, b'\x60')
        return blob, head, spans

    def test_binary_roundtrip_boundaries_and_callback_variants(self):
        blob, head, spans = self.make()
        for every in (False, True):
            ram = model(blob, self.memory, head, every)
            for address,payload,size,flags,_ in spans:
                actual = bytes(ram.get(address+i, 255) for i in range(size))
                self.assertEqual(actual, bytes(size) if flags == 1 else payload)
        # Claims are coalesced by bank; zero-fill participates in ownership.
        self.assertEqual(head[32:48], bytes([2,0,1,0,2,0,2,0,2,0,2,0,1,0,0,0]))

    def test_claims_and_regions_reject_without_side_effects(self):
        cases = [
            [(0x10000,b'a',1,2,2),(0x10002,b'b',1,0,3)],
            [(0x10000,b'a',1,2,2),(0x10000,b'b',1,0,2)],
            [(0x2800,b'a',1,0,2)], [(0x6800,b'a',1,0,2)],
            [(0x8800,b'a',1,2,2)], [(0x8fff,b'ab',2,0,2)],
            [(0x400000,b'a',1,2,2)], [(0xffffff,b'ab',2,0,2)],
            [(0x10000,b'',0,2,2)], [(0x10000,b'a',65536,2,2)],
        ]
        original = copy.deepcopy(self.memory)
        for regions in cases:
            with self.subTest(regions=regions), self.assertRaises(ValueError):
                validate_extents(regions, self.memory)
            self.assertEqual(self.memory, original)
        hole = copy.deepcopy(self.memory)
        hole['usable_banks'].remove(2)
        with self.assertRaises(ValueError):
            manifest(self.image, hole)

    def test_banked_consumer_preserves_image_and_entry_contracts(self):
        from native_program import image_regions, require_executable
        image = copy.deepcopy(self.image)
        image.update(format='actionc-65816-image',version=2,target='wdc-65816-native',
                     abi='action65816.native.v2',stack_overflow=0x3c00,
                     task_headroom=26,irq_headroom=13,imports=[],data=[],
                     routines=[{'address':0x10000,'arguments':[],'result_bytes':0}])
        for s in image['segments']:
            s['writable'] = not s['executable']
        for z in image['zero_fill']:
            z['writable'] = True
        image_regions(image,{'stack_overflow':0x3c00},[],self.memory,image_version=2)
        require_executable(image,0x10000)
        for address in (0x8800,0x10001,0x20000,True):
            with self.assertRaises(RuntimeError):
                require_executable(image,address)
        for change in (
            lambda i:i.update(entry=0x8800), lambda i:i.update(abi='wrong'),
            lambda i:i.update(imports=[{'address':0xd000}]),
            lambda i:i['segments'][0].update(writable=True),
            lambda i:i['zero_fill'][0].update(address=0x10000),
            lambda i:i['zero_fill'][0].update(size=0x1000000),
            lambda i:i['routines'][0].update(result_bytes=2),
        ):
            broken = copy.deepcopy(image);change(broken)
            with self.assertRaises((RuntimeError,ValueError)):
                image_regions(broken,{'stack_overflow':0x3c00},[],self.memory,image_version=2)

    def test_full_bank_and_final_address_do_not_wrap(self):
        m = layout(max_banks=256)
        m['usable_banks'].append(255)  # synthetic range validation, not a hardware claim
        spans = validate_extents([(0xff0000,b'',65536,1,2)], m)
        self.assertEqual([(s[0],s[2]) for s in spans], [(0xff0000,65535),(0xffffff,1)])
        with self.assertRaises(ValueError):
            validate_extents([(0xff0000,b'',65537,1,2)], m)

    def test_generated_limits_and_text_conventions(self):
        with tempfile.TemporaryDirectory() as temp:
            p = Path(temp)
            for count in (2,16,256):
                m = layout(max_banks=count)
                self.assertEqual(m['constants']['TABLE_BYTES'], 4*count)
                generate(p/str(count),m)
                generate(p/str(count),m,True)
                for name in ('memory.inc','memory-action.inc','memory.json'):
                    f = p/str(count)/name
                    f.write_bytes(f.read_bytes().replace(b'\n',b'\r\n'))
                generate(p/str(count),m,True)
            for nl in ('\n','\r\n'):
                (p/'config.json').write_bytes(CONFIG.read_text().replace('\n',nl).encode())
                (p/'profile.json').write_bytes(PROFILE.read_text().replace('\n',nl).encode())
                self.assertEqual(layout(p/'config.json',p/'profile.json'),layout())
        for invalid in (0,1,257,-1,True,1.5):
            with self.subTest(limit=invalid),self.assertRaises(ValueError):
                layout(max_banks=invalid)

    def test_kernel_module_instrumentation_lf_and_crlf(self):
        from native_program import kernel_source
        for source in ('MODULE App\nPROC Main()\nRETURN\nENDMODULE\n',
                       'MODULE App\nUSE EXECMEMORY\nPROC Main()\nRETURN\nENDMODULE\n'):
            lf = kernel_source(source)
            crlf = kernel_source(source.replace('\n','\r\n'))
            self.assertEqual(lf,crlf)
            self.assertEqual(lf.count('USE EXECMEMORY'),1)
        for newline in ('\n','\r\n'):
            source = newline.join(['MODULE App','INCLUDE "parts/body.act"','ENDMODULE',''])
            expected = (Path('/tmp/app')/'parts/body.act').resolve()
            self.assertIn(f'INCLUDE "{expected}"', kernel_source(source,Path('/tmp/app')))

    def test_bad_layouts_and_manifest_capacity(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp)/'profile.json'
            for change in (
                lambda m:m['regions'][1].update(address=0x100),
                lambda m:m['regions'][6].update(size=1),
                lambda m:m['regions'][11].update(size=16),
                lambda m:m.update(usable_banks=[1,1]),
            ):
                profile = json.loads(PROFILE.read_text())
                change(profile)
                path.write_text(json.dumps(profile))
                with self.assertRaises(ValueError):
                    layout(profile=path)
        m = copy.deepcopy(self.memory)
        m['constants']['MAX_EXTENTS'] = 1
        with self.assertRaises(ValueError):
            self.make(memory=m)

    def test_wire_corruption_replay_and_incomplete_loads(self):
        from native_program import xex_segment
        blob, head, _ = self.make()
        segs = list(segments(blob))
        first = next(i for i,(a,d) in enumerate(segs) if a == self.memory['constants']['STAGE'] and len(d)>8)
        for mutation in ('index','offset','count','kind','reserved','replay','missing','manifest'):
            changed = list(segs)
            if mutation == 'replay':
                changed[first+2:first+2] = changed[first:first+2]
            elif mutation == 'missing':
                changed = changed[:first]
            elif mutation == 'manifest':
                i = next(i for i,(a,_) in enumerate(changed) if a == 0x6000)
                a,d = changed[i]; changed[i] = (a, bytes([d[0]^1])+d[1:])
            else:
                a,d = changed[first]; d = bytearray(d)
                pos = {'index':0,'offset':2,'count':5,'kind':6,'reserved':7}[mutation]
                d[pos] = 255
                changed[first] = (a,bytes(d))
            damaged = b'\xff\xff' + b''.join(xex_segment(a,d) for a,d in changed)
            with self.subTest(mutation=mutation),self.assertRaises(ValueError):
                model(damaged,self.memory,head,True)
        for short in (blob[:1],blob[:-1],blob[:7]):
            with self.assertRaises(ValueError):
                list(segments(short))


if __name__ == '__main__':
    unittest.main()
