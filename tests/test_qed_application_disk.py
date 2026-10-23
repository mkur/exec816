"""QED's application payload must remain separate from the core SYS disk."""
import hashlib
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from qed_demo import media


class ApplicationDiskTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        (self.root/'system.atr').write_bytes(b'SYS');(self.root/'qed.atr').write_bytes(b'QED')
        digest=lambda b:hashlib.sha256(b).hexdigest()
        self.entry=dict(media='qed.atr',media_sha256=digest(b'QED'),
                        app_sha256=digest(b'APP'),resource_sha256=digest(b'RSC'))
        self.system=Mock(files={'C/HELLO':b'command'})
        self.editor=Mock(files={'QED.APP':b'APP','QED.RSC':b'RSC'})

    def audit(self):
        with patch('filesystem_audit.Audit',side_effect=[self.system,self.editor]):
            return media(self.entry,self.root)

    def test_separate_payload(self):self.audit()

    def test_core_payload_is_rejected_in_any_directory(self):
        for path in ('QED.APP','C/QED.APP','QED.RSC'):
            self.system.files={path:b'payload'}
            with self.assertRaisesRegex(RuntimeError,'main system disk'):self.audit()

    def test_missing_or_changed_application_disk_is_rejected(self):
        (self.root/'qed.atr').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'Changed QED input'):self.audit()

    def test_incorrect_resource_is_rejected(self):
        self.editor.files['QED.RSC']=b'other'
        with self.assertRaisesRegex(RuntimeError,'payload differs'):self.audit()
