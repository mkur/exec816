# GEM text viewer performance implementation plan

[GEM plans](README.md) · [Viewer implementation](text-viewer-implementation-plan.md) ·
[Viewer measurements](../../history/text-viewer.md) ·
[Latency diagnostics](../../guides/aes-latency-diagnostics.md)

Status: TVP1–TVP4 implemented and measured at the development tier. The twofold page target remains open; cancellation latency and transient flicker remain unqualified. See the [execution record](../../history/text-viewer-performance.md).

Reduce the time to repaint a text page while preserving mouse, button and other
application responsiveness. Start with the working `TEXT.APP` and its existing
AES/VDI path. Profile a small repeatable workload, optimize the largest measured
cost, then check the resulting desktop. Keep each production change in a
separate executable slice and commit it after its development checks pass.

## Starting evidence and scope

The TV4 package at commit `018c414` has two page-key observations:

| Observation | Input to model change | Model change to completed repaint |
| --- | ---: | ---: |
| Page 1 | 30.6 ms | 1,250.7 ms |
| Page 2 | 53.6 ms | 1,331.3 ms |

These are software milestone observations, excluding scanout, and do not
establish a median or p95. The [retained evidence](../../development/text-viewer.json)
pins the image and machine. Preserve it; record new results separately.

Current source provides several leads, which the first slice must rank:

- [`TextRun` and `paint`](../../../examples/gem-text/text.c) draw at most four
  text rows per UPDATE, poll events between bands, and issue separate margin,
  status and text calls. Row formatting happens inside visible-rectangle traversal.
- [`v_gtext`](../../../c/calypsi/vdi.c) streams 32-character chunks. Each
  intersecting chunk/strip borrows the display separately; the VDI layer also
  intersects the UPDATE snapshot's visible rectangles.
- [`GemDrawingBorrow`](../../../ports/gem4xe/adapter/gem-vbxe.c) admits delegated
  access, repairs the pointer/outline and fences around a synchronous callback.
  [`GemVdiPaint`](../../../ports/gem4xe/hosted/hosted-dispatch.inc) saves/selects
  renderer state, copies glyph words, calls the donor renderer and flushes.
- Native console text already has a specialized uploader. VDI opcode 8 uses
  the device glyph path. The adapter can transfer a whole 4 KiB staging page,
  but that does not establish that normal viewer text uses staging: count actual
  reads/writes before proposing a transfer optimization.

This pass covers viewer work, caller-local VDI and their drawing backend.
Retain standard GEM application calls, current scheduling and synchronous
drawing semantics. Kernel priorities, interrupt rewrites, a new renderer Task,
screen-copy scrolling and document/VRAM caches are separate architectural work.
Memory traffic matters here when it explains latency; it is not the acceptance
metric by itself.

## Slice sequence

| Slice | Deliverable | Gate |
| --- | --- | --- |
| TVP1 | Bounded timing breakdown and repeatable workload | Reconciled timings, pixels and an identical-image replay |
| TVP2 | One optimization of the dominant VDI/drawing cost | Lower measured cost, preserved drawing semantics and responsiveness |
| TVP3 | Viewer paint-work reduction where the remaining profile justifies it | Faster line/page repaint and correct damage handling |
| TVP4 | Matched desktop comparison and refreshed OF816 package | Exact-package functionality, resources and reported latency results |

TVP2 and TVP3 are ordered by evidence. If TVP1 identifies application work as
the main cost, implement the viewer change first. If one candidate is negligible
or already meets the objective, record that result and omit that production
change. Do not accumulate speculative optimizations or retain tuning modes.

## TVP1 Measure the existing path

Extend the existing viewer runner and model/pixel observers. Add only a small
measurement helper if needed; reuse the passive PC, Task and interrupt accounting
from the [AES diagnostics](../../guides/aes-latency-diagnostics.md). Keep tracing
to selected paint intervals and cap output size. This is a diagnostic slice,
not another full desktop baseline project.

Use optimized emitted code and record source, APP/GEMSYS, compiler, ROM, emulator,
disk and observer hashes. Retain the TV4 machine settings for comparison. Resolve
loaded APP symbols from their actual relocated image and owning Task. Check
entry/return instructions and stack matching; local C helpers such as `paint`
must not be identified by name alone. Missing or incomplete markers fail the
measurement rather than contributing zero time.

Record these milestones per physical key or pointer action:

1. Input submission/capture and application model change.
2. First completed changed content band in VRAM. Record status/thumb changes
   separately; a moving cursor or counter is not viewer feedback.
3. Completion of all damage for the requested model and geometry, with matching
   expected pixels. A paint counter increment or temporary empty damage flag
   alone is insufficient under overlapping redraw requests.

Distinguish VRAM completion from displayed scanout. Use actual scanout observation
when available and label it separately; do not silently turn a draw-return or
IRQ-sampled state change into a display timestamp. Record observer resolution.

Attribute elapsed repaint time to viewer CPU, interrupts, runnable off-CPU time
and blocked time. Within viewer CPU, identify row formatting, VDI setup/clipping,
renderer setup/glyph construction, upload/staging and completion polling. Record
UPDATE acquisition delay, UPDATE hold duration and gaps between paint bands.
Keep hardware launch-to-completion intervals separate from charged CPU; they can
overlap other work. Exclusive categories must reconcile to their parent interval;
do not add inclusive routines or component percentiles together.

Count rows/glyphs, visible fragments, VDI calls, display borrows, list submissions,
records per list, fences and staging bytes in both directions. A wider CPU gap
or more redraw restarts must remain visible even if command construction improves.
Use the existing one-KiB loading boundary to separate DOS waiting, indexing and
post-load paint in one cold Open observation; scrolling measurements use an
already loaded document and perform no disk I/O.

Keep the workload small and reproducible:

| Case | Purpose |
| --- | --- |
| Alternating page down/up in `STORY.TXT`, fixed window | Primary full-page cost, without reaching no-op end positions |
| Alternating line down/up and a boundary no-op | Small-action cost and unnecessary painting |
| Minimum resize, wider resize, partial cover and exposure | Clipped text, odd edges, fragmented damage and repair |
| Viewer redraw beside Panel/counter, then with fixed shell output/disk work | Pointer/button delay and peer progress under load |

Close Files to make room for the viewer beside Panel, counter and shell. Keep
window geometry, text, pointer location, focus and offered background work equal
before/after. Schedule loaded input at fixed offsets, independently of completion;
report offered/completed/cancelled or coalesced actions and backlog. Ensure the
panel workload uses real focus/gesture routing rather than delivering keys to a
covered inactive viewer. Use separate viewer-focused and panel-focused sequences.

Collect at least 30 completed actions per repeated key/button cohort across
three short runs. Retain raw samples, median, nearest-rank p95, maximum and any
timeouts/backlog; report small resize/exposure samples individually. Repeat only
bounded representative intervals with detailed tracing. Replay those scenarios
on the same image without detailed tracing and require the same final state,
pixels and completion. Finish by selecting the dominant cost and the smallest
candidate change for TVP2.

## TVP2 Reduce the dominant drawing cost

Choose one change from the measured breakdown. The leading candidate is to
reuse the existing native text uploader's record construction for eligible
VDI text, because that faster path is currently unavailable to `v_gtext`.
This is conditional on TVP1 showing meaningful device/glyph cost.

Keep both named `v_gtext` and parameter-block opcode 8 on one implementation.
An internal fast path runs under the existing delegated display grant; it must
not call a native-owner public wrapper recursively from `GemDrawingBorrow`.
Use the current bounded private workstation storage. Preserve glyph mapping,
pen translation, replace-mode background, spaces, odd X, partial edge nibbles,
vertical clipping and CPU bank-crossing source reads. Select the existing general
path for geometry the fast path cannot represent. Add no TEXT-specific ABI.

If display admission, renderer setup or fencing dominates instead, combine work
within one already admitted bounded primitive or remove a proven redundant
boundary. Preserve scratch/command-arena dependencies, completion before reuse,
pointer/outline repair and display fault recovery. A four-row application band
does not authorize a 32-row renderer borrow: the current borrow bound is 16 rows.
Retain the existing 64-record and 8,192-work list ceilings.

Optimize whole-page staging transfers only if the trace attributes material time
to them. Likewise, replace arithmetic or write assembly only for an identified
expensive loop. Prefer existing tables/uploaders and ordinary code changes before
adding storage or a second implementation.

Development gate: independent pixels for full/clipped text, blank suffixes,
zero/nonzero pens, odd edges, long strings and bank boundaries; named/PB call
equivalence; two-client workstation isolation/preemption; pointer/outline repair;
and the affected fault/cleanup path. Reuse `test_gem_text.py`,
`test_gem_render.py`, `test_gem_drawing.py` and the `test_vdi_client.py` checks
through their existing drivers, selecting only affected cases. Repeat the TVP1
page and loaded-button measurements before committing the change.

## TVP3 Remove unnecessary viewer paint work

Use the new profile to choose a small application change. Candidate work includes
skipping margin/status calls whose rectangles miss the current band, avoiding
repeated row formatting across visible fragments, or preserving narrower damage
when it can be done without another cache or a complex damage structure.
Continue to pad replaced text so shorter lines and newly exposed blank areas
erase old content correctly.

Keep the four-row limit and event service between bands initially. Change that
constant or event-loop ordering only if measured inter-band overhead dominates,
and compare complete repaint latency with UPDATE hold time, pointer/button p95
and cancellation response. Keep one bounded production policy. Do not hide
pending events with a private polling API or make an idle viewer busy-wait.

Move/resize, scrolling or replacement during an unfinished repaint must continue
from the current model and repair all affected pixels. Covered bands can retire,
but later exposure must redraw correctly. Keep loading and painting bounded;
never hold UPDATE/display ownership across DOS I/O or an event wait. Preserve
Cancel/failed-Open document retention and zero repaint for a no-op scroll.

Development gate: the viewer oracle on initial/page/line/resize/exposure states,
new damage and model changes between bands, peer activity, Escape/Stop and idle
sleep. Rerun document fixtures only if formatting or loading code changes.
Repeat the same timing cohorts and commit only a demonstrated improvement.

## TVP4 Compare the desktop and package it

The first tuning objective is **at least a twofold improvement in median and
p95 full-page completion** against TVP1's matched repeated baseline. This is a
new target, not a claim derived from TV4's two samples. Record input-to-model,
first-content and complete-repaint times separately for each load cohort.

Input responsiveness has priority. Require no reproducible regression in loaded
pointer/button p95, first-content feedback, cancellation or peer progress. Use
TVP1's run-to-run variation and timestamp resolution to fix a comparison tolerance
before measuring candidate builds; retain that tolerance and every run. If a
comparison is inconclusive, repeat the affected matched pair. A throughput gain
with a repeatable responsiveness loss is not accepted. Report remaining misses
explicitly; do not relax the target after seeing the candidate results.

Build the final demo with `tools/build_demo.py --gem-desktop`, retaining OF816,
the five-second autoboot, startup application set, matching disks/ROM and notices.
Run the extracted ZIP's focused viewer and Files workflows through EXIT, plus
the selected Panel-under-redraw comparison. Check pixels, warmed allocation
return, ownership, guards and OS display/input restoration. Keep traces,
manifests and captures in development output; distribute only the normal ZIP.

Write the actual results to `docs/history/text-viewer-performance.md` and
`docs/development/text-viewer-performance.json`, with the baseline/candidate
hashes, sampled distributions, work counts, trace scope, resource costs and
remaining visible repaint/flicker behavior. Link the history index, update this
plan and the roadmap. These development checks do not close HY4/PI4 or qualify
real hardware.

## Resource and validation rules

Use the [development testing tier](../../contributing/testing.md): host checks,
affected generators and focused optimized emitted behavior. Use small raw/optimized
probes only for changed ABI layouts, assembly/compiler bridges or suspected
compiler defects. Edit donor adaptations through the maintained extraction
inputs; keep `~/atari/gem4xe` untouched. Fix compiler defects in actionc.

Target **0 new fixed bank-zero bytes, 0 per public Task and 0 private idle** in
each slice, including guards, alignment and unused reservations. Preserve the
128-byte ordinary-stack headroom target; TV4's minimum was 149 bytes. Record
actual upper-memory, code, loaded-image and VRAM costs. Reuse existing buffers
first. A justified stack or storage change needs explicit accounting and the
affected checks, not weaker guards or a broad refactor to preserve a nominal zero.
Read the [platform contract](../../reference/platform.md) before platform edits.

Trust caller-owned pointers and admitted internal geometry. Retain resource
creation checks, operational errors, finite batch bounds and synchronization;
do not introduce repeated validation along the hot path. This plan itself
changes no executable code or memory reservations.
