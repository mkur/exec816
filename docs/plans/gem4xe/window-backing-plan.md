# Aligned window moves and Shell backing implementation plan

[Design note](aes-layers-vram-design.md#aligned-aes-moves) ·
[GEM plans](README.md) · [Testing policy](../../contributing/testing.md)

Status: implementation in progress, 2026-10-14. Implements the aligned AES move and persistent
Shell backing extensions to the AES/Layers design. The completed
[AV1–AV6 plan](aes-layers-vram-plan.md) remains its own historical scope.

The outcome is an eligible AES window moving by blit on release, and exposed
Shell text restoring from a current backing bitmap. Ordinary GEM exposure
messages remain necessary for external application content. Keep outline
dragging, the existing presenter, one display transfer and existing completion
signals. No live opaque dragging, general bitmap allocator, offscreen VDI
workstations, new worker or kernel operation is included.

Implement WB1–WB6 in order and commit each executable slice after its selected
development checks. Update current reference contracts with the slice that
changes behavior. Do not mark performance gates passed from functional checks.

## Existing boundaries to change

| Boundary | Current behavior | Required change |
| --- | --- | --- |
| `AESWINDOW.ValidBounds`, `DESKDRAG.Position` / `SizePosition` | AES geometry can have odd X/width. | Normalize accepted geometry and drag proposals consistently. |
| `DESKMOVE.Start`, `LAYERS.BeginMove` | Explicitly exclude AES/external-painted windows. | Admit fully visible, completed client pixels and retire through the existing move transaction. |
| `AESWINDOWSTATE.Snapshot` | Changed bounds call `ExternalArea`, even for a pure move. | Preserve completed content during a successful copied move; retain repaint fallback for other geometry changes. |
| `DESKPAINT.PaintStrip`, `CONSOLEBITMAP.DesktopPart` | Shell exposure renders cells; output is clipped before drawing. | Render backing independently of coverage and copy visible client intersections. |
| `CONSOLEDISPLAY.Cells` / `PresentBatch` | Dirty-cell retirement describes screen painting. | Retire model-to-backing work separately from Layers screen damage. |
| Console batch/scroll continuations | Covered scrolling abandons the screen-copy path. | Scroll the backing surface, then present the resulting visible regions. |

Trust established handles, pointers and internal geometry producers. Keep the
checks that decide whether pixels are current, a transaction owns its source,
or hardware has completed; do not add repeated API validation around them.

## Comparisons and gates

Use the current Shell-focus code as the starting baseline, recorded in
[the Shell focus evidence](../../history/shell-focus.md). Preserve its exact
source/build inputs and packaged executable before implementation. Do not use
the older AV6 menu timings as a move/console baseline. Keep compiler, ROM,
emulator, video timing, mouse profile, media, app geometry and workload identical
in each comparison. No compiler pin change belongs in this work.

There is no baseline-only slice. Extend the existing diagnostics in the first
slice that needs each comparison and run the new cohort on unchanged code
before changing that behavior. Use aligned coordinates on both builds for
timing comparisons; test odd requests separately for normalization correctness.

Measure three endpoints separately: release/request to correctly placed moved
window, to repaired exposed background, and to any final external-app repaint.
For Shell, the oracle must match the current retained model and completed output,
not just an earlier cached screenshot. Also record model-to-backing and
backing-to-screen work, client glyph calls, copy count/bytes and fallback reason.
Use existing diagnostics or fixture-only counters; observations must not add
production per-glyph bookkeeping.

Use at least 20 samples per idle cohort (Files and Panel moves, and their close
over Shell), 30 button interactions under continuous output, and five fixed
scrolling runs. Record median/p95 and sampling resolution; use guest timestamps
where available and label PAL-frame sampling honestly. Replay identical input
without diagnostic instrumentation when instrumentation is added. Validate
pixels and model contents outside timed intervals.

The gates below are targets, not measured results. `B` is the same endpoint and
workload on the frozen baseline; one PAL frame is approximately 20.1 ms under
the existing pin. Freeze input sizes/coordinates and sample definitions with
the first baseline record, before optimizing.

| Behavior | Acceptance gate |
| --- | --- |
| Eligible copied AES move | Correct moved-window median and p95 at most 50% of B; no client repaint or glyph rendering caused by the successful pure move. |
| Clean aligned Shell exposure after move/close | Correct exposed-text median and p95 at most 50% of B, with p95 at most 100 ms; zero text glyph calls for the restoration itself. |
| Combined idle move/close over Shell | Entire affected visible scene correct at most 50% of B for median/p95; report moved window and background separately. |
| Ineligible move, focus-only click and ordinary menu transitions | Median/p95 no more than one PAL frame above B. Preserve the zero-client-paint repeated Shell click behavior. |
| Concurrent button feedback during console output | Median/p95 no more than one PAL frame above the matched loaded B; all Tasks and output make progress. |
| Visible and partly covered scrolling | Median completed-output throughput at least 95% of B, including final screen settlement. Use resident fixed text as the primary rendering cohort and a separate loaded CAT check. |

Measure fully covered output throughput, initial backing fill/rebuild and final
AES repaint separately too. Hidden output now maintains pixels and may cost
more than the baseline; disclose that cost and require bounded input service
and eventual exact contents. Do not count accepted bytes as completed rendering.
Missed gates remain open with their actual results; do not relax them after
measurement or replace final repaint with an earlier cached image.

## WB1 Align accepted AES geometry

Change [AES window admission](../../../lib/aes/aeswindow.act) and
[drag geometry](../../../lib/desktop/deskdrag.act) to use even outer X and width:
round X down, width up, and enforce existing screen limits without losing
alignment. Apply this to create/open, `WF_CURRXYWH` and move/resize proposals.
Compare normalized dimensions for fixed-size windows so an odd-width create
followed by open does not become a false resize error. Preserve Y/height pixel
precision, existing minimum sizes, native Shell's eight-pixel movement and
file/icon drag coordinates.

Publish the accepted outer and work rectangles in the existing view and
`WM_MOVED`/`WM_SIZED` proposals. Keep `wind_calc` a predictable border/work
conversion; document that actual placement comes from `wind_get` after open/set.
Audit shipped app move/open handlers for use of returned work geometry rather
than assuming their requested rectangle was accepted unchanged. Avoid a new
normalization RPC or general geometry layer. Rendering still uses the current
redraw path in this slice.

Extend `tools/test_aes_windows.py` and the native window fixture for odd/even
open/set, repeated moves without coordinate drift, fixed-size open, resize
edges and full-screen bounds. Check physical outline/release coordinates,
accepted work rectangles and app painting. Update the odd-X expectations in
`tools/test_aes_cache.py`: odd window requests now normalize; odd clipped
restoration edges must still be tested directly. Commit WB1.

## WB2 Copy completed AES windows through the move transaction

Route same-size `WF_CURRXYWH` moves through the existing
[move continuation](../../../lib/desktop/deskmove.act). Extend
`LAYERS.BeginMove` admission to external windows whose client has no pending
paint and whose complete source is clean and visible. Require an onscreen
destination unobscured by higher layers, even source/destination X and width,
and no conflicting UPDATE/display owner. Preserve no-op moves and the existing
native window path. Do not substitute a client snapshot for a partially covered
window in this slice.

Use `UPDATE_MOVE`, overlap-safe screen copying and the existing completion pump.
Extend its bounded completion state to distinguish native and AES requests.
Keep `AESCORE.Settle` as the sole owner of the AES reply: the move continuation
completes Layers/AES geometry publication before admitting further input, then
records the terminal result for the retried `AESWINDOW.Request` to consume.
Retain the existing pending request/owner lifetime until then. A retry must not
launch another move or run the ordinary bounds setter after the copy succeeds.
No second request queue, worker or busy wait is needed.

Commit Layer bounds, external paint geometry, slider geometry and the AES view
before releasing the request. Preserve local snapshot contents and translate
geometry-dependent metadata. Advance the existing paint/view generation as
needed so an acknowledgement for old coordinates cannot clear newer damage.
Split the copied-move publication from the normal `Snapshot` invalidation;
do not skip `ExternalArea` for arbitrary moves or resizes. Keep the copied
client clean through `Rebuild`, damage only the old exposed area, and preserve
genuine underlying `WM_REDRAW`. An application without completed-paint evidence
continues through ordinary redraw.

Before launch, ineligible sources fall back normally. After a failed copy,
retain old committed geometry and repair affected source/destination pixels
under existing failure semantics. Quiescent failure releases the transaction;
unquiesced failure keeps its sources and ownership retained. Owner exit/close
must not free an in-flight move's window/view/request. Do not hold `Forbid`
across DMA or background repaint.

Extend `tools/test_layers.py`, `tools/test_aes_windows.py` and
`tools/test_aes_cache.py` with exact-pixel moves in all directions, overlapping
and disjoint destinations, a disjoint menu bar, covered/dirty/resize fallback,
delayed UPDATE, old acknowledgements, queued close/exit and failed/unquiesced
DMA. Check one geometry publication/reply, no moved-client redraw, correct
underlying exposure and retained cache validity. Run the eligible-move timing
cohort now; final Shell-background acceptance waits for WB6. Commit WB2.

## WB3 Reserve the Shell bitmap and reuse destination-aware drawing

Add `shell_backing` to the machine-readable
[VBXE map](../../../platform/altirraos/vbxe-vram.json) at `$41000–$4AFFF`:
512×160 packed pixels, pitch 256, 40,960 bytes. Generate dependent definitions
through existing tools. Keep both shared AES snapshots intact and exclude the
diagnostic range at `$3FFF0–$4000F`.

Extend the private [console bitmap protocol](../../../abi/console-bitmap.json)
with backing-text and backing-fill operations using the existing coordinates,
text/count and colour fields. Select the fixed destination explicitly in
`lib/console/console-bitmap.c`; no packet size growth is needed for this choice.
Refactor the common renderer's text/fill internals to accept destination base
and pitch while existing screen entry points retain screen defaults. The
backing operations call those same internals with client-local coordinates.
Reuse the optimized atlas, text upload and solid-fill paths; keep a target from
leaking into the next frame, menu or VDI draw. Copies already carry surfaces.

Carry the destination through `ports/gem4xe/adapter/gem-vbxe.c` and the native
text producer in `platform/altirraos/vbxe.c`. The latter currently constructs
screen addresses, and `_VbxeTextUpload` in `vbxe-map.s` emits screen-pitch
records. Add an explicit destination pitch to the private C/assembly upload
record and use it for every destination record, including background/optional
fill records. This private upload record may grow even though the console
packet does not. Reuse call-clobbered DP space within its current reservation;
check layout, context and actual stack use. Use shifts for the 256-byte backing
row pitch rather than adding division or a general per-glyph surface resolver.

Change handwritten renderer code or its generator/patch source as appropriate;
do not edit extracted/generated output or the upstream GEM4XE checkout.
Regenerate the private protocol version and rebuild its native/C consumers.
This is an executable backend slice: production console presentation switches
in WB4, after the target primitives have pixel coverage.

Extend `tools/test_gem_drawing.py` or the smallest console bitmap fixture to
draw text and fills into the backing surface, compare with an independent
pixel oracle, copy to screen, and check destination/neighbor guards. Exercise
first/last rows, colours, 64-cell text runs and a subsequent ordinary screen
draw. Add a small raw/optimized probe for the changed private Action!/C boundary;
run rendering behavior optimized. Check map totals/overlaps and commit WB3.

## WB4 Maintain and restore the Shell backing image

Use a small fixed presenter-owned backing state for the current Shell unit and
lifetime; reuse console dirty spans and batch identities. In the desktop
console path, dirty rows now mean model-to-backing work. A completed backing
span retires only its observed model generation and creates screen damage for
the corresponding visible area. Layers damage tracks screen repair separately.
Fully covered output must still advance backing work; bypassing all rendering
because visibility is empty is no longer correct for this unit.

Integrate the backing path into `CONSOLEDISPLAY.Cells` and the existing
`DESKPAINT` continuation. Draw changed spans once, then restore visible
intersections through Layers paint transactions and asynchronous display copies.
Use the current rendering/copy budgets and presenter input boundaries. Avoid
clearing restored client pixels first or converting every exposure into a full
backing rebuild. Backing maintenance must run when an exposure needs dirty
pixels, without holding a scene token that prevents that maintenance.

Keep separate completed-backing and screen-presentation facts. Retire only the
span/transaction submitted; output arriving during DMA remains pending. Store
unit/generation/cursor scalars across turns and reborrow live model data as the
existing console continuations do. Pin backing source regions until the active
copy retires; serialize conflicting writes through the one display owner.
Real content updates invalidate intersecting menu saves, even if screen output
is currently covered. Position-only changes retain backing validity.
Adjust `DESKMOVE.Rebase` and `DESKPAINT.Sync` accordingly: a changed screen
origin can invalidate a visible-copy destination without dirtying unchanged
local backing cells or discarding their completed model generation.

Exclude caret and pointer pixels from the bitmap. Remove the caret from screen
using its backing cell where valid; redraw overlays after visible repair.
Preserve title-only focus changes and repeated-click behavior. Initialization,
clear, unsupported geometry and display failure use bounded retained-model
rebuild or the existing screen fallback, with no false valid publication.
Fallback screen painting must not acknowledge unfinished backing work. No
storage may be released/reused before DMA completion or proven quiescence.

Keep scrolling correct initially by invalidating/rebuilding affected backing
rows after the model scroll; WB5 replaces that bounded fallback with a backing
blit. Do not retain this temporary full-row rebuild as a separate production
profile. Other console units and text-only presentations keep their existing
supported behavior; this bitmap belongs to the desktop Shell only.

Extend `tools/test_desktop_presentation.py` and `tools/test_cache_desktop.py` for
idle exposure with zero glyph redraws, partial and full coverage, typed edits,
clear, caret/focus, moves and menu overlap. Inject output between backing draw
and visible-copy completion; verify both latest model pixels and untouched
neighboring windows. Include initial/rebuild and selected display fault/lifetime
cases. Commit WB4 with scrolling optimization explicitly pending.

## WB5 Scroll and publish the backing image in batches

Adapt `console-batch-display.inc` and `console-bitmap-display.inc` so batch-copy
eligibility describes a synchronized backing surface, not an unobscured screen.
Retain bounded gathering, accepted-byte accounting, cancellation and fairness.
Scroll the backing surface with the existing overlap-safe `CopyStart` path,
clear new rows through backing fill, then render the batch's resulting dirty
spans. The specialized `VbxeScrollStart` currently accepts screen surfaces only;
do not send the backing surface through it or add a second async engine.
Advance backing generation only after the copy/fill/text sequence succeeds.

After a backing scroll, damage the visible viewport and copy its resulting
visible fragments from backing. Fully covered batches perform no screen copy.
Coalesce final spans/viewport repair rather than sending a copy per character.
Do not mix an old screen-scroll optimization with a newer backing model or let
later output overtake an unfinished batch. If a new model edit invalidates the
admitted scroll, rebuild from retained cells instead of replaying the stale
copy. Keep ordinary input service between bounded copy/render units.

Extend `tools/test_console_bitmap_scroll.py`,
`tools/test_console_batch_lifetime.py` and the desktop presentation fixture for
one/multiple-row scrolling, sustained short writes, partial/full coverage,
batch cancellation, clear/position controls, unit retirement and transfer
failure. Preserve source/destination guards and final output contents. Adapt
`tools/measure_console_batch_load.py` and the desktop measurement fixtures to
measure the backed desktop path; standalone bitmap results alone do not measure
this integration. Record visible/covered throughput and loaded button latency.
Commit WB5.

## WB6 Measure the combined desktop and package the demo

Run the frozen WB2 move cohorts and WB4/WB5 exposure/scroll cohorts on the final
build. Include Files and Panel over Shell, closing an overlapping window,
back-and-forth moves, and an external AES window underneath as a contract check.
Exercise physical pointer release as well as direct geometry requests; exclude
the user's drag duration from release latency. Include a hidden Counter model
change without drawing: later exposure must still deliver `WM_REDRAW`.

Keep Layers transaction checks, AES pixel/lifetime checks and console batch
checks focused and optimized. Add raw mode only for changed compiler-facing
boundaries. Run host checks and relevant generators with `--check`; no compiler
suite, full release matrix or hardware qualification is required. Reuse passed
checks whose inputs did not change and retain documented fixture limitations.

Refresh with `tools/build_demo.py --gem-desktop`, including OF816, pinned ROM,
matching system/work disks, notices and five-second autoboot. Exercise the exact
ZIP through Files, Panel, Counter, Text, menus, shell output and clean EXIT.
Record source/toolchain/artifact hashes, raw timings, accepted geometry,
memory deltas and missed gates in a history page and machine-readable evidence;
link them from this plan and the relevant indexes. Provide the launch command.
Distribute only the normal `exec816-demo.zip`, leaving intermediates and traces
in the development directory. Commit WB6 evidence and documentation.

## Memory budget and completion

| Reservation | Planned delta |
| --- | ---: |
| Fixed bank zero, including guards/alignment/unused capacity | 0 bytes |
| Bank zero per public Task | 0 bytes |
| Idle Task bank zero | 0 bytes |
| VRAM, introduced in WB3 | +40,960 bytes |
| Additional fixed upper-RAM metadata | Budget at most 256 bytes, including alignment |
| New per-Task/per-AES-client storage | 0 bytes |

Use existing scene rectangles, dirty spans, packet fields and batch state.
Reserve the metadata allowance for move completion ownership and the Shell's
surface/lifetime/progress state; report actual generated sizes and occupied
arena growth per slice rather than allocating 256 bytes speculatively. No new
stack, DP, CPU aperture, font bank or CPU copy of the bitmap is planned. Report
any required stack/arena growth explicitly and update this budget before it is
introduced. Code/image reservation growth is recorded separately from metadata.

Production VRAM becomes **416,256 / 524,288 bytes**, leaving **108,032 bytes**
unassigned and **108,000 bytes** after the existing diagnostic exclusion.
WB1/WB2 add no VRAM; WB4–WB6 reuse WB3's full reservation. This plan itself adds
no executable code or memory reservation.

Completion means all slices have development evidence, both new paths obey
completion/ownership rules, references describe actual behavior, and the final
demo and performance results are recorded. Functional completion alone does not
close a missed latency/throughput gate; list those separately rather than
claiming the whole performance goal achieved.

## Execution record

- WB1: accepted geometry and physical drag/resize proposals use even X/width;
  `wind_calc` retains unsnapped conversion semantics. Development checks: 459
  host tests (4 skips), optimized AES windows (268 checks) and cache (96 checks),
  with stack/domain guards intact. Reports: `build/window-backing/wb1-windows`
  and `wb1-cache`. Reserved bank-zero delta: 0 fixed, 0 per public Task, 0 idle;
  VRAM and additional persistent metadata delta: 0 bytes.
- WB2: completed external windows use the existing move transaction; geometry
  and coordinate epochs publish before AESCORE replies. Panel/form object roots
  follow accepted geometry without forcing repaint. Development checks: optimized
  Layers (60,184 checks) and AES cache (99 checks, exact moved pixels and genuine
  exposure delivery). Reports: `build/window-backing/wb2-layers`, `wb2-cache`.
  Timing gates remain for the combined comparison in WB6. Reserved bank-zero
  and VRAM deltas: 0; move continuation adds one 3-byte request pointer and one
  2-byte status in upper RAM (alignment recorded with final image metadata).
- WB3: reserved the fixed 40,960-byte bitmap; added explicit offscreen text/fill
  calls sharing the atlas uploader and fill producer. Packet stays 78 bytes;
  the private C/assembly text record grows by 2 stack bytes, with no reserved
  stack/DP growth. Development checks: 459 host tests (4 skips), raw and optimized
  drawing fixtures (172 checks each), exact backing/screen pixel oracles, owner
  admission, OS restoration and stack/domain guards. Reports: `wb3-drawing` and
  `wb3-drawing-raw` under `build/window-backing`. Reserved bank zero: 0 fixed,
  0 per public Task, 0 idle. No additional persistent CPU metadata.
