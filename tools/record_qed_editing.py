#!/usr/bin/env python3
"""Freeze measured editing development evidence after reconciling its inputs."""
import argparse
import json
import re
from pathlib import Path
from check_qed_baseline import check, checked
from native_program import ROOT, require, sha256


def checked_stack_reanalysis(path, result):
    origin = result.get('stack_reanalysis')
    if origin is None:
        return None
    original = ROOT / origin['results_path']
    checked(original, origin['results_sha256'])
    checked(original.parent / 'emulator.log', origin['trace_sha256'])
    checked(path / 'emulator.log', origin['trace_sha256'])
    checked(ROOT / 'tools/qed_stack_observer.py', origin['observer_sha256'])
    prior = json.loads(original.read_text())
    require({k: v for k, v in result.items() if k not in ('stacks', 'stack_reanalysis')} ==
            {k: v for k, v in prior.items() if k != 'stacks'},
            'Stack reanalysis changed execution evidence: ' + str(path))
    return origin


def record(slice_name, directory, cohorts, destination, host_log, supplements=(),protocols=()):
    audit = check(directory, cohorts, [])
    audit_path = directory.parent / (slice_name.lower()+'-baseline.json')
    audit_path.write_text(json.dumps(audit, indent=2)+'\n')
    host = re.search(r'Ran (\d+) tests.*\n\nOK(?: \(skipped=(\d+)\))?\s*$',
                     host_log.read_text(), re.S)
    require(host is not None, 'Missing passing host suite result')
    layout = json.loads((directory / 'layout.json').read_text())
    frames = json.loads((directory / 'stack-frames.json').read_text())
    baseline = json.loads((ROOT / 'docs/development/qed-startup-qs5.json').read_text())
    measured = layout['layout']
    prior = baseline['executable']['layout']
    provider = layout['resident_provider']
    public = baseline['resident_provider']
    private_growth = dict(code_bytes=measured['code_bytes']-prior['code_bytes'],
        data_bss_bytes=measured['initialized_bytes']+measured['bss_bytes']-
            prior['initialized_bytes']-prior['bss_bytes'],
        metadata_bytes=(measured['serialized_bytes_if_executable']-measured['code_bytes']-
            measured['initialized_bytes'])-(prior['serialized_bytes_if_executable']-
            prior['code_bytes']-prior['initialized_bytes']))
    provider_growth = {k: provider[k]-public[k] for k in
                       ('code_bytes', 'table_bytes', 'data_bss_bytes')}
    remaining = {k: baseline['growth_from_step2']['provider_remaining_allowances'][k]-v
                 for k, v in provider_growth.items()}
    require(all(v >= 0 for v in remaining.values()), 'Provider exceeds frozen growth allowance')
    # Compare complete reservations, rather than only used stack watermarks.
    old_memory = json.loads((ROOT / 'build/qed-startup/qs4-failures/program/memory.json').read_text())
    memory = json.loads((cohorts[0] / 'program/memory.json').read_text())
    same_pools = memory['task_pools'] == old_memory['task_pools']
    same_regions = memory['regions'] == old_memory['regions']
    require(same_pools and same_regions,
            'Reservation changed: record a measured bank-zero budget amendment first')
    executed = []
    scenes = []
    for path in cohorts:
        result = json.loads((path / 'results.json').read_text())
        scenes.extend(result.get('qed_editing', []))
        executed.append(dict(path=str(path.relative_to(ROOT)),
            results_sha256=sha256(path / 'results.json'), completed=result['completed'],
            checks=result['checks'], snapshots=[s['name'] for scene in result.get('qed_editing', [])
                for s in scene['snapshots']],
            minimum_headroom=min(r['headroom'] for r in result['stacks']['minima']
                if r['lifetime'] and r['kind'] != 'async')))
        origin = checked_stack_reanalysis(path, result)
        if origin is not None:
            executed[-1]['stack_reanalysis'] = origin
        if 'clipboard_core' in result:
            executed[-1]['clipboard_core_heap'] = result['clipboard_core']
        if 'qed_selector' in result:
            executed[-1]['qed_selector'] = result['qed_selector']
    if slice_name == 'QE1':
        expected = {'empty', 'insert', 'split', 'join', 'allocation-rollback',
            'split-allocation-rollback', 'literal-tab', 'tab-delete', 'save-disabled',
            'close-cancel', 'native-up', 'native-right', 'overwrite',
            'forward-delete-join', 'quit-cancel', 'clean-shortcut', 'stop-dirty', 'stop-cancel'}
        seen = {s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected <= seen, 'Incomplete QE1 checkpoints: '+str(expected-seen))
        for scene in scenes:
            for snapshot in scene['snapshots']:
                require(snapshot['ending'] == 1 and bool(snapshot['dirty']) ==
                    (snapshot['name'] not in ('empty', 'clean-shortcut')),
                    'Incorrect ending/dirty state: '+snapshot['name'])
                require(snapshot['pixels']['checked'] > 0, 'Missing independent pixels')
    if slice_name == 'QE2':
        expected={'wide-line-end','wide-desired-column','wide-line-start',
            'covered-document','moved-document','covered-after-move','exposed-document',
            'full-document','restored-document','resized-document','vertical-end',
            'vertical-up','vertical-down','vertical-page-up','vertical-page-down',
            'vertical-thumb-top','cursor-revealed'}
        seen={s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected<=seen,'Incomplete QE2 checkpoints: '+str(expected-seen))
        carets={c['name'] for scene in scenes for c in scene.get('carets',[])
                if c['pixels'].get('caret_checked',0)>0}
        require({'wide-line-caret','wide-start-caret','exposed-caret','scrolled-caret'}<=carets,
                'Missing completed caret pixel checks')
        require(all(s['pixels']['checked']>0 for scene in scenes for s in scene['snapshots']),
                'Missing viewport pixels')
    if slice_name in ('QE2','QE3','QE5'):
        for path,item in zip(cohorts,executed):
            if not (path/'peer/app.json').exists():continue
            peer=json.loads((path/'peer/app.json').read_text())
            checked(path/'peer/program.app',peer['sha256'])
            for name,digest in peer['inputs'].items():checked(Path(name),digest)
            item['peer_app_sha256']=peer['sha256']
    if slice_name=='QE3':
        expected={'forward-range','backward-range','escape-clears','shift-click',
            'select-all','collapse-start','fast-click','held-inside-release',
            'geometry-cancels','focus-cancels','input-loss-cancels',
            'selection-close-cancel','exposed-range','exposed-cleared',
            'scroll-left','scroll-right','scroll-down','scroll-up',
            'clock-failure-retains-document','after-clock-failure','selection-stop-cancel'}
        seen={s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected<=seen,'Incomplete QE3 checkpoints: '+str(expected-seen))
        editor=[s for s in scenes if s['cycle']==0 and 'inside_wait' in s]
        require(len(editor)==1,'Missing ordinary-client selection session')
        session=editor[0];wait=session['inside_wait']
        require(wait['task_state']==4 and wait['interest']==7 and
            wait['update']==wait['mctrl']==wait['alarm_state']==0 and
            wait['peer_paints_after']!=wait['peer_paints_before'],
            'Inside selection did not sleep while its peer painted')
        scroll=session.get('autoscroll',[])
        require({(s['axis'],s['direction']) for s in scroll}==
            {('x',-1),('x',1),('y',-1),('y',1)},'Missing autoscroll direction')
        require(all(0<=s['first_progress_frames']<=250 and
            1<=s['steps']<=s['frames']//5+1 for s in scroll),'Invalid autoscroll bound')
        require({s['cycle'] for s in scenes}=={0,1,2,3},'Missing selection lifetimes')
        require(all(s['pixels']['checked']>0 for scene in scenes for s in scene['snapshots']),
            'Missing independent selection pixels')
        require(any(c['name']=='selection-exposed-caret' and c['pixels']['caret_checked']>0
            for scene in scenes for c in scene.get('carets',[])),'Missing exposed caret')
    if slice_name=='QE4':
        expected={'shortcut-copy','shortcut-cut','shortcut-paste','undo-cut',
            'undo-toggle-cut','undo-paste','undo-toggle-paste','menu-cut-newline',
            'menu-paste-newline','menu-undo','menu-toggle','clipboard-allocation-rollback',
            'cut-allocation-rollback','typed-selection-replacement','undo-selection-replacement',
            'undo-typing-group','toggle-typing-group','edit-invalidates-toggle',
            'cut-to-empty','paste-from-empty','clipboard-stop-cancel'}
        seen={s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected<=seen,'Incomplete QE4 checkpoints: '+str(expected-seen))
        require({s['cycle'] for s in scenes}=={0,1,2,3},'Missing clipboard lifetimes')
        require(all(s['pixels']['checked']>0 for scene in scenes for s in scene['snapshots']),
            'Missing independent clipboard pixels')
        require(any(scene.get('clipboard') for scene in scenes),'Missing clipboard byte oracle')
        require(any(c['name']=='clipboard-caret' and c['pixels']['caret_checked']>0
            for scene in scenes for c in scene.get('carets',[])),'Missing clipboard caret')
        require(any(item.get('clipboard_core_heap',{}).get('peak_backing',0)>131072
            for item in executed),'Missing multi-bank clipboard heap observation')
    if slice_name=='QE5':
        expected={'literal-find','literal-find-next','find-not-found-retains-range',
            'find-cancel-retains-pattern','find-move-resumes-draft','find-close-cancel','find-close-escape-zero',
            'find-too-small','find-field-limit','find-allocation-rollback',
            'about-cancel','find-stop-cancel'}
        seen={s['name'] for scene in scenes for s in scene['snapshots']}
        require(expected<=seen,'Incomplete QE5 checkpoints: '+str(expected-seen))
        require({s['cycle'] for s in scenes}=={0,1,2,3},'Missing dialog lifetimes')
        require(all(s['pixels']['checked']>0 for scene in scenes for s in scene['snapshots']),
            'Missing document pixels around dialogs')
        forms={f['name'] for scene in scenes for f in scene.get('forms',[]) if f['pixels']>0}
        require({'find-empty','find-literal','about','about-native-details'}<=forms,'Missing independent native form pixels')
        require(any(s.get('accepted_pattern_bytes')==50 for s in scenes),'Missing Find field limit')
        session=next(s for s in scenes if 'form_peer' in s)
        peer=session['form_peer'];move=session['form_move']
        require(peer['task_state']==4 and peer['update']==peer['mctrl']==0 and
            peer['paints_before']!=peer['paints_after'],'Dialog blocked its ordinary peer')
        require(move['starts_after']==move['starts_before']+1,'Move did not resume exactly once')
        selectors=[s for item in executed for s in item.get('qed_selector',[])]
        require(len(selectors)==2 and all(len(s['executed'])==5 for s in selectors),
            'Missing actual native selector lifetimes')
    supplemental=[]
    for path in supplements:
        result=json.loads((path/'results.json').read_text())
        require(result['status']=='pass' and result['AESFailures']==0 and
                result['AESDone']==2 and result['mode_pixels'], 'Failed VDI pixel cohort')
        resident=json.loads((path/'c-image.json').read_text())
        for name,digest in resident['provenance']['source_inputs'].items():
            checked(ROOT/name,digest)
        supplemental.append(dict(path=str(path.relative_to(ROOT)),
            results_sha256=sha256(path/'results.json'),provider_sha256=sha256(path/'c-image.json'),
            checks=result['AESChecks'],mode_pixels=result['mode_pixels'],
            scope='Instrumented general VDI provider; separate from production provider identity'))
    protocol_records=[]
    for path in protocols:
        result=json.loads((path/'results.json').read_text())
        require(result['status']=='pass' and result['AESFailures']==0 and
            result['AESChecks']>0 and result['runtime']['native_nmi_count']>0 and
            result['runtime']['native_irq_count']>0,'Failed AES protocol cohort')
        for group in ('platform_inputs','task_inputs','console_inputs','banked_inputs'):
            for name,digest in result['build'].get(group,{}).items():checked(ROOT/name,digest)
        resident=json.loads((path/'c-image.json').read_text())
        for name,digest in resident['provenance']['source_inputs'].items():checked(ROOT/name,digest)
        protocol_records.append(dict(path=str(path.relative_to(ROOT)),
            results_sha256=sha256(path/'results.json'),checks=result['AESChecks'],
            boundary_checks=result.get('boundary_checks',0),
            scope='Separate emitted AES protocol fixture; no QED session or production-provider identity claim'))
    result = dict(schema_version=1, slice=slice_name, status='pass', tier='development',
        qualification=False,
        audit=dict(path=str(audit_path.relative_to(ROOT)), sha256=sha256(audit_path),
            auditor_sha256=audit['auditor_sha256'],provider_identity=audit['provider_identity']),
        source_pins={name: {k: pin[k] for k in ('revision', 'tree')}
                     for name, pin in audit['source_pins'].items()},
        resource=audit['resource'],
        host_checks=dict(path=str(host_log.relative_to(ROOT)),sha256=sha256(host_log),
            tests=int(host[1]),expected_skips=int(host[2] or 0)),
        executable=dict(path=str(directory.relative_to(ROOT)),
            sha256=layout['app']['sha256'], layout=measured,
            requested_image_backing_bytes=measured['span_bytes']+65535,
            rounded_image_backing_bytes=(measured['span_bytes']+65535+7)//8*8,
            backing_basis='CAPP bank-alignment request, rounded to the public heap eight-byte allocation; historical layout field rounds to four bytes'),
        frame_ledger={k: frames[k] for k in ('source_chain_bytes', 'continuation_cap_bytes',
            'interrupt_reserve_bytes', 'required_headroom_bytes', 'admission_bytes', 'margin_bytes')},
        growth_from_QS5=dict(private=private_growth, provider=provider_growth),
        provider_remaining_allowances=remaining, executed=executed, supplemental=supplemental,
        private_heap=dict(peak_backing_bytes=max((s['private_heap'][3] for scene in scenes
            for s in scene['snapshots'] if 'private_heap' in s),default=0),
            basis='Private allocation headers included; underlying allocator rounding and native GUI owners charged separately'),
        bank_zero_delta=dict(fixed=0, per_public_task=0, private_idle=0,
            basis='Complete Task-pool and region maps equal QS5; guards, alignment and slack included'),
        recorder_sha256=sha256(Path(__file__)))
    if protocol_records:
        result['protocol_checks']=protocol_records
    if slice_name=='QE3':
        result['selection']=dict(inside_wait=editor[0]['inside_wait'],autoscroll=scroll)
        path=ROOT/'docs/development/qed-shortcuts.json'
        result['shortcut_checks']=dict(path=str(path.relative_to(ROOT)),sha256=sha256(path))
    destination.write_text(json.dumps(result, indent=2)+'\n')
    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--slice', required=True)
    parser.add_argument('--layout', type=Path, required=True)
    parser.add_argument('--cohort', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--host-log', type=Path, required=True)
    parser.add_argument('--supplement', type=Path, action='append', default=[])
    parser.add_argument('--protocol', type=Path, action='append', default=[])
    args = parser.parse_args()
    record(args.slice, args.layout.resolve(), [p.resolve() for p in args.cohort],
           args.output, args.host_log.resolve(), [p.resolve() for p in args.supplement],
           [p.resolve() for p in args.protocol])
    print('QED editing evidence reconciled:', args.slice)
