"""Port contract validation before native compilation."""
import copy
from pathlib import Path
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from generate_ports import ABI,constants,generate,check_routine,public_api


class PortPackageTests(unittest.TestCase):
    def test_layouts_and_staleness(self):
        c=constants()
        self.assertEqual((c['MSGPORT_BYTES'],c['MESSAGE_BYTES']),(27,16))
        with tempfile.TemporaryDirectory() as d:
            generate(d);generate(d,True)
            p=Path(d)/'ports.inc';p.write_bytes(p.read_bytes().replace(b'\n',b'\r\n'))
            generate(d,True)
            p.write_text(p.read_text()+'; stale\n')
            with self.assertRaises(ValueError):generate(d,True)

    def test_rejects_invalid_contract(self):
        mutations=[lambda a:a['services'].update(PUT_MSG=26),
                   lambda a:a['services'].update(PUT_MSG=15),
                   lambda a:a['services'].update(PUT_MSG=58),
                   lambda a:a['services'].update(PUT_MSG=33),
                   lambda a:a['errors'].update(MISUSE=0xff11),
                   lambda a:a['constants'].update(PA_IGNORE=1),
                   lambda a:a['records']['MsgPort'].update(size=28),
                   lambda a:a['records']['Message']['fields'][2].__setitem__(2,15),
                   lambda a:a['imports']['GetMsg'].update(result_bytes=2)]
        for mutate in mutations:
            a=copy.deepcopy(ABI);mutate(a)
            with self.assertRaises(ValueError):constants(a)

    def test_import_widths(self):
        for name,shape in ABI['imports'].items():
            check_routine(shape,name)
            bad=copy.deepcopy(shape);bad['outgoing_bytes']+=2
            with self.assertRaises(ValueError):check_routine(bad,name)
            bad=copy.deepcopy(shape);bad['result_bytes']+=1
            with self.assertRaises(ValueError):check_routine(bad,name)
        self.assertIn('PUBLIC TYPE MsgPort',public_api())

    def test_registry_prefix(self):
        from generate_memory import layout
        from generate_heap import reserve_metadata as heap
        from generate_ports import reserve_metadata,registration_include
        from generate_tasks import validate_memory
        from task_capacity import configure
        for capacity in (4,8):
            memory=layout(upper_table=capacity==8)
            if capacity==8:configure(memory,8)
            heap(memory);old=memory['profile']['code_origin'];reserve_metadata(memory)
            self.assertEqual(memory['ports_storage'],dict(BASE=old,BYTES=16,ACTIVE_BYTES=11))
            self.assertEqual(memory['profile']['code_origin'],old+16)
            validate_memory(memory)
            with tempfile.TemporaryDirectory() as directory:
                registration_include(directory,memory)
                self.assertIn(f'${old:x}',(Path(directory)/'ports-storage.inc').read_text())
        memory['profile']['code_origin']=0x1fff1
        with self.assertRaises(ValueError):reserve_metadata(memory)

    def test_publish_rejects_failed_timing(self):
        import json
        from record_ports import publish
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'report.json'
            path.write_text(json.dumps(dict(status='pass',timing_verdict='fail')))
            with self.assertRaises(RuntimeError):publish(Path(directory)/'record.json',[path])
            self.assertFalse((Path(directory)/'record.json').exists())
