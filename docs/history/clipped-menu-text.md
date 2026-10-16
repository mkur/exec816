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
