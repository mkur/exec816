"""Do not drop the first instruction when an emitted label shares its row."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from measure_qed_frames import emitted_instructions,frame_cost,source_listings

class QedFrameTests(unittest.TestCase):
    def test_retired_unit_listings_do_not_override_the_current_link(self):
        from tempfile import TemporaryDirectory
        with TemporaryDirectory() as directory:
            root=Path(directory)
            linked=root/'0-current.o'
            linked.with_suffix('.lst').write_text('current frame')
            (root/'0-retired.lst').write_text('obsolete frame')
            image=dict(provenance=dict(link_objects=[str(linked),str(root/'1-imports-asm.o')]))
            self.assertEqual(source_listings(image),[linked.with_suffix('.lst')])

    def test_inline_entry_reservation_is_counted_with_saved_registers(self):
        listing=r'''
    \ 000000 3b        undo:     tsc
    \ 000001 38                  sec
    \ 000002 e90604              sbc     ##1030
    \ 000005 1b                  tcs
    \ 000006 d408      `?L1`:    pei     dp:(_Dp+8)
    \ 000008 22......            jsl     long:memcpy
'''
        instructions=emitted_instructions(listing)
        self.assertEqual(instructions[0][2],'tsc')
        self.assertEqual(frame_cost(instructions),(1030,2))
        self.assertEqual(instructions[-1][3],'long:memcpy')

    def test_unknown_reservation_does_not_silently_disappear(self):
        with self.assertRaisesRegex(RuntimeError,'Unclassified'):
            frame_cost([(0,'3b','tsc',''),(1,'e9..','sbc','##unsupported'),(4,'1b','tcs','')])

class QedObservationTests(unittest.TestCase):
    def test_actual_image_base_resolves_aliases_and_excludes_candidate_sites(self):
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import qed_stack_observer as observer
        memory=dict(task_pools=[dict(stack_base=0x2000,stack_bytes=1312,dp=0x1000)],
                    regions={'kernel-stack':(0x3000,0x3400)})
        native={0x1234:'M_PROCESS_RUN_TEST'}
        broad={**native,0x1240:'app:wrong-name',0x1242:'app:wrong-base:after-tcs',
               0x1244:'app:another-alias'}
        actual={**native,0x1240:'app:main',0x1244:'app:actual:after-tcs'}
        # The candidate-only site has a lower S and a different DP. It is not
        # an APP frame for this owner and must not affect either check.
        events=[(10,0x1234,0x2500,0x1000),(11,0x1240,0x2480,0x1000),
                (12,0x1242,0x2010,0x1001),(13,0x1244,0x2400,0x1000)]
        log=''.join(f'[SIOPOC] cpu {clock} 0 8 {pc:06x} 0000 0000 0000 {s:04x} {dp:04x} 00 00 0\n'
                    for clock,pc,s,dp in events)
        owner=dict(slot=0,identity=41,image_base=0x50000)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'trace.log';path.write_text(log)
            def points(program,app,image_bases=None):
                if image_bases is not None:self.assertEqual(image_bases,[owner['image_base']])
                return actual if image_bases is not None else broad
            with patch.object(observer,'markers',side_effect=points):
                report=observer.summarize_owned(path,{}, {},memory,[owner])
                self.assertEqual(report['lifetimes'][0]['app_entry'],0x1240)
                frame=next(x for x in report['minima'] if x['kind']=='frame-reservation')
                self.assertEqual(frame['marker'],'app:actual:after-tcs')
                self.assertEqual(frame['minimum_s'],0x2400)
                # Actual sites still enforce direct-page ownership.
                path.write_text(log.replace('2400 1000','2400 1001'))
                with self.assertRaisesRegex(RuntimeError,'direct-page ownership'):
                    observer.summarize_owned(path,{}, {},memory,[owner])

    def test_stack_reanalysis_preserves_execution_evidence(self):
        import json
        from tempfile import TemporaryDirectory
        from unittest.mock import patch
        import record_qed_editing as recorder
        from native_program import sha256
        with TemporaryDirectory() as directory:
            root = Path(directory)
            prior = root / 'original'
            current = root / 'reanalyzed'
            prior.mkdir(); current.mkdir()
            observer = root / 'tools/qed_stack_observer.py'
            observer.parent.mkdir(); observer.write_bytes(b'observer')
            for path in (prior, current):
                (path / 'emulator.log').write_bytes(b'unchanged native trace')
            old = dict(status='pass', checks=[14], stacks={'minimum': 1000})
            (prior / 'results.json').write_text(json.dumps(old))
            origin = dict(results_path='original/results.json',
                results_sha256=sha256(prior / 'results.json'),
                trace_sha256=sha256(prior / 'emulator.log'),
                observer_sha256=sha256(observer))
            new = dict(old, stacks={'minimum': 700}, stack_reanalysis=origin)
            with patch.object(recorder, 'ROOT', root):
                self.assertEqual(recorder.checked_stack_reanalysis(current, new), origin)
                new['checks'] = [15]
                with self.assertRaisesRegex(RuntimeError, 'changed execution evidence'):
                    recorder.checked_stack_reanalysis(current, new)

    def test_selected_lifetime_keeps_its_identity_and_checks_dp(self):
        from tempfile import TemporaryDirectory
        from qed_stack_observer import summarize
        memory=dict(task_pools=[dict(stack_base=0x2000,stack_bytes=1312,dp=0x1000)],
                    regions={'kernel-stack':(0x3000,0x3400)})
        points={0x1234:'M_PROCESS_RUN_TEST',0x1238:'M_PROCESS_RUN_TEST:after-tcs',
                0x1240:'app:body:after-tcs'}
        events=[(10,0x1234,0x2500),(10,0x1238,0x2480),(11,0x1240,0x2400),
                (20,0x1234,0x2500),(21,0x1240,0x2300)]
        log=''.join(f'[SIOPOC] cpu {clock} 0 8 {pc:06x} 0000 0000 0000 {s:04x} 1000 00 00 0\n'
                    for clock,pc,s in events)
        with TemporaryDirectory() as directory:
            path=Path(directory)/'trace.log';path.write_text(log)
            report=summarize(path,points,memory,dict(slot=0,identity=41))
            self.assertEqual(report['lifetimes'][0]['identity'],41)
            self.assertEqual(len(report['lifetimes']),1)
            frame=next(x for x in report['minima'] if x['kind']=='frame-reservation')
            self.assertEqual(frame['minimum_s'],0x2400)
            path.write_text(log.replace('2400 1000','2400 1001'))
            with self.assertRaisesRegex(RuntimeError,'direct-page ownership'):
                summarize(path,points,memory,dict(slot=0,identity=41))
