#!/usr/bin/env python3
"""Freeze DR0's optimized rendering executable, inputs and matched pixel scenes."""
import argparse
import json
import shutil
import subprocess
from pathlib import Path
from native_program import ROOT, require, sha256
from generate_layers import layout


def record(folder):
    folder = folder.resolve()
    report = json.loads((folder/'presentation-results.json').read_text())
    require(report['status'] == 'pass' and report['build']['optimize'],
            'Run the optimized rendering presentation fixture first')
    require(len(report['observations']) == 15, 'Missing directional/edge move scenes')
    vram = json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text())
    proposed = [(0x50000, 0x60000), (0x60000, 0x70000)]
    occupied = [(r['base'], r['base']+r['reserved_bytes']) for r in vram['regions']]
    occupied += [(r['base'], r['base']+r['bytes']) for r in vram['diagnostics']]
    for start, end in proposed:
        require(end <= vram['bytes'] and all(end <= a or b <= start for a,b in occupied),
                'Snapshot reservation overlaps current usage')
    freeze = folder/'frozen'
    freeze.mkdir(exist_ok=True)
    sources = {}
    # Keep the exact baseline build: later compilers and layouts cannot recreate it.
    for relative in ('program/program.xex', 'program/program.a816.json',
                     'program/build.json', 'program/memory.json', 'c-image.json'):
        source = folder/relative
        target = freeze/source.name
        shutil.copy2(source, target)
        sources[str(source.relative_to(ROOT))] = sha256(source)
    pins = ['toolchain/actionc.json', 'toolchain/altirra-gem-vdi.json',
            'build/mouse-bridge/AltirraBridgeServer', 'build/firmware/altirraos-816.rom',
            'abi/layers.json', 'abi/desktop.json', 'platform/altirraos/vbxe-vram.json',
            'tests/programs/desktop_presentation.act', 'tools/test_desktop_presentation.py']
    evidence = ['docs/development/mouse-performance-mp4.json',
                'docs/development/blitter-irq-bi5.json', 'docs/development/aes-widgets-aw4.json']
    sources.update({name: sha256(ROOT/name) for name in pins+evidence})
    result = dict(slice='DR0', tier='development', qualification=False, status='pass',
        source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        local_overrides='Expanded test fixture and observation runner only; production renderer unchanged.',
        source_hashes=sources, build=report['build'], machine=report['machine'],
        observations=report['observations'], stack_usage=report['stack_usage'],
        reused_evidence=evidence,
        comparison_scope='Full-frame correctness and request-to-settled elapsed time, including two settling frames. Passive observer, no production code instrumentation.',
        timing_limits='These samples do not measure actual DMA BUSY edges. Existing IRQ evidence records the available upper bounds; DMA and completion-service timing must remain distinct.',
        layout=layout(), proposed_damage_capacity=8,
        proposed_cache_ranges=proposed, vram=vram,
        memory_delta=dict(bank_zero=dict(fixed=0, root_kernel=0,
            per_public_task=[0]*8, idle=0), vram=0, upper_ram=0))
    target = ROOT/'docs/development/desktop-rendering-dr0.json'
    target.write_text(json.dumps(result, indent=2)+'\n')
    print(target)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    record(parser.parse_args().baseline)
