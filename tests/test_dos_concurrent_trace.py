import sys,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT/'tools'))
from dos_concurrent_trace import packet_observations,call_marker,sector_end_marker
LABELS=dict(dos_submit=16,dos_dispatch=32,dos_collect=48)
def event(t,pc,dp=0,pointer=0):
    return t,['cpu',str(t),'0','8',f'{pc:x}',f'{pointer&65535:x}',f'{pointer>>16:x}','0','7000',f'{dp:x}','0','0','0']
class PacketTraceTests(unittest.TestCase):
    def test_interleaved_collection_and_reused_packet(self):
        rows=[event(1,16,0x2200),event(2,16,0x2400),event(3,32,pointer=0x80000),event(4,32,pointer=0x90001),event(5,48,0x2400,0x90001),event(6,48,0x2200,0x80000),event(7,16,0x2200),event(8,32,pointer=0x80000),event(9,48,0x2200,0x80000)]
        errors=[];result,ops=packet_observations(rows,LABELS,lambda ok,msg:errors.append(msg) if not ok else None)
        self.assertFalse(errors);self.assertEqual(result['count'],3);self.assertEqual(result['caller_dps'],[0x2200,0x2400])
        self.assertEqual([(r['submitted'],r['dispatched'],r['collected']) for r in ops],[(2,4,5),(1,3,6),(7,8,9)])
    def test_empty_reply_poll_is_not_collection(self):
        rows=[event(1,16,0x2200),event(2,48,0x2200),event(3,32,pointer=0x80000),event(4,48,0x2200),event(5,48,0x2200,0x80000)]
        errors=[];result,ops=packet_observations(rows,LABELS,lambda ok,msg:errors.append(msg) if not ok else None)
        self.assertFalse(errors);self.assertEqual(result['count'],1);self.assertEqual(ops[0]['collected'],5)
    def test_missing_or_duplicate_packet_is_rejected(self):
        for rows in ([event(1,16,0x2200)], [event(1,16,0x2200),event(2,16,0x2200)], [event(1,48,0x2200,0x80000)]):
            errors=[];packet_observations(rows,LABELS,lambda ok,msg:errors.append(msg) if not ok else None)
            self.assertTrue(errors)
    def test_markers_require_unique_actual_call_bytes(self):
        p=dict(labels={'get':0x123456},image=dict(routines=[dict(name='M_CALL_F',address=0x10000,size=8)],segments=[dict(address=0x10000,bytes=list(b'\xea\x22\x56\x34\x12\xea\xea\xea'))]))
        self.assertEqual(call_marker(p,'M_CALL_','get',True),0x10005)
        p['image']['segments'][0]['bytes']=list(b'\x22\x56\x34\x12'*2)
        with self.assertRaises(RuntimeError):call_marker(p,'M_CALL_','get',True)
    def test_sector_end_follows_transfer_not_pending_collect(self):
        p=dict(labels={'io_collect':0x123456},image=dict(routines=[
            dict(name='M_BLOCKWIRE_TRANSFER_F',address=0x20000,size=8),
            dict(name='M_FSWORKER_WORKER_F',address=0x10000,size=8)],segments=[
            dict(address=0x20000,bytes=list(b'\x22\x56\x34\x12\xea\xea\xea\x6b')),
            dict(address=0x10000,bytes=list(b'\xea\x22\x00\x00\x02\xea\xea\x6b'))]))
        self.assertEqual(sector_end_marker(p),0x10005)
        self.assertNotEqual(sector_end_marker(p),call_marker(p,'M_BLOCKWIRE_TRANSFER_','io_collect',True))
if __name__=='__main__':unittest.main()
