# Signals and Wait implementation plan

Status: slices 1–7 and the required eight-task part of slice 8 are complete;
see the [implementation record](../history/signals-implementation.md) and
[capacity qualification](../architecture/task-capacity.md). Task and IRQ signal delivery pass
functional checks. General worker-per-byte timing fails 125 kbaud; the restricted
IRQ-buffered experiment passes at four and eight live tasks. Twelve/sixteen-task
layouts, a production SIO driver and general concurrent SIO timing remain later
work. This plan records how to implement the
[updated design](../reference/signals.md) and its
[direct-delivery decision](../history/signals-delivery-review.md). Those documents define
the public semantics; this document defines executable slices and acceptance.

Commit each completed slice separately, with its focused checks and evidence.
Maintain one current implementation and rebuild callers after ABI changes.
Do not expose unimplemented calls as successful stubs or advertise IRQ support
at a task-only milestone.

## Scope and starting point

Deliver the five classic calls in EXEC: AllocSignal, FreeSignal, SetSignal,
Signal and Wait. Retain 32-bit masks, wait-for-any, coalescing, pending signals
and blocking Wait's restoration of Forbid nesting. Implement direct target
association and the private pending-wake queue; no all-waiters scan belongs in
posting, draining or ready-head selection.

At the start of this plan the default implementation had four public task
contexts, including root, plus private idle. Its 42-byte Task had no signal
fields. `Lookup()` searched private contexts, `Wake()` checked all timed sleepers
on each dispatch, and interrupt return scheduled only when a VBI tick was pending.
All three paths required changes in the new profile. The scheduler already used
`tc_Node` in its FIFO
ready list; retain that representation and keep wake linkage separate.

The [POKEY latency proof](../history/sio-latency-poc.md) is the completed prerequisite
experiment, not an implementation of Signal. Its emulated 8× PAL profile passed
the 125 kbaud target using direct native IRQ delivery, fast ROM and scoped
CRITIC. The maximum observed refill was 66.537 µs against the actual
78.942 µs deadline at 126.675 kbaud. The remaining 12.405 µs is an observed margin
for that small workload, not a budget already qualified for general kernel work.

This plan includes the adapter prerequisite and later capacity requalification.
The allocator, message ports, complete asynchronous SIO/DOS, priority scheduling,
Disable/Enable nesting, signal exceptions and arbitrary NMI/ROM signal callers
remain separate work. Static Task storage suffices. The
[eight-task milestone](../history/roadmap-chronology.md#7-bank-zero-task-capacity) owns capacity/layout
implementation; this plan defines the signal checks it must pass.

## Sequence and commit boundaries

| Slice | Deliverable | Depends on | Completion gate |
| --- | --- | --- | --- |
| 1 | Bounded native device IRQ adapter and SIO/OS ownership | Existing latency proof | Shared adapter passes the minimal latency path and coexistence checks. |
| 2 | Versioned ABI, emitted layouts and storage plan | 1 | Raw/optimized layout and call-shape probes agree; malformed calls are rejected. |
| 3 | Task integration, direct context access and mask bookkeeping | 2 | Existing Task behavior and AllocSignal/FreeSignal/SetSignal pass through emitted code. |
| 4 | Task-context Signal and Wait | 3 | Atomic blocking, direct ready transitions, Forbid restoration and idle behavior pass. |
| 5 | Intrusive pending-wake queue and bounded IRQ posting | 4 | Real IRQ posts preserve target identity and queue invariants under injected interruption. |
| 6 | Safe draining, IRQ-exit scheduling and idle handshake | 5 | Wake without a VBI; IRQs remain serviceable between target transactions. |
| 7 | Integrated four-task qualification and timing record | 6 | Functional, timing and compatibility results recorded with explicit profile limits. |
| 8 | Capacity requalification at eight, then twelve/sixteen tasks | 7 and roadmap milestone 7 | Simultaneous live-task tests pass on each advertised layout. |

Slices 1–7 produce the first qualified signal profile at the existing capacity.
Eight live public tasks plus idle remains the minimum for SIO/DOS integration;
a four-task signal milestone does not satisfy it. Twelve and sixteen are later,
independently qualified configurations.

## Implementation locations

Names of new files below are proposed; existing sources are linked for context.

| Area | Existing inputs | Planned work |
| --- | --- | --- |
| Platform entry and return | [hosted.s](../../platform/altirraos/hosted.s), [preemptive.s](../../platform/altirraos/preemptive.s), [cooperative.s](../../platform/altirraos/cooperative.s) | Add qualified native device posting, protected IRQ-permitting drain boundaries and pending-wake return eligibility. |
| Task ABI and generated definitions | [tasks.json](../../abi/tasks.json), [generate_tasks.py](../../tools/generate_tasks.py), [tasks.s](../../platform/altirraos/tasks.s) | Update the single Task ABI/generator/gateway; generate public/private layouts and all new selectors. |
| Kernel policy | [taskpolicy.act](../../lib/exec/taskpolicy.act), [execlists.act](../../lib/exec/execlists.act) | Add the new profile's direct context access, masks, wait continuation and safe ready transitions; share unchanged helpers where practical. |
| Packaging and memory | [native_program.py](../../tools/native_program.py), [generate_memory.py](../../tools/generate_memory.py), [banked_image.py](../../tools/banked_image.py) | Use the current Task build; reserve and validate new metadata, linker symbols and platform settings. |
| Tests and observation | [test_tasks_abi.py](../../tools/test_tasks_abi.py), [test_tasks_exec.py](../../tools/test_tasks_exec.py), [sio_latency.py](../../tools/sio_latency.py) | Add signal ABI/policy/IRQ runners and fixtures; reuse bounded execution, guards, far-memory inspection and hardware timing. |
| Regression coverage | [test_tasks_regressions.py](../../tools/test_tasks_regressions.py), [test_task_bindings.py](../../tests/test_task_bindings.py) | Exercise current Task behavior and reject malformed calls. |

Use the clean compiler revision in [toolchain/actionc.json](../../toolchain/actionc.json)
and matching native ABI inputs. Fix compiler defects in actionc with focused
regressions, then update the pin and provenance. Do not special-case Exec
routines to compensate for compiler defects. Emulator correctness fixes belong
with the emulator; distinguish observer instrumentation from a semantic change.

## Slice 1 — Carry the latency path into the platform adapter

Implement the direct native POKEY serial entry as a bounded adapter path. Keep
a hardcoded probe binding and the small worker/background fixture for this
slice; it needs neither the new Task ABI nor public signal services. Arrange
for the fixture to execute the actual shared adapter code, not a second copy
that could diverge from production.

Specify native entry arguments, clobbers, M/X handling, D/DBR ownership, scratch,
stack headroom, acknowledgment and nested-entry rules. Handle only registered
device sources through the fast path; preserve the existing OS path for other
sources and test simultaneous sources. Retire live IRQ/OS activations before
switching. Preserve complete native context and the OS's COP `$00`; Exec stays
on COP `$50`.

Define scoped serial ownership: register the stable binding before enabling the
source; save/restore affected vectors, serial interrupt-enable state and CRITIC;
quiesce the source and retire handlers before releasing the binding. Preserve
unrelated IRQ-enable bits. Test normal completion and abort cleanup, including a
preexisting nonzero CRITIC value. Reject overlapping serial ownership rather
than silently competing with ROM SIO. Document stage-two VBI work postponed
during the window and demonstrate its return after release.

Create an explicit measured platform configuration for the 8×/fast-ROM path.
Record actual ROM, emulator, CPU clock, RAM map, DMA, VBI and serial settings;
leave the existing 1× pins unchanged. Adding upper RAM later requires its own
combined profile measurement, even with the same nominal CPU clock.

Acceptance: rerun the minimal path with busy and idle backgrounds, initial
phase variation, a 65,535-byte stream and the deliberate long-masking negative
control. Require zero missed refills, gaps and overwrites in passing cases,
final-byte completion, intact context/guards and restored OS state. Include
uninstrumented replay on the pinned emulator. Record the adapter's instruction
and stack costs. This is the gate before building the full signal stack; a
failure sends work back to the delivery/ownership design.

## Slice 2 — Qualify the ABI and storage before policy

Update the machine-readable Task ABI and its generated definitions. Assign
selectors after checking current core and allocator ranges. Rebuild callers;
do not retain older Task layouts or implementations.

Generate the four signal fields after `tc_TDNestCnt` and the opaque
`ADDRESS tc_ExecPrivate` after `tc_UserData`. Generate the private wait reason,
pending MinNode, queued flag, queue header and adapter binding fields. All
assembly and Action! consumers use these definitions, including context stride
and node-to-context offsets.

Run emitted layout probes before accepting any offsets. The current prediction
is 62 bytes: signal masks at 16/20/24/28, stack fields at 32/36/40, MemEntry at
43, UserData at 54, ExecPrivate at 58, and tail padding at 61. Verify array stride,
all offsets and guarded field accesses in both raw and optimized code, including
odd and bank-crossing Task placement. The compiler output is authoritative;
update the design/budget if it differs, rather than forcing the prediction.

Probe all five native call shapes with full-width arguments/results. Generate
COP wrappers and saved-frame marshalling; LONGCARD results use all of A/X.
Do not borrow the pointer result convention for a 32-bit mask or truncate bit
31. Qualified Action! callers use the native ABI widths; interrupt preservation
tests separately cover every interrupted M/X combination.

Choose and record the exact private storage layout before writing policy. Prefer
upper RAM for queue/header/context metadata and use a generated constant-time
context address calculation. Audit all `T_BASE`/`T_SHIFT`, bank-relative accesses,
initialization loops and frame-validation consumers. Do not silently expand the
current 32-byte bank-zero contexts into 64-byte reservations or overwrite the
adjacent DP guard. Reuse reserved fields only where the lifetime permits it.
The new profile must account for placement from the selected image/memory map;
do not introduce a hardcoded kernel-bank assumption while the build parameter
remains separate roadmap work.

Acceptance: layout/call probes and package rejection tests pass, current
callers build, and a complete before/after reservation map fits. No
new public service is claimed operational from ABI probes alone.

## Slice 3 — Integrate tasks and implement mask bookkeeping

Integrate signals with the core Task operations. Successful
AddTask initializes masks, wait state, queue node/flag and reciprocal Task/context
links before publishing the task. Root follows the same rules; private idle is
not signalable. Failure preserves caller storage. Removal clears association
and private state before reuse; keep the existing caller-owned storage contract.

Use `tc_ExecPrivate` plus constant-time pool-range/alignment and reciprocal-owner
checks to resolve a live Task. Selecting the ready head must use that link too.
Enumeration and admission checks may still search, but posting and selection
must not fall back to `Lookup()` scans. Retain a known current-context reference
for kernel operations and the separate private idle path.

Separate timed-sleep expiry from ordinary signal/dispatch entry. Consume timer
work on a pending tick or due deadline, retaining the existing modular deadline
semantics. A tick-only scan may be an intermediate implementation if its own
masked interval is bounded; qualify coincident timer work before accepting the
SIO profile. Do not run `Wake()` unconditionally on every signal delivery.

Implement AllocSignal, FreeSignal and SetSignal with bounded mask transactions
and preserved caller I. Keep low sixteen bits reserved, user allocation in
16–31, `$FF` allocation failure/no-preference, FreeSignal `$FF` no-op and a zero
exception mask. Allocation clears a previously received bit; FreeSignal does
not promise clearing. SetSignal returns the entire old 32-bit received mask.

Acceptance: existing admission, selection, sleep, removal/reuse, priority-storage
and Forbid behavior passes in the new profile. Add per-task allocation isolation,
exhaustion, invalid/reserved bits, bit 31, reallocation, full old-mask returns and
no mutation on rejected calls. Check cold root initialization and repeated reuse.

## Slice 4 — Implement task-context Signal and Wait

Signal updates and tests its known target, making a matching blocked signal
waiter ready before returning. Running/ready targets retain bits; zero-bit posts
do nothing. Sleep and `Wait(0)` retain their separate behavior. Public READY
means runnable, not selected next.

Implement Wait as an atomic pending-test/consume or wait-publication transaction.
On blocking, save its mask, private reason and continuation; dispatch another
task while preserving the waiter's Forbid depth for resumption. Consume matching
bits only when completing the continuation, returning them in the saved A/X.
Reject caller-masked Wait before mutation, even if a bit is already pending.
Immediate completion preserves Forbid and unrelated pending bits.

Make FindTask include signal waiters. RemTask cancels the wait without returning
a fabricated result. The no-ready path uses private idle and retains explicit
bounded completion/shutdown behavior. Queue fields remain initialized but there
are no IRQ signal producers in this milestone.

Acceptance: self-post, preposted and blocked waits; any-of multiple bits;
unrelated bits; coalescing; posts while READY joining the returned mask; nested
Forbid restoration; `Wait(0)` removal; timed Sleep isolation; masked-I rejection;
all tasks waiting; and removal/reuse. Exercise emitted raw/optimized programs
and NMI interruption of mask/publication/restore transitions. This qualifies
task-context signals only.

## Slice 5 — Implement the pending-wake queue and IRQ post

Implement the private FIFO MinList with one separate doubly linked MinNode and
queued flag per context. Its fixed node offset gives the context directly.
IRQ post uses its registered Task/context/mask binding, ORs received bits, tests
only that target and appends it once if blocked in a matching signal Wait.
There is no queue allocation, bounded-ring overflow or global wait-mask summary.

Use bounded assembly for the IRQ mask/test/queue transaction with adapter-owned
scratch. Do not call ordinary Lists/Action! wrappers using an active kernel
domain. NMI may record a tick but cannot inspect a half-written mask, queue link
or state. Queue nonemptiness is authoritative; any cached pending flag must be
updated with enqueue, dequeue and cancellation, including the last entry.

Implement one-target dequeue/revalidate/READY publication as an indivisible
transaction. Task-context Signal must cancel its target's existing pending node
when it delivers directly. RemTask unlinks head/middle/tail in constant time;
quiesce producers and retire the binding first, then clear state before reuse.
Do not release a context while a detached wake entry can still reference it.

Use real IRQs to populate the queue and explicit safe test boundaries to drain
it initially. This isolates queue correctness before enabling automatic exit
scheduling. Trace target IDs against an independent FIFO model and bound all
validation walks; the production path never walks unrelated contexts.

Acceptance: empty/singleton/full-capacity queue; FIFO first-post order; repeated
posts without duplicates; nonmatching/running/ready/Sleep targets; known-node
cancellation in every position; task-context takeover; and immediate reuse after
producer quiescence. Inject IRQ/NMI around each multi-byte link and mask write,
final-entry flag clear and revalidation. Use far nodes/header, equal low-word
addresses in different banks and bank-crossing fields. Verify no unrelated Task
or guard writes. An IRQ asserted during I=1 must remain pending until unmasked;
NMI may run there but must not observe/mutate the protected transaction. Do not
simulate an impossible maskable handler entry to stand in for this check.
Measure the posting transaction's maximum masked duration now, before adding
exit scheduling. IRQ posting remains experimental until slice 6 passes.

## Slice 6 — Drain at safe exits and close the idle race

Allow pending wakes, independently of pending ticks, to request safe policy
entry. Separate permission to process readiness from permission to switch:
Forbid defers the latter; active OS/kernel/IRQ frames and unsafe transitions can
defer both. Test the outer IRQ, task gateway, outermost Permit and native OS
return boundaries. Retain work across ineligible exits without depending on a
new VBI after the boundary becomes eligible. Preserve caller-masked I; arbitrary
application code that masks interrupts indefinitely has no latency guarantee.

Drain complete target transactions one at a time. Where original I permits,
enable IRQ service between transactions while the kernel activation remains
protected against recursive draining, scheduler reentry and task switching.
Define which transition/domain guards stay asserted through these windows,
where nested IRQ frames live and which scratch remains activation-local. Keep
partial save/restore and stack transitions masked. This changes the old
all-kernel-work-masked protocol and requires its own execution evidence.

The later [critical-section slice](../history/kernel-critical-sections.md) refines this
boundary: partial frame save/restore stays masked, while ownership validation
and the transition into kernel S/D permit IRQs after the complete frame is saved
and SWITCHING is asserted. IRQ scratch and S/D restoration are activation-local.
This bounds entry blackouts as well as policy transactions. Claimed wake nodes
and small native operations replace whole-target masking.

Complete the eligible drain before selection. No task runs/reenters Wait during
the pass; unrelated tasks are not inspected. Recheck the pending queue and ready
state atomically at the final idle transition. An IRQ between the last check and
WAI must either select newly ready work or force recheck without sleeping. A
later VBI must not hide a lost wakeup.

Acceptance: real serial IRQ wakes a blocked worker with VBI disabled as a
functional control; normal VBI cases also pass. Force posts during each protected
entry/exit, while OS/kernel work is active, between drain transactions and around
idle entry. Cover all-target bursts, repeated posts, pending timers and nested
Forbid. Verify full A/B/X/Y/P/D/DBR/S/PC/PBR restoration for all native M/X
combinations, bounded nesting and stack/DP guards. Record per-transaction masked
duration, total drain duration and time until the worker actually runs.

## Slice 7 — Qualify the integrated profile and publish results

Replace the hand-rolled post/Wait in a diagnostic fixture with the new public
Task services and actual IRQ entry. Keep the original proof available as a
baseline. First use one worker plus busy/idle background, then the complete
current four-task capacity. Run task/policy fixtures in raw and optimized modes;
assembly-only portions have no separate NIR mode.

Measure hardware-ready to actual SEROUT write, not just entry-to-Signal time.
Retain byte sequence, next shifter-load interval, final completion and overwrite
checks. Include maximum queue population, unrelated waiters, runnable peers,
timer expiry, permitted task services and documented OS interference. Test the
combined upper-RAM/fast-ROM profile explicitly. Keep negative controls and
uninstrumented replay; instrumented race builds do not substitute for timing
the production instruction path.

Distinguish functional acceptance from timing acceptance:

- Signal correctness requires no lost wakeups, duplicate readiness, corruption
  or unbounded completion under the documented caller/producer contract.
- A worker-per-byte 125 kbaud claim requires every refill before the actual
  configured deadline, zero gaps/overwrites and the documented interference
  matrix passing. The current round-robin policy does not promise this under
  arbitrary runnable load or Forbid/OS blocking.
- Record numeric maximum IRQ-masked intervals, IRQ service and worker latency
  limits for the qualified workload. Derive and enforce those limits from the
  emitted path and observed interference; a statement that sections are merely
  "bounded" is insufficient. The 12.405 µs proof margin is not automatically
  assigned to this implementation.

If general worker-per-byte delivery misses the deadline, retain the functional
result and mark that timing profile unqualified. Do not silently lower the baud,
remove interference or describe the failure as an async-SIO impossibility.
Return to a separately measured IRQ-buffered byte path with block/phase signals,
as the design recommends for production, before claiming SIO readiness.

Add committed qualification records for the adapter, signal ABI, functional IRQ
delivery and timing, with commands, input revisions/hashes, actual machine
settings, source/image hashes, modes, bounds, memory reservations, counts, worst
event windows and explicit exclusions. Proposed runners are
`tools/test_signals_abi.py`, `tools/test_signals.py` and
`tools/test_signals_irq.py`; follow existing `--compiler-dir`, `--bridge-dir`,
`--rom`, case-selection and raw/optimized conventions. Put generated artifacts
under `build/signals-tests/`. Document runnable commands when the tools exist.

Run affected package/generator tests and old Task/Lists regressions. Changes to
shared gateway, interrupt, loading or OS paths also require the corresponding
hosted/cooperative/preemptive/banked checks. Broaden only for changed consumers
or unresolved failures. Update the contract, roadmap and examples with actual
supported contexts and profiles; change defaults only after replacement
qualification passes. No public success stub stands in for a missing feature.

## Slice 8 — Requalify at the required capacity

After [roadmap milestone 7](../history/roadmap-chronology.md#7-bank-zero-task-capacity) provides the
parameterized memory/context layout, run eight simultaneously live public tasks
plus idle. Include blocked signal waiters, a timed sleeper, runnable work and
device/filesystem stand-ins using static work buffers. Capacity is not a count
of sequential task creations; waiting tasks retain their stack and direct page.

Repeat ABI-dependent layout, direct association, all-target queue occupancy,
removal/reuse, shutdown racing a final in-flight post, overflow admission rejection,
timer coexistence and full-context checks. Compare one active target with many
unrelated waiters: its posting and one-target delivery must not gain per-bystander
work. All-target draining can take O(k); record its total cost and maximum
individual masked interval separately. Measure worker scheduling delay with
competing ready tasks instead of assuming READY implies immediate execution.
After producer quiescence, no retained binding may post into reused storage;
raw Task pointers do not promise stale-address detection.

Repeat at twelve and sixteen only on complete validated layouts, including idle,
OS/kernel/IRQ headroom, guards and boot reservations. Reject configurations that
do not fit or fail bounds. Each advertised capacity gets its own committed
result; until then it remains a target. Ports and full SIO/DOS integration use
the eight-task baseline and require their own queue, RX/turnaround, timeout,
cancellation and real-device qualification.

## Memory accounting and completion

The design currently predicts 20 additional public Task bytes: sixteen signal
bytes and a three-byte context link plus one added alignment byte. Private
wake-node/flag/wait-reason data adds eight logical bytes per public task; the
pending MinList header adds nine fixed bytes. The provisional delta is therefore
`9 + 28 * public_tasks`: 233 / 345 / 457 bytes at 8 / 12 / 16 tasks, before
private record padding/reuse, per-binding context pointers and adapter headroom.
These are storage estimates, not bank-zero reservations.

Every implementation slice reports fixed and per-task reserved bank-zero
before/after totals, counting padding, guards, unused stride/capacity and separate
idle/boot costs. Keep public Tasks and additional metadata in upper RAM wherever
the CPU/adapter does not require bank zero. Signals need no extra worker, stack,
direct page or general allocator. This documentation-only plan reserves
**0 additional bank-zero bytes**.

Mark slices complete only with the stated emitted-code evidence and commit
reference. The first signal milestone ends after slice 7 with explicit capacity
and timing limits; the required SIO/DOS capacity gate ends after the eight-task
part of slice 8. The later allocator, ports and driver remain separate milestones
with their own acceptance, rather than implied results of this plan.
