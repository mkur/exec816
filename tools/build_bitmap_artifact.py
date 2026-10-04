"""Optional bitmap shell payload; keep build metadata outside the distribution."""
import json
import shutil
from pathlib import Path
from build_bitmap_demo import build as build_demo
from native_program import ROOT,sha256
from package_demo import BITMAP_FILES


def copy_notices(selected,output):
    for source,name in [('COPYING','GEM-COPYING.txt'),('COPYING.LIB','GEM-COPYING.LIB.txt'),
                        ('docs/licence.md','GEM-LICENSING.md')]:
        shutil.copyfile(selected/source,output/name)
    font=(selected/'src/vdi/font8x8.c').read_text().split('*/',1)[0]+'*/\n'
    (output/'GEM-FONT-NOTICE.txt').write_text(font)


def build(output,media_bundle):
    output=Path(output).resolve()
    program=build_demo(output,media_bundle)
    foreign=json.loads((output/'c-image.json').read_text())
    shutil.copyfile(program['xex'],output/'Exec-bitmap-console.xex')
    shutil.copyfile(program['output']/'system.atr',output/'system.atr')
    shutil.copyfile(ROOT/'docs/bitmap-console-distribution.txt',output/'README.txt')
    copy_notices(output/'selected',output)
    record=dict(format='exec816-bitmap-artifact-v1',diagnostic=False,
        status='functional development preview; responsiveness targets remain open',
        files={name:sha256(output/name) for name in BITMAP_FILES},
        pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text()),
        provenance=foreign['provenance'],build=program['build'],
        source_inputs={str(p.relative_to(ROOT)):sha256(p) for p in (
            Path(__file__),ROOT/'docs/bitmap-console-distribution.txt')},
        bank_zero_delta=dict(fixed=0,root_kernel=0,per_task=[0]*8,private_idle=0))
    (output/'bitmap.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
