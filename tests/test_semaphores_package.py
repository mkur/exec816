"""Native semaphore ABI placement and selector admission contracts."""
import copy
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import generate_semaphores as sem
from generate_tasks import ABI as tasks, fields


class SemaphorePackageTests(unittest.TestCase):
    def test_native_object_is_compact_and_word_aligned(self):
        c = sem.constants()
        self.assertEqual((c['SEM_SIZE'], c['SEM_ALIGNMENT']), (12, 2))
        self.assertEqual([c['SEM_'+n] for n in ('OWNER', 'DEPTH', 'HEAD', 'TAIL')], [0, 4, 6, 9])
        self.assertEqual(tasks['task']['size'], 62)
        self.assertEqual(tasks['context']['size'], 64)
        c = fields(tasks['context'], 'TCB')
        self.assertEqual((c['TCB_SEMAPHOREOWNED'], c['TCB_SEMAPHOREWAIT']), (50, 52))

    def test_collision_with_existing_public_service_is_rejected(self):
        damaged = copy.deepcopy(sem.ABI)
        damaged['services']['ATTEMPT_SEMAPHORE'] = tasks['services']['FORBID']
        with patch.object(sem, 'ABI', damaged), self.assertRaisesRegex(RuntimeError, 'collision'):
            sem.constants()

    def test_native_imports_use_far_pointer_and_full_long_result(self):
        for name, shape in sem.ABI['imports'].items():
            self.assertEqual(shape['arguments'], [{'alignment': 1, 'offset': 0, 'size': 3}])
            self.assertEqual(shape['outgoing_bytes'], 3)
            self.assertEqual(shape['result_bytes'], 4 if name == 'AttemptSemaphore' else 0)
        with tempfile.TemporaryDirectory() as folder:
            sem.generate(folder)
            self.assertTrue((Path(folder)/'semaphore-abi.inc').is_file())


if __name__ == '__main__':
    unittest.main()
