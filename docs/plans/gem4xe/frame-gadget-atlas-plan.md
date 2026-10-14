# Window gadget atlas implementation plan

[GEM plans](README.md) · [Roadmap](../../roadmap.md) ·
[Frame measurements](../../history/window-frame-exposure.md) ·
[Response follow-up](window-menu-response-plan.md) ·
[Desktop contract](../../reference/desktop.md) ·
[VRAM map](../../../platform/altirraos/vbxe-vram.json)

Status: GAT1–GAT3 implemented and development-checked; GAT4 pending. See the
[combined development record](../../history/window-menu-response.md).

Render fixed window gadgets from a small permanent VRAM atlas, as we already
do with font glyphs. Replace repeated construction of tiny rectangles with
clipped atlas copies inside the existing frame batches. Preserve the current
pixels, dimensions, hit targets and interaction behavior.

## Scope and starting point

The frame renderer already draws through VBXE. Its fixed marks are still
procedural: close and full-size marks each issue fourteen tiny fills; arrows,
iconify and resize marks add further fills. Each surviving fill builds one or
more records, including extra operations at packed-pixel edges. The atlas
targets that CPU work and command traffic.

The title pattern already has a compact implementation: a strided constant
fill writes alternating pixels on alternate scanlines, with masked edges when
clipped. Keep `GemFramePattern`. Keep text on the font atlas and variable-sized
borders, separators, scrollbar tracks and thumbs on the solid-fill path.

Include seven fixed images: close, full-size, iconify, up arrow, down arrow,
resize mark and the miniature window drawn on an iconified tile. Store only
the existing image/state combinations. Current focus-dependent text, title
pattern and separator colour remain outside the images; do not invent pressed,
disabled or theme variants that the presenter does not currently display.

This plan changes the renderer, not the AES/application interfaces or scheduling.
Directory enumeration, the provisional `Files` title, control-message overhead,
desktop file icons and general AES object caching are separate follow-ups.
Keep the four initial cold-frame batches and current warm body restoration.
The [window and menu response plan](window-menu-response-plan.md) coordinates
the title/control changes with GAT1–GAT3 and shares the final GAT4 delivery.

## Representation and memory

Use one small source file of fixed pixel rows plus a build-time packer. Generate
packed hardware pixels, even/odd placement variants and constant descriptors
with offsets, dimensions and source pitch. Keep palette indices consistent with
the existing GEM logical-to-hardware mapping; palette RGB changes do not require
new pixel data. No runtime rasterization, asset allocation, lookup hash or atlas
eviction is needed.

Use opaque white-backed image rectangles where the current frame already
provides white. Keep their rectangles inside the gadget interior, leaving
shared borders and focus-dependent separators to the frame. In particular,
an atlas copy must not erase the active-title pattern, an adjoining gadget or
a dynamic scrollbar thumb. Preserve the current paint order where these meet.

Proposed storage is one 4 KiB VRAM page at `$39000–$39FFF`, currently unassigned
and separate from the command arena and diagnostic cross-page transfer. Seven
images, two X phases and twelve rows at a sixteen-byte source pitch occupy
2,688 bytes including slot padding. The shifted sixteen-pixel image needs at
most nine bytes per row, so this pitch admits both phases without special row
arithmetic. Descriptors specify the actual image extent, not the padded slot.

During implementation add `frame_gadgets` to the machine-readable VRAM map and
derive private constants from it. Reserved VRAM grows by **4,096 bytes**, including
unused page capacity; other reservations stay in place. The current map totals
would become 420,352 reserved and 103,936 unassigned bytes. Do not copy the older
totals in adapter prose without reconciling them with the map.

Packed source data and descriptors live in upper image memory. Report their
actual linked size and any padding. Reuse the existing upload path, command
arena and widget scratch; add no new CPU staging page or per-window record.
Every slice targets **0 additional fixed, per-public-Task and idle bank-zero
bytes**, including guards, alignment and unused reserved capacity. No stack or
direct-page enlargement is planned.

## GAT1 Install immutable gadget images

Primary files: a small asset definition/packer beside the desktop renderer,
`tools/build_bitmap_console.py`, `ports/gem4xe/adapter/gem-vbxe.c` and the VRAM map.

1. Transcribe the seven existing marks without changing their design. Generate
   both packed phases and descriptors; include generated inputs in build
   provenance and verify geometry/palette/storage consistency at build time.
2. Upload the used atlas bytes once during a successful `GemDrawingOpen`, after
   acquiring the display and before enabling presentation. Reuse
   `VbxeOwnerWrite`; frame painting must perform no atlas upload or VRAM readback.
3. Re-upload on each new display session. Follow the existing open-failure and
   close/recovery path if upload fails; do not publish a usable display with
   incomplete images or add a second lifetime protocol.
4. Keep procedural drawing until its callers migrate in the following slices.
   No public API or native/C packet layout changes are required.

Focused checks: deterministic asset generation, independent expected pixels,
disjoint VRAM ranges and capacity; one optimized open/readback/close/reopen case
using the existing display fixture. Verify that writing the atlas leaves its
neighbors intact. Retain the fixture's normal context/guard checks and exercise
atlas-upload failure through the existing startup cleanup path, without a new
full fault matrix.

## GAT2 Copy title gadgets from the atlas

Primary files: `lib/desktop/desktop-frame.c`,
`ports/gem4xe/adapter/gem-vbxe.c` and its private `gem-drawing.h`.

Add one private helper accepting a fixed gadget ID, destination and admitted
clip. Intersect once; invisible images produce no records. Select the stored
phase from the original destination X, then derive the source offset from the
clipped image coordinates. Do not select phase from the clipped left edge.

Append copies to the existing command list. A complete byte-aligned image
should use **one copy record**; partial bytes need only the existing bounded
edge-preservation operations. An odd placement or clip must preserve each
neighboring nibble. No CPU fallback or per-paint repacking is needed. Retain
the current record/work limits and completion rules, without adding a separate
owner admission, immediate submission or fence for each gadget.

The helper must calculate its destination from the current scratch origin and
pitch. Ordinary title strips use pitch 320; compact frame sides use pitch 8 or
16. Reuse the compact mapping already established for solid fills. The current
generic `blit_mask` redirection adds only `stripOffset`, so calling it unchanged
for a compact destination would be incorrect. Keep that mapping private rather
than introducing a general surface framework or changing the font path.

Migrate close, full-size and iconify marks, plus the miniature iconified-window
image. Keep the live title, pattern, paper, outer outline and separators. Publish
only the completed scratch fragment through the existing pointer/outline-safe
boundary. Remove the migrated procedural marks from production.

Focused checks: one optimized pixel fixture covering active/inactive titles,
Shell's no-closer title, iconified tiles, both X phases, clipped top/left/right
edges and an overlapping window. Use the existing procedural host raster as an
independent oracle; it must not import the new atlas data to decide correctness.
Check unchanged pixels outside the admitted clip.

## GAT3 Copy scrollbar and resize marks

Use the same helper for up/down arrows and the resize mark. Retain variable
track and thumb fills and shared separators, in their existing order. Cover
both the bottom strip and compact tall-side path: the resize image may cross
their clipping boundary and must compose identically in each fragment.

Broaden the private `GemDrawingFrameBatch` contract from solid-only callbacks
to solid fills plus fixed atlas copies. Both destination calculations use the
same compact scratch geometry. Do not raise the global strip height or add
another scratch surface. Remove the remaining fixed-mark fill loops.

Focused checks: extend the same optimized pixel fixture for a complete scrollbar,
minimum/maximum thumb positions, a clipped arrow and resize mark, odd exposure
edges, and a maximum-height compact side with scratch canaries. Include one
ordinary widget/menu draw after the frame to catch leaked scratch pitch/state.
Recheck one warm cached body restore: its side pixels must still come from the
snapshot, with no new atlas reconstruction on exposure.

## GAT4 Measure and refresh the demo

Reuse the FE4 baseline package at
`build/frame-exposure/demo/exec816-demo.zip` and its recorded pins/hashes.
There is no separate baseline-establishment slice, compiler update or broad
qualification run. If additional baseline call boundaries are needed, observe
that same frozen package with a narrowly selected case.

Extend the existing passive frame observer to distinguish:

- Entry/exit of the actual frame calls, with title, bottom and sides identified.
- Frame-local fill/gadget calls, blitter records, list submissions and fences.
- Time before the first frame call and between frame calls.
- First complete frame, later resolved-path title, and complete folder pixels.

When combined with response slice UI2, the initial frame already has its path
title. Keep the historical baseline's later-title endpoint explicit; the expected
elimination of that update is separate from the atlas's renderer savings.

Use existing Task-switch observations when reporting active CPU time; otherwise
label entry-to-exit intervals as elapsed time including preemption. Do not count
whole-action submissions as frame-only cost. The existing roughly 943 ms
New Window result includes application setup and the later path-title change,
so it is not a pure drawing benchmark or an atlas speedup target.

Acceptance is exact pixels, no per-redraw atlas transfers, one record per
aligned opaque image, fewer frame-construction records and lower measured
frame-renderer CPU cost for representative title and scrollbar cases. Report
actual before/after results; a frame-count reduction is not expected because
the atlas changes work inside the existing batches. Keep any unresolved cost
visible instead of adding scheduling or filesystem changes to this slice.

Run a small matched New Window and warm Shell/SYS focus comparison, with three
samples where useful and medians/maxima rather than p95 claims. A single menu
smoke case is sufficient because the pattern and menu implementation are
unchanged. Reuse passing focused checks unless their inputs change.
For the coordinated response work, UI5 replaces this atlas-only measurement
scope with its selected menu comparisons and performs the final package pass
once. Retain frame-only observations at GAT3 to distinguish the atlas gain.

Build the final desktop demo through `tools/build_demo.py`, including OF816,
the five-second autoboot, matching disks, pinned ROM, notices and checksums.
Keep development traces outside `exec816-demo.zip`. Update the desktop/adapter
reference, plan status, indices and a short development record with memory
deltas, selected test scope and measurements. Commit each executable slice.
