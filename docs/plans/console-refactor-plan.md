# Console size and drawing refactor

Status: C0–C5 implemented and committed; final development measurements and the
standard play-image smoke passed. The
[development record](../history/console-refactor-implementation.md#final-comparison) contains
the before/after results. The original plan follows. Preserve the console API and four nonoverlapping text
windows. Improve scrolling first, then simplify request and lifetime policy.

## Baseline footprint

The standard system artifact at `build/development/fs-cpu-steps/system/` uses
compiler `bcabe0a4cbb8bb57b389a8596aa8fd72cb9ee0c7`, optimized code and stack
checks. Its console input hashes match the sources at Exec816 `dfb952b`.
Image SHA-256: `5cf7b8aae4d5385906dc29dab852c7f67ff29603d8e76022c30664763a4a7808`.
These are sums of emitted routine sizes in `program.a816.json`, excluding data,
alignment and assembly:

| Responsibility | Bytes |
| --- | ---: |
| Retained terminal state: `CONSOLECORE` | 2,798 |
| Screen drawing and OS screen ownership: `CONSOLEDISPLAY` | 5,048 |
| Worker, startup and request processing: `CONSOLEDRIVER` | 9,619 |
| Keyboard translation: `CONSOLEINPUT` | 3,261 |
| Foreground/BREAK routing: `CONSOLEFOREGROUND` | 7,892 |
| Instance creation/destruction: `CONSOLE` | 4,675 |
| Window registry/selection: `CONSOLEWINDOWS` | 3,048 |
| Presentation/focus transactions: `CONSOLETILING` | 5,755 |
| Console routines from `task-console.inc` in `TASKPOLICY` | 17,374 |
| **Console Action! total** | **59,470 (58.1 KiB)** |

`platform/altirraos/console.s` adds 1,519 instruction bytes and a 32-byte mask
table in the existing assembly regions. The separate ROM-output bridge is not
part of this native display path. DOS's `DOSRAW`, `DOSCOOKED` and `COOKEDLINE`
add another 20,968 bytes; report those separately rather than charging line
editing and stream adaptation to the renderer.

The console is substantial, but only 7,846 bytes implement retained terminal
state and drawing. Windows, asynchronous I/O, safe retirement and captured
foreground identities explain much of the rest. Removing those safeguards is
not a useful size optimization. There is nevertheless avoidable duplication:

- Window lookup/live checks exist in both `CONSOLEWINDOWS` and `TASKPOLICY`.
- Worker readiness is interpreted in both `Runnable` and `ConsoleRunnable`;
  the kernel's all-window check also searches again for each instance's entry.
- `Control(2/3/4/8/9/10)` marshals arrival, write claim, completion and idle
  checks through a console-specific kernel protocol. SIO already uses the
  [ordinary resident-driver boundary](../reference/resident-drivers.md).
- Fixed display geometry is checked on each drawing quantum, while clipping,
  cursor removal and cursor restoration repeat for tiny batches.

Moving 17 KiB out of `TASKPOLICY` does not itself save 17 KiB: necessary policy
still exists in the driver. Count whole-image savings, including added helpers.

## Why scrolling was expensive

This section describes the implementation before C1–C5.

[`EditQuantum`](../../lib/console/consolecore.act) handles at most 40 cells. A
40×24 scroll copies 920 retained bytes and clears 40, spread over **24 calls**.
The worker revisits selection, read/write handling and presentation between
these calls and normally yields after each turn.

[`Cells`](../../lib/console/consoledisplay.act) translates at most 38 cells per
call, reserving two stores for the cursor. A full repaint takes **26 calls**.
Edit and drawing calls overlap in the worker; these counts should not be added
as if they were separate scheduler turns. The problem is repeated small turns
and general per-byte work in both paths.

Every scroll currently dirties the entire retained screen. Already translated
physical screen bytes are discarded as a source and generated again. Dirty
ranges can widen further when another scroll starts before drawing catches up.
Ordinary text also calls `Character` and `Dirty` for every byte.

The [historical benchmark](../history/console-scrolling.md#measurement) reported 22.5 ms
for retained scrolling, 53.8 ms for redraw and 97.5 ms for a visible worker
scroll, optimized on PAL 8× without I/O. Its compiler and console predate the
current image, so these are motivation, **not current timings**. Optimizing
only the retained copy leaves presentation and worker overhead intact.

## Selected design

Keep one contiguous retained ASCII buffer per instance, the existing dirty
interval and one worker. No row ring, second framebuffer, damage queue or new
kernel call is needed for this work.

- Perform one bounded logical clear/scroll with native bulk memory helpers.
  At most 960 cells are involved; IRQs and preemption remain enabled.
- Draw contiguous spans through a small native glyph-translation loop. Compute
  clipping and row addresses outside that loop. Use the same span path for
  fullscreen and tiled output.
- When physical contents match the pre-scroll retained contents, remove the
  cursor, move the existing screen bytes upward and clear the bottom row.
  A full-width view uses a contiguous move; a narrow tile uses rows at stride
  40 and never touches its neighbors. Clipped/unsynchronized views use redraw.
- Coordinate the retained and physical scroll while the worker holds its
  existing instance borrow. A short pending dirty span may be drawn before
  scrolling; if it cannot be settled within the turn's budget, use redraw.
  Decide eligibility **before** changing retained cells. Mark the presentation
  clean only after both operations complete.
- Keep input checks and round-robin fairness between useful batches. Start with
  the existing 64-source-byte limit, at most one logical scroll per turn, and a
  drawing budget of four rows / 160 cells. Select the final budget from measured
  latency rather than retaining the old 40-store limit by habit.

Cursor overlays never enter retained state or a screen-copy source. Remove
once before a batch, restore once afterward, and skip both when neither cells,
focus nor cursor changed. Write completion still means source bytes are retained
and any logical scroll is complete; it does not become a physical-display fence.

## Implementation slices

Commit each completed slice with its focused development results. Keep the
speed work independent of the later driver migration.

### C0 — Freeze the measurement

Extend the existing scroll fixture rather than build a profiling framework.
Record retained copy, full redraw, hidden worker and visible worker separately;
add a short printable write and a scrolling narrow tile with nonblank rows.
Count worker turns, presentation calls and translated cells using test-only
observation. Measure write reply and final visibility separately.

Use the same compiler, ROM, PAL 8× emulator, task count and stack checks for each
before/after comparison. Record median/batch throughput and longest observed
turn; increase repetitions if 50 Hz clock resolution hides improvements.
Reproduce the footprint table from the same standard shell build.

Performance goals for the final optimized, unloaded profile are **at most one
PAL frame (20 ms) per synchronized full-screen scroll and full-screen repaint**,
with a short write visible within one frame while the worker is runnable.
These are proposed engineering targets, not measured guarantees on real hardware
or under contention. Keep existing SIO and loaded-window latency limits.

### C1 — Bulk retained scroll and clear

The pinned actionc already has `runtime/65816/a816memory.act` with `Move` and
`Clear`, but these are Action! byte loops. Give that reusable runtime a compact
native implementation and a byte-value fill operation, then update the Exec816
compiler pin in a separate commit. Do not introduce console-pattern compiler
optimizations or a second memory library in Exec816.

Helpers must be reentrant, handle overlapping moves and bank boundaries, treat
zero length as a no-op, and preserve the native ABI and interrupted context.
Use an efficient word loop or block move as measurements justify; shared patched
bank operands are unacceptable with preemption. No interrupt masking around a
copy and no dedicated new DP scratch reservation.

Replace row-sized edit continuation with one bounded scroll/clear call. Keep
the request owned until the logical edit finishes, including cancellation.
Remove `editIndex`/old continuation machinery when all callers and fixtures have
moved. Retained spaces remain ASCII 32; physical blank cells remain screen code 0.

Acceptance: raw/optimized native memory-helper regressions in actionc, then
focused console core/scroll and active-scroll cancellation checks in Exec816.
Include height one, odd widths, nonblank overlap and bank-crossing buffers.

### C2 — Native spans and useful drawing batches

Add the platform glyph-span helper and use it for dirty presentation. Retain
the existing glyph mapping, clipping and unsupported-character behavior. Cache
row/column progression within the batch, and restore the cursor once per batch.
Use bulk copy/fill for screen snapshot, restoration and tile erasure too.

Validate geometry at claim/show/admission; internal drawing then consumes a
validated presentation. Keep a checked entry for direct display fixtures rather
than silently weakening their clipping contract. Update generated definitions
through `abi/console.json` and `tools/generate_console.py` if layouts change.

Acceptance: focused raw/optimized display checks covering partial rows, hidden
output, neighboring tiles, glyphs, cursor and exact borrowed-screen restoration;
compare redraw cost and total code bytes. No writes beyond admitted spans.

### C3 — Reuse the physical screen when scrolling

Implement the synchronized-scroll path described above, with a single decision
in the worker coordinating core and display. Full-width and narrow presentations
share the rule; only the physical copy stride differs. Hidden and clipped views
retain the ordinary redraw path. Showing a hidden view invalidates its screen
contents. Clear fills both representations when eligible.

Drain a small pending dirty span before a visible scroll when the batch budget
allows it, so ordinary text followed by newline can use the fast path too. A
fallback must remain exact when pending damage is larger. Finish the physical
update before releasing the borrow; hide/destroy already wait for that borrow.

Acceptance: scroll patterned rows, not just blank screens; verify cursor removal,
text-plus-newline, consecutive scrolls, dirty fallback, hidden/show, narrow tiles
and cancellation. In the clean case, unchanged rows undergo **no glyph
translation**. Compare visible completion against C0.

### C4 — Feed printable runs and simplify worker turns

Handle a printable run up to its row boundary, source limit or control byte;
update cursor and dirty extent once per run. Preserve current high-byte
substitution, control characters, immediate wrapping and `io_Actual` semantics.
Keep one clear control-character dispatcher alongside the run path.

Skip presentation when there is no cell/cursor/focus change. Rotate windows and
check input at the defined batch boundaries; do not flush an unbounded write
before servicing another instance. Retain durable wakeups across the idle check
and `Wait`, including arrivals during that gap.

Acceptance: core/device control and byte-count checks, then the bounded
eight-Task fairness/SIO workload because worker scheduling changes. Measure
small writes and sustained text in addition to newline-only scrolling.

### C5 — Consolidate request and lifetime policy

This is the size/architecture follow-up, not a prerequisite for fast rendering.
Split it into two commits:

1. Route console Open/Bound/Close/BeginIO/AbortIO through the existing resident
   driver mechanism. Move queue claim, cancellation, reply and readiness policy
   into the driver using public Forbid/GetMsg/ReplyMsg/Signal/Wait operations.
   Share window lookup and readiness logic; retire the corresponding `Control`
   operations and generated kernel copies as each caller moves. Keep generic
   request/address checks at their required boundary, including bank-zero buffers.
2. Use existing Task leases and resident shutdown facilities for worker,
   instance-owner and presentation-owner retention. Replace their console-specific
   scheduler hooks and the remaining worker control operations. Preserve startup
   rollback, stale unit/route rejection and final application shutdown ordering.

Do not merge the four-window registry and sixteen captured-route records simply
to save source lines: they protect different lifetimes. Do not replace the
private protocol with another console-only kernel operation. The existing
keyboard Bind/Release admission and producer-retention hook remain: the public
`EXECPRODUCER` currently supports only the serial producer and cannot also bind
the keyboard. Generalizing producer admission is a separate API change, outside
this rendering/size refactor. Do not claim all console kernel code disappears.

Acceptance: focused device/cancel tests for the first commit, lifetime/focus/
startup rollback for the second, with lost-wakeup and reply-once coverage.
Report net code size including moved routines, generic dispatch and new runtime
helpers; relocation between modules is not a saving.

## Memory, validation and completion

Target **0 added fixed and 0 added per-Task reserved bank-zero bytes** in every
slice, counting alignment, guards and unused capacity. Keep the existing worker
and task pools. Reuse existing upper state where possible; explicitly account
for any record growth and rounded allocation/reservation costs. Fast drawing
must not depend on another 960-byte buffer.

Bulk helpers and drawing remain ordinary task-context calls. Preserve D, DBR,
stack/domain ownership and ABI-required state; IRQ/NMI may interrupt any copy.
Include targeted interruption/bank-boundary checks when those helpers change,
and retain SIO byte deadlines and protected stack reserves.

Follow the [two-tier test policy](../contributing/testing.md): host checks plus the affected
native fixtures after a coherent slice, with raw/optimized coverage where
compiler-facing behavior changes. Reuse unchanged binaries and do not rerun the
complete console, media or placement matrices after every edit. At completion,
publish one current footprint/timing comparison and refresh/smoke-test the
standard play image. Full release qualification remains a separate activity.
