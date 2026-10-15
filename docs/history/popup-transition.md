# Popup replacement implementation

[Design](../plans/gem4xe/popup-transition-design.md) ·
[Plan](../plans/gem4xe/popup-transition-plan.md) ·
[Layers contract](../reference/layers.md)

## PT1 Layers transaction

`BeginSavedReplace` claims before publication and retains the old geometry,
visibility and saved-image pin. `FinishSavedReplace` commits clean or dirty
replacement geometry with one rebuild, or retains old geometry and damages
both touched rectangles on failure. Generic `Finish` rejects this token kind.
Successful retirement subtracts only the old restored footprint; application
pending repaint and bounded-overflow damage remain intact.

Development checks pass: 491 host tests (four historical skips), generated
Layers definitions, and 2,250 optimized emitted Layers assertions, including
117 additional checks for replacement/damage/ownership and the existing scene,
region, bank-crossing, guard and OS-return cases. Artifacts are in
`build/popup-transition/pt1-layers`. No raw or qualification matrix was run.

The fixture's first build exceeded its incidental no-argument Task-entry
capacity; passing the strip count to the new regression keeps that helper out
of the Task entry table without enlarging production reservations.

Layers/Regions native code grows 36,391 → 38,646 bytes (+2,255).
Begin/finish replacement occupy 803/1,426 bytes with 34/32-byte local stack
peaks; the library maximum remains 56. These are local compiler figures, not
whole-call-chain bounds. Scene storage remains 9,186 bytes with no mutable
Layers globals. Reserved bank-zero delta is **0 fixed bytes, 0 per public Task
and 0 idle**, including guards, alignment and unused capacity. DP, stack and
VRAM reservations are unchanged.

## PT2 Cache continuation

The cache adapter now retains one Layers token and the image pins through
background restore and optional popup copy. It freezes the existing popup key,
uses staged bounds for the second copy, and reports CLEAN, DIRTY or REPAIR for
the menu owner to adopt. A dirty commit records the cache miss once; ordinary
painting skips the redundant lookup. Production menu admission is unchanged
in this slice.

The optimized presenter fixture passes eight cases and 163 emitted assertions:
hit with a differently sized popup, miss, rejected background submission,
failed background completion, rejected popup submission, failed popup completion,
invalidated background and stale menu revision. It checks independent VRAM
pixels across both popup footprints, one final rebuild, retained pins while
unquiesced, damage/save validity, and stale completion rejection during a later
transaction. The fixture suspends unrelated console painting while supplying
its own synthetic scene; the console caret lies outside the compared rectangle.
Fault controls exist only in generated fixture modules.

Artifacts: `build/popup-transition/pt2-cache`. Host checks pass (491 tests,
four historical skips). Stack/domain guards, ownership cleanup and normal OS
return pass. Observed presenter stack peak is 690 of 2,560 bytes, with 1,614
bytes above its floor remaining; kernel peak is 283 of 1,536 bytes. These are
observations in this fixture, not worst-case bounds or qualification.

New fixed upper-memory fields total **21 bytes**: an 18-byte frozen key and
three scalar bytes. Final production code/alignment accounting follows in PT4;
the fault-instrumented fixture is not a production code-size comparison.
Reserved bank-zero delta is **0 fixed, 0 per public Task, 0 idle bytes**, including
guards, alignment and unused capacity. Scene, DP, stack and VRAM reservations
are unchanged.
