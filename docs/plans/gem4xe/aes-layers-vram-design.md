# AES and Layers cooperation for VRAM caching

[GEM designs](README.md) · [Implementation plan](aes-layers-vram-plan.md) ·
[Layers](../../reference/layers.md) ·
[AES](../../reference/aes.md) · [Display](../../reference/display.md)

Status: implemented at the development tier, 2026-10-13; optional copied AES
moves remain disabled and latency acceptance remains open. See the
[execution record](../../history/aes-layers-vram.md) for measured results.
The design joins AES repaint tracking and Layers pixel reuse: menu backgrounds,
popup images and completed client snapshots, using ordinary GEM calls,
caller-local drawing and the existing presenter Task.

This extends the [desktop rendering design](desktop-rendering-design.md) and
the [menu latency work](../../history/menu-latency.md). It proposes changes to
their cache ownership and external-paint contracts. The reference documents
describe the implemented contracts; the existing-boundary discussion below
describes the pre-AV1 baseline.

## Existing boundary and the missing information

Layers owns geometry, stacking, visible regions, damage and scene transactions.
AES window management runs in the presenter, creates an external-painted layer
for each application window, and publishes work-area visibility when granting
`BEG_UPDATE`. Applications draw through their local VDI/object bindings. They
do not traverse or mutate the live scene.

The presenter paints frames and hands work-area damage to AES as `WM_REDRAW`.
`FinishHandoff` retires manager damage without asserting that the application
painted it. Consequently external layers cannot currently use `BeginRead`,
copied moves or window snapshots. `END_UPDATE` releases ownership; it is not a
whole-window repaint acknowledgement.

The existing [DESKCACHE](../../../lib/desktop/deskcache.act) holds two 64 KiB
client snapshots for presenter-owned content. It excludes AES and console
windows. Menus use a reusable 640 by 16 scratch strip but retain neither their
rendered pixels nor the background they cover. The current
[VRAM map](../../../platform/altirraos/vbxe-vram.json) reserves 243,200 of
524,288 bytes, leaving 281,088 bytes unassigned before diagnostic exclusions.

The missing information is whether pixels are available, which application
redraws remain outstanding, and what changes invalidate saved pixels. Adding
VRAM buffers alone would not establish that information.

## Ownership

| Component | Responsibility |
| --- | --- |
| Layers | Exposure and content damage, pending external repaint, cache identities and validity, visibility-safe restoration and transaction lifetime. |
| AES and its caller bindings | Window ownership, update arbitration, redraw delivery, content-change and completed-paint reports. |
| Presenter | Schedule capture/restore/render work, draw frames and menus, remove overlays and choose which useful cache to populate. |
| Display/VBXE | Fixed surfaces, address/pitch construction, asynchronous copies, completion and fault recovery. |
| Application | Maintain its model and obey the drawing/update contract. |

Move the reusable metadata/policy out of `DESKCACHE` into a small Layers cache
companion. Keep Layers free of VBXE register accesses, application callbacks,
Task pointers and waits. A cache decision produces geometry and a surface-slot
identity; the presenter submits the transfer and reports completion. This
continues the Amiga-inspired separation adopted by the earlier rendering design,
without introducing a general compositor or bitmap allocator.

Use existing direct calls inside the presenter and existing application update
exchanges. No new worker, kernel selector, message class or per-draw RPC is
needed. Caller bindings accumulate reports in upper RAM; only the presenter
mutates the scene. Generate changed shared layouts and rebuild all clients.

## Repaint state

Keep three facts distinct:

- **Exposure:** a region needs visible repair because its coverage changed.
  This alone does not invalidate a layer-local image.
- **Content change:** previously saved pixels may no longer represent the
  layer. Record this even when the changed region is covered or hidden.
- **Completed painting:** a renderer has finished a specified region for the
  current window lifetime and repaint generation. Hardware completion precedes
  publication of that fact.

External damage remains pending after `WM_REDRAW` delivery, independently of
the manager's frame transaction. Pending application work holds no scene token
and does not keep the presenter spinning or send duplicate messages every turn.
An application that delays drawing cannot stall other windows.

The internal operations are conceptually `Expose`, `ContentChanged` and
`Painted`; their final names/layouts belong in the implementation plan. Use
bounded rectangles and the existing visibility machinery. Changed regions may
collapse to a conservative bounding rectangle. Completed regions must never
be expanded across unpainted gaps. If their bounded storage overflows, retain
the remaining repaint obligation and use the normal redraw path.

Closing retires the layer identity and its caches. Resizing invalidates client
pixels. A position-only change preserves eligible layer-local pixels but
invalidates a saved screen background whose composition changed. Frame-only
title/focus changes preserve client images. Client focus styling, menu state,
fonts or palette changes invalidate the affected images. Revisions must not
wrap into a previously valid identity.

## AES update and completion reporting

Use the outermost `BEG_UPDATE` and `END_UPDATE` as the publication boundaries.
Nesting does not publish a partly finished repaint. Preserve the current update
lock: it waits for existing display/scene work and excludes conflicting drawing
while the application owns it. It does not stop unrelated Tasks.

At acquisition, make saved content intersecting the owner's windows ineligible
for restoration during that update. The first implementation may conservatively
invalidate those windows' cached content and any intersecting menu background.
This catches a fully covered Counter update even if the application's visible
rectangle loop executes zero drawing calls. It also produces harmless misses
for read-only updates; avoid a more elaborate classification in the first slice.

VDI and object bindings can accumulate modified bounds and a sticky drawing
failure once per public drawing call, before visibility clipping. Do not scan
the scene, union large regions or report each glyph/blitter record. These
reports help narrow subsequent invalidation and window-cache maintenance; they
are not evidence that every pixel in an object's bounding box was painted.

Provide a small internal redraw helper for the shipped applications and shared
dialog code to report completed regions. The renderer reports a region only
after reconstructing its background/content and completing its drawing calls.
Associate the report with the repaint generation observed at update acquisition;
an old acknowledgement cannot clear newer damage. Combine reports with the
existing outermost END exchange. A failure prevents the affected completion
from being acknowledged, even if a later call resets the ordinary diagnostic.

Use this helper in the common redraw paths for Files/desktop, Counter, Text and
dialogs as they become cache consumers. The application-specific drawing code
continues to use ordinary GEM calls. The helper is optional port glue, not a
new mandatory GEM opcode or an inference that exhausting `WF_NEXTXYWH` proves
painting. Arbitrary GEM callers retain correct `WM_REDRAW` behavior without it;
their unacknowledged regions remain ineligible for fresh capture.

### Hidden model changes

An application can change its model without any AES/VDI call. Neither Layers
nor the bindings can observe that. A completed image is therefore a record of
painted pixels, not an unrestricted promise about future application state.

Preserve conventional exposure `WM_REDRAW` for external windows, including
regions restored from a cache. A valid saved image can repair the screen
immediately while that request is pending; it does not discharge the request.
Known-stale regions are never restored. Applications with delayed redraw may
temporarily show their last completed image, but must receive the exposure
event needed to reconstruct their current model. Do not claim final repaint
completion at the earlier cache-copy completion.

Restoration must not be followed by a presenter placeholder clear of the same
client area. The app's subsequent redraw may still cost time or show intermediate
drawing; caching alone does not remove that work. Measure immediate visual
repair and final redraw separately, including any flicker during the latter.

Suppressing that exposure event would require the application to declare all
logical changes, including changes made while completely covered. That stronger
application contract is outside this design. Completion helpers alone do not
enable it. This preserves GEM source compatibility and prevents an invisible
Counter update from being silently lost.

## Menu background restoration

Reserve one screen-background slot for the single open dropdown. Its contents
can include portions of several windows, frames and desktop background. It is
not the menu layer's own client image.

Before showing a popup, intersect its footprint with the scene and capture only
when all source pixels in that footprint are known complete. Remove pointer,
caret and drag overlays. A small scene-read transaction holds geometry and
pixel ownership stable across the copy; the existing single-layer `BeginRead`
cannot by itself describe this composite source. Extend that transaction family
with a bounded scene-rectangle capture, rather than creating an independent
locking mechanism. Pin the destination until DMA retires.

Publish the popup after capture completes. If the source is pending or invalid,
open through the existing drawing path without waiting for an application to
make it cacheable. Cap capture work through the existing copy machinery and
measure its contribution to cold-open latency.

For the first implementation, any intersecting underlying content change or
relevant window lifetime/geometry change invalidates the entire saved rectangle.
The popup's own show/highlight/hide operations do not invalidate its saved
background. Pointer motion also does not invalidate it: overlays are excluded
and handled separately. Nonintersecting updates can continue without losing the
save. No allocation of per-occluded-fragment buffers is required.

On dismissal, admit hide and restore as one coordinated scene transaction.
Intersect the saved region with the resulting visibility and commit restored
presentation damage only after DMA completion. Draw/requeue the remainder;
preserve external application exposure messages as above. A Layers geometry
rebuild must not blindly re-damage pixels whose restoration just completed.
Transaction failure leaves repair damage pending.

Heading switches restore the old footprint before saving the new one. Never
capture pixels containing the previous popup as the new background. If either
source is incomplete, fall back without requiring all underlying applications
to finish first. Queued close, owner exit and menu replacement retire through
the same pinned-source rules as window caches.

## Rendered popup images

Use two small fixed slots for recently rendered popup images. Key an image by
menu owner/lifetime, tree/content revision, dimensions, appearance and selected
state. Native menus use their own content revision. Preserve the existing
contract for live trees and menu mutation APIs; do not hash/revalidate every
string during painting.

Capture a completed popup opportunistically after the first visible paint.
Do not render twice or perform speculative captures ahead of pending input.
A matching image can be blitted on reopening or a heading switch. Never reuse
a cached selected row as an unselected row: restore only matching state, or
reuse known unchanged rows and draw the changed rows through the existing path.
Disabled/checked entries retain their ordinary renderer semantics.

An oversized popup or a cache miss uses current strip rendering. This is a
bounded cache of rendered results; it does not require an offscreen version of
every VDI operation. Eagerly rendering all menus or all highlight combinations
is outside the initial scope. Warm opening and highlight measurements must be
reported separately from cold opening.

## Window images and maintenance

Replace the two 64 KiB slots with two fixed 75 KiB slots. Each can hold a packed
640 by 240 image, removing the current full-screen-size exclusion. Continue
to cache client pixels separately from frame decoration and retain them in
local coordinates. Use invalid slots first, then the least recently used
unpinned slot. A background save and popup image have dedicated slots, so
opening a menu does not evict a useful window image.

Admit AES windows only where completed-paint records establish valid source
pixels. A first complete, fully visible client can seed a snapshot. Subsequent
small, fully completed visible updates can patch an existing snapshot with a
screen-to-VRAM copy; unavailable or hidden changes invalidate it. Start with
whole-slot invalidation on uncertainty. Never fill a hole from pixels belonging
to an occluding window.

Patching requires the later, more precise update bookkeeping to retain the
previous image as a base while marking its changed region unusable. The first
whole-slot-invalidation slice cannot recover a whole image from a partial
repaint acknowledgement. If the required repair region is not completely
painted and copied, keep the slot invalid.

Schedule maintenance after pending input and visible repair. Coalesce changed
rectangles within an update and skip a capture if a newer update supersedes it.
Do not recapture an entire large window for every digit change. An application
whose image changes too frequently may remain uncached. Retained native windows
and eligible AES clients use the same slot lifecycle after migration; remove
the old independent `DESKCACHE` policy.

The console keeps its retained cells and existing scroll path. It does not get
a permanent client snapshot in this work. Its visible pixels may participate
in a menu background save; output/scrolling invalidates intersecting saves.
Copied AES moves become eligible only after the relevant pixel-completion rules
are implemented and tested. A flag declaring all external layers clean is not
an acceptable shortcut.

## Proposed VRAM budget

All addresses below are VBXE-private byte addresses, unrelated to CPU banks.
The production map changes during implementation; this note does not reserve
the proposed ranges yet.

| Use | Inclusive range | Reserved bytes |
| --- | --- | ---: |
| Screen | `$00000–$12BFF` | 76,800 |
| Existing widget strip | `$12C00–$13FFF` | 5,120 |
| One menu background | `$14000–$26BFF` | 76,800 |
| Popup image 0 | `$27000–$2AFFF` | 16,384 |
| Popup image 1 | `$2B000–$2EFFF` | 16,384 |
| Existing XDL, fonts, glyph scratch, cursor and BCB | Existing mapped ranges | 30,208 |
| Client image 0 | `$50000–$62BFF` | 76,800 |
| Client image 1 | `$62C00–$757FF` | 76,800 |
| **Total production reservation** | | **375,296** |

This increases production reservation by **132,096 bytes**, from about 46% to
72% of 512 KiB, and leaves **148,992 bytes** unassigned, including alignment gaps.
The existing 32-byte diagnostic at `$3FFF0–$4000F` stays outside every production
range, leaving 148,960 bytes after that exclusion. A popup slot holds a compact
image of up to 32,768 pixels; larger menus still work through ordinary painting.
Client and background surfaces can cross 64 KiB boundaries; qualify those
descriptors explicitly rather than treating CPU bank boundaries as VRAM limits.

Keep even-X/even-width admission for the first copy consumer. Unaligned regions
redraw; do not widen a restoration over a neighboring owner to gain alignment.
Masked edge copying can follow if measurements justify it. No new CPU aperture,
font/glyph arena or staging page is needed.

Target **0 fixed, 0 per public Task and 0 idle reserved bank-zero bytes added**,
including guards, alignment and unused stack/DP capacity. Budget at most 2 KiB
additional fixed upper-RAM metadata and 256 upper-RAM bytes per registered AES
client for bounded journals; determine exact generated sizes in the plan.
Reuse existing scene work regions and rectangle operations. Do not place
region arrays on Task stacks. Any required stack growth must be measured and
reported explicitly instead of being hidden within the zero-delta target.

## Completion, cost and failure rules

Cache states need only distinguish invalid, capture pending, valid and pinned
for restore. Invalidation removes eligibility immediately; it does not release
storage still referenced by DMA. Publish validity only for matching lifetime,
dimensions and revision after successful completion. Remove overlays before
capture/restore and reestablish them after completion through existing paths.

Use the display driver's one active transfer, completion signal, deadline and
quiescence rules. A completed prefix followed by failure leaves the destination
dirty. Quiescent failure releases pins and follows normal display recovery;
reset-required failure retains the referenced storage and transaction. No new
IRQ/NMI policy is introduced.

Cache hits should cost bounded metadata checks and blits. Keep ordinary input
service between copy/render units and the current bounded menu precedence.
Establish surfaces at initialization and trust internal producers; add no
per-glyph geometry scans, repeated request validation or new arithmetic-heavy
cache addressing. Drawing reports belong at public-call/update granularity.

## Implementation order and acceptance

The [AV1–AV6 implementation plan](aes-layers-vram-plan.md) expands this joint
design into executable slices in this order:

1. AES/Layers pending repaint and completion bookkeeping, with ordinary drawing
   preserved; integrate a shared completion helper and a focused application.
2. Composite menu background capture, invalidation and coordinated dismissal
   restore, with redraw fallback and normal external exposure notification.
3. Rendered popup reuse and migration/enlargement of window cache slots; extend
   completion integration to the shipped desktop applications.
4. Measure useful incremental window maintenance and qualify eligible copied
   moves through focused development cases before enabling them.

The implementation plan must freeze comparison cases and numeric gates before
tuning. Use the existing [menu measurement tool](../../../tools/measure_menu_feedback.py)
and [recorded baseline](../../history/menu-latency.md), on the same pinned
compiler, ROM, emulator configuration and workload. Measure cold/warm opening,
heading switching, highlight and dismissal. Separate first correct restored
pixels from final application repaint, and report median/p95 plus sample
granularity, cache hits/misses and capture cost. Restoring an old Counter value
does not finish a current-model latency measurement.

Require exact pixels and eventual latest-model repaint with Counter and shell
output, including fully covered updates, changes outside the saved area,
multiple windows owned by one app, nested updates, a delayed redraw consumer,
new damage arriving after acknowledgement was prepared, menu replacement/exit,
rapid heading switches, resize/move, odd edges, oversized popups, eviction and
transfer faults. Include an application that changes hidden state without a
drawing call: its later exposure must still deliver `WM_REDRAW`. Check source
and destination guards, overlay removal, pinned lifetimes and EXIT cleanup.

Use development-tier host checks and focused optimized emitted-code tests;
add small raw/optimized probes for changed Action!/C layouts and publication
boundaries. Demo refreshes use `tools/build_demo.py`, OF816, the pinned ROM,
matching disks and the existing five-second autoboot. Report bank-zero and
upper-RAM/VRAM deltas per slice. No compiler-wide test run, full release matrix
or hardware qualification follows automatically from this design.
