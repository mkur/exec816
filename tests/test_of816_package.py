"""Reject boot layouts that would overwrite the preloaded kernel or OS."""
import copy
from pathlib import Path
import struct
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from build_of816 import boot_layout, xex_segments
from native_program import xex_segment
from boot_config import ABI as BOOT_ABI
from banked_image import split_setup


class OF816PackageTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.folder = Path(self.temp.name)
        seed = b'\2\0\1\0'+b'\2\0\2\0'+b'\1\0\0\0'*2
        (self.folder/'manifest.bin').write_bytes(bytes(32)+seed)
        self.xex = self.folder/'program.xex'
        self.xex.write_bytes(b'\xff\xff'+xex_segment(0x1400,b'\xea'))
        self.program = dict(output=self.folder,xex=self.xex,labels=dict(loader_start=0x6800,
            loader_error=0x6820,loader_init=0x6830,loader_progress_add=0x6900,
            loader_progress_finish=0x6920),
            image=dict(segments=[dict(address=0x10000,bytes=[0x6b])],zero_fill=[]),
            build=dict(tasks=True,banked=True,dos_mounts=[],system_mount=None,task_storage=dict(CAPACITY=4),memory=dict(
                task_pools=[dict(dp=0x0b00,stack_base=0x2410),dict(dp=0x0c00,stack_base=0x3050)],
                regions={'kernel-stack':[0x2a20,0x3040],'boot-state':[0x0900,0x0a00]},
                boot_config=dict(abi=BOOT_ABI,address=0x0980,cache_blocks=512,system_slot=255,system_drive=0,allowed_drives=0),
                constants=dict(TABLE_BYTES=16,STAGE=0x5bf0,OLD_MEMLO=0x0908),usable_banks=[1,2,3])))

    def test_boot_uses_free_banks_and_preserves_manifest(self):
        before = (self.folder/'manifest.bin').read_bytes()
        layout = boot_layout(self.program)
        self.assertEqual((layout['OF_CODE'],layout['OF_DATA']),(0x30000,0x20000))
        self.assertEqual((self.folder/'manifest.bin').read_bytes(),before)

    def test_rejects_unknown_boot_contract_and_location(self):
        for field,value in [('abi',{}),('address',0x0900),('cache_blocks',513)]:
            bad = copy.deepcopy(self.program)
            bad['build']['memory']['boot_config'][field] = value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'boot configuration'):
                boot_layout(bad)
        del bad['build']['memory']['boot_config']
        with self.assertRaisesRegex(RuntimeError,'boot configuration ABI'):
            boot_layout(bad)

    def test_rejects_inconsistent_system_selection(self):
        for field,value in [('system_slot',0),('system_drive',2),('allowed_drives',255)]:
            bad=copy.deepcopy(self.program)
            bad['build']['memory']['boot_config'][field]=value
            with self.subTest(field=field),self.assertRaisesRegex(RuntimeError,'system-volume'):
                boot_layout(bad)

    def test_eight_slots_borrow_kernel_stack_instead_of_smaller_worker_stack(self):
        self.program['build']['task_storage']['CAPACITY'] = 8
        self.program['build']['memory']['task_pools'][0]['stack_bytes'] = 1536
        self.program['build']['memory']['task_pools'][1]['stack_bytes'] = 1024
        layout = boot_layout(self.program)
        self.assertEqual(layout['OF_ADAPTER'],0x2a30)
        # Both adapter code/state and its startup stack fit inside this arena.
        self.assertLessEqual(layout['OF_ADAPTER']+1536,0x3030)

    def test_rejects_insufficient_banks_or_other_task_layout(self):
        (self.folder/'manifest.bin').write_bytes(bytes(32)+b'\2\0\1\0'*4)
        with self.assertRaisesRegex(RuntimeError,'unused upper banks'):
            boot_layout(self.program)
        bad = copy.deepcopy(self.program)
        bad['build']['memory']['task_pools'][0]['stack_bytes'] = 1024
        with self.assertRaisesRegex(RuntimeError,'Root Task pool'):
            boot_layout(bad)
        bad = copy.deepcopy(self.program)
        bad['build']['memory']['regions']['kernel-stack'][1] -= 16
        with self.assertRaisesRegex(RuntimeError,'Kernel stack reservation'):
            boot_layout(bad)

    def test_rejects_payload_and_bss_in_borrowed_storage(self):
        for address in (0x0b00,0x0bff,0x2410,0x2a2f,0x302f):
            with self.subTest(address=address):
                self.xex.write_bytes(b'\xff\xff'+xex_segment(address,b'\x01'))
                with self.assertRaisesRegex(RuntimeError,'payload overlaps'):
                    boot_layout(self.program)
        self.xex.write_bytes(b'\xff\xff'+xex_segment(0x1400,b'\xea'))
        self.program['image']['zero_fill'] = [dict(address=0x2a0f,size=2)]
        with self.assertRaisesRegex(RuntimeError,'image data overlaps'):
            boot_layout(self.program)

    def test_dp_neighbours_are_not_borrowed_by_of816(self):
        for address in (0x0aff,0x0c00):
            self.xex.write_bytes(b'\xff\xff'+xex_segment(address,b'\x01'))
            boot_layout(self.program)

    def test_xex_callback_order_and_truncation(self):
        raw = b'\xff\xff'+xex_segment(0x2e0,struct.pack('<H',0x6800))
        raw += xex_segment(0x7c00,bytes(range(256)))
        raw += xex_segment(0x2e2,struct.pack('<H',0x5200))
        self.assertEqual([address for address,_ in xex_segments(raw)],[0x2e0,0x7c00,0x2e2])
        for truncated in (b'',raw[:3],raw[:-1]):
            with self.subTest(size=len(truncated)),self.assertRaises(RuntimeError):
                list(xex_segments(truncated))

    def native_records(self):
        memory=self.program['build']['memory']
        memory['regions']['resident']=[0x1400,0x2400]
        memory['constants'].update(LOADER=0x6800,LOADER_BYTES=5120,MANIFEST=0x6000,CHUNK=1024)
        return [(0x6800,b'\xea'),(0x2e0,struct.pack('<H',0x6800)),(0x1400,b'\xea'),
                (0x6000,b'EBM1'),(0x5bf0,bytes(8)),(0x2e2,struct.pack('<H',0x6830)),
                (0x5bf0,struct.pack('<HHHBB',0,0,1,2,0)+b'\x6b'),
                (0x2e2,struct.pack('<H',0x6830)),(0x2e0,struct.pack('<H',0x6800))]

    def test_setup_boundary_precedes_payload_and_keeps_guarded_runad(self):
        segments=self.native_records()
        setup,payload=split_setup(segments,self.program['build']['memory'],self.program['labels'])
        self.assertEqual(setup,segments[:6])
        self.assertEqual(payload,segments[6:])
        self.assertEqual(setup[1],payload[-1])

    def test_rejects_bad_setup_and_later_direct_writes(self):
        original=self.native_records()
        for index,item in [(4,(0x5bf0,b'\1'+bytes(7))),
                           (5,(0x2e2,struct.pack('<H',0x6900))),
                           (6,(0x0980,bytes(8))),
                           (7,(0x2e2,struct.pack('<H',0x6900))),
                           (8,(0x2e0,struct.pack('<H',0x6830)))]:
            bad=list(original);bad[index]=item
            with self.subTest(index=index),self.assertRaises(ValueError):
                split_setup(bad,self.program['build']['memory'],self.program['labels'])
        for bad in (original[:5],original[:6]+original[7:]):
            with self.assertRaises(ValueError):
                split_setup(bad,self.program['build']['memory'],self.program['labels'])
