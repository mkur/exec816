# Damage retirement implementation plan

Status: planned; production code is unchanged. Implement and commit DR1, then
measure and commit DR2.

[Latest measurements](../../history/warm-menu-input.md) ·
[Bookkeeping analysis](../../history/warm-menu-bookkeeping-analysis.md) ·
[Layers contract](../../reference/layers.md#saved-scene-rectangles) ·
[Testing policy](../../contributing/testing.md)

## Goal and evidence

Avoid reconstructing a damage list when restored/completed pixels intersect
none of its rectangles. Make this change in the existing `SubtractDamage`
helper in [layers-repaint.inc](../../../lib/display/layers-repaint.inc), shared
by saved-background restoration, saved-popup replacement and external
`Painted` acknowledgements.

The preserved WI2 demo is `build/warm-menu-input/demo` (clean `426f3f8a`), with
its matched capture in `build/warm-menu-input/menus`. The representative complete
keyboard switch spends **16.472 ms CPU** in `FinishSavedReplace`, including
**11.309 ms** in `Rebuild`. The remaining **5.163 ms** includes damage retirement,
geometry publication, lookup and cleanup; it is not all removable. The full
switch uses 61.063 ms presenter CPU in that sample; its three-sample median is
60.274 ms and the complete sampled visual endpoint remains about 100 ms.

Currently, every nonempty list outside the single-rectangle containment shortcut
is reconstructed through `Scene.work`. Disjoint rectangles go through
intersection, `PaintPiece` and copy-back even though their contents do not change.
Damage lists hold at most eight rectangles; subtraction can produce at most
32 temporary pieces in the existing workspace.

Scope is this shared helper and its focused regressions. Keep the full visibility
rebuild, summary publication, popup transaction, cache policy, renderer and
presenter scheduling unchanged. No new ABI, persistent flag, region abstraction,
allocation or caller validation is needed.

## DR1 Delay scratch work until the first overlap

1. Retain the empty-list and single-rectangle containment shortcuts. Treat a
   valid zero-area completion rectangle as successful no-change.
2. Scan for the first intersecting damage rectangle using signed, half-open
   edge comparisons. Touching edges count as disjoint. Trust the existing
   well-formed, bounded damage records; do not add per-record validation.
3. If the scan reaches the end, return success with the damage record untouched.
   Do not initialize or populate `Scene.work`, call `PaintPiece`, or copy the
   unchanged list back.
4. On the first hit, initialize the existing workspace, copy the unchanged
   prefix once, and run the current intersection/splitting logic from that
   entry onward. Preserve prefix/suffix order. Do not scan the prefix again or
   make a second pass over the whole list. Keep later disjoint entries in the
   ordinary suffix path; further compaction is outside this slice.
5. Publish the resulting count and rectangles only if the final count fits
   `MAX_DAMAGE`. On overflow return failure with the entire original damage
   record intact. Avoid in-place mutation: saved restores deliberately retain
   conservative damage when the result cannot be represented.

Leave `FinishSave`, `FinishSavedReplace` and `Painted` ownership/lifetime rules
intact. Manager-damage retirement must not acknowledge external pending repaint.
Existing callers continue updating `dirty` and `visibleDamage`; saved replacement
still performs one rebuild and releases its existing pin/token on the same paths.

Extend the current Layers fixture, primarily
`tests/programs/layers-external-checks.inc` and
`tests/programs/layers-save-checks.inc`, with bounded cases for:

- Zero, one, several and eight disjoint entries; cuts on all four sides,
  touching edges, and empty cuts inside existing damage. Verify unchanged
  counts and rectangle bytes.
- First overlap at the start, middle and end, including unchanged entries
  before and after it; full containment and partial subtraction.
- Exactly eight output pieces and overflow beyond eight, including a retained
  prefix before the split. Verify the original record survives overflow.
- Saved restore and CLEAN/DIRTY replacement with unrelated manager damage,
  plus external `Painted` completion. Preserve external pending paint, scene
  summaries, one replacement rebuild and existing stale/failure behavior.

Use the existing host coverage oracle machinery for expected remaining pixels,
with **union semantics** for Damage: damage rectangles may overlap, unlike exact
visibility Region partitions. Keep existing bank-crossing, ownership, stack/domain
guards and OS-return assertions. Do not add a separate testing framework.

Run the focused Layers host checks and one optimized emitted Layers fixture:

```sh
python3 -m unittest discover -s tests -p 'test_layers_contract.py'
python3 tools/test_layers.py --mode opt --output build/damage-retirement/dr1-layers
```

Inspect the emitted disjoint path to confirm it avoids scratch construction and
copy-back. Preserve the bounded intersecting path and check its local stack/code
cost. No compiler-facing change requires raw-mode execution or a compiler suite.
Commit this implementation with its focused checks before building the demo.

## DR2 Measure and deliver

Build a clean package through `tools/build_demo.py --gem-desktop
--release-compiler --output build/damage-retirement/demo`, retaining OF816 and
its five-second autoboot, matching disks, pinned ROM and distribution notices.

Run one matched 36-action menu capture using `tools/trace_menu_response.py` with
`--native-check --load-check`. Reuse the preserved WI2 baseline. Existing passive
markers already distinguish `FinishSavedReplace` and its nested `Rebuild`;
compare their inclusive and exclusive CPU separately. The exclusive residual
includes other bookkeeping, so do not label it an isolated helper measurement.
Record keyboard/pointer complete pixels, title retirement and presenter CPU,
including individual frame brackets and pointer crossing times. Also retain
open/dismiss, cold-menu and native controls because the helper serves restore
paths beyond heading replacement.

Require matching cache-transfer behavior, no incidental Files repaint or timed
disk traffic, correct pixels, Counter progress, intact guards and normal EXIT.
Report a CPU gain even if PAL frame sampling does not resolve earlier feedback;
do not promise a 5.163 ms saving or infer p95 from three samples. If intersecting
controls materially regress, revisit the helper before accepting the slice.

Record actual production code/data and observed stack changes, verify archive
checksums, and save compact measurements plus an execution record under
`docs/development` and `docs/history`. Update their indexes and this plan, provide
the demo launch command, and commit the delivery slice. These are development
checks; no full AES, filesystem, raw or release qualification matrix is planned.

Expected reserved bank-zero delta for both slices: **0 fixed, 0 per public Task,
0 idle bytes**, including guards, alignment and unused capacity. Scene, DP, stack,
VRAM and upper-memory reservations remain unchanged; local temporary costs are
measured separately.
