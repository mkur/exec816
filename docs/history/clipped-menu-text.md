# Clipped menu text

[Implementation plan](../plans/gem4xe/clipped-menu-text-plan.md) ·
[MT3 baseline](menu-title-response.md)

## CG1 Private encoder

The existing glyph-run encoder accepts one through eight atlas rows. Its donor
wrapper offsets the atlas once; record construction emits one stencil record
per nonblank glyph portion at either X parity. Existing full-height callers
still request row zero and height eight in this slice.

Full-height capacity tables conservatively reserve each prefix. One lookup in
the existing work table charges the aggregate written width and actual row
count. No table, cache or per-glyph validation was added. The emitted encoder
and record writer call no multiplication, division or remainder helpers.

Development checks pass: four extraction tests, four widget host tests, two
table-generator tests and all 37 optimized emitted widget pixel stages. The
new stage checks all 72 valid first-row/height/parity combinations against the
independent font oracle. The builder also checks actual list work, mixed-list
record/work limits, blank-only suffixes and failed submission/reopening.
Existing full-height, strip continuation, pointer, guard and cleanup cases pass.

The fixture now uses the pinned release compiler executable, matching the AES
runner. Its initial debug-executable compilation was stopped for excessive
build time before execution; the release-executable run completed successfully.
This changes neither compiler revision nor target optimization mode.

Artifacts: `build/clipped-menu-text/cg1-pixels` and the adjacent host logs.
Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. VRAM, upper-memory, Scene, DP and stack
reservations are unchanged. Final production code/stack costs and timings will
be recorded with CG3. No raw or release qualification matrix ran.

## CG2 Widget and menu routing

`GemWidgetText` intersects the vertical cell once and routes horizontally
complete nonzero-ink cells through the row-span encoder. Partial horizontal
cells and hardware-zero ink retain the general path. Scratch publication,
menu geometry, painter budgets and scheduling remain unchanged.

All 38 optimized widget pixel stages pass. The added stage exercises the same
72 row/parity combinations through `GemWidgetText`, plus 16 cases covering
combined edge cuts, a single cut cell, zero ink, blanks, empty clips, screen
edges and one visible row. Emitted list assertions require one stencil record
per nonblank complete cell. Mixed-list and failed-submission checks also run
through the new routing. The four widget host tests pass.

The optimized AES-menu fixture passes all seven pixel phases, the long
checked/disabled odd-X menu, replacement input, title continuation/failure,
native menu controls and cleanup. Artifacts: `build/clipped-menu-text/cg2-pixels`
and `build/clipped-menu-text/cg2-menus`. Both use the same pinned release
compiler binary as the MT3 demo; no compiler override was used.

Reserved bank-zero delta: **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. Other reservations remain unchanged.
The widget fixture observes 658/2,560 presenter stack bytes, with 1,646 above
the floor remaining; this is a workload observation, not a stack bound.
