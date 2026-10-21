"""Check the independent checksum oracle against the host POSIX utility."""
import shutil
import subprocess
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
from qed_coexist_load import cksum


class CoexistChecksum(unittest.TestCase):
    @unittest.skipUnless(shutil.which('cksum'), 'Host POSIX cksum unavailable')
    def test_posix_length_encoding_and_octets(self):
        for payload in (b'', b'123456789', bytes(range(256)), b'abc'*1000):
            with self.subTest(bytes=len(payload)):
                expected = subprocess.check_output(['cksum'], input=payload).split()
                self.assertEqual((cksum(payload), len(payload)), tuple(map(int, expected[:2])))


if __name__ == '__main__': unittest.main()
