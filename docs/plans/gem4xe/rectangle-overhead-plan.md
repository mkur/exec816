# Rectangle drawing overhead implementation plan

[GEM plans](README.md) · [Roadmap](../../roadmap.md) ·
[Baseline observation](../../development/rectangle-overhead-baseline.json) ·
[Display ownership](../../reference/display.md#delegated-renderer-access) ·
[AES contract](../../reference/aes.md)

Status: in progress. RP1–RP2 are implemented; RP3–RP5 follow in order. See the
[implementation record](../../history/rectangle-overhead.md) and
[development measurements](../../development/rectangle-overhead.json).

Reduce the cost surrounding solid rectangle drawing: physical display
contention, repeated presenter housekeeping, VDI dispatch and UPDATE processing.
Keep standard GEM calls, the existing blitter encoder and Exec coordination.
The useful result is faster ordinary application drawing with responsive input,
not just a lower number from a less demanding benchmark.

## Evidence and comparison scope

The retained observation covers 300 rectangles of 100×50 pixels in three
100-operation batches, with an idle Shell, the desktop Task, no open folder,
no Counter and the pointer outside the benchmark. It uses the existing packaged
demo and its recorded PAL, 8× CPU, VBXE, compiler, ROM and emulator inputs.

| Cost per rectangle | Measured time |
| --- | ---: |
| Benchmark Task CPU | 10.068 ms |
| Presenter Task CPU | 9.437 ms |
| Interrupt processing across both Tasks | 4.173 ms |
| Total elapsed mean | 23.678 ms |
| Displayed median of the three batch averages | 23.6 ms |

Within those totals, command construction, upload, submission and completion
polling take about **1.020 ms CPU**. Each rectangle has one display borrow,
one upload and one launch: one command at even X or five at odd X, transferring
21 or 105 bytes. GEM4XE uses the same basic edge-fill strategy. This is software
CPU attribution, not a measurement of hardware BUSY duration.

`DisplayEnter` takes 4.731 ms elapsed, including 3.464 ms off the benchmark Task.
The begin/end UPDATE calls, amortized over four rectangles, take 7.396 ms
elapsed. `v_bar` takes 4.247 ms CPU and 11.097 ms elapsed. These are inclusive
intervals and must not be added to the table above. Off-Task time includes
scheduling and does not by itself prove how long a particular owner blocked
admission.

The presenter issues no drawing submissions in these measured intervals.
Nevertheless, `AESMOUSE.Refresh` runs 2.203 times per rectangle and consumes
2.124 ms presenter CPU. Direct cache begin/end bookkeeping costs only 0.152 ms.
The existing turn-wide display reservation and repeated snapshot publication
are therefore stronger first targets than the fill encoder or cache copies.

The package predates merge `2fba321`; retain its observation and obtain one
matched rectangle result on the merged parent before RP1 changes. Fold this
small comparison and repair of the current desktop launcher in the existing
diagnostic into RP1; do not create another full baseline milestone. The attempted
Counter comparison did not complete. Establish its unchanged-parent result
before claiming any loaded improvement. The screenshot's 29.6 ms and donor's
1.702 ms are context, not matched acceptance baselines.

## Scope and slice sequence

| Slice | Change | Main evidence |
| --- | --- | --- |
| RP1 | Reserve physical display access around actual renderer work | Shorter admission waits; safe handoff and DMA retirement |
| RP2 | Publish mouse snapshots when their inputs change | Fewer refreshes and less presenter CPU; correct input routing |
| RP3 | Give named rectangle and fill-colour calls a direct VDI path | Lower caller CPU with identical clipping and pixels |
| RP4 | Remove remaining measured UPDATE bookkeeping duplication | Cheaper transactions with unchanged ownership and exposure |
| RP5 | Compare ordinary drawing and desktop response; refresh the demo | Recorded results and one focused OF816 package check |

No new Task, scheduler priority, kernel service, generic cache or rendering
framework is required. Keep the current one/five-command encoder, work limits,
VRAM reservations and synchronous application drawing contract. Interrupt
assembly tuning, asynchronous application blits and larger UPDATE groups are
separate work. Correct API use and live caller storage remain caller obligations;
do not add validation layers or repeatedly revalidate admitted resources.

## RP1 Shorten physical display reservations

Primary files: `lib/console/consoledriver.act`,
`lib/display/display-access.inc` and the existing desktop/console drawing
entries that use `OwnerEnter`, `OwnerEnd` and `OwnerDrop`.

Replace the surrounding service-turn reservation with reservations covering
actual shared renderer work. Message handling, logical UPDATE admission,
input-state publication and other CPU-only housekeeping should proceed without
keeping a physical borrower out of the renderer.

Before moving a boundary, inventory the calls it protects: pointer/caret/outline
operations, frame/menu painting, cache copies, staging, console continuations
and DMA completion adoption. Reuse their existing owner-entry helpers. Where
several calls share mutable renderer state or one scratch buffer, retain one
reservation for that complete unit. A boundary must never expose a half-built
command list or redirect state to another Task.

Preserve nested owner depth, FIFO admission and the asynchronous DMA pin.
Dropping the last ordinary reservation must not release hardware still in use.
BUSY leaves pending rendering available for retry through the existing wake
path; housekeeping can continue. Keep completion retirement possible while a
borrower is queued, and preserve timeout, revocation and shutdown cleanup.
Do not insert unconditional Yield calls, spin while busy, hold Forbid during
rendering or increase interrupt-disabled intervals. Keep logical AES UPDATE
and physical display ownership separate.

Use existing passive markers to distinguish owner-held work, DMA pinning,
queued admission and runnable off-CPU time. Extend `tools/trace_g4bench.py` and
its existing analysis only where those boundaries are missing. Capture bounded
intervals and keep large logs in `build/`; preserve compact results and hashes.

Focused checks: affected optimized cases from `test_display_access.py` and
`test_display_borrow.py` for owner nesting, queued handoff, BUSY retry, DMA pin
retirement and fault cleanup; one mixed application/console drawing case with
input and cancellation. Retain guard, scratch isolation and OS-return assertions.
Update the display reference's service-turn description after implementation.

Acceptance: CPU-only presenter work no longer holds physical access; matched
rectangle admission and elapsed time improve; native output and input still
progress between bounded units. Do not attribute every off-CPU millisecond to
display contention.

Commit: `Limit presenter display ownership to drawing units`.

## RP2 Publish mouse state only when needed

Primary files: `lib/aes/aesmouse.act`, `aeshost.act`, `aeslocks.act`,
`aesinbox.act` and the existing client/window lifecycle call sites.

Replace unconditional all-client refreshes with a simple presenter-owned dirty
flag and publication at the existing synchronization boundaries. Mark it for
actual pointer/button/modifier changes and changes to routing or eligibility:
focus, window identity/epoch/visibility, client registration/retirement,
UPDATE/MCTRL ownership, capture, native gestures, menus and loss/release state.
Audit these sources before suppressing any refresh; stationary pointer position
does not imply an unchanged recipient or eligibility.

Coalesce redundant refresh requests within a turn, but publish before replying
to a lock/lifecycle operation or delivering input that relies on the new state.
An actual ownership transition must remain observable at its required boundary.
Do not delay all publication until a later turn or discard ordered button edges.
Keep lost-input recovery and caller-local event matching unchanged. Use one
small state flag in upper RAM, not another queue or per-Task mechanism.

Focused checks: idle no-change turns, stationary pointer across focus and lock
changes, nested UPDATE/MCTRL, menu/drag capture and release, moving pointer and
button transitions, and client/window retirement followed by slot reuse. Reuse
the relevant AES/input fixtures and one physical-input desktop sequence.

Acceptance: unchanged turns do no snapshot publication; necessary state changes
reach the correct clients without stale eligibility or lost wakeups. Record
refresh count and CPU per rectangle after RP1 and RP2 separately.

Commit: `Publish AES mouse snapshots on state changes`.

## RP3 Reduce rectangle binding overhead

Primary file: `c/calypsi/vdi.c`.

Make named `v_bar` and `vsf_color` bindings use the established caller context
directly, following the existing `v_gtext` approach. Avoid constructing a VDI
parameter block, copying control/point arrays and redispatching an operation
whose identity and argument count are already known. Keep generic `vdi_call`
working through the same internal rectangle and colour operations, with its
parameter counts checked once at the public boundary.

Normalize and user-clip rectangle geometry once before recording the changed
area and intersecting it with the published visible rectangles. Preserve
inclusive GEM endpoints and sufficiently wide arithmetic before screen clipping;
negative/reversed coordinates and one-pixel edges must retain their pixels.
Keep one change report for the logical operation, including covered content,
and the existing bounded physical fragments, overlay restoration, final fence
and display-error reporting. Do not infer that invisible drawing is unchanged
application content.

Focused checks: named versus parameter-block calls using the same workstation,
even/odd X, narrow/reversed/clipped rectangles, multiple visible fragments and
fully covered content followed by exposure. Use the existing G4BENCH/VDI pixel
fixtures; compare pixels and state, not wrapper call structure. No public ABI
change is planned.

Acceptance: lower `v_bar`/colour binding CPU with unchanged pixels and command
counts. Extra encoder arithmetic work is justified only by a new trace.

Commit: `Use direct VDI bindings for solid rectangles`.

## RP4 Reduce remaining UPDATE bookkeeping

Primary files: `lib/aes/aeslocks.act`, `aeswindowstate.act` and `aeshost.act`.

Remeasure UPDATE after RP1–RP3 before selecting this slice's edit. Separate
caller preparation, request intake, eligibility, snapshot/publication, reply
and resumption. The 7.396 ms starting interval is not all server computation.
Remove repeated scans or unchanged publication shown by that trace, using
existing owner/window records and existing scene/focus revisions where valid.
Do not add a second window registry or cached lock state in each caller.

Keep outermost Begin/End processing, recursive counts, try-acquire, eligible
queue order, pending-lock gates and exit cleanup. Publish the drawing snapshot
before the grant reply. Geometry may be reused only when its existing revision
proves it unchanged; drawing and paint epochs still follow each transaction.
Preserve cache invalidation for hidden changes, paint failure, partial completion
and the ordinary GEM exposure contract. An UPDATE containing no visible VDI call
must not silently certify a cache as current.

Do not hold physical display access for an entire UPDATE or move lock ownership
into clients. Do not enlarge benchmark groups to hide exchange costs. If the
remaining interval is required state transition or ordinary scheduling, record
that limit and omit a speculative production change.

Focused checks: affected optimized AES lock cases, a two-client handoff with
continuous native output, and hidden/partial/failed paint followed by exposure.
Include a bounded input/cancellation comparison if service ordering changes.
The [earlier UPDATE experiments](../../history/update-admission-latency.md)
remain historical failures; their input/cancellation or stack regressions are
not waived by this plan's throughput improvement.

Acceptance: reduced measured UPDATE CPU or avoidable handoff time with unchanged
lock/cache semantics. Report required exchanges and remaining scheduling cost.

Commit: `Reduce redundant AES UPDATE bookkeeping`, or document why no further
production change is justified.

## RP5 Compare results and package the desktop

Keep ordinary G4BENCH's four-rectangle groups, visibility checks, event polling,
visible pointer, synchronous completion and timer method unchanged. Use matched
parent/candidate inputs, window positions and loads. Report batch averages and
their median accurately; they are not individual rectangle latency percentiles.
Collect cycle CPU attribution separately from untraced elapsed measurements.

Run the rectangle row on an idle desktop and beside the Counter, after fixing
the diagnostic's launcher/focus handling through normal application input.
Confirm Counter progress and normal benchmark closure. Use three batches per
condition; repeat a matched pair only when the difference is inconclusive.
Report per-slice and cumulative costs, upload/command counts and remaining waits.
The initial performance objective is roughly **12 ms per rectangle** in the
unchanged idle workload, about half the observed mean. Treat it as an objective,
not a predicted result or a reason to change the workload; report any shortfall.

Add a separately labelled drawing-only comparison to the existing diagnostic
if needed to compare the fill with GEM4XE: prepare state/visibility and acquire
UPDATE outside a bounded timed batch; hide the pointer for that diagnostic;
include completion of the last blit. Release and service events between batches.
Record the donor's asynchronous submission difference instead of claiming exact
equivalence. Never substitute this diagnostic result for ordinary throughput.

One focused desktop walkthrough covers Files selection/redraw, Shell/SYS focus,
File/View dropdowns, opening/closing a folder, a live Counter and a Panel button.
Check completed pixels, first visible feedback, cancellation and background
progress. Use a short matched input cohort if service ordering changed; report
individual results for small samples rather than manufacturing a p95. Expand
only an affected case when a regression or unresolved timing concern appears.

Build the final demo with `tools/build_demo.py --gem-desktop`, retaining OF816,
the five-second autoboot, matching disks/ROM, notices and checksums. Test the
exact extracted ZIP through normal closure and EXIT. Record results in a compact
development JSON and `docs/history/rectangle-overhead.md`, update indexes and
this plan, and provide the demo launch command. Full qualification and claims
about real hardware or HY4/PI4 remain separate.

Commit: `Record rectangle overhead improvements and refresh the desktop demo`.

## Resource and validation limits

Target **0 additional reserved bank-zero bytes fixed, 0 per public Task and
0 private idle**, including guards, alignment and unused reserved capacity.
Report each slice's code, upper-RAM, stack and VRAM changes; the dirty flag belongs
in upper RAM and no new VRAM reservation is planned. Preserve existing guards
and report stack headroom. A demonstrated need for more stack should receive
explicit capacity accounting rather than force a broad refactor.

Follow the [development testing tier](../../contributing/testing.md): ordinary
host checks and the smallest affected optimized emitted-code fixtures. Use
small raw/optimized checks only for changed ABI/layout/bridge behavior or a
suspected compiler defect. Do not run full qualification matrices. This planning
change requires only content, JSON and local-link checks.
