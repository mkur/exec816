"""Real cursor renderer with diagnostic hardware-fault phase selection."""
import json
from pathlib import Path
from calypsi_build import emit
from extract_gem_vdi import extract,PORT
from gem_vdi_inputs import local_inputs
from library_paths import read_source
from generate_gem_vdi import expected_layout
from native_program import ROOT,build,compiler,sha256

def build_cursor(output,optimize=True):
    output=Path(output).resolve();output.mkdir(parents=True,exist_ok=True)
    extraction=extract(output/'selected');src=output/'selected/src'
    service=PORT/'service';adapter=PORT/'adapter'
    hardware=(ROOT/'platform/altirraos/vbxe.c').read_text()
    hardware=hardware.replace('#define BUSY ','extern UBYTE ProbeBusy(void);\nextern void ProbeStarted(void);\nextern volatile UWORD stopped;\n#define BUSY ')
    hardware=hardware.replace('REG(BUSY)&3','ProbeBusy()&3').replace('REG(BUSY)=0;', 'REG(BUSY)=0; stopped=1;')
    hardware=hardware.replace('REG(BUSY)=1;', 'REG(BUSY)=1; ProbeStarted();')
    (output/'vbxe-cursor.c').write_text(hardware)
    backend=(adapter/'gem-vbxe.c').read_text().replace('static struct VbxeDisplay display;',
        'extern void ProbeCursorPhase(UWORD);\nstatic struct VbxeDisplay display;')
    backend=backend.replace('if (cursorDrawn && !fault)\n        latch(',
        'if (cursorDrawn && !fault) {\n        ProbeCursorPhase(1);\n        latch(')
    backend=backend.replace('cursorBytes,cursorRows,255,0,0));\n    cursorDrawn=0;',
        'cursorBytes,cursorRows,255,0,0));\n    }\n    cursorDrawn=0;')
    backend=backend.replace('    latch(VbxeBlit(&display,cursorAddress',
        '    ProbeCursorPhase(2);\n    latch(VbxeBlit(&display,cursorAddress')
    backend=backend.replace('    if (!fault) latch(VbxeBlit(&display,CURSOR_AND',
        '    if (!fault) ProbeCursorPhase(3);\n    if (!fault) latch(VbxeBlit(&display,CURSOR_AND')
    backend=backend.replace('    if (!fault) latch(VbxeBlit(&display,CURSOR_OR',
        '    if (!fault) ProbeCursorPhase(4);\n    if (!fault) latch(VbxeBlit(&display,CURSOR_OR')
    (output/'gem-cursor-backend.c').write_text(backend)
    sources=[ROOT/'c/calypsi/exec.c',ROOT/'c/calypsi/display.c',output/'vbxe-cursor.c',
        service/'gem-validation.c',service/'gem-service.c',service/'gem-client.c',
        src/'vdi/vdi.c',src/'vdi/font.c',src/'vdi/font8x8.c',src/'vdi/dev_vbxe.c',
        output/'gem-cursor-backend.c',ROOT/'tests/programs/gem_cursor.c']
    foreign=emit(output,sources,[ROOT/'c/calypsi/gateway.s',ROOT/'c/calypsi/display.s',
        ROOT/'c/calypsi/image-info.s',ROOT/'platform/altirraos/vbxe-map.s'],['GemServiceWorker'],
        optimize=optimize,includes=[src,service,adapter],
        definitions={'dev_vbxe.c':['-DGEM4XE_DEV_IMPL','-DGEM4XE_DEV_PREFIX=vbxe_']},
        probes=[(service/'gem-layout.c',expected_layout())])
    paths=[*adapter.glob('*'),*service.glob('*'),*PORT.glob('hosted/*'),*PORT.glob('patches/*'),
        ROOT/'abi/gem-vdi.json',ROOT/'platform/altirraos/vbxe-vram.json',
        ROOT/'platform/altirraos/vbxe.c',ROOT/'platform/altirraos/vbxe-map.s',
        ROOT/'tests/programs/gem_cursor.c',ROOT/'tests/programs/gem_render_launcher.act',
        Path(__file__),*ROOT.glob('c/calypsi/*'),*ROOT.glob('c/include/**/*.h'),*ROOT.glob('lib/display/*')]
    foreign['provenance'].update(slice='I5',hardware_execution=True,extraction=extraction,local_inputs=local_inputs(),
        source_inputs={p.relative_to(ROOT).as_posix():sha256(p) for p in sorted(set(paths)) if p.is_file()})
    (output/'c-image.json').write_text(json.dumps(foreign,indent=2)+'\n')
    include=output/'c-image.inc'
    include.write_text(''.join(f'CONST C_{name.upper()}=${foreign["symbols"][name]:x}\n' for name in ('main','stage','ExecDisplayEntries')))
    source=output/'launcher.act';source.write_text(read_source(ROOT/'tests/programs/gem_render_launcher.act',{'c-image.inc':include}))
    return build(compiler(ROOT/'build/actionc'),source,output/'program',optimize=optimize,tasks=True,
                 task_capacity=8,console=False,foreign_image=foreign),foreign
