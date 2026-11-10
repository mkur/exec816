# GemARC native port

[Shared runtime plan](../../../../docs/plans/c-runtime-implementation-plan.md#cr5--prove-reuse-with-gemarc-and-deliver-matching-artifacts)

[inputs.json](inputs.json) freezes GemARC's application, archive engine, codecs,
resource generator and notices at GEM4XE revision
`0692b5519112dcde1f29f061ebcebe7a095aaf60`.
The original cache and patched work are separate from the donor checkout:

```sh
python3 tools/prepare_gemarc.py --output build/gemarc/prepared
```

Preparation verifies every original SHA-256, reads the selected Git revision
from the local donor when available, and otherwise uses the pinned download.
Keep adaptations in the ordered patches or native adapter sources. The About
resource uses the supported NORMAL state in place of OUTLINED. Source and
resource preparation alone do not establish native archive correctness.

The imported application, codecs and resource tools retain the donor's GPL
terms and notices. The copied COPYING, COPYING.LIB and licence note accompany
the prepared source. Exec's public interfaces and common C runtime retain their
existing licences.

Build with `python3 tools/build_gemarc.py --output build/gemarc/application`.
The ordinary APP links the common runtime and declares a 2,560-byte native
stack. `tools/build_demo.py --basic-workbench` installs it and its resource on
SYS and includes its donor notices. The desktop's ARC fallback respects saved
user associations. See [the user guide](../../../../docs/guides/gemarc.md) for
commands, formats, limits and recovery files.

Patch 0002 fixes checked reads, Close ownership, CRC/size validation, exclusive
temporary names and recoverable publication. Patch 0003 adapts the GUI and
bounded cancellation. Native adapters translate standard FILE streams, native
path enumeration and timestamps; all backing ownership belongs to the common
runtime. Portable independent-oracle tests and native emitted-code tests are
separate gates (`tools/test_gemarc_host.py`, `test_gemarc_native.py`,
`test_gemarc_paths.py`, `test_gemarc_allocation.py`, `test_gemarc_ui.py`).

`tools/package_gemarc_source.py --application BUILD --output DELIVERY` creates
matching corresponding sources outside the boot ZIP, including cached originals,
patched application/resource sources, runtime notices and the committed Exec
tree. Supply the exact source revision used for the application.
