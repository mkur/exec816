# FastBasic integer and floating-point targets

This source port starts from FastBasic 4.7 and the submodule revisions in
[upstream.json](upstream.json). It retains the donor parser and 6502 runtime.
The [target contract](../../docs/reference/fastbasic.md) defines the Exec profile.
FBC adds a private Altirra decimal math package; the native GEM workbench integrates editing, Check, Run, Stop and Build. `target/mathpack.asm` is generated from the pinned mini65 source by
`tools/generate_fastbasic_math.py`, retaining its own notice. Change the generator
and regenerate, rather than editing that output.

Build with Python 3, a C/C++ compiler, Make, Git and network access for the two
SHA-256 checked source archives:

```sh
python3 tools/generate_fastbasic.py --check
python3 tools/build_fastbasic.py
python3 tools/build_fastbasic.py --compile examples/fastbasic/HELLO.BAS \
  --program-output build/fastbasic/HELLO.COM
python3 tools/build_fastbasic.py --float --compile examples/fastbasic/CALC.BAS \
  --program-output build/fastbasic/CALC.COM
```

The helper builds the bundled cc65 assembler/linker and FastBasic host compiler,
then uses the host cross-compiler to build the on-machine frontend. The patched source's
Makefile selects `atari-int-compiler` for the internal compiler frontend and
`atari-int` for user programs. Only the former admits the port's own assembly
callbacks. The on-machine compiler itself emits the restricted user grammar.
`build/fastbasic/FBCI.COM` contains the integer compiler; `FBC.COM` is the FP
compiler, using `atari-fp-compiler` internally and restricted `atari-fp` for
user output. The host compiler is rebuilt from patched sources so literal
conversion agrees with AFP instead of binary-double rounding. Its historical
intermediate name `source/build/bin/fbci.xex` does not describe its new format.

`build.json` records source inputs, tool hashes and the FBCI envelope/hash.
`port-source.json` hashes every donor and added target source file. Reused source
caches are checked; edited caches fail rather than silently replacing a pin.
Make changes in [patches/exec6502.patch](patches/exec6502.patch) or [target/](target/),
then rebuild. Build directories are disposable; original source is verified
against the archives before reuse. The checked-in patch retains donor notices;
target helper/callback routines and generated interface constants are MIT.
The maintained command-line frontend optionally registers a diagnostic job before
source I/O. It normalizes line endings, rejects source lines over 255 bytes and
unsupported bytes before entering the donor parser, and keeps tab byte positions.
The port-owned whitespace helper accepts ASCII tab between tokens. The donor
parser stores its error-table offset before printing; the native adapter writes
the bounded record after the guest retires its channels. See the target contract
for the four-argument diagnostic invocation and required completion checks.

To rebuild from the accompanying source ZIP without fetching archives, in the
already-patched `fastbasic/` tree run:

```sh
make -j4 build/bin/fastbasic build/bin/ca65 build/bin/ld65 build/bin/ar65 \
  build/gen/syntp
make -j4 build/bin/fbci.xex build/bin/fbc.xex \
  build/compiler/fastbasic-int.lib build/compiler/fastbasic-fp.lib
```

The resulting `build/bin/fbci.xex` is `FBCI.COM` and `build/bin/fbc.xex` is
`FBC.COM`. The target's Makefile builds
its host cross-compiler before compiling the frontend.

Development checks:

```sh
python3 tools/test_fastbasic_controls.py
python3 tools/test_fastbasic.py --group all --output build/fastbasic/all
python3 tools/test_fastbasic.py --group runtime --raw --output build/fastbasic/raw
python3 tools/test_fastbasic_lifetime.py --output build/fastbasic/lifetime
python3 tools/test_fastbasic_lifetime.py --return-probe 7 \
  --output build/fastbasic/lifetime-nmi
python3 tools/test_fastbasic_faults.py
python3 tools/audit_fastbasic.py
python3 tools/audit_fastbasic.py --compiler FBC
python3 tools/test_fastbasic.py --float --group all --output build/fastbasic/fp-all
python3 tools/test_fastbasic.py --float --group runtime --decimal-probe --raw \
  --output build/fastbasic/fp-raw
python3 tools/test_fastbasic_controls.py --float --output build/fastbasic/fp-controls
python3 tools/test_fastbasic_rom_control.py
python3 tools/test_fastbasic_lifetime.py --float --output build/fastbasic/fp-lifetime
python3 tools/test_fastbasic_faults.py --float --output build/fastbasic/fp-faults
```

These need the pinned Action! compiler, AltirraOS ROM and Altirra bridge described
in the repository's [build guide](../../docs/contributing/building.md). The original
fixture controls use mini65's Atari OS simulation. The separate ROM control
runs an unmodified numeric program under original SDX and the pinned AltirraOS
ROM, with the emulator math patch disabled. These and the Exec development
checks do not qualify arbitrary Atari programs or physical hardware.

Build boot demos with `tools/build_demo.py --fastbasic` (optionally
`--bitmap-shell-only`), and run `tools/test_fastbasic_demo.py --bundle DIRECTORY`.
Ship `exec816-fastbasic-source.zip` from `tools/package_fastbasic_source.py`
alongside the boot ZIPs. It contains the complete modified donor and Exec source
snapshot, notices and build instructions. See [NOTICE.txt](NOTICE.txt) and
[LICENSING.md](../../LICENSING.md).

The optional native workbench demo is `tools/build_demo.py --basic-workbench`.
Its [guide](../../docs/guides/fastbasic-workbench.md) describes the first editor/Run
profile. Source debugging and native graphics have separate later gates.

To rebuild BASIC.APP from the source ZIP, use the supplied `exec816/` tree and
an installed Calypsi 65816 5.18 toolchain (large code, huge data). No Action
compiler checkout or downloaded GEM tree is needed for this disk application:

```sh
cd exec816
python3 tools/build_c_program.py --output build/basic \
  --minimum-stack 1312 \
  --source examples/gem-basic/main.c --source examples/gem-basic/basic.c \
  --source examples/gem-basic/editor.c --source examples/gem-basic/editor-paint.c \
  --source examples/gem-basic/document.c \
  --source examples/gem-basic/files.c --source examples/gem-basic/file-ui.c \
  --source examples/gem-basic/assist.c --source examples/gem-basic/assist-ui.c \
  --source examples/gem-basic/build.c --source c/calypsi/file-list.c \
  --source c/calypsi/fastbasic-diagnostic.c
```

The result is `build/basic/program.app`. Use the matching native system from the
boot package; the C program ABI and FastBasic target must agree. Calypsi is an
external licensed prerequisite and is not part of this corresponding-source ZIP.
