# Desktop rendering implementation plan

[Design note](desktop-rendering-design.md) · [GEM plans](README.md) ·
[Roadmap](../../roadmap.md) · [Testing policy](../../contributing/testing.md)

Status: DR0–DR3 implemented, 2026-10-05; DR4–DR7 remain pending.
See the [implementation record](../../history/desktop-rendering.md). Implement DR0–DR7 in order, keeping each slice executable and committing
it with focused development evidence. AW5–AW6 remain paused and are not
prerequisites; use existing graphical/widget fixtures for this work.

The result is the current desktop with smaller repairs, IRQ-completed window
copies and bounded optional pixel caches. Retained content, one presenter,
current placement/input policy and fault quiescence remain the foundation.

## Scope and interfaces

Adopt eight damage rectangles per layer with streamed visibility intersections,
one typed asynchronous copy sharing scroll completion, transactional moves for
clean top windows, fewer background passes, and two 64 KiB VRAM snapshot slots
for retained-command/widget client areas, with separately painted frames. Keep
obscured scrolling on redraw. Menus, live dragging, extra Tasks and a general
compositor remain outside this plan.

The design defines success/failure behavior. New API names below are proposed
until their implementing slice freezes declarations and migrates all callers.
Maintain one current generated layout and completion implementation. Do not
retain old APIs or production compatibility modes. Current references remain
authoritative before each change lands.

## Build modes

Use optimized builds for all routine functional, failure, pixel, integration,
input and performance cases, including DR0 baselines and the DR7 preview. Keep
small probes in both modes only for changed compiler-facing boundaries:

| Slice | Focused raw and optimized coverage |
| --- | --- |
| DR1 | New Layers record layout/access and paint-advance call boundary. |
| DR2 | Changed copy/completion descriptors and Action!/C bridge, including a bounded completion/context-restoration case. |
| DR3 | New move-transaction layout/access and call/return checks. |
| DR5 | New shared snapshot records and any changed native/C boundary. |

All broader geometry, DMA failure, lifecycle, desktop/widget pixel and loaded
input scenarios run optimized. DR4 and DR6 add raw coverage only if they expose
a specific compiler-facing change or suspected compiler defect. Run its smallest
reproducer in both modes rather than duplicating the slice's scene matrix.
Retain all guard, context, ownership and cleanup assertions in optimized tests.
Follow the [build-mode policy](../../contributing/testing.md#build-modes).

## DR0 Record inputs and add focused observations

Preserve the current executable. Record source revision/local overrides,
compiler/Calypsi pins, ROM/emulator hashes, PAL and 4 MiB configuration, 4 kHz
ST capture, sensitivity and maps. Reuse matching
[desktop](../../history/desktop.md), [mouse](../../history/mouse-performance.md)
and [IRQ](../../history/blitter-completion-irqs.md) evidence. Run only missing
comparable cases; there is no new broad baseline matrix.

Extend `tools/measure_desktop.py`, `tools/desktop_oracle.py` and focused desktop
fixtures, or add a small rendering runner. Observe clean top-window moves in
all directions, overlapping/disjoint destinations, screen edges, separated
widget/command damage, complete repaint and exposure with two independent
clients. Include pointer/key activity, console output and cold physical I/O.

Count copied/filled bytes, lists and launches; separate setup CPU, upload,
actual DMA, completion service and final repair/scanout. Preserve raw samples
and stimulus ordering. Check an observer-disabled production control whenever
instrumentation changes executable code. Never infer DMA completion from the
asynchronous function return.

Freeze eight-damage capacity and cache addresses against generated sizes and
the combined VRAM map. Check stack headroom and list durations before selecting
any additional continuation limit. Comparison switches may exist in test builds
only, not as production old-ABI modes.

Exit: reproducible missing baselines, independent final pixels, recorded hashes
and memory reservations. Instrumentation leaves production behavior unchanged.
Expected bank-zero and VRAM reservation delta: 0.

## DR1 Retain bounded damage and stream paint batches

Update `abi/layers.json`, `tools/generate_layers.py`, `layers.act` and
`layers-update.inc`. Keep eight damage slots plus count/traversal state in upper
RAM. Apply containment/exact-union merging; at overflow retain all damage in
one bound. Keep visibility computation and its 96-entry work buffer unchanged.

BeginPaint captures damage. Add explicit advance to the next nonempty clipped
batch. PaintRegion stays stable until advance/finish. Reject Finish-success
before traversal exhaustion without releasing the token. Failure retains the
original damage. Empty/covered work must not cause a runnable spin.

Migrate `deskpaint`, `deskwidgets`, direct console drawing and every fixture
using BeginPaint/PaintRegion/Finish in the same slice. Rebuild all callers.
Document visible acknowledgement and the requirement that later exposure marks
new damage; no old consumer may silently stop after the first batch.

Validation: host oracle plus optimized `tools/test_layers.py` and focused
desktop/widget presentation. Use a small both-mode record/access and paint-call
probe as specified above. Cover eight separated rectangles, overflow on a
ninth, containment, overlaps, hidden work, four occluders, more than 96 total
fragments across batches, early Finish, retry, stale tokens and mutation rejection.
Compare union coverage against an independent pixel-set model.

Exit: no lost damage, out-of-visibility writes or unchecked product capacity;
all consumers migrated. Record exact generated upper-RAM growth. Expected
reserved bank-zero and VRAM delta: 0.

## DR2 Share asynchronous completion and add typed copies

Refactor the active-operation state in `platform/altirraos/vbxe.c` and its
declarations. Add `VbxeCopyStart` and common completion querying; migrate the
scroll bridge, console and tests. Preserve copy-plus-fill and one-launch scrolling.

Reuse complete copy extent/signed-step checks. Initially cap copies at 640 by
240 pixels/76,800 bytes with even X/width. Define an empty result without an
ID. Validate descriptors and output storage before mutation, then snapshot
accepted arguments. Different surface pitches require disjoint extents;
equal-pitch overlap preserves bytes in all directions.

Reuse the completion signal, non-reused IDs, original deadline, IRQ and timeout
recovery. Add no separate queue, arena or watchdog. BUSY preserves the active
operation and new output. Synchronous access and Close still fence DMA.
Unquiesced failure retains all storage. Preserve register/DP restoration and
native/emulation interrupt routing.

Validation: extend emitted `bitmap_copy.c`/`bitmap_scroll.c` and
`tools/test_gem_display.py`, with selected `tools/test_blitter_irq.py` cases in
optimized mode. Add the small both-mode descriptor/bridge/context probe; do not
repeat the complete DMA fault matrix in raw mode. Cover overlap directions,
zero-valued pixels, empty/max geometry, pitches, VRAM wrap/arena exclusion,
descriptors changed after return,
BUSY/stale IDs, reopen/exhaustion, completion-before-Wait, coalesced wakes,
lost IRQ, wrap and quiescent/reset-required failures. Add focused NMI/SIO cases.

Exit: exact pixels and one launch for an admitted copy; existing scrolling and
lifetime checks pass with one completion implementation. Record setup, DMA and
completion costs separately. Expected bank-zero/VRAM reservation delta: 0;
record upper-RAM driver-state changes.

## DR3 Copy eligible window moves transactionally

Add generated Layers move-copy state for old/new geometry. Require a clean,
shown, fully visible top layer with unchanged dimensions. Keep committed geometry
unchanged until success; calculate old-minus-new exposure while preserving other
damage. Hold the scene through DMA and metadata commit.

Integrate one presenter continuation for desktop MOVE and drag release through
`deskcore`, `deskdrag`, `deskpaint` and the shared drawing bridge. Check hardware
alignment before claiming and remove intersecting overlays before copying.
Dirty/covered/unsupported cases use ordinary Move and retained repair. A launched
move survives queued HIDE/CLOSE, further moves and shutdown until retirement.
Replies acknowledge committed geometry, not scanout.

After successful DMA, publish bounds/rebuild visibility, keep copied content
clean and invalidate only exposed old pixels below it. After quiescent failure,
keep old geometry, invalidate touched areas and follow display recovery.
Never release a token/surface following unquiesced failure.

Add a placement-only console rebase preserving circular cells, dirtiness and
presentation generation while updating offsets and retiring caret saves.
`DESKPAINT.Sync` must not then dirty every cell. Focus/chrome changes continue
to invalidate normally and prevent clean-copy admission until painted.

Validation: optimized Layers, presentation and drag cases, with a small
both-mode move-layout/call probe. Exercise programmatic and
drag moves in all directions, overlapping/disjoint locations, screen edges,
console/command/widget windows, dirty/covered rejection, crossing overlays,
queued focus/close, source loss and transfer faults. Assert old geometry during
flight, atomic commit, exact affected/unaffected pixels, consistent console
output and no content replay within the copied window.

Exit: eligible window pixels are reused and exposure is repaired. Compare repair
and input delay with DR0. If a full rectangle misses latency targets, record it
and add an overlap-safe continuation slice before declaring them achieved.
Expected bank-zero/VRAM reservation delta: 0; report transaction-state growth.

## DR4 Remove redundant background passes

Refactor `DESKPAINT.PaintStrip` into disjoint clipped frame/client backgrounds.
Omit other fills only where the following opaque draw proves complete coverage.
Keep donor extraction intact and change generated donor code through patches
or its generator. Avoid unrelated formatting or widget replacement work.

Preserve replacement/transparent text, partial glyphs, disabled styles, XOR and
odd-nibble edges. Keep bounded preparation and current four-command or sixteen-
scanline continuations until measured evidence justifies changing them. Reuse batching;
do not make synchronous public operations return early.

Validation: optimized desktop/widget pixels for sparse and full repaint,
first paint, shortened labels, focus/title changes, overlapping damage batches,
empty clients and glyph clipping. Compare final bytes with independent models
and count fills, copied bytes and launches.

Exit: eliminate the known duplicate strip/client pass with exact pixels and
lower work for the affected scene. Report setup-dominated cases honestly.
Expected bank-zero/VRAM reservation delta: 0.

## DR5 Add bounded snapshots and lifetime checks

Reserve two 64 KiB cache slots in `platform/altirraos/vbxe-vram.json` at the
proposed addresses after checking production and diagnostic regions. Add
upper-RAM metadata for surfaces, identity/revisions, validity, pin state and
replacement order. Generate shared layouts; do not duplicate literal maps.

Add a Layers read/snapshot transaction for clean, fully visible content. It
stabilizes geometry/model state without acknowledging damage. Capture through
DR2 with overlays removed; publish validity only after matching completion.
Failed capture retires the slot without marking any unfinished paint complete
or invalidating clean screen pixels solely because the cache destination failed.

Admit compact even-width images fitting one slot. Choose invalid slots first,
then least-recently-used unpinned storage. Close/eviction/shutdown must retire
active copies before reuse, and unquiesced faults retain referenced storage.
Keep general offscreen rendering unsupported.

Validation: optimized emitted capture/restore with byte comparison and slot
canaries, plus small both-mode shared-layout/bridge checks where changed.
Cover maximum fitting image, oversized rejection, overlays, epoch mismatch,
failed capture, pinning/eviction, close during DMA, reopen and exhaustion. The
528 by 184 raster fixture fits; a 640 by 240 snapshot must fall back. Check
diagnostic and map separation.

Exit: a bounded snapshot facility, not yet an application API. Bank-zero delta:
0. VRAM reservation delta: +131,072 bytes including slack; unassigned capacity:
281,088 bytes. Record metadata growth and stack usage. Borrow no unmapped VRAM.

## DR6 Restore valid snapshots during exposure repair

Integrate cache policy for retained-command/widget windows. Schedule at most
one attempt per eligible visual revision, while clean/fully visible and without
pending input/control work. Do not delay a requested move for capture. Leave
the console's model/scroll paths uncached.

Centralize invalidation for client content/tree/widget changes, interaction
state and font/palette changes, including hidden updates. Frame-only focus/title
changes repaint the frame while preserving client cache validity. A widget focus
highlight changes client pixels and invalidates them. Position alone preserves
cache-local pixels when dimensions/revisions match. Retirement cannot leave a
cache eligible for a reused identity.

Select a valid client cache or retained drawing at paint time. Partition paint
fragments spanning frame and client, retaining frame drawing. Copy current
visible client damage only, keeping the token across asynchronous fragments.
Service input and pointer at quiescent boundaries. Unaligned fragments redraw without widening
over an occluder. Pin sources throughout their DMA; a miss is a normal fallback,
while a hardware fault follows recovery.

Exercise existing independent-client/widget fixtures for cover/uncover, move and
raise. This slice adds no menu, popup, task bar or AW5 control panel. Future
transient saves require separate underlying-content validity.

Validation: optimized exact scenes with cache availability and deterministic
test-only forced misses, against the same independent oracle. Cover hidden
updates, frame-only focus changes that retain a cache hit, client focus changes
that invalidate it, two-slot pressure, retirement/reuse, odd clips, fragmented
visibility, repeated move/raise, input during capture/restore and physical I/O.
Include capture cost and misses in timing, not just warm restoration. Valid
aligned cache fragments must avoid glyph replay; every rejected cache must
produce the same final pixels through fallback.

Exit: faster repeated static exposure without stale pixels, starvation or hidden
allocation growth. Record cases where caching costs more and retain the bounded
policy rather than claiming universal improvement. Expected further bank-zero
and VRAM reservation delta: 0.

## DR7 Measure the combined desktop and refresh the preview

Run matched optimized DR0 scenes with the final optimized code. Report median,
p95, maximum, counts and raw samples for pointer/button, short echo, move-release repair, setup CPU
and DMA/completion. Use at least 100 qualifying motion samples and 30 button
events per cohort with varied frame phase, following the existing desktop plan.
Reuse completed unrelated matrices.

Cover idle, scrolling, cold physical I/O and two-client scenes. Keep existing
targets: pointer/outline p95 at most 40 ms idle and 60 ms loaded, maxima 60/100 ms;
button consumption maxima 40/100 ms; move release to repair at most 250 ms in
the defined scenes. Short echo keeps the matching-baseline 10% p95 and one-PAL-
frame maximum regression allowance. Preserve the less-than-1-ms sampling-gap
gate for the supported stimulus.

Separate correctness completion from timing acceptance. Investigate regressions
by stage; never relax limits, discard samples or compare warm caches against
unrelated cold input. Record open targets and necessary follow-up work before
marking performance accepted.

Update Layers/display/desktop references, ABI descriptions, VRAM commentary and
history/indexes. Retire stale polling-only and old-reservation statements in
touched adapter notes. Put durable summaries in `docs/development/`, narrative
in `docs/history/` and large traces/intermediates in `build/`.

Refresh the optional desktop preview through `tools/build_demo.py`. Include
OF816, matching system disk, pinned ROM and notices. Keep the five-second
autoboot into the standard shell/prime demo. Package only boot files, short
guide, notices and checksums in `exec816-demo.zip`. Execute the extracted
package's desktop walkthrough, shell/disk commands and EXIT/ownership checks
using matching media. Release publication is separate.

Exit: documented development evidence and a checked local preview with actual
timing status. This does not qualify physical hardware or the whole hosted
system. Compare final memory with DR0, not an old compact-stack baseline.
Expected reserved bank-zero delta: 0; cache VRAM delta remains +131,072 bytes.

## Validation and memory rules

Use the [development tier](../../contributing/testing.md): host checks and
focused optimized emitted tests for changed behavior, with the small both-mode
probes in the build-mode table. Add selected deeper IRQ/NMI, SIO, retention and
fault cases when those boundaries change; these use optimized builds unless a
specific compiler/context regression needs raw comparison. Preserve
guard, register/DP restoration, OS coexistence and bounded-completion checks.
Full release matrices belong to an explicit release/qualification task.

Follow the [platform budget](../../reference/platform.md#bank-zero-memory-budget)
and generated maps. Report fixed, root/kernel, each public Task and idle
reserved bank-zero deltas, including zero, guards, alignment and spare capacity.
New per-window/cache stack or DP cost is zero. Report upper-RAM records, full
VRAM reservations and stack high-water separately. Rebuild callers after ABI
changes; compiler defects belong in actionc with focused regressions.

The design and plan themselves reserve no memory. Slice records identify the
actual executed checks and memory changes.
