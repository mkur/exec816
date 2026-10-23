"""A source/relink claim requires the actual mapped sources and objects."""
import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from c_program import ABI
from relink_qed import material, COMPONENTS


class SourceMaterialTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name)
        self.files={name:b'file '+name.encode() for name in ('objects/library.o',
            'source/cflib/library.c','exec816/c/calypsi/layout.scm')}
        for prefix in COMPONENTS.values():self.files[prefix+'source.c']=b'source'
        for name,data in self.files.items():
            path=self.root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(data)
        inventory=dict(status='pass',app_sha256='APP',native_files={'native/source.c':dict(sha256=hashlib.sha256(b'source').hexdigest())},
            link_units=[dict(component='cflib',source='source/cflib/library.c',object='library.o')])
        self.files['link-inventory.json']=json.dumps(inventory).encode()
        (self.root/'link-inventory.json').write_bytes(self.files['link-inventory.json'])
        self.record=dict(schema_version=1,abi=ABI,source_revision='revision',app_sha256='APP',
            application_sources={'source/cflib/library.c':hashlib.sha256(self.files['source/cflib/library.c']).hexdigest()},objects=['objects/library.o'],
            cflib_objects={'objects/library.o':'source/cflib/library.c'},
            components=['qed','cflib','native','bindings','runtime','exec','gem','calculator','g4bench','actionc-runtime'],
            component_sources={c:[prefix+'source.c'] for c,prefix in COMPONENTS.items()},
            files={name:hashlib.sha256(data).hexdigest() for name,data in self.files.items()})
        self.write()

    def write(self):
        (self.root/'source-material.json').write_text(json.dumps(self.record))

    def test_complete_material(self):material(self.root)

    def test_missing_library_source(self):
        (self.root/'source/cflib/library.c').unlink()
        with self.assertRaisesRegex(RuntimeError,'Missing/changed QED material'):material(self.root)

    def test_changed_application_object(self):
        (self.root/'objects/library.o').write_bytes(b'different')
        with self.assertRaisesRegex(RuntimeError,'Missing/changed QED material'):material(self.root)

    def test_missing_component_or_mapping(self):
        self.record['components'].remove('runtime');self.write()
        with self.assertRaisesRegex(RuntimeError,'component inventory'):material(self.root)
        self.record['components'].append('runtime');self.record['cflib_objects']['objects/library.o']='missing.c';self.write()
        with self.assertRaisesRegex(RuntimeError,'library/object mapping'):material(self.root)


    def test_component_label_without_source_is_rejected(self):
        self.record['component_sources']['native']=[];self.write()
        with self.assertRaisesRegex(RuntimeError,'Missing QED component source: native'):material(self.root)
