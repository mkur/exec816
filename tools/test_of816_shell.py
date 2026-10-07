"""Exercise both OF816 boot routes into the unchanged standard shell bundle."""
import json
import shutil
from pathlib import Path

from native_program import ROOT, require, sha256
from os_boundary import run_to
from test_demo import run as run_demo
from test_of816 import boot_environment, check_loading_paused, check_loading_complete
from test_of816 import check_boot_guards, check_exit, enter_forth, press, screen_text
from test_vbxe_aperture import PATTERN


def run(output, record, program):
    media = record['media']
    bundle = program['output']
    require(sha256(output/media['name']) == media['sha256'], 'Changed OF816 companion disk')
    require(sha256(bundle/'demo-manifest.json') == media['manifest_sha256'],
            'Standard shell manifest changed')
    labels = record['labels']
    pin,_,_=boot_environment(record)
    report = dict(status='running',tier='development',boot=record,pin=pin,cases=[],
                  inputs={str(path.relative_to(ROOT)):sha256(path) for path in
                          (Path(__file__),ROOT/'tools/test_of816.py',ROOT/'tools/test_demo.py',
                           ROOT/'tools/test_vbxe_aperture.py')})
    try:
        for manual in (False, True):
            case = dict(route='forth-command' if manual else 'autoboot')
            case_bundle=output/case['route']/'demo'
            shutil.copytree(bundle,case_bundle,dirs_exist_ok=True,
                            ignore=shutil.ignore_patterns('of816','*-walkthrough.atr','results.json'))

            def bootstrap(bridge, native):
                bridge.boot(str(output/'Exec-of816.xex'))
                first=native['labels']['loader_init']
                bridge.bp_set(first)
                run_to(bridge,first,3000,90)
                bridge.bp_clear_all()
                bridge.memload(0x8000,PATTERN)
                bridge.bp_set(labels['of_start'])
                run_to(bridge,labels['of_start'],3000,90)
                bridge.bp_clear_all()
                saved = dict(vectors=bridge.memdump(0x256,9),iocb=bridge.memdump(0x340,32))
                check_loading_paused(bridge,record,native)
                dp_neighbours = (record['layout']['OF_DP']-256,record['layout']['OF_DP']+256)
                neighbour_patterns = (bytes((i*29+7)&255 for i in range(256)),
                                      bytes((i*43+11)&255 for i in range(256)))
                for address,pattern in zip(dp_neighbours,neighbour_patterns):
                    bridge.memload(address,pattern)
                screen = bridge.peek16(88)
                bridge._cmd_ok('KEY ALL up')
                if manual:
                    case['cancel'] = enter_forth(bridge,labels,delay=240,key='RETURN')
                    require(case['cancel']['seconds_remaining'] == 1, 'Missed final-second cancellation')
                    for character in 'decimal 6 7 * .\n':
                        press(bridge,labels,character)
                    require('42 ' in screen_text(bridge.memdump(screen,960)), 'Forth arithmetic failed')
                    address=record['boot_config']['address']+record['boot_config']['abi']['fields']['cache_blocks']
                    for text,value in [('CACHE-BLOCKS@ .',512),('0 CACHE-BLOCKS!',0),
                                       ('65536 CACHE-BLOCKS!',0),('-1 CACHE-BLOCKS!',0),
                                       ('513 CACHE-BLOCKS!',0),('128 CACHE-BLOCKS!',128)]:
                        for character in text+'\n':press(bridge,labels,character)
                        require(bridge.peek16(address)==value,'Forth setter changed/rejected the wrong value')
                    for character in 'CACHE-BLOCKS@ .\n':press(bridge,labels,character)
                    require('128 ' in screen_text(bridge.memdump(screen,960)),'Forth getter returned wrong capacity')
                    drive_address=record['boot_config']['address']+record['boot_config']['abi']['fields']['system_drive']
                    for character in '2 SYSTEM-DRIVE! SYSTEM-DRIVE@ .\n':press(bridge,labels,character)
                    require(bridge.memdump(drive_address,1)==bytes([2]),'System drive setter failed')
                    case['system_drive']=2
                    case['cache_request']=128
                    bridge.screenshot(str(output/'forth.png'))
                    for character in 'exec816':
                        press(bridge,labels,character)
                    press(bridge,labels,'\n',labels['of_handoff'])
                    case['arithmetic'] = 42
                else:
                    # Force a low-byte wrap during the real five-second delay.
                    bridge.poke(0x14,240)
                    bridge.bp_set(labels['of_autoboot'])
                    run_to(bridge,labels['of_autoboot'],1000,30)
                    bridge.bp_clear_all()
                    start = bridge.eval_expr('@frame')
                    clock = bridge.peek(0x14)
                    bridge.bp_set(labels['of_handoff'])
                    run_to(bridge,labels['of_handoff'],300,15)
                    elapsed = bridge.eval_expr('@frame')-start
                    require(249 <= elapsed <= 251, 'Autoboot did not wait five PAL seconds')
                    require(bridge.peek(0x14) < clock, 'Countdown clock did not wrap')
                    require(bridge.peek16(labels['of_keys']) == 0, 'Autoboot required keyboard input')
                    require('Exec816 in: 5 4 3 2 1' in screen_text(bridge.memdump(screen,960)),
                            'Missing countdown')
                    case.update(frames=elapsed,clock_wrap=True)
                check_boot_guards(bridge,record['layout'])
                settings=check_loading_paused(bridge,record,native)
                case['payload_pending_at_return']=True
                case['boot_guards'] = 'intact'
                for address,pattern in zip(dp_neighbours,neighbour_patterns):
                    require(bridge.memdump(address,256) == pattern,
                            'OF816 DP initialization changed an adjacent page')
                case['dp_neighbours_intact'] = True
                bridge.bp_clear_all()
                bridge.bp_set(native['labels']['loader_start'])
                run_to(bridge,native['labels']['loader_start'],3000,60)
                check_loading_complete(bridge,record,native,settings)
                bridge.bp_clear_all()
                bridge.bp_set(native['labels']['start'])
                run_to(bridge,native['labels']['start'],3000,60)
                bridge.bp_clear_all()
                require(bridge.memdump(0x256,9) == saved['vectors'] and
                        bridge.memdump(0x340,32) == saved['iocb'], 'Handoff did not restore vectors/IOCBs')
                require(bridge.peek16(labels['of_phase']) == 2, 'Exec handoff did not run')
                case['os_restored_at_handoff'] = True

            # Reuse the standard physical-key smoke observer and its ownership,
            # stack/domain guard and OS restoration checks after native startup.
            case['shell'] = run_demo(case_bundle,boot_smoke=True,bootstrap=bootstrap,
                                     media_path=output/media['name'],expected_cache=128 if manual else 512,
                                     system_drive=2 if manual else 1,retire_manifest=True,
                                     aperture_pattern=PATTERN)
            screenshot = case['route']+'-shell.png'
            shutil.copyfile(case_bundle/'boot-smoke.png',output/screenshot)
            case['screenshot'] = dict(name=screenshot,sha256=sha256(output/screenshot))
            report['cases'].append(case)
        report['exit_cases'] = [check_exit(output,record),check_exit(output,record,busy=True)]
        report['status'] = 'pass'
    except Exception as error:
        report.update(status='fail',error=str(error))
        raise
    finally:
        (output/'results.json').write_text(json.dumps(report,indent=2)+'\n')
    return report
