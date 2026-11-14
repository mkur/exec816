# Selected GEM4XE raster algorithms

[Implementation plan](../../../docs/plans/gem4xe/vro-cpyfm-plan.md)

`inputs.json` pins the independent 0.15 raster source. The existing renderer
and AES pins remain unchanged. `core.h` extracts the logical row merger,
dedicated S_ONLY row copy and blitter recipe table, with explicit operation
state and fixed-width types. `shift.s` reproduces the donor's word-load/XBA/
four-shift loop using Calypsi's huge-pointer arguments and long-indexed data
access. It uses the existing caller argument workspace, with no DP reservation.
`geometry.h` adapts the donor's rectangle normalization and paired clipping
to widened arithmetic. These units access no hardware or global renderer state.

`staged.h` composes different-parity screen S_ONLY through the drawing adapter:
source blit, existing native shift inside a mapped page, then masked blitter
publication. Its 16 KiB reservation contains sixteen 1,024-byte slots, with
source at +0 and output at +512. Whole-band capture protects overlap; the
complete raster work determines band height within the current 8,192-access
and sixteen-row bounds. Physical access and final fences protect scratch only
until that band returns. The [mapped-copy record](../../../docs/history/gem-raster-mapped.md)
keeps ownership checks, memory costs and packaged measurements separate.

Reproduce or verify with `python3 tools/generate_gem_raster.py --fetch` and
`--check`; both `core.h` and `shift.s` are generated. Preserve GEM4XE's
GPL-2.0-or-later provenance and COPYING notice;
the MIT public interfaces do not relicense these algorithms. The existing
GEM4XE notices accompany distributions using this implementation.

RC0 development checks: the host pixel/geometry and reproduction checks pass;
`tools/test_gem_raster_core.py --mode opt --output build/gem-raster/rc0-opt`
executes the selected algorithms through emitted 65816 code on the pinned
ROM/bridge, retaining stack/domain guards and OS ownership checks. This is a
component check, not hosted-system qualification. Reserved bank-zero changes
are zero for fixed state, root/kernel, idle and every public Task pool.
