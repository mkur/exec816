# Console idle input implementation plan

[Implementation plans](README.md) · [Bitmap console plan](gem4xe/bitmap-console-implementation-plan.md) ·
[Input contract](../reference/input.md) · [Signals](../reference/signals.md)

Status: implementation started, 3 October 2026. Q0–Q1 passed development checks. Remove repeated input validation from console
turns that have no captured input. Collect notifications through the existing
signal API, and retain a worker-local flag until a bounded drain observes EMPTY.
Preserve keyboard routing, loss, BREAK, ownership and shutdown. Implement and
commit each executable slice with its focused development evidence before
proceeding to the next.

This is a bounded part of the bitmap console's open B8 responsiveness work and
applies to both text and bitmap backends. Display ownership checks, blitter
chunking, text rendering and general kernel gateway optimization remain separate
work; this change alone does not meet the 20 ms scroll target.

## Measured problem

The [B8 evidence](../development/bitmap-console-b8.json) records approximately
165 ms for a synchronized one-line scroll of the 80×30 console. A subsequent
passive trace of the same optimized image measured:

| Work inside one scroll | Calls | Elapsed time |
| --- | ---: | ---: |
| `CONSOLEINPUT.Pending` | 16 | 52.0 ms |
| Writable image range searches inside those calls | 32 | 32.5–34.1 ms |
| `FindTask(NULL)` inside those calls | 16 | 8.9 ms |

The last two rows are included in the first. These elapsed spans include
preemption; they are not isolated Task CPU time. The configuration is the pinned
AltirraOS 65816 ROM, PAL, CPU multiplier 8, VBXE and 63 high banks plus base RAM.
The local trace is `build/bitmap-console/scroll-analysis/analysis.json`; its XEX
SHA-256 is `83fecfc876996803396634125dc1d3346c1d748512d8b4b141a0190c40aac57d`.
Slice Q0 makes this local measurement reproducible and records portable evidence.

The worker calls the private `CONSOLEINPUT.Pending` wrapper before pumping and
again through `Runnable` before sleeping. Both calls enter the public INPUT API,
validate two writable extents and inspect lease identity even when idle. The
returned expression in `INPUT.Valid` also evaluates `FindTask(NULL)` for
nonconsumer observations: value-context `OR` is eager in the pinned language.
Avoid those idle calls without changing compiler semantics or weakening the
public INPUT checks.

## Chosen mechanism

Follow the classic Exec signal model: a signal indicates possible work; the
capture ring and durable mailboxes hold the work. Use the existing worker and
signal allocation:

| Bit | Mask | Responsibility |
| --- | --- | --- |
| 29 | `$20000000` | Resident stop notification |
| 30 | `$40000000` | Captured keyboard input, loss and cancellation |
| 31 | `$80000000` | Console requests and control work |

At the start of every worker turn, merge the previous `Wait` result with one
`EXEC.SetSignal(0, $60000000)` result. This atomically acknowledges input and stop
notifications and returns the previous received mask. Latch stop before clearing
the local result, and set `inputPending` if bit 30 is present. Leave bit 31 and
all unrelated bits untouched by this acknowledgement. Service request/control
queues through their existing paths.

Use this public atomic operation even during continuous scrolling. Reading
`tc_SigRecvd` directly is not an atomic full-mask observation and is excluded by
the signal contract. No new kernel selector, input-specific gateway, IRQ flag
or application-visible record is needed. One signal call per turn has a real
cost; Q0 and Q3 measure it rather than assuming it is free.

Native keyboard capture publishes a complete record or durable notice before
posting its binding. `signal_post_binding` writes the received bits immediately;
only readiness for a blocked Task can be deferred through the wake queue. Thus
the worker can observe input while running, without relying on another graphics
call, `Yield` or a VBI to expose it. Keep this producer ordering intact.

## Worker and drain protocol

Initialize `inputPending=1` once after successful worker initialization. This
permits one conservative startup drain across capture and route publication.
The flag then belongs solely to that worker activation and survives ordinary
calls, preemption, `Yield` and `Wait`; IRQ code never writes it.

Each turn performs the following sequence:

1. Collect and acknowledge input/stop notifications. Preserve input returned by
   `Wait`, including a wake containing request and stop bits too.
2. Process stop and controls in the existing order. A successful stop can leave
   the loop through the existing capture release and signal retirement path.
3. If `inputPending` is set, run one bounded `CONSOLEINPUT.Pump` under the current
   exclusion rules. Keep translation, captured route resolution, loss delivery
   and foreground cancellation unchanged.
4. Retain `inputPending` when the pump consumes its full event budget. Clear it
   only when the pump returns early because `INPUT.Take` returned EMPTY. An
   exact-budget drain may cause one extra empty pass; that is intentional.
5. Process one normal console/presentation turn. Include `inputPending` in the
   private `Runnable` decision so a partial batch cannot lead to sleep. Keep
   existing yielding between runnable turns and scroll continuation scheduling.
   Do not drain an unlimited input stream before serving output or controls.
6. When all retained work is empty, call the existing `Wait($e0000000)` without
   clearing notifications between the empty observation and that wait. Preserve
   its result for step 1. New arrivals during a drain remain signaled.

`Pump` currently returns a consumed count and treats every non-OK `Take` result
as empty. Preserve the count interface, but distinguish EMPTY from an invalid
lease, bad buffer or other unexpected status. Such a status is an internal
console invariant failure and must take the established `HEAPCORE.Abort(4)`
path; it must not authorize clearing `inputPending`, silently drop input or
cause an endless retry loop. Caller arguments and capture storage remain
resident and retained for the worker's lifetime.

Use the existing event budget initially. If loaded timing tests require a
smaller pump budget, define a separate private pump constant and update the
count comparison together; do not reduce the capture ring's `RAW_SLOTS` capacity
or relax timing limits. Record the measured reason for such an adjustment.

Remove the private `CONSOLEINPUT.Pending` wrapper and its `pendingMask` storage
when both worker call sites are replaced. Pass the worker flag into the private
`Runnable` helper. Keep public `INPUT.Pending`, `INPUT.Take`, C bindings and
their validation unchanged. Do not retain capture or window pointers across
worker borrows, or reset the pending flag on focus changes and route retirement.

An EMPTY result is an observation, not a promise that capture remains empty.
`Take` may also finish a bounded scan of discarded records; new records published
during that scan carry a wake posted after this turn's acknowledgement. Preserve
that wake even when the local flag is cleared.

## Required race coverage

| Arrival or state | Required result |
| --- | --- |
| Input exists before acknowledgement | The returned signal sets the flag and starts a drain. |
| Input arrives during acknowledgement | Atomic signal semantics place it either in the returned mask or the still-pending mask. |
| Arrival after acknowledgement or during Pump | Work is consumed now or its new wake remains for the next turn. Never clear the wake after draining. |
| Full pump budget with one coalesced wake | The worker completes further batches without another keypress. |
| Exact budget followed by EMPTY | One conservative extra pass settles; it does not leave a permanent runnable flag. |
| EMPTY followed by an arrival before or during Wait | The wake makes Wait return or wakes the waiter; no request is needed to rescue input. |
| Stale or spurious wake with no records | One empty drain clears the local flag and normal waiting resumes. |
| Discard leaves raw tombstones | Bounded Take scanning and concurrent new arrivals cannot strand live records. |
| Loss or BREAK with no ordinary key records | Durable notices drain normally, even with no pending Read. |
| Focus, route retirement, stop or reacquisition | Captured identities and release/drain ordering remain authoritative; no old flag or wake reaches a new worker. |

Forbid defers Task switching, not IRQ/NMI. Rely on existing signal and capture
transactions for asynchronous publication, following the
[platform protocol](../reference/platform.md#vbi-preemption). Do not add a broad
masked region around queue draining or graphics to make these races disappear.

## Implementation slices

| Slice | Executable result | Depends on |
| --- | --- | --- |
| Q0 | Reproducible idle-input cost and notification baseline | Current tree |
| Q1 | Bounded pump results distinguish empty, budget exhaustion and failure | Q0 |
| Q2 | Both console backends use notifications and retained pending work | Q1 |
| Q3 | Loaded fairness, race coverage and performance gain recorded | Q2 |

### Q0 Record the baseline

Extend the existing bitmap scroll observer with input-query and signal-collection
boundaries rather than adding a general profiler. Count public Pending/Take,
writable-range searches, `FindTask`, signal collection and pump calls by worker
Task. Pair entry/return observations by Task direct-page identity so concurrent
calls by other Tasks do not collide. Report nested timing without double counting.

Measure the unchanged optimized scroll scenes and a settled idle worker. Add a
focused emitted case for atomic input/stop acknowledgement with request and
unrelated bits retained. Pin the actual compiler, ROM, emulator, memory and
image hashes; preserve a replay without active timing observation. Store compact
baseline evidence under `docs/development/console-idle-input-q0.json`, with full
traces under `build/console-idle-input/`. These names describe planned artifacts.

**Gate:** reproduce the roughly 52 ms input-query contribution, measure the
replacement signal operation, and demonstrate that a sleeping worker performs
no periodic polling. No target console behavior changes in this slice.

Q0 evidence: [baseline and atomic notification collection](../development/console-idle-input-q0.json).
The unchanged scroll replay measures 52.0 ms in input polling, compared with
9.4 ms for sixteen isolated empty signal collections. All thirteen idle intervals
contain no input calls. Raw/optimized signal checks and observed/control replays
passed. Reserved bank-zero change is zero in every category.

### Q1 Make pump completion explicit

Update `lib/console/consoleinput.act` so its consumed count distinguishes a full
budget from an EMPTY-terminated partial batch; unexpected input statuses fault
as specified above. Document this private interface at the routine. Retain the
event budget and cancellation-before-loss-before-key ordering.

Extend a focused emitted fixture around the existing capture and console-input
fixtures. Exercise zero, budget-minus-one, exact-budget and more-than-budget
work, including a full raw ring plus durable notices. Cover discarded records,
translation that consumes without producing bytes, and the invariant-failure
path. Assert event counts, routes, byte order and guard state, not just calls.

**Gate:** raw and optimized emitted checks establish the count contract and
preserve keyboard/loss/BREAK behavior. Existing callers remain buildable; no
worker notification change is required yet.

Q1 evidence: [bounded pump and invariant failure](../development/console-idle-input-q1.json).
Raw and optimized emitted cases passed with counts for empty, partial, exact and
extended batches, cancellation/loss precedence, tombstones, untranslated keys
and stale routes. A corrupt resident lease terminates with status 4. Host checks
passed (303 tests, four historical skips). Reserved bank-zero change is zero,
including fixed storage and every Task pool.

### Q2 Use notifications in the worker

Change `lib/console/consoledriver.act`, `lib/console/console-requests.inc` and
`lib/console/consoleinput.act` together. Implement the start-of-turn collection,
worker-local flag, startup drain and flag-based `Runnable` decision. Remove both
repeated Pending calls and the unused private wrapper/storage. Reuse named signal
masks where available and keep one definition of the worker's input mask. The
ordinary worker entry still validates its retained identity.

Add focused emitted tests for the race table, especially continuous output
without Wait, partial drains with no fresh wake, Wait-returned bits, and arrivals
after EMPTY. Use controlled publication boundaries or existing IRQ/NMI probes;
do not treat directly writing Task signal fields as a production delivery test.
Use real keyboard/BREAK capture in selected integration cases. Synthetic
interleavings establish correctness, not physical input-to-visible latency.

**Gate:** raw/optimized text and bitmap cases complete within bounded time,
with exact routing, no lost wake, duplicate delivery, starvation or idle spin.
After startup, an output turn with no input notification or retained pending work
makes zero `INPUT.Pending` or `INPUT.Take` calls and zero input-driven extent/owner
validations. It performs at most one input/stop signal collection. A stale wake
may cause one empty drain. Normal shutdown retires capture, lease and signals;
invariant-failure tests enforce the existing bounded terminal fault/reset outcome
and retain ownership where that protocol requires it.

### Q3 Validate integration and record the gain

Run affected development checks, reusing builds where their inputs match:

- The new notification/drain cases in raw and optimized form, plus selected
  `tools/test_console_input.py` native/emulation capture and overflow cases.
- `tools/test_console_bitmap_scroll.py` with passive timing and its unchanged-image
  replay: exact pixels for all thirteen scenes, including narrow/hidden views.
- `tools/test_console_fairness.py --bitmap --pointer` on the pinned configuration:
  eight live Tasks, physical SDFS traffic, keyboard/BREAK, active ST capture and
  continued progress by other instances. Retain existing SIO, pointer and Forbid
  limits and an unobserved replay.
- The affected console cancellation cases and one physical shell BREAK recovery
  case; retain routing/discard/retirement and worker stop/restart checks from the
  focused fixture. Test the text backend as well as bitmap integration.

Do not automatically repeat the entire release matrix. Add deeper cases only
where changed boundaries or failures justify them. Update the console worker
description in the current reference and link new
`docs/development/console-idle-input-q3.json` evidence from the bitmap B8 plan.
Preserve prior measurement records and update this plan's status with actual
results. A local demo refresh, if included, must use `tools/build_demo.py` with
OF816, matching media/ROM/notices and the five-second standard autoboot. GitHub
publication and release qualification are separate work.

**Gate:** on the matched optimized, input-idle full-screen scroll workload,
reduce the input-checking contribution by at least 75 percent: at most **13 ms**
against the observed approximately 52 ms. Include the new signal collection,
flag handling and input contribution to the sleep decision in that total;
moving the cost outside the old Pending marker does not count as a gain. Use
guest cycle timing and report both measured scroll scenes, call counts,
preemption limits and the full scroll result. Preserve exact pixels and existing
loaded correctness/timing gates. Record remaining scroll cost without claiming
the separate 20 ms, 40 ms visible-input or 500 ms repaint targets are achieved.

## Memory and completion reporting

Expected reserved bank-zero change is **0 bytes** for fixed storage, root and
kernel, each of the eight public Task pools, and private idle, including guards,
alignment and unused reserved capacity. No new Task, stack enlargement, DP
reservation, ring or application ABI record is planned. The pending flag uses
the existing worker stack; measure actual frame growth and peak usage. Retired
`pendingMask` storage is in upper RAM; report linked upper-RAM changes and any
alignment effects rather than promising a two-byte reservation saving.

Each slice records source/tool/image hashes, development test scope, timing
boundaries, ownership cleanup and stack guards. Documentation-only work uses
content and link checks. Completion requires Q3 correctness and performance
gates; it does not qualify the whole hosted system or physical hardware.
