"""Optional graphics payload for build_demo; maps and evidence stay outside ZIP."""
import json
import shutil
from pathlib import Path
from build_gem_interactive import build_interactive
from native_program import ROOT, sha256


def build(output):
    output=Path(output).resolve()
    program,foreign=build_interactive(output,optimize=True,instrument=False)
    shutil.copyfile(program['xex'],output/'Exec-gem-vdi.xex')
    shutil.copyfile(output/'system.atr',output/'graphics.atr')
    shutil.copyfile(ROOT/'docs/gem-vdi-distribution.txt',output/'README.txt')
    for source,name in [('COPYING','GEM-COPYING.txt'),('COPYING.LIB','GEM-COPYING.LIB.txt'),
                        ('docs/licence.md','GEM-LICENSING.md')]:
        shutil.copyfile(output/'selected'/source,output/name)
    font=(output/'selected/src/vdi/font8x8.c').read_text().split('*/',1)[0]+'*/\n'
    (output/'GEM-FONT-NOTICE.txt').write_text(font)
    from package_demo import GEM_FILES
    record=dict(format='exec816-gem-vdi-artifact-v1',diagnostic=False,workload='interactive-keyboard-st-mouse',
        files={name:sha256(output/name) for name in GEM_FILES},
        pin=json.loads((ROOT/'toolchain/altirra-gem-vdi.json').read_text()),
        provenance=foreign['provenance'],build=program['build'],
        bank_zero_delta=dict(fixed=0,per_task=[0]*8,private_idle=0))
    (output/'graphics.json').write_text(json.dumps(record,indent=2)+'\n')
    return record
