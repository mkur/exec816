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
