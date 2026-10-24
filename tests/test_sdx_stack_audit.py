import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from audit_sdx_stack import walk


class StackAuditTests(unittest.TestCase):
    def audit(self,code,imports=None):
        memory=bytearray(65536)
        memory[0x3000:0x3000+len(code)]=bytes(code)
        return walk(memory,[0x3000],imports or {},name='TEST')

    def test_native_call_includes_veneer_prefix(self):
        result=self.audit([0x20,0x00,0xf1,0x60],{0xf100:'SERVICE'})
        self.assertEqual(result['cpu_bytes'],4)
        self.assertEqual(result['service_frame_bytes'],15)

    def test_unknown_indirect_transfer_fails_closed(self):
        with self.assertRaisesRegex(RuntimeError,'Unreviewed indirect'):
            self.audit([0x6c,0x00,0x40])

    def test_unbalanced_return_is_not_a_normal_exit(self):
        with self.assertRaisesRegex(RuntimeError,'DYNAMIC RTS'):
            self.audit([0x48,0x60])
        with self.assertRaisesRegex(RuntimeError,'Unreviewed nonlocal'):
            self.audit([0x68,0x68,0x60])

    def test_growing_push_loop_has_no_finite_bound(self):
        with self.assertRaisesRegex(RuntimeError,'LIMIT'):
            self.audit([0x48,0x4c,0x00,0x30])

    def test_branch_successor_refines_the_observed_flag(self):
        result=self.audit([0xa5,0x80,0xc9,0x00,0x90,0x05,
                           0xb0,0x02,0x48,0x60,0x60,0x60])
        self.assertEqual(result['cpu_bytes'],2)


if __name__=='__main__':unittest.main()
