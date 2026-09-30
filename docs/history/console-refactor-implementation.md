# Console refactor development record

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/console.md) and [history index](README.md).

Follow the [implementation plan](../plans/console-refactor-plan.md). These are focused
development checks, not release qualification.

## C0 — Current baseline

The benchmark now checks nonblank retained scrolling and measures short writes
and a 20×8 tile as well as the original four phases. Visibility polling yields
instead of adding a mandatory frame sleep. Each phase contains 16 operations;
the RTC resolves the batch in 20 ms steps. Timings below are batch averages.

| Operation | Raw ms | Optimized ms |
| --- | ---: | ---: |
| Retained scroll | 15.00 | 13.75 |
| Full-screen redraw | 36.25 | 28.75 |
| Hidden worker scroll | 36.25 | 33.75 |
| Visible worker scroll | 67.50 | 58.75 |
| Short write, reply | 11.25 | 12.50 |
| Short write, visible | 12.50 | 12.50 |
| Tile scroll, reply | 13.75 | 12.50 |
| Tile scroll, visible | 15.00 | 12.50 |

Both builds use compiler `bcabe0a4`, PAL 8×, stack checks and the existing pinned
ROM/emulator. No disk or SIO worker is active. An optimized passive observation
reuses the exact same binary and reproduces all eight timings. It counts edit,
drawing, worker-turn and translated-cell visits, and measures median/maximum
edit, drawing and write-quantum call durations including interruptions. It does
not claim that a write-quantum duration covers the whole worker turn.

The [baseline record](../development/console-refactor-baseline.json) includes image
identities, observation counts, stack measurements and source hashes. The size
baseline remains the verified standard shell image in the plan, rather than
the benchmark's additional test code.

Validation: 234 host checks; raw/optimized benchmark; one passive optimized
replay. Exact screen restoration, retained contents, heap ownership and protected
stack reserves pass. Fixed/per-Task reserved bank-zero delta: **0 / 0 bytes**.
Only test fixture/host code changes in this slice.

Reproduce with `tools/test_console_scroll.py --case raw|opt --output PATH`.
Use `--from-build PATH --observe` to measure an already built, hash-verified image
without recompiling it. Keep observed results in a separate output directory.

## C1 — Native retained edits

The compiler runtime now supplies reentrant native `Move`, `Clear` and `Fill`
leaves. The separately committed pin is `5f62c9fd`. These use the calling
Task's existing compiler scratch, preserve D/DBR/S/I, and allocate no stack
frame. Forward/backward word loops handle overlap, odd tails, bank crossings
and full 24-bit lengths. The console completes its at-most-960-byte retained
edit in one call; the request remains active throughout. The obsolete edit
index is removed; its two record bytes remain explicitly reserved.

On the same optimized PAL 8× benchmark, retained scroll falls from 13.75 to
1.25 ms, hidden worker throughput from 33.75 to 2.50 ms and visible worker
throughput from 58.75 to 13.75 ms per scroll. Full redraw remains 28.75 ms.
These are 16-operation batch averages, not per-operation worst-case latency.

Memory: **0 fixed / 0 per-Task added reserved bank-zero bytes**. The native-code
subregion grows by 512 bytes inside the existing upper Task arena; the arena
itself does not grow. Instance size remains 62 bytes, rounded to 64 by allocation.
No new worker, framebuffer or heap allocation is introduced.

Development checks: 234 host tests; generated console/SIO definitions; raw and
optimized core fixtures (including height one, odd width, patterned overlap and
bank-spanning cells); optimized scroll benchmark; all 14 active/queued cancellation phases with exact
committed bytes, reply ownership and OS restoration. The compiler checks cover
raw/optimized memory operations through 65,537 bytes, overlap and guard bytes,
IRQ/NMI re-entry, two live Task contexts and o65 import binding. Native artifacts
are under `build/development/console-refactor/c1-*`.

## C2 — Native glyph spans

Presentation now translates an admitted row span in a native leaf and advances
through at most four retained rows / 160 cells per call. The worker consumes
already admitted geometry; the checked `Quantum` entry retains direct-fixture
clipping validation. Snapshot/restore and tile erasure use the shared native
memory runtime. Cursor removal/restoration occurs once per batch.

Optimized full redraw drops from 28.75 to **7.50 ms** per screen; visible scroll
throughput is 6.25 ms before physical screen reuse. Short writes are visible
in 11.25 ms on the unloaded pinned PAL 8× fixture.

Validation: 234 host tests; raw/optimized display checks including partial rows,
unsupported glyphs, clipping guards, hidden output, physical input during a
write, cursor and exact OS restoration; optimized scroll benchmark. Fixed and
per-Task reserved bank-zero deltas are **0 / 0 bytes**, with no record, arena,
worker or framebuffer growth. The native leaf uses existing caller scratch and
no stack frame or interrupt masking.

## C3 — Synchronized physical scroll

The worker coordinates retained editing and screen movement under its existing
instance borrow. Complete visible views remove the cursor and settle at most one
small dirty batch before scrolling. Full-width views use one contiguous move;
narrow tiles move rows at physical stride 40. Clipped/hidden views and larger
pending damage retain the redraw path. Clears fill both representations.

Optimized visible scroll throughput is **5.00 ms**, with tile reply and visibility
both **3.75 ms**. An unchanged-image passive replay reproduces the eight timings.
Across the complete benchmark, worker selections fall from 964 to 132 and glyph
translations from 35,490 to 17,676. The latter still includes sixteen intentional
full-screen redraws. Clean physical scrolls copy existing codes without translating
unchanged rows. Observed write-call maxima include preemption and are not whole
worker-turn measurements.

Validation: 234 host tests; optimized display and scroll fixtures; raw display
fixture with additional patterned tile, dirty text-plus-scroll, cursor removal,
consecutive scrolls, hidden clear/show and larger-damage fallback guard checks.
Cancellation is rechecked with the request migration in C5. Fixed/per-Task
reserved bank-zero delta: **0 / 0 bytes**; no record/allocation/arena growth.

## C4 — Printable runs and settled presentation

Printable input now advances by runs bounded by a row edge, control byte or
64-byte source quantum, publishing one dirty extent per run. A single `CASE`
handles controls. Unchanged cells/cursor/focus skip screen stores; worker
selection and round-robin/input boundaries remain bounded.

Validation: 234 host tests; raw/optimized core fixtures; optimized scroll
benchmark; the bounded eight-Task multiwindow/SIO fixture. All existing timing
limits pass: worst short-write visibility 60.16 ms, cooked echo 141.87 ms,
BREAK durability 11.35 ms, with zero RX/TX/byte-gap deadline misses. Unloaded
short-write reply/visibility both average 10.00 ms. Visible scroll remains
5.00 ms and full redraw 7.50 ms. Bank-zero reservation delta: **0 / 0 bytes**;
no records, allocations, arenas or workers grow.

The older fairness observer needed its BREAK marker moved to `NotifyOne`, and
now accounts for the existing SIO resident's exact self-removal call as the end
of its final Forbid. It still checks exclusion duration, actual Task retirement
and balanced ordinary calls. `--from-build` reused the unchanged image while
fixing these observation points; no workload limit was relaxed.

## C5a — Ordinary resident request dispatch

Console Open/Bound/Close/BeginIO/AbortIO now use the existing caller-context
resident route. Queue claim, cancellation and exact-once completion live in
`console-requests.inc`; they use public Forbid, GetMsg, PutMsg, ReplyMsg and Signal.
The worker shares `CONSOLEWINDOWS.Runnable` rather than a kernel copy. The old
request/idle/extent Control operations are removed. Worker startup/retirement
control remains only for the next slice.

The internal `TASKMEMORY.Writable` helper shares the loader's immutable writable
image ranges between generic Task validation and console buffer validation.
This preserves bank-zero checks without another gateway service or duplicated
range policy. Fixed/per-Task reserved bank-zero delta: **0 / 0 bytes**; no record
or arena grows.

Validation: 234 host tests; raw/optimized public-device fixtures; all fourteen
optimized cancellation phases, including active scrolling and exact committed
retained/physical contents. Replies, hardware restoration and ownership pass.

## C5b — Public Task lifetime

The console worker uses registered public AddTask admission, a removal lease,
resident shutdown notification and signal-based startup/stop rendezvous. Waiters
retain their callers while their stack records are linked. Final notification,
lease release and self-removal are indivisible under Forbid. Window creators,
presentation transactions and open owners have ordinary removal leases too.
The obsolete console Control selector, worker boot descriptor and console-specific
scheduler removal hooks are removed. Keyboard Bind/Release and its producer hold
remain, as planned; the public producer API is still serial-only.

Task packaging now gives explicit resident registration precedence over the
application-module exclusion list. A focused host regression covers that rule
and still rejects unregistered resident helpers.

Memory: **0 fixed / 0 per-Task added reserved bank-zero bytes**. The console's
upper arena grows **672 → 720 bytes**, counting all capacity and alignment. Its
service record grows 136 → 148 within the existing 160-byte slot. The default
instance reservation grows 64 → 80; the window registry grows 144 → 172, rounded
to 176 in the arena. Extra instances grow 62 → 74 record bytes, **64 → 80 allocated
bytes each** (maximum three extra instances). Presentation/FIFO/cell buffers and
worker/task pools do not grow. Removing the 16-byte worker boot descriptor frees
capacity inside the unchanged upper Task arena; that is not reclaimed bank zero.

Validation: 235 host tests and generated definitions; optimized lifetime modes
0–9 using one image (normal exit, removal guards, child outliving root, ROM reuse,
invalid display, allocation rollback, full Task capacity, signal/binding failure,
and stale-input reopen); raw normal lifetime; raw window isolation/rollback and
removal guards; all thirteen optimized focus/presentation checkpoints. The public
device fixture also holds the worker in its empty-check/Wait gap, posts a request,
and verifies collection exactly once after resumption. Hardware/heap ownership,
stack/domain guards and OS restoration pass.

## Final comparison

The optimized unloaded benchmark uses the same ROM, PAL 8× machine and stack
checks as C0. The compiler backend is unchanged; its pin advances only for the
shared native memory runtime. Production input hashes in the final benchmark
match the committed implementation. Each result is a 16-operation batch average,
with a 20 ms RTC resolution for the batch, not a worst-case guarantee.

| Operation | C0 ms | Final ms |
| --- | ---: | ---: |
| Retained scroll | 13.75 | 1.25 |
| Full-screen redraw | 28.75 | 7.50 |
| Hidden worker scroll | 33.75 | 3.75 |
| Visible worker scroll | 58.75 | 3.75 |
| Short write, reply | 12.50 | 7.50 |
| Short write, visible | 12.50 | 8.75 |
| Tile scroll, reply | 12.50 | 5.00 |
| Tile scroll, visible | 12.50 | 5.00 |

Visible scrolling improves **15.7×**, and full redraw improves **3.8×**.
The final passive observation counts 134 worker selections, 224 drawing calls
and 17,676 glyph stores, versus 964, 1,375 and 35,490 at C0. The glyph count
includes sixteen intentional full redraws. Observed edit/drawing/write-call
maxima are 1.76 / 1.81 / 16.68 ms including interruptions; the write-call maximum
does not measure the entire worker turn. Drawing observation now covers internal
`Present`, where C0 covered the checked `Quantum` entry.

The final eight-Task workload passes unchanged latency limits: short-write
visibility 41.42 ms maximum, cooked echo 116.80 ms, BREAK durability 2.88 ms,
and next-sector submission 34.07 ms. All RX, TX and byte-gap deadline-miss counts
are zero. Console progress now outruns the first mechanical disk read, so the
fixture waits explicitly for both kinds of progress before teardown. It still
requires keyboard input during `DOS.Read` and remains bounded by the native
execution timeout.

### Standard-image footprint

Both images contain the standard shell/prime demo, optimized with stack checks.
The baseline is the artifact identified in the plan; the final image was built
from Exec816 `2bca1c8` and actionc `5f62c9fd`. Routine counts exclude assembly,
data and alignment. Loaded-segment bytes include the shared assembly/runtime
and image data, so movement between modules is not counted as a saving.

| Responsibility | C0 bytes | Final bytes | Change |
| --- | ---: | ---: | ---: |
| `CONSOLECORE` | 2,798 | 3,001 | +203 |
| `CONSOLEDISPLAY` | 5,048 | 6,871 | +1,823 |
| `CONSOLEDRIVER` | 9,619 | 22,320 | +12,701 |
| `CONSOLEINPUT` | 3,261 | 3,261 | 0 |
| `CONSOLEFOREGROUND` | 7,892 | 7,917 | +25 |
| `CONSOLE` | 4,675 | 4,666 | −9 |
| `CONSOLEWINDOWS` | 3,048 | 3,559 | +511 |
| `CONSOLETILING` | 5,755 | 6,163 | +408 |
| Console policy in `TASKPOLICY` | 17,374 | 2,798 | −14,576 |
| **Console Action! routines** | **59,470** | **60,556** | **+1,086** |
| Console assembly instructions | 1,519 | 1,563 | +44 |
| Shared native memory helpers | 0 | 403 | +403 |
| **Whole-image Action! routines** | **479,859** | **480,792** | **+933** |
| **Whole-image loaded segments** | **492,370** | **493,778** | **+1,408** |
| XEX file | 507,070 | 508,444 | +1,374 |

The console Action! total grows **1.8%**; this refactor delivers faster drawing
and an ordinary resident-driver boundary, not a net console size reduction.
Generic resident dispatch grows 356 bytes, and `TASKMEMORY` contains 631 bytes
of shared validation moved from Task policy. Both are included in the whole-image
totals. DOS line/stream adaptation remains 20,968 bytes. Action! code still
occupies banks **1–8**; native adapters also retain their existing placement.

Reserved bank-zero usage remains **24,672 bytes excluding OS reservations**:
10,560 fixed, 2,080 for the root Task, 1,568 for each of seven child slots, and
1,056 for idle. Fixed/per-Task delta is **0 / 0 bytes**. The upper console arena
grows by 48 bytes and each extra instance allocation by 16 bytes, as detailed
in C5b. The shared native-code subregion grows 512 bytes inside the unchanged
Task arena. No additional framebuffer or Task slot is needed.

### Refreshed play image and validation

`build/demo/program.xex` and `build/demo/sdfs.atr` were rebuilt. The packaged
image passed shell boot, SYS:/physical-drive cache sharing, HELLO, CAT→WC,
EXIT, ownership/heap cleanup and exact OS display/input restoration. The host
demo and command-loading tools now use generated window offsets after the
lifetime record change; the same image was reused for the successful smoke.

Final host suite: **235 checks passed**. Generated definitions, documentation
links and whitespace checks pass. The focused raw/optimized, cancellation,
startup/focus/lifetime and concurrency checks are listed with their slices
above. This is development validation; the full release matrix was not run.

The [final machine-readable record](../development/console-refactor.json) preserves
image identities, source hashes, footprint totals and timing summaries. Native
artifacts are under `build/development/console-refactor/`. The updated standard
bundle is under `build/demo/`; the OF wrapper was not rebuilt in this work.
