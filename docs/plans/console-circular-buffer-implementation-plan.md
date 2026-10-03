# Circular character buffer implementation plan

[Implementation plans](README.md) · [Console contract](../reference/console.md) ·
[Instances and windows](../reference/console-windows.md) ·
[Blitter IRQ measurements](../history/blitter-completion-irqs.md)

Status: CB1 complete, 3 October 2026; CB2–CB4 pending.
[CB1 development evidence](../development/console-circular-buffer-cb1.json). Replace the retained console's character-row
copy with a circular row origin. Keep one existing allocation per instance and
clear only the recycled bottom row when scrolling. Implement in executable
slices, committing each slice after its focused development checks pass.

This reduces CPU preparation before drawing. The framebuffer remains linear:
a synchronized bitmap scroll still submits one rectangle copy and exposed-strip
fill in one VBXE list, then waits for its existing completion signal/watchdog.
The ring contains the current screen's characters; it does not add scrollback.
The latest isolated whole-scroll measurements are about 32.5 ms. Reuse the BI5
baseline and its saved retained-edit timings; do not repeat the baseline suite.
Retained-edit timings include damage bookkeeping, so they are not a measurement
of the character copy alone.

## Current path and scope

[`CONSOLECORE.EditQuantum`](../../lib/console/consolecore.act) currently moves
`count-width` bytes toward the start of `instance.cells`, fills `width` spaces
at the end, marks the model dirty and completes OP_SCROLL. An 80×30 scroll moves
2,320 bytes and clears 80; a 40×24 scroll moves 920 and clears 40. OP_CLEAR fills
the whole allocation. Both operations remain preemptible.

The producers and consumers assume that logical cell zero is allocation byte
zero. These assumptions occur in printable Feed runs, presentation row spans,
text cursor reads, bitmap caret restoration and several direct fixtures/host
snapshots. They must migrate together. Allocation, extent checks and FreeMem
continue to use the unchanged allocation base and byte count.

Keep terminal controls, accepted-byte accounting, request replies, cancellation,
damage ages/generations, presentation budgets and instance lifetime unchanged.
Keep the existing worker and all input, drawing and pending-model gates. This
work changes no Exec policy, public device command, producer, drawing packet,
font, VRAM layout, scheduler priority or ownership validation boundary.

## Representation and access

Append a `CARD cellOrigin` to the private Instance record in
[`abi/console.json`](../../abi/console.json), then regenerate
[`consoletypes.act`](../../lib/console/consoletypes.act) and the native layout
through [`generate_console.py`](../../tools/generate_console.py).
`cellOrigin` is a **byte offset** from the allocation base to logical row zero.
Using a byte offset permits mapping with an addition and one conditional
subtraction, without division or multiplication in the character loop.

Maintain these invariants for an initialized instance:

- `count = width * height`, with the existing admitted bounds and exact extent.
- `0 <= cellOrigin < count`; the origin is a multiple of `width`.
- `cells` is always the original allocation pointer, including after wrap.
- `row`, `column`, `lineStart = row * width`, damage row numbers and bitmap
  cursor indexes remain logical coordinates.
- Every logical row occupies one contiguous physical span of `width` bytes.
  The ring wraps between rows, never inside a row.

For an admitted logical index `i` in `[0,count)`, use:

```text
physical = cellOrigin + i
if physical >= count:
    physical -= count
address = cells + physical
```

The intermediate offset is below 4,800 at maximum geometry and fits a CARD.
The final pointer addition must use full far-address semantics, preserving
carry across a CPU bank boundary. A row may cross a 64 KiB CPU bank even though
it does not cross the ring boundary. Keep the existing validated memory helpers
and drawing source checks for that case.

Add a small shared logical-offset/row-address helper in CONSOLECORE for trusted
console callers. Its documented precondition is an initialized instance and an
in-range logical offset; it is an ordinary module helper, not a kernel service.
Preserve checked admission boundaries and do not repeat ownership/extent checks
for every character. Initialize the new field in Init and migrate hand-built
fixture records explicitly; accidental zero-filled storage is not initialization.

Resolve Feed's physical start once per printable run, then advance the pointer
within that row. Keep its logical start separate for column and damage updates.
Resolve presentation sources once per row/span, retaining the 32-glyph batches
and current row/cell budgets. A small mapping helper must not turn into a
per-glyph call, modulo operation or linearization copy. Inspect emitted raw and
optimized code and measure any extra call cost.

For example, physical rows `[A, B, C]` with origin zero become logical
`[B, C, blank]` after clearing physical A and advancing the origin by one row.
The allocation remains `[blank, B, C]`. A full redraw traverses B, C, then A;
the blitter continues to copy its ordinary rectangular pixel source.

## Edit and presentation protocol

For OP_SCROLL, under the same existing instance borrow:

1. Preserve the old origin, identifying the row being recycled.
2. Fill that physical row with exactly `width` ASCII spaces.
3. Advance `cellOrigin` by `width`, wrapping to zero at `count`.
4. Preserve the logical cursor/lineStart behavior. Use the existing full-model
   Dirty call to update generation and damage age, then publish OP_IDLE.

Height one naturally clears its only row and wraps to origin zero. The fill
and origin update form one existing logical-edit quantum: no explicit Yield,
Wait or second edit continuation is added. Ordinary IRQs/preemption remain
enabled. Worker/presentation borrowing already excludes concurrent model
readers and writers; interrupt handlers never access the cell ring. Retain that
protocol rather than adding a long Forbid or SEI around the edit.

For OP_CLEAR, fill the original allocation once, then reset `cellOrigin` to
zero within EditQuantum. Do not reset it as soon as FF is parsed: cursor removal
must still resolve the old displayed cell before the edit commits. Init starts
with origin zero. CMD_CLEAR remains an input-buffer operation and does not
reset or erase this model.

Keep `damageFirst`, `damageEnd` and `dirtyRows` indexed by logical row. Continue
marking the whole logical screen dirty on scroll. This conservative fallback
is required for hidden, clipped, unsynchronized or invalidated presentations;
marking only the exposed bottom row would leave those views stale. Dirty
bookkeeping remains O(height), but character movement becomes an O(width)
fill. Rotating damage arrays or changing generation policy is separate work.

Update [`consoledisplay.act`](../../lib/console/consoledisplay.act) as follows:

| Consumer | Required interpretation |
| --- | --- |
| Cells in both backends | Logical damage row and screen destination; mapped physical character source. |
| Text Cursor | Read the underlying glyph through the mapping; preserve screen-address `previousCursor` and saved `cursorCell`. |
| Bitmap RemoveCursor | Keep `previousCursor` logical for X/Y calculation; map that logical cell only for its character source. |
| CursorPosition, view.index and runnable checks | Keep existing logical indexes; a physical origin is never a screen coordinate. |
| Clear, startup and teardown | Use the allocation base; never free a rotated pointer. |

The text backend's physical screen move remains necessary. The bitmap backend
also retains its current physical copy/fill geometry. Neither operation copies
from the character ring.

In [`console-bitmap-display.inc`](../../lib/console/console-bitmap-display.inc),
remove the cursor and establish synchronization before the logical edit,
commit the ring scroll once, then retain the resulting model generation for the
existing asynchronous launch. Never advance the origin again at completion.
While DMA is pending, preserve the existing gate over model writes, echo,
caret, drawing and presentation controls. Input capture, request admission and
READ replies continue normally. No mapped row pointer may survive a worker
borrow across Wait/Yield.

Matching completion may Clean the damage as today. A mismatched view/model,
PRESENTING deferral, hide/show or fault follows the existing generation and
lifetime rules; fallback redraw reads the current logical row order through
the mapping. AbortIO preserves already accepted bytes and an already committed
origin change. Stop and destruction still settle DMA before releasing storage.

## Storage and interface accounting

The proposed appended CARD occupies offset 198 and grows Instance from 198 to
200 bytes. The default instance starts at resident offset 160; its new end at
360 still precedes Presentation at 362. The existing 880-byte console metadata
reservation should therefore remain unchanged. Validate these bounds through
the generator and emitted layout fixture, including Instance/cell extent overlap
rejection. Update allocations and frees through the generated INSTANCE_SIZE.

Additional instances request two more upper-RAM record bytes each. Record the
actual allocator charge after rounding, rather than assuming its delta is two.
Character allocations remain exactly `count` bytes: no spare row, row-pointer
table, second model or temporary full-screen buffer is needed.

Target **zero new reserved bank-zero bytes**, fixed, root/kernel, each public
Task and private idle, counting guards, alignment and unused capacity. Report
this for every slice, alongside emitted code growth, upper-RAM payload and
reservation changes and stack peaks. Rebuild callers of the private record;
maintain one implementation. Public IOStdReq, the display ABI and the 60-byte
bitmap packet are unchanged by this representation change.

## Existing measurement baseline

Use the completed [BI5 measurements](../development/blitter-irq-bi5.json) as the
before-change baseline. They already cover isolated/repeated scrolling, loaded
input phases, worker turns, IRQ cost, pixels and same-image unobserved replays.
The saved loaded results also contain CONSOLECORE.EditQuantum (`model_edit`),
Feed and Cells CPU charges and entry/return markers in their observed traces.
These distinguish retained editing from BitmapEdit's cursor and drawing work.

Retain the BI5 images, pins, result hashes and traces before implementation:

- `build/blitter-irq/bi5-scroll/results.json` and its observed trace/replay.
- `build/blitter-irq/bi5-loaded-0/results.json`,
  `bi5-loaded-3547/results.json` and `bi5-loaded-14188/results.json`, with their
  `observed-trace.log` files and replays under the same parent directory.

For example, phase zero records 44.25 ms of retained-edit CPU across nine calls
within complete measured worker turns. Preserve that scope; do not divide it
by all ten workload scrolls or label it pure memory-copy time. Extract any
additional available breakdown from saved traces. Separate scroll/clear samples
where the existing boundaries allow it.

There is no new baseline execution or separate baseline commit. If a necessary
comparison cannot be recovered from these artifacts, run only that missing
case on the preserved pre-change image and document why. New wrap and geometry
cases are implementation regressions, not grounds to repeat the BI5 suite.
Use the existing linear host model as the independent semantic oracle.

## Executable slices

### CB1 Make character access logical

Add the generated field and mapping helper; initialize the origin to zero.
Migrate Feed, both presentation backends, cursor paths, direct fixture records
and logical snapshot readers. Keep the existing physical move for this slice,
so ordinary production scrolls still leave the origin at zero. Focused fixtures
may seed a nonzero origin to exercise readers without enabling ring scrolling.
This is a migration step, not a selectable compatibility profile.

Audit all `.cells` accesses, not only the scroll function. Allocation/free,
full clear, guards and explicitly physical setup remain base-relative; logical
content assertions and presentation reads use logical order. Include the direct
device, windows and DOS stream fixtures where they inspect retained bytes.
Validate generated/emitted record offsets, both backends, caret restoration and
bank-crossing row sources in raw/optimized code. Measure ordinary text overhead
and avoid per-character mapping calls before committing.

### CB2 Enable circular scrolling

Replace the retained Move with recycled-row Fill and the bounded origin update.
Reset the origin only during clear/init, preserve logical damage/generations
and remove the old retained-copy path. Keep physical text moves and the single
VBXE list. Update the core host snapshot decoder to read the recorded origin
and raw allocation, comparing logical contents against the independent linear
oracle rather than against a snapshot built by the production mapper.

Exercise every origin for selected heights and more than two full revolutions,
using distinct row contents and writes between scrolls. Check after each edit
that only the recycled physical row changed and that untouched guards/rows are
identical. Include 1×1, height one, odd widths, maximum geometry, CPU bank
crossings, FF after wrap, LF, TAB wrap, printable last-cell wrap, CR and BS.
Run raw/optimized core and text/bitmap scrolling checks. Commit the executable
ring path once both backend oracles pass.

### CB3 Cover wrapped presentation and lifetime

Extend the existing display, bitmap control/fault, focus, window and cancellation
fixtures with a nonzero origin or a ring wrap at the exercised boundary. Cover
partial-row damage, stale Presented generations, bounded redraw across the ring
boundary, cursor movement/removal, hidden repeated output followed by Show,
clipped direct views and neighboring tile isolation.

During a real in-flight blit, check that the origin and cells remain unchanged
while input/READ progresses. Exercise AbortIO after the logical scroll, the
last-WRITE reply followed by Stop, PRESENTING completion deferral, hide/destroy,
quiesced failure and reset-required retention. Check exactly one logical scroll
and correct redraw/reuse after allowed recovery. Cover changed address/generation
behavior in raw and optimized builds without rerunning every unrelated platform
matrix. Commit the focused integration evidence.

### CB4 Compare cost and publish the result

Measure the final image against the preserved BI5 baseline. Use
[`test_console_bitmap_scroll.py`](../../tools/test_console_bitmap_scroll.py),
[`bitmap_console_performance.py`](../../tools/bitmap_console_performance.py) and
[`console_turn_profile.py`](../../tools/console_turn_profile.py) for preparation,
Feed/presentation, whole-scroll and worker-turn costs. Repeat the loaded
[`measure_async_scroll.py`](../../tools/measure_async_scroll.py) workload at
phases 0, 3547 and 14188 base cycles with physical SIO, ST input, keyboard and
BREAK, followed by same-image unobserved replays. Keep comparator configurations,
input phases and accounting boundaries identical. Reuse existing baseline
results rather than rebuilding or rerunning the old implementation.

Require removal of retained character copying and a measured reduction in
retained-scroll CPU cost, with exact pixels and unchanged correctness/peripheral
limits. Quantify added Feed, caret and redraw costs; revise the mapping if they
erase the preparation saving in representative workloads. Report any wall-time
or loaded-input regressions explicitly. Do not claim the ring meets the broader
4 ms worker-turn, 20 ms scroll or 40 ms visible-input targets unless measured.

Save portable evidence in `docs/development/console-circular-buffer-cb*.json`.
Update the current console contract, this plan's status, roadmap and indexes;
add a history record containing final pins, memory accounting and measurements.
Commit that final slice. A demo refresh or release qualification is separate.

## Validation and completion

Use the [development tier](../contributing/testing.md): host checks, the console
generator check and focused emitted raw/optimized behavior tests. Preserve the
fixtures' stack/domain guards, native context, ownership, bounded completion and
OS restoration checks. Normalize host text before parsing newline-sensitive
fixtures; preserve binary and ATASCII bytes. Compiler defects belong in actionc
with focused regressions and a recorded pin change, not console special cases.

The plan is complete when all slices have committed evidence: logical content
matches the linear reference after wrapping, both backends display identical
pixels, one-list IRQ/watchdog behavior survives, cancellation and lifetime
remain correct, and the measured preparation saving includes mapping overhead.
No additional bank-zero reservation or unrecorded toolchain override is allowed.
Full qualification is reserved for a release, explicit qualification claim or
request; a refreshed demo must use the existing OF816 packaging workflow.
