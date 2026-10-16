# Damage retirement

[Implementation plan](../plans/gem4xe/damage-retirement-plan.md) ·
[Starting measurements](warm-menu-input.md) ·
[Layers contract](../reference/layers.md#saved-scene-rectangles)

## DR1 First-overlap scratch construction

`SubtractDamage` now returns without rebuilding a list when the completion
rectangle is empty or disjoint from all its entries. Signed half-open edge
comparisons treat touching edges as disjoint. At the first overlap it copies
the unchanged prefix once, then uses the existing splitting and publication
path. Results larger than eight rectangles still leave the original record
untouched. The single-rectangle containment shortcut remains.

This shared change covers saved-background restoration, saved-popup replacement
and external `Painted` completion. There is no new caller check, state, allocation
or ABI. Visibility rebuilding, cache policy, dirty summaries and transaction
ownership are unchanged; manager-damage retirement does not acknowledge an
application's pending repaint.

Development checks pass: six focused host checks and the optimized Layers
fixture, with **8,919 emitted checks**, 128 geometry cases and 40 scene cases.
Twenty-four new completion cases check empty/disjoint/touching rectangles,
first overlap at each position, preserved prefixes/suffixes, exactly eight
pieces, overflow, signed coordinates and overlapping damage. The host oracle
checks the remaining pixel union independently. Saved CLEAN/DIRTY replacement
and dismissal preserve unrelated manager damage and external pending paint,
release the token/pin and retain one rebuild per replacement. Existing stale,
failure, bank-crossing, ownership and guard coverage remains in the fixture.
Normal return and zero live Tasks pass. No raw or qualification matrix ran.

Artifacts are `build/damage-retirement/dr1-layers` and adjacent host/fixture
logs. Emitted-code inspection is retained as
`build/damage-retirement/dr1-subtract.asm`: the disjoint scan returns before
workspace stores, `PaintPiece` or copy-back, and rectangle indexing uses shifts.
The containment shortcut still calls `REGIONS.Contains` for a one-entry list.

The helper grows **1,254 → 1,755 bytes** (+501). Its fixed frame, spill allocation
and local stack peak remain **26 / 16 / 42 bytes**; these are local figures, not
whole-call-chain bounds. No mutable globals are added. Reserved bank-zero delta
is **0 fixed, 0 per public Task, 0 idle bytes**, including guards, alignment and
unused capacity. Scene, DP, stack, VRAM and upper-memory reservations are unchanged.

## DR2 Production measurement

Pending: build a clean OF816 package and run the unchanged 36-action menu
capture against the preserved WI2 demo. Report the saved-popup commit and
nested visibility rebuild separately; the exclusive residual includes other
bookkeeping and is not an isolated measurement of `SubtractDamage`.
