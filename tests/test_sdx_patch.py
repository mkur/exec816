"""Loader transactions and malformed inputs, without downloaded SDX binaries."""
import copy
import hashlib
import json
from pathlib import Path
import struct
import sys
import unittest
import zlib

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))
from sdx_file import FormatError, parse, place
from sdx_patch import PatchError, apply, manifests, prepare, select, selectors
from generate_sdx import products


def fixture():
    code = bytes.fromhex('781400eaeaea0000eaeaeaeaeaeaeaea')
    raw = struct.pack('<HBBHH', 0xfffe, 1, 0, 0, len(code))+code
    raw += struct.pack('<HBBHH', 0xfffe, 2, 0x80, 16, 16)
    raw += struct.pack('<HBH', 0xfffd, 2, 4)+bytes([0xfe, 1, 1, 0xfc])
    raw += struct.pack('<H8sH', 0xfffb, b'PRINTF  ', 4)+bytes([0xfe, 1, 6, 0xfc])
    raw += struct.pack('<HBH8s', 0xfffc, 1, 0, b'@TEST   ')
    module = dict(file='TEST.COM', role='command', entry_export='@TEST',
                  bytes=len(raw), crc32=f'{zlib.crc32(raw):08x}',
                  sha256=hashlib.sha256(raw).hexdigest(), patches=[
        dict(id='irq', block=1, offset=0, expected='78', replacement='ea',
             intersections=[], fixups=[]),
        dict(id='pointer', block=1, offset=1, expected='1400', replacement='0000',
             intersections=[dict(base=2, offset=1)],
             fixups=[dict(offset=0, kind='block16', block=2, addend=6)])])
    return raw, [dict(schema_version=1, personality_abi=1, id='test', revision=1,
                      execution_status='patch-probe-only', modules=[module])]


class SDXPatchTests(unittest.TestCase):
    def setUp(self):
        self.raw, self.catalog = fixture()
        self.module = self.catalog[0]['modules'][0]
        self.symbols = {'PRINTF': 0xe000}

    def prepared(self, start=0x2000, end=0x8000):
        return prepare(self.raw, self.catalog, start, end, self.symbols)

    def test_relocate_then_patch_at_two_placements(self):
        original = self.raw
        for start in (0x2000, 0x4100):
            result = self.prepared(start)
            self.assertEqual(result.image[start], 0xea)
            self.assertEqual(int.from_bytes(result.image[start+1:start+3], 'little'), start+22)
            self.assertEqual(result.image[start+6:start+8], b'\0\xe0')
            self.assertEqual(result.image[start+16:start+32], bytes(16))
            self.assertEqual(result.layout['exports'], {'@TEST': start})
            self.assertEqual(len(result.record['patches']), 2)
        self.assertEqual(self.raw, original)

    def test_wrong_size_crc_and_host_sha(self):
        for changed in (self.raw+b'\0', self.raw[:-1], self.raw[:9]+b'\xff'+self.raw[10:]):
            with self.subTest(raw=changed), self.assertRaisesRegex(PatchError, 'size/CRC32'):
                prepare(changed, self.catalog, 0x2000, 0x8000, self.symbols)
        self.module['sha256'] = '0'*64
        with self.assertRaisesRegex(PatchError, 'SHA-256'):
            self.prepared()
        # Target-style selection intentionally does not compute SHA-256.
        select(self.raw, self.catalog, verify_sha=False)

    def test_selector_ambiguity_even_for_unused_module(self):
        duplicate = copy.deepcopy(self.module)
        duplicate['file'] = 'OTHER.COM'
        self.catalog[0]['modules'].append(duplicate)
        with self.assertRaisesRegex(PatchError, 'Ambiguous'):
            self.prepared()

    def test_exact_preimage_both_before_and_after_relocation(self):
        self.module['patches'][0]['expected'] = '79'
        with self.assertRaisesRegex(PatchError, 'Original patch preimage'):
            self.prepared()
        self.module['patches'][0]['expected'] = '78'
        p = parse(self.raw)
        original, layout = place(p, 0x2000, 0x8000, self.symbols)
        changed = bytearray(original)
        changed[0x2001] ^= 1
        with self.assertRaisesRegex(PatchError, 'Relocated patch preimage'):
            apply(p, self.module, changed, layout, self.symbols)
        # Failure in patch 2 cannot expose the successful patch 1.
        self.assertEqual(changed[0x2000], 0x78)

    def test_patch_overlap_and_split_relocation(self):
        extra = copy.deepcopy(self.module['patches'][0])
        extra['id'] = 'other'
        self.module['patches'].append(extra)
        with self.assertRaisesRegex(PatchError, 'Overlapping patches'):
            self.prepared()
        self.module['patches'] = [dict(id='split', block=1, offset=1,
                                       expected='14', replacement='00',
                                       intersections=[], fixups=[])]
        with self.assertRaisesRegex(PatchError, 'splits a relocation'):
            self.prepared()

    def test_unapproved_intersection_and_unknown_replacement(self):
        self.module['patches'][1]['intersections'] = []
        with self.assertRaisesRegex(PatchError, 'Undeclared'):
            self.prepared()
        self.module['patches'][1]['intersections'] = [dict(base=2, offset=1)]
        self.module['patches'][1]['fixups'][0]['kind'] = 'magic'
        with self.assertRaisesRegex(PatchError, 'Unknown'):
            self.prepared()

    def test_capacity_import_and_entry_failures(self):
        with self.assertRaisesRegex(FormatError, 'placement interval'):
            self.prepared(end=0x201f)
        self.symbols.clear()
        with self.assertRaisesRegex(FormatError, 'Undefined imports'):
            self.prepared()
        self.symbols['PRINTF'] = 65536
        with self.assertRaisesRegex(FormatError, 'outside bank'):
            self.prepared()
        self.symbols['PRINTF'] = 0xe000
        self.module['entry_export'] = '@MISSING'
        with self.assertRaisesRegex(PatchError, 'Missing entry'):
            self.prepared()

    def test_duplicate_application_is_rejected(self):
        p = parse(self.raw)
        result = self.prepared()
        with self.assertRaisesRegex(PatchError, 'Relocated patch preimage'):
            apply(p, self.module, result.image, result.layout, self.symbols)

    def test_branch_range_and_replacement_overlap(self):
        patch = dict(id='branch', block=1, offset=8, expected='eaea', replacement='8000',
                     intersections=[], fixups=[dict(offset=1, kind='relative8', block=1, addend=0)])
        self.module['patches'].append(patch)
        self.assertEqual(self.prepared().image[0x2008:0x200a], b'\x80\xf6')
        patch['fixups'].append(copy.deepcopy(patch['fixups'][0]))
        with self.assertRaisesRegex(PatchError, 'overlaps'):
            self.prepared()
        patch['fixups'].pop()
        # An independent relocated layout forces an otherwise valid near branch
        # across the allowed signed-byte range before any image is returned.
        p = parse(self.raw)
        original, layout = place(p, 0x2000, 0x8000, self.symbols)
        patch['fixups'][0].update(block=2, addend=0)
        layout['blocks'][2] = 0x3000
        # Remove the earlier relocation patch so the branch is the failure.
        self.module['patches'] = [patch]
        with self.assertRaisesRegex(PatchError, 'branch out of range'):
            apply(p, self.module, original, layout, self.symbols)

    def test_records_reject_truncation_unknown_tags_and_overlapping_fixups(self):
        for length in (7, 10, 23, len(self.raw)-1):
            with self.subTest(length=length), self.assertRaises(FormatError):
                parse(self.raw[:length])
        with self.assertRaisesRegex(FormatError, 'Unsupported SDX record'):
            parse(b'\xff\xff'+self.raw[2:])
        extra = struct.pack('<HBH', 0xfffd, 2, 4)+bytes([0xfe, 1, 2, 0xfc])
        with self.assertRaisesRegex(FormatError, 'Overlapping fixups'):
            parse(self.raw+extra)

    def test_repository_manifest_selectors_and_generated_crc(self):
        catalog = manifests(ROOT/'compat/sdx')
        self.assertEqual(len(selectors(catalog)), 5)
        for name, content in products().items():
            self.assertEqual((ROOT/name).read_text(), content)
        abi = json.loads((ROOT/'abi/sdx.json').read_text())
        self.assertEqual(abi['crc32']['polynomial'], 0xedb88320)


if __name__ == '__main__':
    unittest.main()
