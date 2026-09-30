"""Fail closed on incomplete transport evidence and malformed ATR geometry."""
import copy,hashlib,json,struct,sys,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from sio_sector_record import validate,validate_historical_inputs,validate_current_inputs,fresh_inputs,snapshot_inputs
from sector_images import disk_image
from historical_git import history_repository

class SectorTests(unittest.TestCase):
    def test_short_boot_and_large_atr(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'disk.atr'
            for size in (128,256):
                sector=disk_image(p,size,65535);image=p.read_bytes()
                magic,lo,actual,hi=struct.unpack_from('<HHHH',image)
                self.assertEqual((magic,actual),(0x296,size))
                self.assertEqual((lo+(hi<<16))*16,len(image)-16)
                self.assertEqual(len(image),16+384+65532*size)
                self.assertEqual(image[400:400+size],sector)
                self.assertEqual(image[272:400],bytes((i^45)&255 for i in range(128)))
                self.assertEqual(image[-size:],bytes((i^(65535*15))&255 for i in range(size)))

    def test_published_gate(self):
        r=json.loads((ROOT/'docs/qualification/sio-sectors.json').read_text())
        validate(r)
        for fault in ('mode','case','deadline','replay','capacity','recovery','profile','input'):
            bad=copy.deepcopy(r);suite=bad['suites'][0];case=next(c for c in suite['cases'] if c['name']=='concurrent-8')
            if fault=='mode':bad['suites'].pop()
            elif fault=='case':suite['cases'].pop()
            elif fault=='deadline':case['timing']['rx_service']['max_us']=100
            elif fault=='replay':case['replay']['status']='skipped'
            elif fault=='capacity':case['observed']['peakTasks']=4
            elif fault=='recovery':next(c for c in suite['cases'] if c['name']=='recovery')['cases'].pop()
            elif fault=='profile':next(c for c in suite['cases'] if c['name']=='regression-1')['runtime']['status']=1
            else:case['build']['task_inputs']['lib/siodriver.act']='stale'
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):validate(bad)

    def test_historical_provenance(self):
        record=json.loads((ROOT/'docs/qualification/sio-sectors.json').read_text())
        provenance=json.loads((ROOT/'docs/qualification/sio-sectors-provenance.json').read_text())
        history=history_repository(ROOT,(item['commit'] for item in provenance['inputs'].values()))
        validate_historical_inputs(record,provenance,ROOT,git_root=history)

    def test_historical_provenance_rejects_changed_identity(self):
        record=json.loads((ROOT/'docs/qualification/sio-sectors.json').read_text())
        provenance=json.loads((ROOT/'docs/qualification/sio-sectors-provenance.json').read_text())
        history=history_repository(ROOT,(item['commit'] for item in provenance['inputs'].values()))
        validate_historical_inputs(record,provenance,ROOT,git_root=history)
        for fault in ('missing','blob','hash','record'):
            bad=copy.deepcopy(provenance)
            if fault=='missing':bad['inputs'].pop('lib/siodriver.act')
            elif fault=='record':bad['record_sha256']='0'*64
            else:bad['inputs']['lib/siodriver.act']['blob' if fault=='blob' else 'sha256']='0'*(40 if fault=='blob' else 64)
            with self.subTest(fault=fault),self.assertRaises(RuntimeError):
                validate_historical_inputs(record,bad,ROOT,git_root=history)

    def test_fresh_sources_and_execution_snapshots(self):
        inputs=snapshot_inputs(ROOT)
        suites=[{'inputs':dict(inputs)},{'inputs':dict(inputs)}]
        self.assertEqual(fresh_inputs(suites,ROOT),inputs)
        validate_current_inputs({'inputs':inputs},ROOT)
        suites[0]['inputs']['tools/test_sio_sectors.py']='stale'
        with self.assertRaises(RuntimeError):fresh_inputs(suites,ROOT)
        with self.assertRaises(RuntimeError):fresh_inputs([{}],ROOT)
        with self.assertRaises(RuntimeError):validate_current_inputs(suites[0],ROOT)

if __name__=='__main__':unittest.main()
