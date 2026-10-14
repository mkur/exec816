# Window frame and desktop exposure implementation plan

[GEM plans](README.md) · [Roadmap](../../roadmap.md) ·
[Preservation plan](window-preservation-plan.md) ·
[Preservation measurements](../../history/window-preservation.md) ·
[AES and Layers design](aes-layers-vram-design.md)

Status: implementation in progress. FE1–FE2 are implemented; FE3–FE4 remain.
FE1 passed the focused optimized presentation fixture (117 native assertions
and independent framebuffer comparisons), recorded in
`build/frame-exposure/presentation/presentation-results.json`. Reserved
bank-zero change: 0 fixed, 0 per public Task, 0 idle; VRAM reservation change: 0.
The adapter adds two upper-RAM words for compact scratch pitch/mode.
FE2 passed 31 AES cache phases, including full frame pixels, INFO/slider
invalidation, no-op setters, small patches, hidden changes, move/resize,
eviction and conventional/preserved exposure. See
`build/frame-exposure/aes-cache/results.json`. This also found and corrected
a tall-side offset that exceeded the old sixteen-row work table: sides now
use an 8/16-byte power-of-two pitch. FE2 adds no persistent storage or reserved
bank-zero/VRAM bytes.
This is development evidence, not hosted-system qualification.

Make newly opened frames appear sooner, restore unchanged window decorations
along with their contents, and stop closing a folder from repainting unrelated
desktop icons. Keep the existing presenter, application update contract, two
snapshot slots, Shell backing and display completion mechanism. Use small
executable slices, with focused development checks after each.

## Starting point

The current frame already uses the VBXE blitter. CPU work constructs and clips
commands; `GemDrawingWidgetBatch` composes each fragment in VRAM scratch, copies
it to the screen and fences completion. The 640×16 scratch layout imposes a
sixteen-row limit even on narrow vertical edges. A fully exposed default Files
frame consequently needs about 24 fragments: title, bottom and eleven per side.

The current snapshot contains only client pixels. The measured SYS: client
finishes at about 642 ms while its whole window finishes at 1,163 ms. Those are
the two-sample medians in the preservation record, not new-window timings.

Closing SYS: was also observed to redraw the desktop's left icon column. The
desktop application respects its supplied damage rectangle. Both
`AESWINDOWSTATE.Damage` and `AESGUI.Queue` can widen separate exposure rectangles
to one bounding box, and desktop snapshot capture requires complete visible
pixels. These are relevant paths, **not a confirmed explanation of that close
case**. Trace the actual close before selecting its fix.

Reuse the current exact baseline package at
`build/window-preservation/demo-final/exec816-demo.zip` and its manifests. Extend
the existing observer for cold frames and close exposure, run those cases on
that package, then reuse the observations for the affected slices. There is no
separate baseline-only implementation slice or compiler-pin change.

## FE1 Draw complete frame sides in larger batches

Primary files: `lib/desktop/deskpaint.act`, `lib/desktop/desktop-frame.c`,
`ports/gem4xe/adapter/gem-vbxe.c` and its private `gem-drawing.h` declarations.

Keep the existing 5,120-byte scratch reservation. Add a small private frame
batch path that can pack a narrow, tall, non-text side into that storage:

- Keep titles, INFO text and ordinary widgets/menus on the existing short-strip
  path. The eleven-row title already fits in one fragment.
- Compose each complete left or right side with a compact row pitch and local
  origin. A default 16×174 right side needs 1,392 bytes; its 8×174 left side
  needs 696. Both fit without additional VRAM.
- Establish destination origin, pitch and capacity once for the admitted
  fragment. Map solid fills at the primitive boundary, where X/Y are already
  available; do not decode VRAM addresses with division for every command.
  The existing text/atlas address path need not acquire variable pitch.
- Keep composition offscreen and publish only completed fragments, preserving
  edge nibbles and pointer/outline handling. Do not draw an intermediate blank
  side onto the screen before its gadgets are complete.
- Preserve list record/work limits and driver completion rules. A complete
  frame fragment may require several hardware lists; it should not require a
  separate presenter operation and final fence for every sixteen rows.
- Skip nonintersecting gadget groups before expanding their fill geometry.
  Reuse the current marks and palette; this is not a visual redesign or a new
  object/gadget framework.
- Prefer the focused window at existing transaction boundaries. Keep input
  servicing between complete frame fragments and retain the current fallback
  for fragments that do not fit. Do not enlarge the global strip limit or mask
  interrupts to keep painting uninterrupted.

For the default unobscured Files frame without INFO, the structural target is
four completed frame batches: title, bottom, left and right, instead of about
24. Partly covered windows follow their actual visible pieces; do not copy
across an occluder to meet a batch-count target.

Focused checks: use the existing presentation fixture and independent pixels
for a default cold frame, INFO/scroll/size gadgets, partial exposure and odd
clip edges. Exercise maximum-height narrow sides and scratch canaries. Check
ordinary widget/menu pixels once because the storage is shared. Retain one
existing quiesced-transfer failure case; no full application matrix.

Measure New Window frame completion separately from directory enumeration and
first complete folder contents. Record frame batches, list submissions and
completion waits. The frame must improve against the unchanged baseline;
report actual times rather than inferring a sixfold speedup from batch counts.

## FE2 Extend saved window pixels to include the frame

Primary files: `lib/desktop/deskcache.act`, `lib/desktop/deskpaint.act`,
`lib/aes/aeswindow.act`, `lib/aes/aeswindowstate.act` and the existing move path.

Change the existing non-console snapshot geometry from client bounds to outer
window bounds. Keep one snapshot format and the same two 76,800-byte slots;
Shell retains its dedicated backing. An aligned 640×240 outer window fits one
slot. The default 462×196 image occupies 45,276 bytes, versus 38,106 for its
438×174 client: 7,170 additional used bytes, with no larger reservation.

Capture only when the complete source is visible, manager damage is retired
and application pixels are complete. A covered desktop or partially hidden
window still falls back; do not capture another window's pixels or synthesize
hidden contents. Maintain the existing source pin, identity, revision and
asynchronous completion rules.

Keep client geometry distinct from snapshot storage coordinates:

- `ClientBounds` and AES paint completion still describe application pixels.
- Snapshot dimensions, source offsets and patch destinations use the outer
  origin and outer row pitch. Update capture, lookup, patch and restore
  together, including native non-console callers of this shared cache path.
- A small completed client update still patches only that client rectangle at
  its new offset. It must not recapture the full image on every button change.
- Same-size moves retain local pixels and reuse the image. Resize/full restore
  invalidates dimensions as before. Iconified tiles are not the normal image;
  hidden updates continue to invalidate it, and slot reuse cannot inherit it.

The title is always drawn for the **current** focus/name state. Even if stored
in the snapshot, do not replay the old title before repainting it: clip saved
restoration below the title and render the title once through FE1. For an
unobscured default Files window this permits one body copy containing client,
side borders, scrollbar and bottom, plus the live title batch. Borderless
windows have no title exclusion.

Reuse the existing visual revision and invalidation mechanism. A changed INFO
line or scrollbar position/size now changes saved frame pixels and must
invalidate that image before restoration can use it. Ignore unchanged setters;
focus and title-only changes need not discard the reusable body. Start with
conservative whole-image invalidation for actual non-title frame changes;
separate frame revision counters and frame-only repair queues are not required.

Preserve the AES contract: a completed restore suppresses new client exposure
only for `AES_WF_EXEC_PRESERVE` windows. Conventional owners still receive
`WM_REDRAW` for the client intersection. Misses, failures and unaligned clips
retain ordinary drawing; do not clear an earlier content obligation. Successful
frame restoration alone never certifies hidden application changes.

Focused checks: extend the existing AES cache fixture for whole-window extent
and pitch, preserved/default owners, a client patch, an INFO/slider change,
focus/name changes, a same-size move and resize/eviction fallback. Verify that
old title colours never flash and that no frame copy overwrites another owner.
Reuse the prior hidden-update and failure cases where their inputs are unchanged.

Acceptance for warm idle SYS: raise: one aligned body copy, one current title
batch, no side/scrollbar reconstruction, no duplicate Files redraw and no cache
maintenance caused solely by exposure. Record the larger restored byte count;
the relevant endpoint is the correct complete window, not only its client.

## FE3 Restrict desktop repaint after closing a folder

Begin with the actual default close case and a folder placed wholly to the
right of the icon column. Use the existing observer to record the close bounds,
Layers damage, AES redraw rectangles, desktop draw clips and final framebuffer
destinations. Observe the existing code with passive traces or fixture-only
counters; add no permanent per-icon instrumentation.

Follow `AESWINDOW.Close` / `LAYERS.Show`, focus restoration, desktop frame
handling, `AESWINDOWSTATE.Damage` / `Handoff`, `AESGUI.Queue` and
`desktop_draw`. In particular:

- A close should damage the newly exposed scene inside the old window bounds.
  Focus/title/menu changes have their own small extents.
- A borderless desktop has no title strip to repaint on focus changes.
- Separate desktop exposures must not become an unnecessarily broad rectangle
  covering unchanged icons merely because they share one owner.
- Keep the application's existing scoped update and clip-aware object drawing.
  Do not suppress legitimate desktop redraw messages or rely on a lucky cache
  hit to hide incorrect damage.

Fix the demonstrated broadening at its source. If disjoint damage must survive
AES handoff and queued-message coalescing, retain a small bounded per-window
rectangle set, reusing the existing damage representation/capacity. Merge only
when the exact union is rectangular; stream ordinary eight-word `WM_REDRAW`
messages through the current endpoint as it becomes available. Keep a single
pending rectangle set, not copies at every layer or an unbounded message queue.
Epoch retirement, close and backpressure must still work. On capacity overflow,
retain a conservative repaint fallback rather than dropping damaged pixels.
Do not add this storage if the trace identifies a simpler bounds/focus defect.

No new GEM call, client callback, desktop-specific bitmap allocation or full
offscreen drawing contract is needed for this slice. If generic Layers order
damage is independently excessive, limit changes to what the close case needs;
leave a general stacking-difference algorithm outside this work.

Focused acceptance cases:

- Closing a folder wholly right of the icon column emits no icon draw work and
  no framebuffer writes to that column. Keep the pointer outside the column
  during this check, so cursor save/restore is not counted as desktop repair.
- Closing a folder that actually covers icons repairs the exposed portions
  correctly; those icons are not excluded by a special-case rule.
- Closing the last folder restores sensible focus/menu state. The same holds
  with Shell iconified and another folder still open.
- Disjoint repaint requests remain complete through ordinary message
  backpressure, and the bounded overflow case preserves correctness.

Use a cache miss or eviction for at least the first case so a restored image
cannot conceal unnecessary damage. Match pixels as well as operation counts;
an unchanged screenshot alone cannot prove that unnecessary writes stopped.

## FE4 Focused comparison and demo delivery

Extend `tools/measure_window_preservation.py` and reuse the existing scene
oracle. Keep the sample set small: three matched repetitions each of New
Window, warm Shell/SYS: focus switching, closing a folder right of the icons
and closing one that exposes icons. Add one File → View → dismiss check and
one iconify/restore check. Reuse earlier slice checks instead of rebuilding
unchanged fixtures or running a qualification matrix.

Keep compiler, ROM/emulator configuration, mouse profile, media, directory
contents, window geometry and cache warmup identical. For New Window, report
input-to-frame and input-to-complete-folder separately, plus admitted-frame
construction time if available. For focus/close, distinguish foreground pixels
from final background repair. Record individual samples, median/max and timing
resolution; three samples do not establish a p95 distribution.

The decisive structural gates are four cold frame batches for the simple
unobscured default, one warm body copy without side reconstruction, and zero
unrelated icon writes on close. Report observed speedups and any remaining
delay honestly. Compare cold-frame and full SYS: completion with the baseline;
neither improvement is established by client-only timing. Check that Shell and
the warm menu case do not regress beyond the frame-sampling resolution.

Check normal EXIT, guards, Task progress and that a display fault retains its
ownership until quiescence. Routine behavior runs use optimized emitted code.
Only changed shared ABI layouts/calling conventions need a small raw/optimized
bridge probe and regenerated definitions; private bookkeeping does not justify
a full raw run.

Build the final package through `tools/build_demo.py --gem-desktop
--release-compiler`, retaining OF816, five-second autoboot, matching disks,
pinned ROM and notices. Exercise the exact extracted ZIP and provide its launch
command. Keep diagnostics and build intermediates outside the ZIP. Update the
AES/desktop references, record measured results in history and mark these slices
complete only after their selected checks pass.

## Memory and scope

Each slice targets **0 additional fixed bank-zero bytes, 0 per public Task and
0 idle Task bytes**, including guards, alignment and unused reserved capacity.
VRAM reservations stay unchanged: reuse the 5,120-byte scratch and two 75 KiB
snapshot slots. Count actual upper-RAM scalar state and any bounded AES damage
storage added by FE3 in the implementation record. Do not add large stack
region arrays or increase Task stacks for this work without measured need.

Keep validation at existing ownership/admission boundaries. Internal geometry
and blit producers are trusted; preserve capacity, clipping, lifetime and
completion rules without decoding or revalidating every command. No scheduler
priorities, new Tasks, general render-target abstraction or cache allocator is
part of this plan.

Implement FE1 → FE2 → FE3 → FE4, keeping each slice reviewable. Preserve the
current uncommitted implementation and its baseline package. Preparing this
plan changes documentation only.
