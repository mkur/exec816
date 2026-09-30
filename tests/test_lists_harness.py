"""Protect the independent Lists oracle and test-only source instrumentation."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from test_lists import Model, STRIDE, SNAPSHOT_BYTES, instrument, validate_snapshot


class ListsHarnessTests(unittest.TestCase):
    def test_trace_is_legal_deterministic_and_covers_each_operation(self):
        near,far = Model().fixture(),Model(True).fixture()
        self.assertEqual(near.trace,far.trace)
        self.assertEqual(near.expected,Model().fixture().expected)
        self.assertEqual({op[0] for op in near.trace},set(range(11)))
        self.assertEqual(near.queues,[[],[]])
        self.assertEqual(len(near.expected),len(near.trace)*STRIDE)
        for start in range(0,len(near.expected),STRIDE):
            self.assertEqual(near.expected[start+SNAPSHOT_BYTES:start+STRIDE],bytes([0xa5])*(STRIDE-SNAPSHOT_BYTES))

    def test_model_preserves_high_bank_bytes_and_rejects_invalid_membership(self):
        model = Model()
        model.apply(2,0,0)
        model.apply(3,0,1)
        self.assertEqual(model.nodes[0]&0xffff,model.nodes[1]&0xffff)
        self.assertNotEqual(model.nodes[0],model.nodes[1])
        with self.assertRaises(AssertionError):
            model.apply(2,1,0)
        with self.assertRaises(ValueError):
            model.apply(5,1,0)
        model.apply(6,0)
        self.assertEqual(model.expected[-STRIDE:-STRIDE+3],b'\x01\x8e\x04')
        model.apply(2,1,0)
        self.assertEqual(model.queues,[[1],[0]])

    def test_instrumentation_handles_lf_and_crlf_and_has_no_production_hooks(self):
        source = (Path(__file__).resolve().parents[1]/'lib/exec/execlists.act').read_text()
        self.assertNotIn('LISTSPROBE',source)
        lf,sites = instrument(source)
        crlf,windows_sites = instrument(source.replace('\n','\r\n'))
        self.assertEqual((lf,sites),(crlf,windows_sites))
        self.assertEqual(lf.count('LISTSPROBE.Checkpoint('),17)
        self.assertTrue(all('.' in site for site in sites))
        with self.assertRaises(RuntimeError):
            instrument(source.replace('item.ln_Succ=first','item.ln_Succ=first\n  item.ln_Succ=first'))

    def test_target_snapshot_validator_rejects_broken_links_and_cycles(self):
        model = Model()
        model.apply(2,0,0); model.apply(3,0,1)
        snapshot = model.expected[-STRIDE:-STRIDE+SNAPSHOT_BYTES]
        self.assertEqual(validate_snapshot(snapshot,model),[[0,1],[]])
        def corrupted(address,value):
            result = bytearray(snapshot)
            offset = 5
            for start,size in model.regions:
                if start <= address < start+size:
                    result[offset+address-start:offset+address-start+3] = value.to_bytes(3,'little')
                    return result
                offset += size
            self.fail('Missing test address')
        for address,value in [(model.nodes[1]+3,0), (model.nodes[1],model.nodes[0]),
                              (model.headers[0],0x008e01), (model.headers[0]+3,model.nodes[0])]:
            with self.assertRaises(RuntimeError):
                validate_snapshot(corrupted(address,value),model)


if __name__ == '__main__':
    unittest.main()
