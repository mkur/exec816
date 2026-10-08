# GEM4XE calculator inputs

`inputs.json` pins the application and resource generator independently from
Exec's extracted AES/VDI. `tools/prepare_calculator.py --output DIR` verifies
cached inputs (fetching missing files), copies them below DIR, applies the
explicit patches and generates `CALC.RSC` and `source/src/apps/calcrsc.h`.

The cache is `build/calculator/upstream`. Neither extraction nor generation
writes to `~/atari/gem4xe`. Host helpers, font/pattern tables and VBXE constants
are included because the donor resource generator imports its host AES model;
they are not additional target application code.

The first resource patch disables the donor's 3D flags. Object IDs, labels,
geometry and TEDINFO text storage remain donor-owned definitions. Generated
outputs and provenance stay in the build directory.

Preserve the pinned donor `COPYING`, `COPYING.LIB` and `docs/licence.md` notices.
The calculator application is donor code under GPL-2.0-or-later; Exec's MIT
interface/example grant does not relicense it. See [the licence map](../../../../LICENSING.md).
