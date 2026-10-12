"""Host producer interface checks; emitted/disk read-back runs separately."""
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import sdfs_reference


class Labels(unittest.TestCase):
    def test_default_and_explicit_labels(self):
        with patch.object(sdfs_reference, 'reference', return_value=Path('/producer')), \
                patch.object(sdfs_reference.subprocess, 'run') as run:
            for label in ('EXEC816', 'SYS', 'WORK', 'ABCDEFGH', ''):
                if label == 'EXEC816':
                    sdfs_reference.make('disk.atr', 'source')
                else:
                    sdfs_reference.make('disk.atr', 'source', label=label)
                self.assertEqual(run.call_args.args[0][-1], label)

    def test_invalid_labels_rejected_before_build(self):
        with patch.object(sdfs_reference, 'reference') as producer:
            for label in ('123456789', 'SYS\x00', 'SYS\n', 'zażółć'):
                with self.assertRaises(ValueError):
                    sdfs_reference.make('disk.atr', 'source', label=label)
            producer.assert_not_called()
