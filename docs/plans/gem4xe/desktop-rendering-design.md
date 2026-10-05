# Desktop rendering with pixel reuse

[GEM plans](README.md) · [Implementation plan](desktop-rendering-implementation-plan.md) ·
[Layers contract](../../reference/layers.md) · [Display contract](../../reference/display.md)

Status: proposed design, 2026-10-05. Combine classic Amiga refresh semantics
with GEM4XE's VBXE optimizations for the existing Exec816 desktop: reuse valid
pixels, repaint smaller areas and preserve input service while DMA runs.
Retained models and the single presentation worker remain the foundation.

This milestone does not resume paused AW5–AW6 widget work or general console
optimization. Current public contracts remain authoritative until executable
slices implement these proposals.

## Existing behavior and evidence

The source baseline is Exec816 `be672b9` and GEM4XE 0.9.4 at
`e413c39d2f8e1bec8fe16596f610b923de4a0ae9`, selected by the
[donor pin](../../../ports/gem4xe/inputs.json). Existing
[desktop results](../../history/desktop.md) and
[mouse measurements](../../history/mouse-performance.md) apply to their
recorded builds. This note makes no new measured performance claims.

| Existing behavior | Consequence for this design |
| --- | --- |
| Four opaque layers and a background, exact visibility, one damage bound per layer | Retain several small damage areas before combining them. |
| Move invalidates old/new areas and the moved window | Add a transaction that preserves copied pixels as clean. |
| Clean, fully visible scrolling uses one asynchronous copy/fill list | Share its completion/lifetime machinery with rectangle copies. |
| General copying and ordinary drawing complete synchronously | Add explicit asynchronous copies; preserve synchronous call semantics. |
| Pointer moves use one list and cached parity masks | Preserve this path and service it between repair quanta. |
| Retained cells, graphical commands and widget trees belong to the presenter | Repair exposure without an application redraw round trip. |

The [move code](../../../lib/display/layers.act),
[painter](../../../lib/desktop/deskpaint.act) and
[VBXE adapter](../../../platform/altirraos/vbxe.c) are the starting points.
`PaintStrip` fills a whole strip before painting its client background again.
`DESKPAINT.Sync` dirties all console cells when placement changes. Pixel reuse
must address these paths, or subsequent repaint would erase its benefit.

## Lessons from Amiga and GEM4XE

Classic Amiga Layers maintains clipping, stacking and damage. Simple Refresh
discards hidden pixels; Smart Refresh stores obscured fragments and directs
hidden drawing into those buffers; SuperBitMap uses an application-supplied
backing bitmap. Adopt the separation between window semantics and pixel storage,
with retained redraw as our default and optional storage as an optimization.
[Amiga Layers manual](https://www.theflatnet.de/pub/cbm/amiga/AmigaDevDocs/lib_30.html)

Amiga graphics calls can return with their final blit running; dependent access
must wait. Ownership and completion are separate concerns. Queueing also has
overhead for small blits. Keep bounded synchronous pointer work and use IRQ
completion for larger copies.
[Graphics manual](https://www.theflatnet.de/pub/cbm/amiga/AmigaDevDocs/lib_27.html),
[blitter API](https://www.theflatnet.de/pub/cbm/amiga/amigadev.elowar.com/read/ADCD_2.1/Includes_and_Autodocs_2._guide/node05A6.html)

GEM4XE copies eligible top-window moves, repaints exposed content, aligns windows
to even pixels and caches glyph/pointer masks in VRAM. Its upstream submission
starts lists without waiting and spins at dependencies. Adopt its pixel reuse
and alignment while retaining Exec's completion signal and watchdog.
[Window moves](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/wind.c#L741),
[drawing](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vdi/dev_vbxe.c),
[submission](https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/vbxe/vbxe.c#L74)

Amiga's source shifters and three-source logic do not map directly onto VBXE.
Keep even-pixel copy admission and existing odd/even glyph and pointer masks.
Arbitrary unaligned raster operations are not promised as single blits.
[Amiga blitter hardware](https://www.theflatnet.de/pub/cbm/amiga/AmigaDevDocs/hard_6.html)

## Responsibilities and lifetime

| Component | Responsibility |
| --- | --- |
| Exec | Existing Tasks, messages, signals and retained resource lifetime. |
| Layers | Geometry, visibility, damage and stable paint/move transactions. |
| Presenter | Retained content, cache policy, overlays, rendering and input fairness. |
| VBXE driver | Descriptor checks, copy direction, one in-flight operation, IRQ/watchdog completion and quiescence. |

All display access stays with the existing presenter. Applications send requests
and consume events. No application callback runs in the presenter or IRQ. No
window, cache or blit allocates a Task, native stack or DP.

Capture, event delivery and request intake continue during DMA. Geometry,
dependent model changes and other screen operations remain gated by the live
scene transaction. The IRQ records completion and signals; the worker consumes
the result and handles recovery. A signal alone never releases a scene token,
cache slot or command arena. No new kernel gateway is required.

## Bounded damage and paint traversal

Keep up to eight damage rectangles per layer, including the background. Remove
contained rectangles and merge rectangular unions that add no area. Overlap may
conservatively cause repeat painting. At capacity, collapse to one bounding
rectangle. Never discard damage or widen drawing permission beyond visibility.

Eight damage rectangles intersected with 96 visibility rectangles can exceed
the existing 96-entry work region. The four-occluder visibility proof does not
bound this product. Clip one damage rectangle into `scene.work`, render that
batch, then explicitly advance to the next under the same token. Borrowed
batches stay stable until advance/finish. Keep traversal state in upper RAM;
do not put a product-sized region on the native stack.

BeginPaint captures damage while the mutation gate is held. Successful Finish
requires traversal exhaustion; reject early success without releasing the token.
Failure preserves the original damage. Fully covered damage remains non-runnable.
After complete visible painting, covered damage may be retired because later
exposure independently marks newly visible pixels dirty, as in the existing
retained-content contract. Hidden framebuffer pixels are never thereby valid.

Migrate console, graphical-command and widget paint consumers together. Keep
one current generated layout/API, with no old first-batch-only consumer.

## Asynchronous rectangle copies

Add typed `VbxeCopyStart` and a common completion query for copying and scrolling.
Names are proposed until the implementing slice freezes declarations. Keep
`VbxeScrollStart` for copy-plus-fill; retire the scroll-only completion entry
and migrate all callers rather than maintaining parallel engines.

Initially accept even X coordinates/width, at most 640 by 240 pixels and 76,800
copied bytes. Reuse surface extents, command-arena exclusion and overlap checks.
Overlapping equal-pitch views use the correct ascending/descending direction;
different pitches require disjoint extents. Empty geometry launches nothing
and returns a defined empty result without allocating an operation ID.

Copy accepted descriptors before return. A second start returns BUSY without
changing the active list or output ID. Source, destination and driver storage
remain live through matching completion or proven quiescence. IDs never repeat
across reopen. Reuse the signal, launch deadline and IRQ/watchdog producer.
Validate the owner once per public entry and all geometry before hardware writes.

Synchronous calls retain their lifetime guarantees and fence dependencies. The
presenter avoids entering one while it intends to service input during pending
DMA. Do not silently make the donor's `blit_start` adapter asynchronous while
its callers still reclaim source buffers on return.

One rectangle is a work bound, not a latency guarantee. Measure duration and
service the latest pointer immediately after completion, before exposure repair.
A long list cannot be preempted for the pointer. Do not relax synchronous list
limits or chain a whole desktop repaint into this operation. If the rectangle
budget misses input targets, implement a separately tested continuation with
globally safe overlap order before claiming responsiveness acceptance.

## Transactional window moves

Add a Layers move-copy transaction for a clean, shown, fully visible top layer,
unchanged dimensions and an onscreen destination. Check hardware alignment
before claiming; preserve the current placement grid. Other moves use redraw.

Snapshot old/new geometry without publishing the new position. Hit testing sees
committed old geometry until completion; queued focus/layout/model mutations
wait. Remove pointer, caret and drag-outline pixels intersecting the union of
source/destination before copying. Transient pixels must not move with content.

After successful DMA, publish bounds, rebuild visibility, keep the moved window
clean and damage only the newly exposed old area in underlying layers. Preserve
unrelated existing damage. Old minus new requires at most four rectangles.
A control reply acknowledges committed geometry, not scanout or lower-window
repair completion.

Before-launch rejection permits fallback without partial geometry changes.
Quiescent hardware failure retains old geometry and invalidates all potentially
touched areas and overlay saves. Follow normal display recovery; repaint needs
a usable display. Unquiesced failure retains the transaction/storage under the
reset-required policy. Complete or recover a launched move before queued hide,
close or further moves execute.

A successful console copy needs a placement-only rebase: change viewport offsets
and retire caret saves while preserving clean cells and presentation generation.
Ordinary redraw moves retain full invalidation. Focus/chrome changes must be
painted before a move can claim a clean source.

## Repaint work and overlay ordering

Paint disjoint frame/client backgrounds instead of a whole-window base fill
followed by a client fill. Omit a fill only where a subsequent opaque operation
provably covers those clipped pixels. Transparent text, partial glyph edges and
other styles retain necessary backgrounds. Preserve font, palette and XOR
semantics, bounded CPU preparation and current paint continuations.

Reuse current batching and parity masks. Restore caret, outline and pointer
against current underlying pixels in their established order. Any intersecting
change invalidates the corresponding saved background.

Amiga's backfill guidance similarly avoids clearing pixels immediately before
repainting them. Our retained painter supplies replacement pixels directly,
without an application callback.
[Backfill discussion](https://wiki.amigaos.net/wiki/Optimized_Window_Refreshing#Backfill_Hook)

## Optional pixel caches

Use complete client-area snapshots with retained content authoritative. Paint
frames and titles separately: a focus change must not discard an otherwise
valid cached client just because its title-bar colour changed. These are whole
rectangular surfaces rather than per-obscured-fragment allocations. They provide
some Smart Refresh benefits, without implementing full Smart Refresh or
continuously updated SuperBitMaps.

Propose two 64 KiB slots at `$50000–$5FFFF` and `$60000–$6FFFF`, subject to a
combined production/diagnostic map check. Each compact even-width 4bpp image
must fit a slot. A 320 by 160 image uses 25,600 bytes; a 528 by 184 image uses
48,576 bytes. These are raster dimensions, not outer-window sizes. A 640 by
240 image uses 76,800 bytes and does not fit. Reserve the full 131,072 bytes
including slack; introduce no general VRAM heap.

Initially cache retained-command/widget windows; exclude automatic console
capture. Capture only clean, fully visible content, with overlays removed, at
a low-priority quiescent boundary without pending input/control work. Hold a
read/snapshot scene transaction across DMA. Failed capture invalidates its slot,
not otherwise clean screen pixels. Never delay a move just to populate a cache.

Key slots by non-reused window/layer identity, content revision, client dimensions
and client appearance revision. Use cache-local coordinates. Origin changes alone
preserve validity. Content/tree/widget, font/palette and hidden client updates
invalidate before changed state can be presented. Frame-only title/focus changes
damage the frame without invalidating client pixels; a focused-widget highlight
inside the client does invalidate them. Publish validity only after completion
for matching live revisions. On revision exhaustion, disable reuse safely rather
than match an old cache.

Schedule at most one capture attempt per eligible visual revision. A busy
window may miss caching and use redraw. Choose an invalid slot first, then the
least recently used unpinned slot. Active copies pin all referenced slots.
Invalidation removes eligibility immediately, but reuse waits for DMA retirement.
Close, eviction and shutdown follow the same rule.

Restore only valid cached client pixels intersecting current visible damage
under a paint token. Partition frame/client pieces when a paint batch spans
both; retain ordinary frame painting. Use asynchronous copies and service input
between fragments. Stale, missing, oversized or evicted caches fall back to
retained painting.
Unaligned fragments also redraw; never widen a copy through an occluder.
Hardware failure follows recovery rather than assuming a healthy redraw path.

Snapshots exclude transient overlays. GEM4XE-style menu/popup save-under is a
later consumer, not new UI in this milestone. Such saves must independently
track underlying-content changes; saved screen pixels are not automatically a
current window image.

## Memory and performance boundaries

The current [VRAM map](../../../platform/altirraos/vbxe-vram.json) reserves
112,128 of 524,288 bytes, leaving 412,160 unassigned. Cache slots reduce
unassigned capacity to 281,088 bytes. This is separate from 4 MiB CPU RAM.

Target additional reserved bank-zero memory: zero fixed, root/kernel, public
Task and idle bytes, including guards, alignment and unused stack/DP capacity.
No per-window/cache stack or DP. Damage payload is at most 64 bytes per layer
before count/state; exact generated metadata deltas belong in upper RAM.
Keep the 4 KiB CPU aperture, 4 KiB command arena and worker stack reservation.
Report emitted stack high-water separately from reservation growth.

Reuse measurements with matching inputs; collect only missing before/after
move, sparse-damage, overdraw and cache cases. Separate preparation CPU excluding
IRQ/off-Task time, upload/submission, DMA, completion service and repair scanout.
Count commands, launches, copied/filled bytes, misses and damage inflation.
Include capture cost, not just warm restore speed.

Use optimized builds for the functional, failure, pixel, lifecycle and timing
scenes, including the packaged preview. Keep small raw/optimized probes for
changed generated layouts, Action!/C bridges and compiler context behavior;
use a minimal both-mode reproducer for suspected compiler defects. Do not repeat
the desktop scenarios in raw mode by default. Follow the
[build-mode policy](../../contributing/testing.md#build-modes).

Existing [desktop timing targets](desktop-implementation-plan.md#timing-acceptance-and-evidence)
remain unchanged and open where missed. Correct pixels and lower CPU cost do
not establish responsiveness. Use matched pins/configuration and frame-phase
cohorts, independent pixel comparisons and explicit qualification scope.

## Deferred work

Partially obscured scrolling requires valid source and destination pixels.
Destination clipping alone can copy another window's pixels. Fragmented copies
also need globally safe ordering or scratch storage. Keep retained redraw until
a separate planner proves both properties.
[Amiga scrolling damage](https://wiki.amigaos.net/wiki/Optimized_Window_Refreshing#Scrolling_Your_Life_Away)

Also defer live window dragging, dynamic per-obscured-fragment backing,
general offscreen VDI/widget rendering, more layers, transparency, resizing,
scanout synchronization, a hardware pointer, arbitrary asynchronous raw lists
and a full-desktop compositor.
