# Selected GEM4XE raster algorithms

[Implementation plan](../../../docs/plans/gem4xe/vro-cpyfm-plan.md)

`inputs.json` pins the independent 0.15 raster source. The existing renderer
and AES pins remain unchanged. `core.h` extracts the logical row merger and
blitter recipe table, with explicit operation state and fixed-width types.
`geometry.h` adapts the donor's rectangle normalization and paired clipping
to widened arithmetic. Neither file accesses hardware or global renderer state.

Reproduce or verify with `python3 tools/generate_gem_raster.py --fetch` and
`--check`. Preserve GEM4XE's GPL-2.0-or-later provenance and COPYING notice;
the MIT public interfaces do not relicense these algorithms. The existing
GEM4XE notices accompany distributions using this implementation.

RC0 development checks: the host pixel/geometry and reproduction checks pass;
`tools/test_gem_raster_core.py --mode opt --output build/gem-raster/rc0-opt`
executes the selected algorithms through emitted 65816 code on the pinned
ROM/bridge, retaining stack/domain guards and OS ownership checks. This is a
component check, not hosted-system qualification. Reserved bank-zero changes
are zero for fixed state, root/kernel, idle and every public Task pool.
