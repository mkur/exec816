# Layers visibility rebuild plan

Status: LR1 implemented; LR2 measurement and delivery pending.

[Popup results](../../history/popup-transition.md) ·
[Layers contract](../../reference/layers.md)

The PT4 warm switch spends 18.612 ms CPU in its remaining visibility rebuild,
including 15 rectangle subtractions. This is part of the 23.247 ms final
replacement commit and 78.920 ms presenter CPU, not an additional cost.

Rebuild currently starts each shown layer with its full bounds and subtracts
occluders from front to back. A nearer covering window can therefore erase a
region only after unrelated frontmost overlays have fragmented it. Disjoint
occluders also pass through subtraction and copy the unchanged result back.

## LR1 Reduce unnecessary subtraction work

Implemented; [development checks](../../history/layers-rebuild.md).

Subtract the same opaque occluders in nearest-to-farthest order, skipping
disjoint bounds and stopping when visibility becomes empty. The visible set is
still the layer rectangle minus the union of shown rectangles above it. Keep
damage publication, one rebuild counter increment, fail-closed behavior and
the existing work buffer. No incremental-visibility protocol, extra cache,
public ABI or presenter scheduling change is needed for this slice.

Extend the existing emitted Layers fixture with independent pixel and software
recomposition checks for a covered layer beneath overlapping and disjoint
overlays, touching edges, hiding/exposure, moving and reordering the cover.
Retain existing scene, saved replacement, pending-damage, capacity, bank-crossing,
guard and OS-return coverage. Run the host suite and optimized Layers fixture;
no compiler-facing change requires a raw matrix.

## LR2 Measure and deliver

Build the OF816 GEM desktop using the pinned compiler and compare the same
18 menu actions against the preserved PT4 package. Require exact fixture
visibility/recomposition, one warm-switch rebuild, two cached copies, no Files
paints and no timed disk traffic. Compare rebuild/subtraction CPU separately
from end-to-end response and menu-title work. Inspect open/dismiss and pointer
controls because the rebuild is shared by every scene mutation.

Record actual code/local-stack changes and the measured limit if frame sampling
hides a CPU improvement. Verify the demo ZIP and five-second OF816 autoboot.
Commit the implementation and measurement slices separately. These are
development checks, not release or hardware qualification.

Expected memory delta: **0 fixed bank-zero bytes, 0 per public Task, 0 idle**,
including guards, alignment and unused capacity. No new mutable data, Scene,
VRAM, DP, stack or upper-memory reservation is planned.
