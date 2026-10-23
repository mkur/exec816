"""Final delivery rejects incomplete execution and stale concrete artifacts."""
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from native_program import sha256
from record_qed_delivery import passed_execution, reproduced, grants, gate_identities
from check_qed_reproduction import RUNTIME


class DeliveryRecordTests(unittest.TestCase):
    def setUp(self):
        temporary=tempfile.TemporaryDirectory();self.addCleanup(temporary.cleanup)
        self.root=Path(temporary.name);(self.root/'of816').mkdir()
        for name in ('exec816-demo.zip','system.atr','of816/Exec-of816.xex'):(self.root/name).write_bytes(name.encode())
        observer=Path(__file__).resolve()
        self.result=dict(status='pass',tier='development',autoboot_frames=250,
            observer_inputs={str(observer):sha256(observer)},
            integration=dict(normal_collection=True),production_app_sha256='APP',
            runtime=dict(status=0,guards='intact',live_tasks=0,native_nmi_count=1,native_irq_count=1,
                         switching=0,os_busy=0),zip_sha256=sha256(self.root/'exec816-demo.zip'),
            media_sha256=sha256(self.root/'system.atr'),boot_xex_sha256=sha256(self.root/'of816/Exec-of816.xex'))
        self.path=self.root/'result.json';self.write()

    def write(self):self.path.write_text(json.dumps(self.result))

    def test_completed_execution(self):passed_execution(self.path,self.root,'APP')

    def test_live_task_and_missing_os_return_do_not_pass(self):
        self.result['runtime']['live_tasks']=1;self.write()
        with self.assertRaisesRegex(RuntimeError,'Incomplete QED delivery execution'):
            passed_execution(self.path,self.root,'APP')

    def test_diagnostic_media_does_not_close_healthy_package(self):
        self.result['diagnostic_media_sha256']='diagnostic';self.write()
        with self.assertRaisesRegex(RuntimeError,'healthy candidate'):
            passed_execution(self.path,self.root,'APP')

    def test_changed_zip_or_media_rejects_old_execution(self):
        for name in ('exec816-demo.zip','system.atr'):
            path=self.root/name;original=path.read_bytes();path.write_bytes(b'changed')
            with self.assertRaisesRegex(RuntimeError,'healthy candidate'):
                passed_execution(self.path,self.root,'APP')
            path.write_bytes(original)

    def test_incomplete_or_changed_reproduction(self):
        record=dict(status='pass',clean_checkout=True,builds=[str(self.root),str(self.root/'second')],
            runtime_files={name:sha256(self.root/'system.atr') for name in RUNTIME},zip_sha256=sha256(self.root/'exec816-demo.zip'))
        self.path.write_text(json.dumps(record));(self.root/'second').mkdir()
        (self.root/'second/system.atr').write_bytes(b'changed')
        with self.assertRaisesRegex(RuntimeError,'Changed QED input'):reproduced(self.path,self.root)
        record['builds']=[];self.path.write_text(json.dumps(record))
        with self.assertRaisesRegex(RuntimeError,'Incomplete QED reproducibility'):reproduced(self.path,self.root)

    def test_stale_gate_does_not_close_current_candidate(self):
        identity=dict(app_sha256='APP',provider_identity='PROVIDER',resource_sha256='RSC')
        records=dict(qd1=identity,qd2=dict(qed=identity),qd3={},
            qd4=dict(production_app_sha256='APP'),
            qd5=dict(production_app_sha256='OLD',provider_identity='PROVIDER'),
            qd6=dict(**identity,source_revision='REV'))
        gates={}
        for name,record in records.items():
            path=self.root/(name+'.json');path.write_text(json.dumps(record));gates[name]=path
        manifest=dict(qed=identity,kernel=dict(exec_build=dict(revision='REV')))
        with self.assertRaisesRegex(RuntimeError,'Stale QED gate APP: qd5'):gate_identities(gates,manifest)


    def test_missing_component_grant_is_not_supported(self):
        with self.assertRaisesRegex(RuntimeError,'Incomplete QED component grants'):
            grants(dict(grants={'qed':'donor terms'}))

    def test_clearing_unresolved_does_not_supply_authority(self):
        policy=dict(grants={name:'grant' for name in ('qed','cflib','native','bindings','runtime')},unresolved=[])
        with self.assertRaisesRegex(RuntimeError,'Missing explicit native adapter grant'):grants(policy)
