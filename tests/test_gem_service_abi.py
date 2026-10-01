"""Keep the generated wire/lease ABI and the host acceptance gate in sync."""
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_calypsi import expected_layout as exec_layout
from generate_gem_vdi import files, expected_layout, ROOT


class GemServiceTests(unittest.TestCase):
    def test_generated_wire_definitions_are_current(self):
        for path,content in files().items():
            self.assertEqual(path.read_text(),content,str(path))

    def test_emitted_checks_cover_every_wire_field_and_task_lease(self):
        checks=dict(expected_layout())
        abi=json.loads((ROOT/'abi/gem-vdi.json').read_text())
        for name,record in abi['records'].items():
            self.assertEqual(checks[f'sizeof(struct Gem{name})'],record['size'])
            for field,_,offset,_ in record['fields']:
                self.assertEqual(checks[f'offsetof(struct Gem{name}, {field})'],offset)
        checks=dict(exec_layout())
        self.assertEqual(checks['sizeof(struct TaskLease)'],12)
        self.assertEqual(checks['offsetof(struct TaskLease, identity)'],8)
        self.assertEqual(checks['sizeof(struct ExecRetainTaskPacket)'],6)
        self.assertEqual(checks['offsetof(struct ExecRetainTaskPacket, lease)'],3)

    def test_reply_capacity_covers_the_allowed_batch(self):
        abi=json.loads((ROOT/'abi/gem-vdi.json').read_text())
        ops=abi['vdi_operations']
        outputs={op['opcode']:op['reply_words'] for op in ops}
        self.assertEqual({op for op,n in outputs.items() if n==1},{17,22,23,25,32})
        self.assertEqual(outputs[1],abi['limits']['reply_words'])
        largest=max(op['reply_words'] for op in ops if op['transport']=='SUBMIT')
        self.assertLessEqual(largest*abi['limits']['commands'],abi['limits']['reply_words'])


if __name__=='__main__':
    unittest.main()
