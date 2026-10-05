# Layers and regions

[Reference](README.md) · [Desktop design](../plans/gem4xe/desktop-design.md) ·
[Implementation plan](../plans/layers-implementation-plan.md)

`LAYERS` is an ordinary Action! library for up to four opaque rectangular layers
and a permanent background. It maintains stacking, cached visibility, damage and
one drawing transaction per scene. It does not draw pixels, acquire the display,
route input or create Tasks. The desktop and its bitmap console consume these transactions.

The generated records and status constants are in `LAYERTYPES`, from
[layers.json](../../abi/layers.json). Implementation lives in
[layers.act](../../lib/display/layers.act) and
[regions.act](../../lib/display/regions.act). All coordinates are signed 16-bit,
half-open screen coordinates: left/top included, right/bottom excluded.

## Storage and ownership

The presenter supplies an address-stable `Scene` in upper RAM. Call `Init` once
before publishing it; reinitializing a live scene is outside the contract. One
owner serializes every access. Preemption is permitted, but interrupt handlers
must not call Layers, and a second Task must not access the same scene while its
owner runs. Separate scenes have no shared library state.

Pointer arguments name valid live storage. Output scalars must be disjoint from
the scene and input descriptors. Records and cached regions are read-only to
callers after initialization. This is the registration-and-lifetime contract,
not memory protection: operations check their geometry, identities and state,
without searching writable-memory tables or crossing the Exec gateway.

The window service retains application Tasks, console instances and requests.
Layers itself stores no Task pointers or borrowed drawing buffers. Retire any
transaction and all external handles/borrows before releasing scene storage or
ending its enclosing lifetime. Individual deletion retires a layer's ID; whole
scene teardown needs no additional library cleanup once its users have retired.
IDs and update tokens never repeat within that lifetime.

## Scene operations

| Call | Behavior |
| --- | --- |
| `Init(scene,width,height)` | Positive dimensions through 32767. Establish a background at `[0,width) × [0,height)`, initially dirty. No allocation. |
| `Create(scene,bounds,idOut)` | Admit a nonempty rectangle fully within the screen. Create it hidden at the front of the stacking order and return a fresh nonzero ID. FULL at four live layers; EXHAUSTED after the last 32-bit ID. Rejection leaves `idOut` unchanged. |
| `Show(scene,id,shown)` | Show with 1 or hide with 0. Retain content identity while hidden. |
| `Move(scene,id,left,top)` | Preserve dimensions; reject positions outside the screen without overflow. Mark old/new areas for repair. |
| `BeginMove(scene,id,left,top,tokenOut)` | Admit a clean, shown, fully visible front layer for a copied move; retain old/new bounds until Finish. EMPTY for unchanged placement, REDRAW for a nonclean/covered/nonfront source. |
| `Order(scene,id,front)` | Move to front with 1 or back with 0. Background always remains below ordinary layers. |
| `Delete(scene,id)` | Retire the layer and damage the affected area. Reusing its slot assigns a different ID. |
| `Find(scene,id)` | Borrow a read-only layer record, or NULL for a stale ID. Zero selects the permanent background. |
| `Hit(scene,x,y)` | Return the frontmost shown layer's ID; zero for background or outside the screen. Uses existing geometry without rebuilding visibility. |
| `Invalidate(scene,id,rect)` | Accumulate damage clipped to that layer's bounds. Retains eight rectangles, merging containment and exact rectangular unions. Overflow collapses all damage to one bound. Does not rebuild visibility. |

All status-returning calls use `LAYERTYPES.OK` on success. Geometry errors return
BAD_ARGUMENT and unknown/retired identities return BAD_ID. Show, Move, Order and
Delete reject background ID zero. Repeating a no-op Show, Move or Order succeeds
without rebuilding. Hidden creation, movement, reordering and deletion leave
other layers' visibility unchanged. `scene.rebuilds` is a diagnostic wrapping
counter, not an identity or completion token.

Visibility is exact and consists of disjoint rectangles. Changes recompute the
cache and conservatively damage intersecting layers, including background.
Painting always clips damage against visibility, so an oversized damage bound
cannot authorize drawing through another layer. Geometry and content mutation
calls return BUSY while a drawing transaction is active, including otherwise
harmless no-ops. Find, Hit and PaintRegion may inspect stable state during it.

## Painting and copying

`BeginPaint(scene,id,tokenOut)` intersects current damage with cached visibility.
It returns EMPTY without acquiring anything when there is no visible work. OK
publishes a fresh nonzero token and holds the scene stable. Obtain the read-only
rectangle list through `PaintRegion(scene,token)` and render every rectangle.
Call `AdvancePaint(scene,token)` after each batch. OK exposes another nonempty
batch; EMPTY means traversal is exhausted. Only then call
`Finish(scene,token,1)` after drawing completes. An early successful Finish
returns BUSY and leaves the token and damage intact. PaintRegion stays stable
until AdvancePaint or Finish; an exhausted region has zero entries. A mismatched or retired token
returns NULL from PaintRegion and BAD_TOKEN from Finish.

The renderer may process a bounded part of the list per turn and yield or wait
between parts. It must retain the scene and transaction throughout. Input
capture and unrelated computation can continue; dependent model edits, layout
changes and another drawing operation wait. The gate freezes the retained
eight-entry damage list for the whole transaction. Each damage rectangle is
clipped independently into the existing 96-entry work region; the potentially
larger product is never stored in that buffer. Partial overlaps may be painted
more than once. Empty clipped batches are skipped. Finish with zero after a failed
paint preserves damage for retry. Invalid completion flags leave the transaction
active. Successful paint acknowledges the visible work; any covered pixels are
reconstructed from retained content when later exposure marks them dirty again.
An entirely hidden or covered dirty area returns EMPTY and remains dirty.

`BeginCopy(scene,id,source,target,tokenOut)` admits equal-sized rectangles wholly
inside a clean, fully visible layer. Empty geometry returns EMPTY. Covered,
hidden or dirty layers return REDRAW without acquiring a transaction. The
caller then updates its retained model, invalidates affected content and uses
the paint path. The first implementation intentionally does not plan partial
copies around occluders, even if an individual source/target pair is visible.

On OK, source and target are copied into `scene.copySource` and
`scene.copyTarget`, which remain stable until Finish. These are geometry only;
the renderer supplies surface addresses and chooses overlap-safe copy direction.
Remove intersecting pointer/caret/drag overlays before drawing and respect the
VBXE driver's even-pixel and extent requirements. Layers admission alone is not
hardware admission. A successful copy must leave the retained model and copied
pixels consistent; exposed strips and later content edits still need drawing.
Finish with zero invalidates the entire layer after a failed copy.

A move transaction reuses the saved rectangle pair for old and new bounds.
Hit testing and Find continue to expose the old committed bounds during DMA.
Finish-success publishes the target geometry, rebuilds visibility and marks at
most four old-minus-new exposure rectangles below it. The copied layer stays
clean. Finish-failure keeps old geometry and invalidates both touched areas;
it is permitted only after the driver proves quiescence. No extra region,
transaction buffer or per-window storage is reserved.

The token does not signal hardware completion. Keep it active until the driver
has completed or proved DMA quiescent. A reset-required failure retains storage
and the token. See [display ownership and completion](display.md). No Layers
call waits for a blitter, disables IRQ/NMI or adds a completion interrupt.
The last 32-bit token is usable, after which new nonempty transactions return
EXHAUSTED. Finish and deletion remain available; caller output tokens are
unchanged on every unsuccessful begin.

## Region operations

`REGIONS` supplies `Assign`, `Copy`, `Intersect`, `Contains`, `Equal`, `Valid`
and `Empty` rectangle helpers. Except Valid, these trust initialized, valid
rectangle pointers and geometry; Assign sets the supplied bounds directly.
Intersect supports its output aliasing either input and canonicalizes disjoint
results to zero area. It adds no coordinates, so signed extremes are safe.

`FromRect(region,rect)` initializes a region to one nonempty rectangle or an
empty region. `Subtract(source,cut,target)` removes a rectangle, while
`Clip(source,bounds,target)` intersects the region with one rectangle. Inputs
come from these operations and remain read-only. Source and destination regions
must occupy disjoint complete records, including unused capacity. Overlap is
rejected before writing. Valid empty inputs succeed with an empty result.

Each region has room for 96 rectangles. Subtraction counts before emitting and
returns FULL with all destination bytes unchanged on overflow; malformed bounds
or an excessive input count return BAD_ARGUMENT. Clipping cannot increase the
rectangle count. Four scene occluders introduce at most nine intervals on each
axis, so their subdivision fits within 81 cells and cannot exhaust this region
capacity. Generic repeated subtraction remains subject to FULL.

## Memory and supported scope

| Caller-owned record | Bytes including alignment and unused capacity |
| --- | ---: |
| Rect | 8 |
| Region with 96 rectangle slots | 770 |
| Eight-entry Damage record | 66 |
| Layer including visibility and damage | 850 |
| Scene with four layers, background, scratch region and transaction state | 5,074 |

All large arrays belong in upper RAM. Local rectangle temporaries use the
caller's existing native stack. The library adds zero reserved bank-zero bytes:
fixed, root/kernel, per-Task and idle reservations, guards and alignment are
unchanged. It allocates no per-window stack, DP, signal or Task, and reserves no
VRAM. Generated layouts require rebuilt callers when changed.

Unsupported: overlapping access to one scene by different Tasks, partially
offscreen layers, resizing, transparency, nested layers, offscreen backing
bitmaps, font clipping, window controls, input policy, dynamic library loading,
C bindings and direct hardware submission. The desktop presenter supplies drawing, input and window policy separately.

### Read transactions

`BeginRead(scene,id,source,tokenOut)` holds a clean, shown source contained in a
visible rectangle. Covered/dirty sources return `REDRAW`; empty sources acquire
no token. Geometry and retained mutations remain gated until `Finish` after DMA
retirement. `UPDATE_READ` completion never acknowledges paint and a failed read
does not mark clean framebuffer pixels dirty merely because its destination
failed. The saved source rectangle is owned by the scene. The existing copy,
move and paint operations remain mutually exclusive with a read.
