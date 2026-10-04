# Layers implementation plan

[Plans](README.md) · [Desktop design](gem4xe/desktop-design.md)

Implement a bounded Layers library before the desktop window manager. The
library owns opaque rectangular geometry, stacking, cached visibility, damage
and drawing transactions. The caller owns retained content, input, window
decorations and hardware execution. This is the simple-refresh direction from
the [Amiga Layers model](https://wiki.amigaos.net/wiki/Layers_Library), adapted
to one presentation worker and the 65816 memory budget.

## Scope and contracts

Use ordinary Action! calls with caller-owned, address-stable upper-RAM storage.
No new Task, message per primitive, kernel selector, dynamic library loader,
interrupt hook, VRAM allocation or runtime memory-table scan is introduced.
The caller serializes access; IRQs do not call Layers. Window/application Task
retention belongs to the future window service. Initial public bindings are
Action! only.

Rectangles use signed 16-bit half-open bounds. Scenes admit at most four opaque
layers fully within a positive screen rectangle, plus a permanent background.
Hidden layers retain identity and damage. IDs are nonzero, monotonically
allocated during a scene lifetime; background uses zero. No slot reuse can make
a stale ID valid. Visible rectangles are cached and recomputed only when the
layout changes. A fixed region holds 96 disjoint rectangles: four occluders
introduce at most nine intervals on each axis, bounding their subdivision at
81 grid cells. Generic region overflow fails without modifying the destination.

Damage may conservatively coalesce to a bounding rectangle, but presentation
always intersects it with exact visibility. A paint transaction snapshots that
intersection. Its non-reused token keeps layout and damage stable until the
caller reports completed drawing or failure. New operations return BUSY while
a transaction is active. The caller must wait for hardware completion before
finishing; the token is not itself a DMA completion notification.

The first copy transaction admits equal-sized source/destination rectangles
within a clean, fully visible layer. Covered or dirty layers request redraw.
Pixel alignment, overlap direction, transient removal, submission and fences
remain drawing/driver responsibilities. Failed copying invalidates the layer.

## Executable slices

| Slice | Implementation | Development acceptance |
| --- | --- | --- |
| L1 Regions | Machine-readable capacities/layouts, generated native types, rectangle intersection and exact bounded region subtraction/clipping. | Raw/optimized emitted geometry against an independent pixel-set oracle; touching, empty, signed extremes, alias rejection, overflow atomicity and storage guards. |
| L2 Layer scenes | Initialization, hidden creation, show/hide, move, front/back, delete, hit testing and cached visibility. | Independent stacking oracle through repeated overlap/movement/slot reuse; stale IDs, capacity, invalid bounds, identity exhaustion, no-op operations and cache stability. |
| L3 Damage and drawing transactions | Damage accumulation, clipped paint iteration, completion/failure, fully visible copy admission and shared in-flight gate. | Emitted retained-scene rendering compared with independent complete recomposition; covered edits, exposure, stale completion, BUSY rejection, failed drawing/copy and token exhaustion. |
| L4 Integration contract and evidence | Current reference, runnable test tool, host checks, recorded memory/stack and execution scope. Update desktop design and roadmap to consume Layers. | Host suite, generation check, final raw/optimized scene corpus on pinned AltirraOS/emulator, guard/ownership and OS restoration checks; content/link checks. |

Commit each completed slice separately. Keep fixtures executable as the API grows;
rebuild callers together with generated layouts. Do not add compatibility APIs.
Use pinned actionc inputs without overrides. A compiler defect belongs in actionc
with a focused regression, not a Layers-specific workaround.

## Memory and timing

Every slice targets **zero additional fixed, root/kernel, per-Task and idle
bank-zero reservations**, including guards, alignment and unused capacity. All
region/scene arrays are in caller-owned upper RAM; do not place them on the
native stack or in the resident globals arena. Report exact generated sizes and
observed stack use in the execution record. No application Task is added.

Measure bounded geometry work and record cached-query behavior, but do not turn
this into another console optimization milestone. End-to-end pointer, drag and
exposure timing requires the later window/presenter integration. Pure Layers
execution and its software raster fixture do not establish VBXE timing or a
working desktop. No demo refresh is needed for this library-only milestone.

## Completion status

L1 and L2 complete: raw/optimized emitted geometry, 28 scene transitions
and host checks passed; [regions](../development/layers-l1.json) and
[scene evidence](../development/layers-l2.json). L3 also passed: 32 scenes,
incremental pixels and transaction failures in both builds;
[drawing evidence](../development/layers-l3.json). L4 pending.
Current console presentation remains unchanged. Desktop controls,
pointer integration, clipped font rendering, optional backing bitmaps and actual
VBXE presentation of overlapping windows follow this library milestone.
