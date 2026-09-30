"""Independent v3 examples and corruptions at the hosted package boundary."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from native_frame_maps import validate
from native_program import image_regions


def routine():
    return dict(id=0, address=0x6000, fixed_frame=4, spill_bytes=4,
                arguments=[dict(offset=0, body_displacement=8, size=2)], result_bytes=0,
                objects=[], temporaries=[dict(id=0, size=2, home=dict(kind='stack', displacement=1)),
                                        dict(id=1, size=2, home=dict(kind='stack', displacement=1))],
                calls=[], local_stack_peak=4, whole_task_stack_bound=None)


class FrameMaps(unittest.TestCase):
    def test_reused_stack_homes_and_call_peak(self):
        r = routine()
        r['calls'] = [dict(outgoing=7, transfer_peak=6), dict(outgoing=1, transfer_peak=3)]
        r['local_stack_peak'] = 17
        validate([r])

    def test_pointer_and_scalar_dp_boundaries(self):
        for size, offsets in ((3, (0x80, 0x83, 0x86)), (3, tuple(range(0xa0, 0xbc, 3))), (2, (0xa0, 0xbe))):
            r = routine()
            r.update(fixed_frame=0, spill_bytes=0, arguments=[], local_stack_peak=0,
                     temporaries=[dict(id=i, size=size, home=dict(kind='direct_page', offset=offset))
                                  for i, offset in enumerate(offsets)])
            validate([r])

    def test_pointer_and_byte_residents_share_only_unused_pool_bytes(self):
        r = routine()
        r.update(fixed_frame=0, spill_bytes=0, arguments=[], local_stack_peak=0,
                 temporaries=[dict(id=0, size=3, home=dict(kind='direct_page', offset=0xa0)),
                              dict(id=1, size=1, home=dict(kind='direct_page', offset=0xa3)),
                              dict(id=2, size=1, home=dict(kind='direct_page', offset=0xbf))])
        validate([r])
        for offset in (0x80, 0x9f, 0xa0, 0xa1, 0xa2, 0xc0):
            bad = copy.deepcopy(r)
            bad['temporaries'][1]['home']['offset'] = offset
            with self.subTest(offset=offset), self.assertRaises(RuntimeError):
                validate([bad])
        bad = copy.deepcopy(r)
        bad['temporaries'][0].update(size=2)
        with self.assertRaises(RuntimeError): validate([bad])

    def test_rejects_invalid_frame_maps(self):
        changes = [lambda r: r.update(fixed_frame=256), lambda r: r.update(fixed_frame=3),
                   lambda r: r.update(spill_bytes=6), lambda r: r.update(local_stack_peak=2),
                   lambda r: r.update(whole_task_stack_bound=100),
                   lambda r: r['arguments'][0].update(body_displacement=6),
                   lambda r: r['temporaries'][1].update(id=0),
                   lambda r: r['temporaries'][0].update(size=True),
                   lambda r: r['temporaries'][0]['home'].update(displacement=4),
                   lambda r: r['temporaries'][0]['home'].update(kind='register'),
                   lambda r: r.update(objects=[dict(displacement=0, size=1)]),
                   lambda r: r.update(calls=[dict(outgoing=2, transfer_peak=3)], local_stack_peak=9)]
        for change in changes:
            r = routine(); change(r)
            with self.subTest(r=r), self.assertRaises(RuntimeError):
                validate([r])

    def test_rejects_dp_calls_outside_scratch_and_mixed_classes(self):
        for size, offset, call in ((3, 0x81, False), (2, 0xc0, False), (2, 0xa1, False), (2, 0x20, False),
                                   (3, 0xa1, False), (3, 0xbe, False), (3, 0xc0, False),
                                   (3, 0xa0, True), (4, 0xa0, False), (2, 0xa0, True)):
            r = routine()
            r['temporaries'] = [dict(id=0, size=size, home=dict(kind='direct_page', offset=offset))]
            if call: r.update(calls=[dict(outgoing=1, transfer_peak=3)], local_stack_peak=8)
            with self.subTest(size=size, offset=offset, call=call), self.assertRaises(RuntimeError):
                validate([r])
        r = routine()
        r['temporaries'] = [dict(id=0, size=3, home=dict(kind='direct_page', offset=0x80)),
                            dict(id=1, size=2, home=dict(kind='direct_page', offset=0xa0))]
        with self.assertRaises(RuntimeError): validate([r])

    def test_image_requires_explicit_matching_contract(self):
        r = routine(); r['arguments'] = []
        image = dict(format='actionc-65816-image', version=3, target='wdc-65816-native',
                     abi='action65816.native.v2', entry=0x6000, stack_overflow=0x3c00,
                     task_headroom=26, irq_headroom=13, routines=[r], data=[], imports=[],
                     segments=[dict(address=0x6000, bytes=[0x6b], executable=True, writable=False)],
                     zero_fill=[])
        self.assertEqual(image_regions(image, {'stack_overflow':0x3c00}, [], image_version=3),
                         [(0x6000, b'\x6b')])
        with self.assertRaises(RuntimeError):
            image_regions(image, {'stack_overflow':0x3c00}, [], image_version=2)
        old = copy.deepcopy(image); old["abi"] = "action65816.native.v1"
        with self.assertRaises(RuntimeError):
            image_regions(old, {"stack_overflow":0x3c00}, [], image_version=3)
        arithmetic=copy.deepcopy(image); arithmetic.update(version=4,arithmetic_fault=0x3c40)
        labels={'stack_overflow':0x3c00,'arithmetic_fault':0x3c40}
        self.assertEqual(image_regions(arithmetic,labels,[],image_version=3),[(0x6000,b'\x6b')])
        for value in (None,0x3c00,0x6000,True):
            bad=copy.deepcopy(arithmetic);bad['arithmetic_fault']=value
            with self.subTest(arithmetic_fault=value),self.assertRaises(RuntimeError):
                image_regions(bad,labels,[],image_version=3)
        bad=copy.deepcopy(arithmetic);bad['version']=3
        with self.assertRaises(RuntimeError):image_regions(bad,labels,[],image_version=3)
        bad = copy.deepcopy(image); bad['routines'][0]['temporaries'][0]['home']['displacement'] = 255
        with self.assertRaises(RuntimeError):
            image_regions(bad, {'stack_overflow':0x3c00}, [], image_version=3)


if __name__ == '__main__': unittest.main()
