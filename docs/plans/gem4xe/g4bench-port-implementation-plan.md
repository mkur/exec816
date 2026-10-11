# GEM4XE benchmark port implementation plan

[GEM plans](README.md) · [C application profile](../../reference/c-program-loading.md) ·
[Application VDI](../../reference/gem-vdi.md#resident-application-workstations) ·
[AES](../../reference/aes.md) · [Timer](../../reference/timer.md)

Status: G4B1–G4B2 pass focused development checks; G4B3 remains pending.
See the [execution record](../../history/g4bench-port.md).

Port a small, useful subset of GEM4XE's `G4BENCH` as a loadable
`C:G4BENCH.APP`. Measure the drawing paths ordinary applications use, including
the VDI text uploader and AES widget glyph builder. Keep the benchmark separate
from renderer optimization: first obtain repeatable, correctly labelled results.
Implement and commit each executable slice separately.

## Source and boundaries

The inspected donor is `src/apps/g4bench.c` at GEM4XE revision
`fbfea9b0b1233a5d659d5ec583c63f863cceadfa` (0.11), also used by the
[calculator port](../../../ports/gem4xe/apps/calculator/inputs.json).
It is a single-file, resource-free application with eighteen tests, a windowed
report and a text-file report. `docs/phase59.md` explains its original timing;
`tests/emu/g4bench.py` and `g4bench_ref.json` provide its emulator observer and
historical regression reference.

Record the application revision, input hashes, notices and adaptation patches
under `ports/gem4xe/apps/g4bench/`. Prepare sources and build products under
`build/`, following the calculator's existing extraction/build convention.
Leave `~/atari/gem4xe` unchanged. Keep the separate AES/VDI extraction pins and
the compiler pins; this port does not require an upstream renderer refresh.
Preserve donor licensing and update the third-party licence map and packaging
notices. Do not place adapted donor code under the MIT examples grant.

Build through `tools/build_c_program.py` with the current Calypsi profile and
normal `main()` entry. No PRG/G4A binary loader, GEMDOS compatibility layer,
new renderer entry point or general benchmark framework is needed.

## First subset

Three donor workload families produce five measured rows:

| Row | Work performed | Adaptation and meaning |
| --- | --- | --- |
| Solid rectangles | Donor `t_solid` positions, colours and rectangle sizes; 50 operations per base pass | Use supported `v_bar` instead of `vr_recfl`; omit unsupported pattern-style setting. Name the row `solid bars`, and identify the changed call. |
| Plain text, even X | Donor text string and colour cycling, fixed 8×8 face; 50 strings per base pass | Use the supported replacement mode and baseline metrics. Exercises the complete-cell VDI uploader. |
| Plain text, odd X | The same string, count, colours and visible extent, shifted one pixel | Exercises the alternate glyph path without changing the amount of text. This is an Exec diagnostic variant. |
| Plain text, clipped | The same text with a fixed clip cutting the first and last cells and one vertical edge | Exercises partial-glyph drawing. Record exact clip and visible pixels; its reduced pixel area makes it a separate workload. |
| Five-object dialog | Donor `t_dialog` tree, labels, button flags and position sequence; 20 tree draws per base pass | Adapt flat `ob_spec` pointers and remove unsupported `OUTLINED` state. Uses ordinary `objc_draw`, including widget text and background/border work. |

Retain the donor string byte-for-byte and record its actual length rather than
assuming the donor label “40 characters” is a length guarantee. Preserve donor
iteration order across scheduling groups. Repeat complete base passes when
longer timing intervals are needed. Exclude initial canvas clearing, font warmup
and result formatting from measured intervals. Attribute changes within the
donor workload remain measured.

The public VDI binding currently accepts only replacement writing mode and
one fixed font. The donor's plain-text test uses transparent text; it therefore
cannot be presented as an unchanged test or a direct glyph-only comparison.
AES labels exercise transparent widget text, but a whole dialog also measures
object traversal, clipping, fills and display ownership. Keep those results
separate.

Defer the other fifteen donor tests:

- Lines, patterned fills, circles, ellipses, polygons and rounded boxes require
  public VDI operations/attributes outside the application subset.
- Bold/underlined text and varying heights require text attributes/fonts that
  the binding does not expose.
- Screen copies, memory round trips and icons require the public MFDB/raster
  interfaces. Backend capabilities alone do not make these application APIs.
- Opening a second window while retaining the report window conflicts with
  the current one-window-per-registration contract. Repeatedly replacing the
  report window would be a different benchmark; leave it for later.
- Mandelbrot uses unsupported polylines and primarily measures arithmetic.
  Do not substitute bars or turn it into a new CPU test in this port.

List deferred families and reasons in the report. They are unsupported results,
never zero-time successes. Do not expose missing VDI features just to fill out
the table, call the private packet renderer, or add a composite GEMBench score.

## Application and timing

Use one movable, closable window and one virtual workstation. Launch from Files
or `RUN C:G4BENCH.APP`; close an existing GEM application first if the desktop
has no free layer. Do not enlarge the Task, layer or AES-registration pools or
autostart the benchmark. Return starts a run or reruns the completed report;
Escape/close stops it at the next drawing-group boundary.

Handle redraw, move, top and close messages with the usual event loop. Paint
results through visible rectangles and retain results across ordinary exposure.
For timed work require the fixed canvas to be fully visible. A move, resize,
coverage change or loss of benchmark focus during a sample invalidates that
sample; display the reason and let the user rerun it. Check geometry/visibility
at UPDATE boundaries so a covered no-op draw cannot produce a good score.
This is benchmark validity checking, not new renderer validation.

Use a fixed 480×160-pixel work canvas, positioned with the existing window
geometry calls. Record its actual coordinates and dimensions. The three text
variants explicitly choose X parity and clip; do not let window position choose
the measured path accidentally. Leave the pointer visible under existing cursor
ownership; park it outside the canvas for controlled runs. Omit donor
`graf_mouse`, `vq_extnd`, font/effect setters and GEMDOS calls rather than adding
successful no-op shims. Workstation inquiry already supplies the colour count.

Replace `Tgettimeofday` with an application-private adapter over existing
`timer.device`, `UNIT_VBLANK`, `TD_READCLOCK`. Its resolution is one VBI:
50 Hz PAL or 60 Hz NTSC, not GEM4XE's approximately 4 kHz clock. No new timer
unit, interrupt source, hardware-register clock or kernel service is proposed.

The loadable C import table currently omits device I/O. Add only these existing
public functions to [c-program.json](../../../abi/c-program.json):
`CreateMsgPort`, `DeleteMsgPort`, `CreateIORequest`, `DeleteIORequest`,
`OpenDevice`, `CloseDevice` and `DoIO`. Advance the C application ABI version
and rebuild the provider and all packaged applications together. Do not retain
an old import profile or export an AES-private clock helper.

Open one port/request/device binding before measurement. Reuse the idle request
for quick clock reads and close/free it in reverse order on every exit path.
No alarm, asynchronous request or per-iteration allocation is needed. Handle
ordinary resource exhaustion, clock errors and file errors explicitly.

Timing procedure:

1. Perform an untimed warmup, then calibrate by doubling the number of complete
   base passes until the batch spans at least two nominal seconds
   (`2 * ticks_per_second`). Cap calibration at 4,096 primitive/tree operations
   per sample. If the target cannot be reached, label the result low-resolution.
2. Run three measured samples with that same operation count. Read the clock
   only at each sample's start/end; retain the full start/end tick words and
   rate and subtract them correctly across a low-word rollover. Conversion and
   division belong in reporting, after measurement.
3. Draw at most four bars/strings, or one complete dialog, per UPDATE acquisition.
   Release UPDATE and poll/process application events between groups. Never
   retain UPDATE for the entire benchmark or block in an event wait while
   holding it. The workload's iteration position continues across groups.
4. Include UPDATE acquisition/release, event polling, scheduling and drawing
   completion in elapsed time. These are application-throughput measurements.
   Exclude canvas preparation and progress/report drawing. Existing synchronous
   draw completion supplies the endpoint; do not add a benchmark-only fence.
5. Publish raw elapsed ticks and actual operation counts for each sample,
   plus median approximate milliseconds per operation. A long batch improves
   average resolution; it does not create a microsecond clock. Do not report
   per-click latency, p95, or falsely precise `g4b_us` values from these samples.

Give a run a bounded operation count and the observer a completion timeout.
Clock failure or cancellation yields an error/cancelled row, never a partial
sample labelled complete. Keep partial completed rows available for inspection.

## G4B1 — Pinned loadable shell and clock

Add the source manifest, preparation patches and a small dedicated builder
under `tools/`, reusing the existing extraction and C-image builders. Adapt
startup, window/workstation cleanup, the event loop and the report shell. Add
the seven imports and timer adapter. Keep model/results in the application's
upper-memory image; this slice can report that measurement cases are pending.

Deliver a loadable app that opens, redraws, obtains monotonic clock samples,
closes and reloads cleanly. Cover timer-open failure and cancellation cleanup
with the smallest existing emitted-app fixture. Verify the new imports resolve
through the normal Process loader and keep the builder's relocation checks.
No separate renderer-baseline project or full qualification run is needed.

## G4B2 — Five workloads and honest reports

Enable the selected donor functions and three text variants. Add bounded
grouping, calibration, repeat samples and validity/cancellation handling. Use
a small fixed table of results and statuses; no plugins or configurable test
graph. Keep adapted tests and skipped donor tests identifiable by stable names.

Render the report in the app and save it after measurement to
`WORK:G4BENCH.TXT` with existing DOS `Open`/`Write`/`Close`. Report a failed or
short write without losing on-screen results. Saving and formatting are outside
all timings. Include workload version, adaptations, canvas/clip, operation
counts, clock rate, raw ticks and sample statistics. Development observers may
read the app's private result/phase symbols, following existing loaded-app
symbol relocation; do not add a production measurement service.

Focused development coverage:

- Independent pixels for bars, complete even/odd text, partial clipping and
  the five-object tree. Confirm the intended visible work actually occurred.
- Correct operation counts and tick conversion, including a low-word rollover,
  skipped rows, low-resolution batches and cancellation.
- Close/reload, exposure and invalidation on coverage/movement; normal desktop
  operation resumes after every completed or cancelled run.
- Saved report contents and write failure, plus the existing stack/domain
  guards. No renderer or scheduler changes belong in this slice.

## G4B3 — Repeatable observation and demo package

Add a small runner using the existing emulator launcher and loaded-Process
symbol observer. Launch the same normal APP through the shell, start it through
normal input and read its completed results. Store raw results and a screenshot
with image/compiler/ROM/emulator hashes, VBXE/CPU/TV settings, app provenance,
canvas, cursor position and other running applications. Normalize report text
line endings before host parsing; preserve binary/ATASCII data unchanged.

Establish the first Exec baseline with only the benchmark drawing, the shell
idle, and other animated GUI clients closed. Make one separate run beside the
counter as a coexistence check; label that load and do not merge its numbers
with the idle baseline. No full load matrix or inherited ten-percent failure
threshold: GEM4XE's reference measures different semantics and a different
system. Preserve measurements first; set regression tolerances only after
observing repeatability.

For a later direct GEM4XE comparison, run the same adapted workload and clock
accounting boundaries on a pinned donor image: same replacement text, font,
canvas, clipping, grouping and operation count. Its existing asynchronous flush
must be accounted for before treating an endpoint as completed drawing. Original
donor scores may be shown as historical context but cannot establish an Exec
speed ratio. A matched donor run is separate from this first port.

Package `C:G4BENCH.APP` through `tools/build_demo.py --gem-desktop`, including
OF816, matching system/work disks, ROM and notices. Keep the five-second default
shell/prime autoboot. Add launch/run/stop instructions to the application guide
and concise demo guide. Ship only the normal `exec816-demo.zip` payloads; keep
manifests, traces, provenance and test output under the development directory.
Record implementation evidence in `docs/history/` and update its index.

The completion gate is all five rows doing the intended drawing, reports
agreeing with observed counts, clean cancellation/reload and a usable exact
demo package. This establishes a development benchmark, not hosted-system or
real-hardware qualification. Do not claim a speedup as part of the port.

## Budgets and validation scope

Expected additional reserved bank-zero bytes for every slice: **0 fixed,
0 per public Task and 0 private-idle**. Reuse an existing Process/stack/DP slot.
Report actual reservation deltas, including guards, alignment and spare capacity,
along with the C image, upper-heap requests/results, provider growth and stack
margin. No VRAM reservation is needed. If stack headroom proves insufficient,
measure the required increase and its per-task reservation rather than forcing
a broad refactor solely to avoid stack growth.

Implementation uses development-tier checks for the new app and import boundary.
Use optimized emitted code for workloads and timings; use a small raw/optimized
probe only if new compiler-facing ABI behavior needs it. Do not rerun compiler
qualification or full Exec matrices for the port. This plan itself changes only
documentation and creates no benchmark results.
