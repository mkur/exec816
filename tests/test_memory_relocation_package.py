"""Check ownership boundaries independently of compiler and loader execution."""
import copy
import sys
import json
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from adapter_state import addresses
from generate_memory import PROFILE, layout, reserve_image_data, validate_compiled_data
from generate_tasks import validate_memory
from generate_heap import reserve_metadata
from task_capacity import configure
from banked_image import validate_extents, manifest


class MemoryRelocationTests(unittest.TestCase):
    def test_firmware_bank_is_reserved_and_cannot_hold_image_payload(self):
        for name in ('memory-4m.json','memory-1m.json'):
            memory = layout(profile=PROFILE.with_name(name),upper_table=True)
            self.assertNotIn(1,memory['usable_banks'])
            self.assertEqual(memory['constants']['TABLE'],0x20000)
            image = dict(entry=0x30000,zero_fill=[],segments=[
                dict(address=0x30000,bytes=[0x6b],executable=True)])
            header,_ = manifest(image,memory)
            self.assertEqual(header[36:40],bytes([2,0,1,0]))
            for address in (0x10000,0x10100,0x1ffff):
                with self.assertRaises(ValueError):
                    validate_extents([(address,b'x',1,0,2)],memory)
            with self.assertRaises(ValueError):
                layout(profile=PROFILE.with_name(name),kernel_bank=1)

    def test_profiles_protect_small_loader_memory(self):
        for name in ('memory-4m.json','memory-1m.json'):
            with self.subTest(profile=name):
                memory = layout(profile=PROFILE.with_name(name))
                self.assertEqual(memory['constants']['MEMLO_LIMIT'],0x0a00)
                self.assertEqual(memory['regions']['os-low'],[0,0x0a00])
                self.assertEqual(memory['regions']['state'],[0x0a00,0x0b00])
                self.assertEqual(memory['regions']['loader'],[0x6a00,0x7c00])
                self.assertEqual(memory['constants']['LOADER_BYTES'],4608)

    def test_resident_linker_layout_survives_sorted_metadata(self):
        from adapter_state import hosted_config, resident_addresses
        profile=json.loads(json.dumps(layout()['profile'],sort_keys=True))
        self.assertEqual(hosted_config(profile),hosted_config())
        self.assertEqual(resident_addresses(profile)['RESIDENT_BASE'],0x1600)
        profile['resident_segments']['FAULT']=profile['resident_segments']['EXIT']
        with self.assertRaisesRegex(ValueError,'resident adapter layout'):
            resident_addresses(profile)

    def test_data_placement_follows_metadata_and_kernel_bank(self):
        for bank in (2, 3):
            m = layout(kernel_bank=bank, upper_table=True)
            reserve_metadata(m)
            previous = m['profile']['code_origin']
            reserve_image_data(m)
            arena = m['image_data']
            self.assertEqual(arena['address'] % 256, 0)
            self.assertGreaterEqual(arena['address'], previous)
            self.assertEqual(arena['address'] >> 16, bank)
            self.assertEqual(m['profile']['code_origin'], arena['address']+2048)
            self.assertEqual(addresses(m['profile'])['KERNEL_OWNER'], 0x0a60)
            self.assertEqual(m['regions']['state'], [0x0a00, 0x0b00])

    def test_data_permission_does_not_expose_metadata_or_padding(self):
        m = layout(upper_table=True)
        reserve_image_data(m)
        low = m['image_data']['address']
        validate_extents([(low, b'x', 1, 0, 2), (low+1, b'', 2047, 1, 2)], m)
        for address, size, kind, owner in (
            (low, 1, 2, 2), (low, 1, 0, 3), (low+2047, 2, 1, 2),
            (low-1, 1, 0, 2), (0x0800, 1, 0, 2), (0x8800, 1, 0, 2),
            (0x6000, 1, 0, 2), (0x10000, 1, 0, 2),
        ):
            with self.subTest(address=address, kind=kind), self.assertRaises(ValueError):
                validate_extents([(address, b'' if kind == 1 else bytes(size), size, kind, owner)], m)
        image = dict(entry=0x30000, zero_fill=[], segments=[
            dict(address=0x30000, bytes=[0x6b], executable=True)])
        header, _ = manifest(image, m)
        self.assertEqual(header[36:40], bytes([2, 0, 1, 0]))
        self.assertEqual(header[40:44], bytes([2, 0, 2, 0]))

    def test_compiler_data_overflow_is_rejected_before_foreign_bindings(self):
        m = layout()
        reserve_image_data(m)
        low = m['image_data']['address']
        image = dict(segments=[dict(address=low, bytes=[1], executable=False)],
                     zero_fill=[dict(address=low+1, size=2047)])
        validate_compiled_data(image, m)
        bad = copy.deepcopy(image)
        bad['zero_fill'][0]['size'] += 1
        with self.assertRaises(ValueError):
            validate_compiled_data(bad, m)
        m = layout()
        m['profile']['code_origin'] = 0x2ff00
        with self.assertRaises(ValueError):
            reserve_image_data(m)

    def test_eight_task_pools_avoid_vbxe(self):
        m = layout(upper_table=True)
        pools = configure(m, 8)
        self.assertEqual([p['dp'] for p in pools],
                         [0x0d00+i*256 for i in range(9)])
        self.assertEqual([p['stack_base'] for p in pools],
                         [0x2610, 0x3250, 0x3670, 0x3a90, 0x3eb0,
                          0x42d0, 0x46f0, 0x5110, 0x5b30])

    def test_aperture_reserved_during_loading_and_runtime(self):
        for capacity in (4, 8):
            memory = layout(upper_table=capacity == 8)
            if capacity == 8:
                configure(memory, 8)
            validate_memory(memory)
            self.assertEqual(memory['regions']['vbxe-aperture'], [0x8000, 0x9000])
            self.assertEqual(memory['regions']['staging'], [0x5df0, 0x6200])
            spans = memory['runtime_reservations']
            self.assertEqual(sum(r['size'] for r in spans if r['name'] == 'vbxe-aperture'), 4096)
            for name, (start, end) in memory['regions'].items():
                if name != 'vbxe-aperture':
                    self.assertTrue(end <= 0x8000 or start >= 0x9000, name)
            for region in spans:
                if region['name'] != 'vbxe-aperture':
                    self.assertTrue(region['address']+region['size'] <= 0x8000 or
                                    region['address'] >= 0x9000, region)

    def test_loading_overlap_and_missing_aperture_rejected(self):
        profile = json.loads(PROFILE.read_text())
        for mutation in ('staging', 'missing', 'partial'):
            bad = copy.deepcopy(profile)
            if mutation == 'staging':
                next(r for r in bad['regions'] if r['name'] == 'staging')['address'] = 0x7c00
            elif mutation == 'missing':
                bad['regions'] = [r for r in bad['regions'] if r['name'] != 'vbxe-aperture']
            else:
                next(r for r in bad['regions'] if r['name'] == 'vbxe-aperture')['size'] = 2048
            with tempfile.TemporaryDirectory() as folder:
                path = Path(folder)/'profile.json'
                path.write_text(json.dumps(bad))
                with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                    layout(profile=path)

    def test_retirement_separates_loading_and_runtime_reservations(self):
        from ports_budget import current
        budgets = current()
        for capacity, total, saving, loading in (('four',51904,-80,336),('eight',56640,-1248,544)):
            before, after = budgets['before'][capacity], budgets['after'][capacity]
            self.assertEqual(after['runtime_including_os'], total)
            self.assertEqual(after['runtime_including_os']-before['runtime_including_os'], -6144-saving)
            self.assertEqual(after['loading_including_os']-before['loading_including_os'], -4096-loading)
            per_task = 32 if capacity == 'four' else 256
            expected = [v-per_task for v in before['public']]
            if capacity == 'eight':
                expected[6] += 1536
                expected[7] += 1536
            self.assertEqual(after['public'], expected)
            self.assertEqual(after['idle'], before['idle']-per_task)
        m = layout(upper_table=True)
        configure(m,8)
        self.assertEqual(m['regions']['manifest'], [0x6200,0x6a00])
        self.assertNotIn('manifest', [r['name'] for r in m['runtime_reservations']])
        self.assertEqual(m['startup_retirement']['address'], m['constants']['RETIRED'])
        self.assertEqual(m['constants']['RETIRED'], 0x0b23)


if __name__ == '__main__':
    unittest.main()
