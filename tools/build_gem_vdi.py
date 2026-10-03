#!/usr/bin/env python3
"""Build hosted GEM probes: extraction, service, display and real VDI rendering."""
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


def build_service_probe(output, optimize=True):
    from generate_gem_vdi import files, expected_layout
    output = Path(output).resolve()
    inputs = local_inputs()
    service = PORT/'service'
    for path,content in files().items():
        require(path.read_text()==content,'Stale GEM binding: '+str(path))
    sources = [ROOT/'c/calypsi/exec.c', service/'gem-validation.c', service/'gem-service.c',
               service/'gem-client.c', ROOT/'tests/programs/gem_service.c']
    foreign = emit(output,sources,(ROOT/'c/calypsi/gateway.s', ROOT/'c/calypsi/image-info.s'),
                   ['GemServiceWorker','Peer','Blocker'],optimize=optimize,includes=[service],
                   probes=[(service/'gem-layout.c',expected_layout())])
    paths = [*service.glob('*.c'),*service.glob('*.h'),ROOT/'abi/gem-vdi.json',ROOT/'abi/tasks.json',
             *ROOT.glob('tools/*gem*.py'),ROOT/'tools/generate_calypsi.py',
             ROOT/'tools/calypsi_build.py',ROOT/'tools/calypsi_image.py',
             ROOT/'tests/programs/gem_service.c',ROOT/'tests/programs/gem_vdi_launcher.act',
             *ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h')]
    foreign['provenance'].update(slice='G2',local_inputs=inputs,hardware_execution=False,
        backend='fixture-only',source_inputs={p.relative_to(ROOT).as_posix():sha256(p)
        for p in sorted(set(paths)) if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include = output/'c-image.inc'
    include.write_text(f'CONST C_MAIN=${foreign["symbols"]["main"]:x}\n')
    source = output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_vdi_launcher.act',{'c-image.inc':include}))
    program = build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
                    tasks=True,task_capacity=8,console=False,foreign_image=foreign)
    return program,foreign



def build_display_probe(output, optimize=True, instrument=True):
    from generate_display import files, expected_layout
    from generate_bitmap import expected_layout as bitmap_layout
    from bitmap_copy_oracle import header,corpus
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    for path,content in files().items():
        require(path.read_text()==content,'Stale display binding: '+str(path))
    # The probe substitutes only status reads. Real cases read actual hardware;
    # injected stuck-engine cases still execute the production stop/restore path.
    backend=(ROOT/'platform/altirraos/vbxe.c').read_text()
    backend='extern void ProbeScrollLaunch(void);\n'+backend.replace(
        'REG(BUSY)=1;', 'REG(BUSY)=1; ProbeScrollLaunch();')
    if instrument:
        backend=backend.replace('#define BUSY ', 'extern UBYTE ProbeBusy(void);\nextern UBYTE ProbeVcount(void);\nextern volatile UWORD ProbeStopped;\n#define BUSY ')
        backend=backend.replace('REG(BUSY)&3','ProbeBusy()&3').replace('REG(VCOUNT)','ProbeVcount()')
        backend=backend.replace('REG(BUSY)=0;', 'REG(BUSY)=0; ProbeStopped=1;')
        backend='extern void ProbeCopyChunk(void);\n'+backend
        hook='        rows-=n;\n        if (rows)'
        require(hook in backend,'Missing bitmap-copy chunk boundary')
        backend=backend.replace(hook,'        ProbeCopyChunk();\n'+hook)
    (output/'bitmap-copy-cases.h').write_text(header())
    (output/'vbxe-probe.c').write_text(backend)
    mapping=(ROOT/'platform/altirraos/vbxe-map.s').read_text()
    if instrument:
        mapping+='\n              .extern variant, mapPoint, mapGate\n'
    for index,label in enumerate(('VbxeMapDisabled','VbxeMapBank','VbxeMapControl','VbxeMapCommitted') if instrument else (),1):
        delay=f'''
              php
              rep #0x30
              pha
              phy
              lda long:variant
              cmp ##9
              bne map_done_{index}
              ldy ##0
              lda [0x80],y
              and ##0xff00
              beq map_done_{index}
              lda long:mapPoint
              cmp ##{index}
              bcs map_done_{index}
              lda ##{index}
              sta long:mapPoint
map_wait_{index}:
              lda long:mapGate
              cmp ##{index}
              bcc map_wait_{index}
map_done_{index}:
              ply
              pla
              plp
'''
        mapping=mapping.replace(label+':',label+':'+delay)
    (output/'vbxe-map-probe.s').write_text(mapping)
    admission=(ROOT/'c/calypsi/display.c').read_text().replace(
        'UWORD DisplayCheck(struct DisplayLease *p) {',
        'extern volatile UWORD ownerChecks;\nUWORD DisplayCheck(struct DisplayLease *p) { ++ownerChecks;')
    (output/'display-probe.c').write_text(admission)
    sources=[ROOT/'c/calypsi/exec.c',output/'display-probe.c',output/'vbxe-probe.c',
             ROOT/'tests/programs/gem_display.c',ROOT/'tests/programs/bitmap_copy.c',
             ROOT/'tests/programs/bitmap_scroll.c']
    foreign=emit(output,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',output/'vbxe-map-probe.s'],
        ['Renderer','Peer'],optimize=optimize,includes=[output],
        probes=[(ROOT/'c/calypsi/display-layout.c',expected_layout()),
                (ROOT/'c/calypsi/bitmap-layout.c',bitmap_layout())])
    paths=[ROOT/'abi/display.json',ROOT/'platform/altirraos/vbxe.c',
           ROOT/'platform/altirraos/vbxe-map.s',ROOT/'platform/altirraos/vbxe-vram.json',
           ROOT/'tests/programs/gem_display.c',ROOT/'tests/programs/gem_display_launcher.act',
           *ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h'),
           *ROOT.glob('lib/display/*'),ROOT/'tools/build_gem_vdi.py',ROOT/'tools/test_gem_display.py',
           ROOT/'tools/generate_display.py',ROOT/'tools/calypsi_build.py',ROOT/'tools/calypsi_image.py',
           ROOT/'abi/bitmap.json',ROOT/'tools/generate_bitmap.py',ROOT/'tools/bitmap_copy_oracle.py',
           ROOT/'tests/programs/bitmap_copy.c',ROOT/'tests/programs/bitmap_scroll.c']
    foreign['provenance'].update(slice='G3',hardware_execution=True,local_inputs=local_inputs(),
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(paths)) if p.is_file()},
        instrumentation=dict(busy_and_vcount_reads=instrument,mapping_nmi_gates=instrument,
            backend_sha256=sha256(output/'vbxe-probe.c'),mapping_sha256=sha256(output/'vbxe-map-probe.s')),
        bitmap_copy_cases=corpus(),vram=json.loads((ROOT/'platform/altirraos/vbxe-vram.json').read_text()))
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
        for name in ('main','stage','variant','ExecDisplayEntries')))
    source=output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_display_launcher.act',{'c-image.inc':include}))
    from make_data_disk import make
    from generate_dos_mounts import validate_mounts
    from filesystem_formats import SDFS
    media=output/'media'
    media.mkdir(exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes(i^0x5a for i in range(128)))
    make(output/'system.atr',media,binary_names={'DATA.BIN'})
    mounts=validate_mounts([dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=SDFS)])
    program=build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
        tasks=True,task_capacity=8,console=True,foreign_image=foreign,dos_mounts=mounts)
    return program,foreign


def build_render_probe(output, optimize=True, instrument=True):
    from generate_gem_vdi import expected_layout
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    extraction=extract(output/'selected')
    src=output/'selected/src'
    service=PORT/'service'
    adapter=PORT/'adapter'
    hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
    if instrument:
        hardware=hardware.replace('#define BUSY ', 'extern UBYTE ProbeBusy(void);\nextern volatile UWORD stopped;\n#define BUSY ')
        hardware=hardware.replace('REG(BUSY)&3','ProbeBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; stopped=1;')
    (output/'vbxe-render.c').write_text(hardware)
    backend=(adapter/'gem-vbxe.c').read_text()
    backend=backend.replace('static struct VbxeDisplay display;', 'extern void ProbeSnapshot(struct VbxeDisplay *);\nextern void ProbeAcquired(struct VbxeDisplay *);\nextern void ProbePalette(const UBYTE *);\nextern void ProbeCommand(void);\nstatic struct VbxeDisplay display;')
    backend=backend.replace('status=GemVdiOpen(out);', 'ProbeAcquired(&display);\n    status=GemVdiOpen(out);')
    backend=backend.replace('if (!fault) latch(VbxeOwnerPalette(&display,rgb));','ProbePalette(rgb);\n    if (!fault) latch(VbxeOwnerPalette(&display,rgb));')
    backend=backend.replace('return GemVdiCommand(cmd->opcode', 'ProbeCommand();\n    return GemVdiCommand(cmd->opcode')
    backend=backend.replace('return fault ? GEM_DEVICE_FAULT : GEM_OK;', 'if (!fault) ProbeSnapshot(&display);\n    return fault ? GEM_DEVICE_FAULT : GEM_OK;')
    (output/'gem-vbxe-probe.c').write_text(backend)
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',output/'vbxe-render.c',
        service/'gem-validation.c',service/'gem-service.c',service/'gem-client.c',
        src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
        output/'gem-vbxe-probe.c',ROOT/'tests/programs/gem_render.c']
    foreign=emit(output,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s'],
        ['GemServiceWorker'],optimize=optimize,includes=[src,service,adapter],
        definitions={'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_']},
        probes=[(service/'gem-layout.c',expected_layout())])
    paths=[*adapter.glob('*'),*service.glob('*'),*PORT.glob('hosted/*'),*PORT.glob('patches/*'),
        ROOT/'platform/altirraos/vbxe.c',ROOT/'platform/altirraos/vbxe-map.s',
        ROOT/'platform/altirraos/vbxe-vram.json',ROOT/'tests/programs/gem_render.c',
        ROOT/'tests/programs/gem_render_launcher.act',*ROOT.glob('tools/*gem*.py'),
        *ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h'),*ROOT.glob('lib/display/*')]
    foreign['provenance'].update(slice='G4',hardware_execution=True,local_inputs=local_inputs(),
        extraction=extraction,status_read_instrumentation=instrument,
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(paths)) if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
        for name in ('main','stage','ExecDisplayEntries')))
    source=output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_render_launcher.act',{'c-image.inc':include}))
    program=build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
        tasks=True,task_capacity=8,console=False,foreign_image=foreign)
    return program,foreign


def build_concurrent_probe(output, optimize=True, instrument=True):
    """The G5 workload also supplies the uninstrumented optional G6 artifact."""
    from generate_gem_vdi import expected_layout
    from make_data_disk import make
    from generate_dos_mounts import validate_mounts
    from filesystem_formats import SDFS
    output=Path(output).resolve()
    output.mkdir(parents=True,exist_ok=True)
    extraction=extract(output/'selected')
    src=output/'selected/src'
    service=PORT/'service'
    adapter=PORT/'adapter'
    hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
    backend=(adapter/'gem-vbxe.c').read_text()
    if instrument:
        hardware=hardware.replace('#define BUSY ', 'extern UBYTE ProbeBusy(void);\nextern volatile UWORD stopped;\n#define BUSY ')
        hardware=hardware.replace('REG(BUSY)&3','ProbeBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; stopped=1;')
        backend=backend.replace('static struct VbxeDisplay display;', 'extern void ProbeDraw(void);\nextern void ProbeCommand(void);\nextern void ProbeSnapshot(struct VbxeDisplay *);\nstatic struct VbxeDisplay display;')
        draw_hook='if (commandCount && !fault) latch(VbxeOwnerSubmit(&display,commands,commandCount));'
        require(draw_hook in backend,'Changed queued-drawing observer boundary')
        backend=backend.replace(draw_hook,
            'if (commandCount && !fault) { latch(VbxeOwnerSubmit(&display,commands,commandCount)); if (!fault) ProbeDraw(); }')
        backend=backend.replace('return GemVdiCommand(cmd->opcode', 'ProbeCommand();\n    return GemVdiCommand(cmd->opcode')
        backend=backend.replace('return fault ? GEM_DEVICE_FAULT : GEM_OK;', 'if (!fault) ProbeSnapshot(&display);\n    return fault ? GEM_DEVICE_FAULT : GEM_OK;')
    (output/'vbxe-concurrent.c').write_text(hardware)
    (output/'gem-vbxe-concurrent.c').write_text(backend)
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',output/'vbxe-concurrent.c',
        service/'gem-validation.c',service/'gem-service.c',service/'gem-client.c',
        src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
        output/'gem-vbxe-concurrent.c',ROOT/'tests/programs/gem_concurrent.c']
    foreign=emit(output,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s'],
        ['GemServiceWorker','Peer','Blocker'],optimize=optimize,includes=[src,service,adapter],
        definitions={'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_'],
                     'gem_concurrent.c':['-DGEM_DIAGNOSTIC'] if instrument else []},
        probes=[(service/'gem-layout.c',expected_layout())])
    paths=[*adapter.glob('*'),*service.glob('*'),*PORT.glob('hosted/*'),*PORT.glob('patches/*'),
        ROOT/'platform/altirraos/vbxe.c',ROOT/'platform/altirraos/vbxe-map.s',
        ROOT/'tests/programs/gem_concurrent.c',ROOT/'tests/programs/gem_concurrent_launcher.act',
        *ROOT.glob('tools/*gem*.py'),*ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h'),
        *ROOT.glob('lib/display/*')]
    foreign['provenance'].update(slice='G5',hardware_execution=True,local_inputs=local_inputs(),
        extraction=extraction,diagnostic=instrument,
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(paths)) if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n'
        for name in ('main','stage','ExecDisplayEntries')))
    source=output/'launcher.act'
    source.write_text(read_source(ROOT/'tests/programs/gem_concurrent_launcher.act',{'c-image.inc':include}))
    media=output/'media'
    media.mkdir(exist_ok=True)
    (media/'DATA.BIN').write_bytes(bytes((i&255)^0x5a for i in range(2048)))
    make(output/'system.atr',media,binary_names={'DATA.BIN'})
    mounts=validate_mounts([dict(alias='D1',unit=49,sectors=720,sector_bytes=128,profile=4,format=SDFS)])
    program=build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,
        tasks=True,task_capacity=8,console=True,foreign_image=foreign,dos_mounts=mounts)
    return program,foreign


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--no-opt',action='store_true')
    parser.add_argument('--slice',choices=('g1','g2','g3','g4','g5'),default='g1')
    args = parser.parse_args()
    builder = {'g1':build_probe,'g2':build_service_probe,'g3':build_display_probe,'g4':build_render_probe,'g5':build_concurrent_probe}[args.slice]
    output = args.output or ROOT/'build/gem-vdi'/(args.slice+('-raw' if args.no_opt else '-opt'))
    program,_ = builder(output,not args.no_opt)
    print(args.slice.upper(),'image ready:',program['xex'])
