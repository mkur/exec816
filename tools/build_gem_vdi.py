#!/usr/bin/env python3
"""Build G1: selected hosted GEM C plus a recording-device/Task probe."""
import argparse
import json
import re
from pathlib import Path

from calypsi_build import emit
from extract_gem_vdi import extract, PORT
from gem_vdi_inputs import local_inputs
from library_paths import read_source
from native_program import ROOT, build, compiler, require, sha256


def build_probe(output, optimize=True):
    output = Path(output).resolve()
    inputs = local_inputs()
    extraction = extract(output/'selected')
    src = output/'selected/src'
    fixtures = ROOT/'tests/programs'
    sources = [ROOT/'c/calypsi/exec.c', src/'vdi/vdi.c', src/'vdi/font.c',
               src/'vdi/font8x8.c', src/'vdi/dev_vbxe.c', src/'vbxe/vbxe.c',
               fixtures/'gem_vdi_context.c', fixtures/'gem_vdi_recording.c']
    layout = list(zip(('GEM WORD','GEM UWORD','GEM uint32_t','GEM data pointer',
                      'GEM callback','GEM workstation device','GEM font address',
                      'GEM contrl','GEM intin','GEM ptsin','GEM intout','GEM ptsout'),
                     (2,2,4,4,4,4,4,24,256,256,128,64)))
    foreign = emit(output, sources,
                   (ROOT/'c/calypsi/gateway.s', ROOT/'c/calypsi/image-info.s'),
                   ['Renderer','Peer'], optimize=optimize, roots=['hosted_vbxe_device'],
                   includes=[src], definitions={'dev_vbxe.c': ['-DGEM4XE_DEV_IMPL', '-DGEM4XE_DEV_PREFIX=vbxe_']},
                   probes=[(fixtures/'gem_vdi_layout.c',layout)])
    for forbidden in ('kb_init','vdi_init','vdi','gemdos','pr_page','ctx_switch','vdi_font_load'):
        require(forbidden not in foreign['symbols'], 'Unexpected linked dependency: '+forbidden)
    # Calypsi may inline the imported text primitive into the private dispatcher.
    routine = 'vdi_v_gtext' if 'vdi_v_gtext' in foreign['symbols'] else 'GemVdiDispatch'
    placement = re.search(r'^'+routine+r" in section 'farcode'\s+placed at address ([0-9a-f]+)-([0-9a-f]+) of size ([0-9a-f]+)",
                          (output/'link.lst').read_text(),re.M)
    require(placement is not None,'Missing GEM routine placement')
    low,high,size = (int(v,16) for v in placement.groups())
    require(low==foreign['symbols'][routine] and high-low+1==size,'Invalid GEM routine extent')
    source_paths = [*PORT.glob('*.json'), *PORT.glob('patches/*'), *PORT.glob('hosted/*'),
                    ROOT/'abi/gem-vdi.json', *ROOT.glob('tools/*gem_vdi*.py'),
                    ROOT/'tools/calypsi_build.py', ROOT/'tools/calypsi_image.py',
                    *fixtures.glob('gem_vdi_*.c'), fixtures/'gem_vdi_launcher.act',
                    *ROOT.glob('c/calypsi/*'), *ROOT.glob('c/include/**/*.h')]
    foreign['provenance'].update(slice='G1', local_inputs=inputs, extraction=extraction,
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(source_paths)) if p.is_file()},
        hardware_execution=False,preemption_routine=dict(name=routine,start=low,end=high+1))
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include = output/'c-image.inc'
    include.write_text(f'CONST C_MAIN=${foreign["symbols"]["main"]:x}\n')
    source = output/'launcher.act'
    source.write_text(read_source(fixtures/'gem_vdi_launcher.act', {'c-image.inc':include}))
    program = build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
                    tasks=True,task_capacity=8,console=False,foreign_image=foreign)
    return program,foreign


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path,default=ROOT/'build/gem-vdi/g1-opt')
    parser.add_argument('--no-opt',action='store_true')
    args = parser.parse_args()
    program,_ = build_probe(args.output,not args.no_opt)
    print('G1 image ready:',program['xex'])
