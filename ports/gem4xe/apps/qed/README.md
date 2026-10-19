# QED source baseline

[Initial scope and dependencies](../../../../docs/plans/gem4xe/qed-scope-and-dependencies.md) ·
[Port strategy](../../../../docs/plans/gem4xe/qed-port-strategy.md)

[inputs.json](inputs.json) pins the selected QED GEM4XE fork and FreeMiNT cflib
sources, their Git trees and the raw-byte SHA-256 hashes of the editor, headers,
resource, donor adaptation examples and notices. It records the donor's source
selection and the existing Exec toolchain/GUI inputs separately.

This is an input baseline for the native Exec port. The donor does not pin its
external cflib checkout; this pair has been checked at source level, not compiled
or run together on Exec. The donor's SDK, startup and G4A build are references,
not the Exec build recipe. No donor sources are vendored by this baseline.

## Restore and verify

Run from the Exec repository root, with unused `build/qed-sources/qed` and
`build/qed-sources/cflib` destinations. The script checks out the pinned inputs
and verifies their trees and file bytes without compiling or patching them.
It also checks the recorded native inputs; a deliberate future change requires
reviewing and updating that baseline.

```sh
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import subprocess

pin = json.loads(Path('ports/gem4xe/apps/qed/inputs.json').read_text())
for source in pin['sources']:
    target = Path('build/qed-sources') / source['id']
    assert not target.exists(), f'Choose an unused destination: {target}'
    subprocess.run(['git', 'clone', '-c', 'core.autocrlf=false', '--no-checkout',
                    source['repository'], str(target)], check=True)
    subprocess.run(['git', '-C', str(target), 'checkout', '--detach',
                    source['revision']], check=True)
    tree = subprocess.check_output(['git', '-C', str(target), 'rev-parse',
                                    'HEAD^{tree}'], text=True).strip()
    assert tree == source['tree'], f'Changed source tree: {target}'
    for name, expected in source['files'].items():
        actual = hashlib.sha256((target / name).read_bytes()).hexdigest()
        assert actual == expected, f'Changed source file: {target / name}'
for name, expected in pin['exec_baseline']['input_files'].items():
    actual = hashlib.sha256(Path(name).read_bytes()).hexdigest()
    assert actual == expected, f'Changed Exec input: {name}'
print('Pinned source trees and file hashes verified; no compilation performed.')
PY
```

Keep adaptations and future generated files outside these upstream checkouts.
The compilation inventories describe the donor baseline; the final native
source/link closure is established in strategy step 2. Preserve exact source
and resource bytes when checking hashes, including original text line endings.

## Notices

The QED pin includes `gem4xe/NOTICE`, `dist/liesmich.txt`, `doc/qed-en.stg`,
`gem4xe/COPYING.LIB` and `gem4xe/LICENSE-APACHE-2.0`; the cflib pin includes its
own `COPYING.LIB`. Retain their terms and file-specific notices in future source
adaptations and distributions. The donor states a no-fee redistribution
condition for QED and its port files. Exec's MIT interface licence does not
relicense that material. Final binary notices must match the actual linked
components.
