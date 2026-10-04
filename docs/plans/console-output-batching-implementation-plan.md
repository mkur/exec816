# Console output batching implementation plan

[Plans index](README.md) · [Roadmap](../roadmap.md) ·
[Console contract](../reference/console.md) ·
[Asynchronous scrolling](../reference/display.md#asynchronous-screen-scrolling)

Status: OB1–OB2 implemented and passed development checks; OB3–OB5 pending.
See the [OB1 evidence](../development/console-output-batching-ob1.json) and
[OB2 evidence](../development/console-output-batching-ob2.json). The batch
context is 44 upper-RAM bytes; production batching is not enabled yet.
Preserve the current interactive
echo path. This work targets bulk output such as `CAT LONG.TXT` in the bitmap
console. Implement and validate each executable slice, then commit it before
starting the next.

## Objective and existing evidence

Consume several lines from an existing WRITE request into the circular retained
model, then present them with one multi-row copy/fill launch and bounded text
drawing. CAT already reads and writes 512-byte chunks: it needs no buffer-size
change. A display batch may end anywhere inside that chunk, including mid-line.
No additional 512-byte staging buffer is needed.

Reuse the completed trace of the shell-only 80×30 demo. The
[baseline record](../development/console-output-batching-baseline.json) preserves
its artifact hashes, actual development emulator pin, accounting boundaries and
selected measurements. `LONG.TXT` contains 23,872 bytes and 768 LF characters;
each run performs 48 CAT reads including EOF and 47 writes.

| Existing workload | Command elapsed | CAT Read elapsed | CAT Write elapsed | Physical sectors read |
| --- | ---: | ---: | ---: | ---: |
| Cold `CAT LONG.TXT` | 54.154 s | 26.144 s | 23.861 s | 218 |
| Cached `CAT LONG.TXT` | 26.670 s | 1.457 s | 24.374 s | 0 |
| Cached `CAT LONG.TXT >NIL:` | 2.116 s | 1.226 s | 0.063 s | 0 |

The cached console run spends 91.4% of command time inside CAT's Write calls.
Those intervals contain 12.922 s charged to the console Task, 8.260 s idle,
2.787 s in native IRQ/NMI and 0.406 s in other Tasks. These are disjoint
categories. Nested routine totals, such as text drawing, model editing and
scroll setup, must not be added to that partition.

The cached command window contains 769 scroll launches. Its average
launch-to-completion-IRQ interval is 14.535 ms, an upper bound on hardware
completion time. One full-screen single-row scroll copies 74,240 bytes and
clears 2,560. A four-row scroll copies 66,560 bytes and clears 10,240, replacing
four copies totalling 296,960 bytes with the same total clear area. This reduces
VRAM work as well as setup, completion and worker-turn overhead; it does not
predict a fourfold improvement in whole-command time.

The command boundary is ShellDispatch entry through return, including loading
and unload, excluding typing and the following prompt. Outstanding echo may
overlap it; 769 is an observed launch count, not a required correspondence with
768 LF characters. Preserve that boundary for comparison and add a separately
labelled final-presentation boundary. Do not substitute host profiling duration
for guest elapsed time or interpret the NIL result as an attainable speedup.

There is no new baseline run or separate baseline measurement slice. Retain
`build/cat-long-trace/` and `build/demo-bitmap-shell/` before rebuilding. Recover
additional counters from saved traces where possible. Run an old-image case
only if a necessary comparison, such as loaded input latency, is missing.

## Scope and initial bounds

Keep batching in the existing console worker and display driver. Exec messages,
signals, request ownership and the retained blitter completion contract remain
the coordination mechanism. Add no Task, semaphore, console-specific kernel
operation, polling loop or new timer source. Keep filesystem buffering, the
font, caret optimization and standard text-console behavior outside this work.

Start conservatively with long writes (`io_Length > SOURCE_QUANTUM`, currently
64 bytes) to a fully visible, synchronized bitmap view whose cursor is on its
bottom row. Initial screen filling, hidden or clipped views, stale presentation
and height-one views use the existing bounded presentation path. This targets
steady scrolling without making every console operation transactional.

The fast path accepts printable runs and LF, including automatic right-edge
wrap, using the existing terminal semantics. Before TAB, CR, BS, DELETE, FF or
another control, flush the accepted prefix and process that byte normally.
Preserve the current replacement of high-bit printable bytes. CRLF and controls
split across WRITE boundaries must retain their current meaning.

Initial limits, to be checked against measurements in OB5:

| Limit | Initial value |
| --- | --- |
| Source bytes consumed per worker turn | Existing 64-byte quantum |
| Logical row recycling per worker turn | At most one row |
| Scroll rows accumulated per batch | `min(4, view.height - 1)` |
| Source bytes accumulated per batch | At most 256 |
| Accumulation turns per batch | At most four |
| Text presentation per pass | Existing four-row / 160-cell budgets |

Flush on the first limit reached, request end, a control barrier, cancellation
or pending presentation/lifetime work. If the existing VBI tick has advanced
since accumulation began, flush on the next worker turn before accepting more
bytes; use wrapping subtraction. This limits deliberate gathering time without
adding a timer. Preemption may still delay the worker, so it is not a hard
wall-clock latency guarantee.

Never wait for more input or a subsequent WRITE to fill a batch. Do not merge
different requests or instances. A one-character or other short write keeps its
existing bounded present-before-reply behavior. New short output waiting behind
bulk output requests an early flush at the next service opportunity, subject
to FIFO order and any already active DMA.

## Presentation and retained-state protocol

Use one worker-owned batch context, associated with a live unit, view generation
and model generation. Resolve and borrow the instance on each turn. Do not keep
a borrowed cell pointer across Yield/Wait or use a later instance that happens
to reuse the unit. The active write remains associated with this instance while
its source is being consumed.

1. **Begin.** Require no pending blit, no outstanding damage and matching
   presented/model generations. Remove the caret using the old model before
   making edits. Capture the association and initial cursor position.
2. **Accumulate.** Feed a bounded source prefix. Recycle each logical row once
   through the existing circular model and clear its reused physical character
   row. Increment `io_Actual` exactly once for consumed bytes. Record changed
   spans without dirtying and cleaning the whole viewport for each LF.
3. **Submit.** For `N > 0`, issue one upward copy of `(height - N) * 8` pixel
   rows plus a bottom fill of `N * 8` rows. For `N = 0`, proceed directly to
   bounded text presentation. The worker may return while the blitter runs.
4. **Complete.** Consume the existing operation ID and durable IRQ/watchdog
   result. Do not rotate the character origin again. Copy/fill completion
   acknowledges those pixels only; changed text remains pending.
5. **Paint.** Redraw surviving changed spans in their final logical positions,
   using the circular model and current text budgets. Advance the fully
   presented generation and restore the caret only when this damage is settled.
   Then release the batch association and allow a new batch.

Do not copy the current `BitmapComplete` assumption that a successful scroll
can `Clean` the entire instance. That is valid only when the copied pixels
already contain all the accepted text. New text in this batch has not yet been
drawn and must survive completion as damage.

For the bottom-row fast path, use at most five changed-span entries: the row
at batch start and the rows introduced by up to four scrolls. Each stores a
half-open column interval. Translate these entries once when flushing: entry
`i` ends at logical row `height - 1 - N + i`. Empty spans need no glyph work;
the bottom fill handles newly blank cells. Keep conservative full damage for
fallback, without carrying a second character model or repainting every blank
cell on the ordinary batch path.

For example, starting at the blank bottom row of an 80×30 view,
`one\ntwo\nthree\nfour\n` causes four scrolls. At completion, `one` belongs on
zero-based row 25, above the four cleared rows 26–29. Redrawing only the exposed
strip would lose it. Include that case, an initially partial bottom row and
right-edge wraps in the independent pixel oracle.

Share printable/control parsing and circular row recycling with the canonical
core implementation. Introduce explicit internal damage accumulation helpers
where needed; do not duplicate the terminal parser or retain two selectable
implementations. Standard console callers retain their existing semantics.

### Input, ordering and lifetime

The batch context owns a bounded display continuation, not an uninterrupted
worker turn. Check cancellation, controls, input and request arrival between
quanta. Input capture and READ replies must remain serviceable in accumulation,
DMA and repaint phases, including for another instance. Other writes and
presentation mutations wait for a safe batch boundary; round-robin service
resumes there. Account for that bounded delay in fairness tests.

Once submitted, keep the current gate over model edits and dependent drawing.
If only completion can unblock output, Wait on existing completion/input/control
signals. A queued but blocked WRITE must not keep the worker yielding. No
batch-specific per-turn hardware poll is introduced.

At request end or AbortIO, commit any already accepted logical scroll and
publish the remaining presentation work before replying. The batch context
must then be self-contained in retained state, with no request/source pointer
needed after reply. A long WRITE can still finish before all its pixels are
visible. Preserve the existing short-write bounded pass, accepted-prefix error
reporting and exactly-one-reply contract; never replay or roll back accepted
bytes. Cancellation stops further source consumption at the next service turn.

Before hide/show, focus, supported geometry changes, destroy, Stop or owner
retirement, settle or invalidate the batch under the existing control/lifetime
protocol. With no DMA active, invalidation can discard the optimization and
publish full damage from the already updated model. With DMA active, prove
completion or quiescence before changing geometry or freeing storage. Defer
PRESENTING adoption as today. Stale associations, quiesced failure and
reset-required retention must preserve their existing recovery rules.

## Drawing contract and storage

Generalize the existing asynchronous screen-scroll operation, keeping its
`VbxeCopy` descriptor and public signatures. Define exposed height as
`copy.sourceY - copy.destinationY`: require a positive multiple of eight pixels,
matching source/destination X, and bounds covering both copy and exposed fill.
Keep the existing framebuffer, pitch, even-X/width and ownership restrictions.
Check subtraction before use and all extents before uploading records. Zero
copy height permits a fill-only list when that exposed strip fits the screen.

The copy destination starts at the view top; the fill starts immediately after
the copied destination rows. The list still contains at most two BCB records,
with one launch, one pending operation ID, one original deadline and one
completion notification. Busy rejection must leave the existing list and
caller output ID unchanged. Arbitrary-list and synchronous draw limits remain.

The 70-byte private bitmap packet already contains the required rectangle
coordinates. Keep its layout; revise its generated contract version for the
expanded SCROLL semantics and rebuild both sides together. Update the shared
GEM drawing contract and native validation rather than adding a console-only
hardware bypass or a second public scrolling API.

Budget one reusable context of at most 64 bytes in upper resident RAM, including
identity, phase, limits and five span entries. No per-instance allocation,
character buffer growth, additional Task or VRAM surface is proposed. Prefer
the existing upper-RAM globals arena; verify remaining capacity in emitted
build reports before placing the context. Do not append fields into the packed
Presentation record without accounting for subsequent metadata offsets. If the
context cannot fit, revise the upper-RAM layout explicitly before integration.

Target **zero additional reserved bank-zero bytes**, fixed and per Task. For
each slice report actual reservation deltas for fixed state, root/kernel,
public Tasks and idle, counting guards, alignment and unused capacity. Also
record upper-RAM payload/reservation changes, emitted code size and stack peaks.
Existing C BCB staging, the 2,560-byte worker stack and DP reservation must not
silently grow. Use the recorded compiler pin; fix compiler defects in actionc.

## Executable slices

### OB1 Generalize the copy/fill primitive

Extend `VbxeOwnerScrollStart`, the GEM adapter and private bitmap binding to
accept the checked row delta. Keep production callers at one row in this slice.
Update generated contract inputs/outputs, reference documentation and fixtures
together. Preserve the existing trace and baseline record; do not remeasure it.

Exercise one-, two- and four-row copies, subrectangles with nonzero origins,
maximum legal delta, fill-only height, invalid/overflowing rectangles and odd
alignment. Compare exact pixels and unchanged neighbors against an independent
copy/fill oracle. Verify busy rejection, IDs, IRQ completion, original timeout,
MEMAC closure, guards and ownership through emitted code. Commit the working
general primitive with its focused evidence.

### OB2 Add bounded retained batch state

Implement the small context, span accumulation and shared core edit helpers.
Exercise them through an emitted fixture before enabling production batching.
Make begin/flush/invalidate rules explicit, including the zero-scroll case.
Keep the ordinary core entry points working through the same parser and row
recycling implementation.

Compare against a simple linear host terminal after each accepted prefix,
including `io_Actual`, cursor, circular origin, logical characters and final
damage coverage. Cover 64/65-byte writes, 256-byte boundaries, split lines,
blank lines, partial first/last rows, automatic wrap, high-bit replacement,
control barriers and more than two complete ring revolutions. Check multiple
widths/heights and character rows crossing CPU bank boundaries. Use raw and
optimized NIR; report context size, arena fit and stack/memory deltas. Commit
only after the existing ordinary core cases still pass.

### OB3 Integrate the worker continuation

Enable the long-write fast path and flush limits in `WriteQuantum` and the
bitmap display continuation. Extend completion to retain final text damage.
Service input between quanta, retain the one-in-flight gate, and preserve Wait
when no unblocked work remains. Short writes continue to use the current
present-before-reply path; no production feature toggle remains after migration.

Run focused raw/optimized bitmap, scroll, reply and fairness fixtures. Assert
several eligible logical scrolls produce one multi-row list, every accepted
character appears at the right final location, no origin update occurs at IRQ
adoption, and the row/cell/source budgets hold. Cover early flushes, a final
partial request, control barriers, ordinary text-console output, READ/input
during DMA, cancellation and Stop at each new phase. Commit the functioning
integrated path with these basic lifetime checks already passing.

### OB4 Exercise interleavings and recovery

Extend the existing bitmap control/fault, window and cancellation cases across
accumulation, submission, completion and partial repaint. Include generation
mismatch, ring wrap, hide/show, focus, supported view geometry, PRESENTING
deferral, destroy/reuse, queued writes from another instance and last-WRITE
reply followed immediately by Stop. Height one and clipped views must use the
ordinary path without adopting batch state.

Inject completion before Wait, a coalesced/stale signal, timeout, a quiesced
failure and an unquiesced failure. Check accepted prefixes, one reply, no
post-reply source access, no freed storage referenced by completion, and the
existing reset-required park. Exercise physical keyboard/BREAK and SIO while
batch work is pending; verify READ progress and ordinary peripheral deadlines.
Keep native context, stack/domain guards and OS restoration assertions. Commit
the focused integration evidence; this does not require a full platform matrix.

### OB5 Measure, tune bounds and refresh the demo

Use `tools/measure_bitmap_cat.py` on the final shell-only image with the same
file, 512-byte CAT writes, actual ROM/emulator pin, 4 MiB PAL ×8/VBXE machine
and disk settings as the saved baseline. Repeat cold, cached and cached-to-NIL
runs. Derive new markers from emitted code and update profiler hooks as needed;
never reuse old addresses after rebuilding.

Report command and final-presentation elapsed time, read/write intervals,
console CPU, idle and IRQ time, logical scrolls versus hardware launches,
copied/cleared bytes, batch-size distribution, flush reasons and completion
delay. Quantify retained preparation and repaint overhead without adding nested
routine totals. Validate final model/pixels and repeat without trace observation
on the same image to check observer effects.

Require fewer launches and less VRAM copy traffic per logical scroll, lower
cached CAT elapsed time and lower console CPU. Investigate a **2× cached CAT
throughput improvement** as a target, not a claim or a reason to increase work
quanta without latency evidence. If missed, retain the measured result and mark
that target open; do not describe the target as achieved. Cold disk wait is a
separate cost and may dominate the improved cold run.

Measure unloaded letter/Return echo and input/READ/BREAK latency during bulk
output, including another console instance. Compare representative worst cases
and complete worker-turn CPU against the preserved image; run only missing
baseline input cases. Tune the row/byte/turn limits downward if batching worsens
input service, cancellation or fairness. Preserve current short-write behavior
and report any regression explicitly. The existing 4 ms worker / 20 ms scroll /
40 ms visible-input goals remain open unless independently demonstrated.

Save compact OB evidence in `docs/development/`, add an indexed history record
and update the console/display reference, plan status and roadmap. Refresh the
requested shell-only bitmap demo through `tools/build_demo.py
--bitmap-shell-only`, retaining OF816 and five-second autoboot. Validate its
matching system disk, pinned ROM, checksums, notices and clean
`exec816-demo.zip`; keep traces and intermediates outside the ZIP. Commit this
final slice. GitHub publication is separate from this implementation plan.

## Validation and completion

Use the [development tier](../contributing/testing.md): host checks, generated
definition checks and focused emitted-code tests for changed behavior. Relevant
fixtures include `test_console_core.py`, `test_console_bitmap_scroll.py`,
`test_console_bitmap.py`, `test_console_reply.py`, `test_console_fairness.py`
and bitmap control/fault tests under `tools/`. Cover raw and optimized NIR for
changed core, bridge and worker behavior. Preserve the pinned C/native drawing
checks and interrupt/lifetime cases relevant to each slice. Normalize host text
line endings while preserving binary and ATASCII fixtures.

Completion requires committed slices with exact final pixels and retained
contents, bounded input-aware processing, unchanged request/lifetime contracts,
measured bulk-output improvement and explicit memory accounting. Development
results and a refreshed demo do not constitute release qualification; reserve
full matrices for a release, explicit qualification claim or request.
