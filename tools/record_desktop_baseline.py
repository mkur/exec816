#!/usr/bin/env python3
"""Freeze the existing desktop inputs without repeating completed console matrices."""
import json
from pathlib import Path

from native_program import ROOT, require, sha256


def record():
    bundle = ROOT / 'build/output-batching/demo'
    smoke = json.loads((bundle / 'demo-results.json').read_text())
    manifest = json.loads((bundle / 'demo-manifest.json').read_text())
    memory = manifest['kernel']['memory']
    pin = json.loads((ROOT / 'toolchain/altirra-gem-vdi.json').read_text())
    require(smoke['status'] == 'pass' and smoke['peak_tasks'] == 6,
            'Run the unchanged shell boot smoke before recording DT0')
    require(smoke['xex_sha256'] == sha256(bundle / 'program.xex') and
            smoke['runner_sha256'] == sha256(ROOT / 'tools/test_demo.py'),
            'Stale baseline smoke')
    files = ['toolchain/actionc.json', 'toolchain/altirra-gem-vdi.json',
             'build/mouse-bridge/AltirraBridgeServer',
             'build/firmware/altirraos-816.rom',
             'build/output-batching/demo/program.xex',
             'build/output-batching/demo/of816/Exec-of816.xex',
             'build/output-batching/demo/demo-manifest.json',
             'build/output-batching/demo/demo-results.json',
             'build/output-batching/demo/system.atr',
             'build/output-batching/unloaded-input.json',
             'docs/development/console-output-batching-ob5.json',
             'docs/development/gem-mouse-m5.json',
             'docs/development/layers-l4.json']
    require(sha256(ROOT / files[2]) == pin['mouse_input']['tooling']['sha256'],
            'Unpinned mouse emulator')
    require(sha256(ROOT / files[3]) == pin['rom']['sha256'], 'Unpinned ROM')
    result = dict(status='pass', tier='development', slice='DT0', qualification=False,
        sources={name: sha256(ROOT / name) for name in files},
        machine=smoke['machine'], scope=smoke['scope'],
        autoboot_frames=smoke['autoboot_frames'],
        bank_zero_budget=memory['bank_zero_budget'], task_pools=memory['task_pools'],
        reserved_bank_zero_delta=dict(fixed=0, root_kernel=0,
                                      per_public_task=[0]*8, idle=0),
        task_ledger=dict(existing_prompt=4, existing_pipeline=6,
                        proposed_desktop_prompt=5, proposed_desktop_pipeline=7,
                        capacity=8, root='shell and desktop controller',
                        workers=['console/presenter', 'sio', 'filesystem'],
                        new_application='one ordinary existing pool',
                        presenter='existing 2560-byte pool, admitted first'),
        storage=dict(scene_bytes=4782, resident_globals_capacity=2048,
                     new_ui_storage='caller-owned heap in upper RAM',
                     aperture=[0x8000, 0x9000],
                     vram={'framebuffer': [0, 76800], 'xdl_base': 0x30000,
                           'pointer_save_and_masks': [0x37000, 0x37300],
                           'command_arena': [0x38000, 0x39000]},
                     backing_bitmaps=False),
        measurement_contract=dict(motion_samples_per_case=100, button_samples_per_case=30,
            cases=['idle', 'scrolling', 'cold-read', 'two-client'],
            frame_phase='vary phase in the pinned PAL clock',
            existing_echo='Capture IRQ to drawing return only; not visible scanout',
            visible_baseline='DT3 runs the new scanout observer against this frozen image'),
        ownership='Root controls the shell console/window; the second Task registers itself. '
                  'Close streams and retire windows before destroying instances; '
                  'retire clients before stopping the presenter.')
    target = ROOT / 'docs/development/desktop-dt0.json'
    target.write_text(json.dumps(result, indent=2) + '\n')
    print('DT0 baseline recorded:', target)


if __name__ == '__main__':
    record()
