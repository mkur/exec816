# Queued device I/O and SIO implementation plan

Status: all eight slices implemented, 2026-09-20. The
[design note](../reference/device-io.md) defines the public contract, deviations
from classic Exec and unresolved hardware questions. This plan turns that
contract into eight executable slices, each with acceptance evidence and a
separate commit.

The [two-context hardware probe](../history/device-io-sio-implementation.md) passes the
125 kbaud gate with real bank-crossing buffers, complete transactions and native
phase alarms. Its [qualification record](../qualification/sio-feasibility.json)
does not qualify the production driver or full Task workload.

The [native I/O contract](../history/device-io-sio-implementation.md#slice-2-native-io-contract)
now has emitted raw/optimized layout and call-shape evidence. All ten generic imports execute with test devices and the resident sio.device.
Ordinary registration is now enabled after the slice-7 recovery checks.

Deliver the ten classic device calls and a queued `sio.device` before DOS.
The first work is a small hardware feasibility probe, not the device ABI.
The **125 kbaud target** and **eight simultaneously live public tasks** remain
acceptance requirements. A successful stock-speed transfer or four-task TX
fixture does not complete this milestone.

## Scope and working rules

Implement CreateIORequest, DeleteIORequest, OpenDevice, CloseDevice, BeginIO,
SendIO, DoIO, CheckIO, WaitIO and AbortIO in the generated `EXEC` API. Preserve
IORequest/IOStdReq field meanings, quick versus replied completion, direct
request identity and explicit ownership. Use one SIO worker, one FIFO for all
configured units, one active transfer descriptor and existing signals/ports.
IRQs move bytes and advance a prearmed transaction; the worker publishes replies.

Follow the [platform contract](../reference/platform.md),
[IRQ-permitting policy protocol](../history/kernel-critical-sections.md) and
[bank-zero budget](../reference/platform.md#bank-zero-memory-budget). Queue operations
remain in task-context Action! policy under E816_SWITCHING with IRQs enabled.
Only bounded native handoffs mask IRQs. No public I/O/port calls, allocation,
list traversal or task search occurs inside an IRQ. WaitIO/DoIO continuations
belong to the caller, never a suspended shared kernel activation.

Use the compiler revision in [actionc.json](../../toolchain/actionc.json), currently
`e7266982c22527040dfc2a46508be8475581fe8f`, and the existing native ABI. Compiler
defects belong in actionc with focused regressions and a recorded pin update.
Keep one current Task implementation, Exec COP #$50 and OS COP #$00. Rebuild
callers when the current ABI changes; do not introduce compatibility profiles.

Before implementation, commit the design and this plan as the baseline.
For each slice: implement its bounded result, run relevant checks, update its
qualification/implementation record, and commit before the next major slice.
An unsuccessful probe can be committed as evidence, but its gate stays failed.
Do not mark unexecuted tests passed or bind unfinished imports to successful
stubs. Test devices and forced-race hooks must remain test-only.

DOS, filesystem/block policy, timer.device, dynamic driver loading, semaphores,
IRQ-callable ports, automatic task-exit reclamation and 12–16-task capacity are
outside this implementation. No worker per unit/open/request, hidden request
ledger, bank-zero bounce buffer or ROM SIO fallback is introduced.

## Slice sequence and dependencies

| Slice | Executable result | Commit boundary |
| --- | --- | --- |
| 1. Hardware feasibility | Real upper-RAM RX/TX, phase alarms and hardcoded SIO transactions at one or two tasks | `Probe buffered SIO transactions and phase timing` |
| 2. Native contract | Ten call shapes, constants and IORequest/IOStdReq/IOSIOReq layouts execute in ABI probes | `Define classic Exec device I/O ABI` |
| 3. Lifetime and immediate dispatch | Request creation/deletion, resident open/close, BeginIO/SendIO/CheckIO with an immediate test device | `Implement I/O request lifetime and device dispatch` |
| 4. Queued completion | WaitIO/DoIO/AbortIO and asynchronous ownership pass with a queued test device | `Implement queued I/O waits and cancellation` |
| 5. Production hardware adapter | Qualified ownership, native/emulation RX/TX, alarms and descriptor handoff inside the Task kernel | `Implement SIO hardware ownership and transfer primitives` |
| 6. Queued SIO transactions | One worker executes complete framed transactions through the real driver in an opt-in fixture | `Implement queued sio.device transactions` |
| 7. Failure and recovery | Cancellation, timeout, offline state and shutdown are complete; publish the resident driver | `Complete SIO recovery and publish the device` |
| 8. Concurrent qualification | Actual device I/O passes four- and eight-task functional/timing workloads | `Qualify queued SIO under concurrent kernel work` |

Run slice 1 first. Its outcome determines the hardware approach used by slices
5–8. Slices 2–4 can proceed independently of an unresolved hardware result using
test devices, but they do not waive the gate. Slice 5 requires a passing slice 1;
slice 6 requires slices 4 and 5; slices 7 and 8 follow in order.

Production OpenDevice("sio.device", ...) must continue to fail until slice 7.
Earlier SIO tests use explicit test-only registration of the same driver code,
not a second implementation. An ordinary build must not expose a driver whose
cancellation or cleanup contract is unfinished.

## Repository integration

The following new paths are proposed; create them only as their slices land.

| Location | Work |
| --- | --- |
| `abi/io.json`, `abi/sio.json`, `tools/generate_io.py` | Current public records, constants, import shapes and private native handoff layouts; generated Action!/assembly definitions and stale-file checks. |
| `lib/exec/exec-io-types.inc`, `lib/io/io-call-types.inc`, `lib/io/iocore.act`, `lib/io/task-io.inc` | Public definitions, caller-context allocation/wait helpers and guarded device dispatch/completion policy. |
| [generate_tasks.py](../../tools/generate_tasks.py), [tasks.json](../../abi/tasks.json), [taskpolicy.act](../../lib/exec/taskpolicy.act) | Include actual generated EXEC declarations, coordinate selectors/tags, initialize resident state and protect internal helpers from task-entry admission. |
| `platform/altirraos/io.s`, [tasks.s](../../platform/altirraos/tasks.s) | Checked native imports, signed error results, caller continuations and final helper bindings. |
| `lib/siodevice.act`, `platform/altirraos/sio.s`, [serial-irq.inc](../../platform/altirraos/serial-irq.inc) | One worker, task-side request policy, native transaction engine, hardware ownership, alarm and native/emulation IRQ paths. |
| [native_program.py](../../tools/native_program.py), [generate_memory.py](../../tools/generate_memory.py), [banked_image.py](../../tools/banked_image.py) | Reserve all new code/state before final image/heap layout, bind helpers and retain complete provenance. |
| `probes/sio-transactions/`, `toolchain/altirra-sio-device.json` | Minimal first probe and an explicit machine/peripheral configuration extending the existing 1 MiB serial profile. |
| `tools/test_io.py`, `tools/test_sio.py`, `tests/programs/io_*`, `tests/programs/sio_*` | Named executable suites, immediate/queued test devices, bounded fault/race cases and real serial integration. |
| `tests/test_io_package.py`, `tests/test_sio_package.py` | Schema, generation, binding, memory-map and qualification-record checks. |
| `docs/history/device-io-sio-implementation.md`, `docs/qualification/io-*.json`, `docs/qualification/sio-*.json` | Current implementation status, per-slice evidence, timing limits and complete storage accounting. |

Reuse the existing port, banked-memory, emulator and observer harnesses. Editing
only [lib/exec/exec.act](../../lib/exec/exec.act) does not expose imports in the Task builder's
generated EXEC module. Extend result-shape validation for sixteen-bit signed
results without narrowing pointers or changing existing heap/port imports.

Keep the public I/O ABI separate from the private transfer descriptor and
platform/peripheral profile. Private worker callbacks and kernel helper symbols
must not become arbitrary application entry points. Tests may add an independent
request-state model, but it must describe ownership/events rather than copy the
implementation's link manipulation.

## Slice 1: buffered hardware and phase-timing feasibility

**Complete.** See the [implementation and timer decision](../history/device-io-sio-implementation.md)
and [13-case qualification](../qualification/sio-feasibility.json). The requirements
below define the gate to retain when integrating the hardware path.

Build an opt-in, hardcoded probe with one or two execution contexts. Reuse the
existing IRQ/signal-like wake route and upper-RAM launch support. Do not first
implement OpenDevice, ports, a general timer API or capacity work. Preserve the
earlier [latency proof](../history/sio-latency-poc.md) and
[serial adapter evidence](../history/serial-irq-adapter.md) for comparison.

First move known, nontrivial byte patterns from/to real upper-RAM buffers through
POKEY, including bank-crossing cursors. Then exercise a minimal complete command,
read and write sequence using the same byte/alarm path. Prearm all timing-critical
phases; notify the worker once at the terminal state. Check transmitted/received
bytes independently, not just checksums or driver progress counters.

Settle the design's unresolved alarm choice. Prototype the POKEY timer candidate
without committing production layout to it: prove rearming does not reset serial
clocking, silent-device deadlines fire, and owned/unowned IRQs coexist. Record
clock source, wrap handling, resolution, rearm latency, maximum observed jitter,
timer/vector/register ownership and complete scratch/stack requirements. Reject
a candidate that requires long SEI waits, worker-mediated tight transitions or
unbounded per-byte work.

Pin an emulated peripheral/model or a reproducible wire-level responder for
controlled cases, its firmware/source and writable test-media image. A synthetic
responder exercises the serial hardware, not a host shortcut around it. Include
an actual selected disk model for compatibility claims. Establish a stock
nominal-19.2-kbaud profile and a compatible 125-kbaud profile; record command and
data rates separately. Resolve the design note's conflicting write-start timing
references before assigning profile limits. Keep serial acceleration disabled.

Define acceptance limits before measuring: byte deadlines, host phase windows,
ACK/data/device timeout bounds, alarm lateness and maximum CRITIC deferral.
Sweep initial IRQ/VBI phases and alarm coincidences. Exercise back-to-back
result/data reception, last-byte TX acceptance/completion, command-line changes,
no-response timeout and a background progress counter. Deliberately violate a
byte/phase deadline in a negative control so a final successful-looking reply
cannot hide a failed timing check.

**Acceptance:** lossless actual TX and RX plus complete framed transactions at
the target, within the pinned profile's timing limits, with intact contexts and
guards and a demonstrably bounded silent-device exit. Use passive observation
and identical-image uninstrumented replay. Pure assembly has no raw/optimized
NIR distinction; any compiled caller/worker must be checked in both modes.
Do not advertise more than the tested one/two-task workload.

**Evidence:** proposed `docs/qualification/sio-feasibility.json`, the resolved
platform/peripheral profile and a short finding in the implementation record.
Record diagnostic reservations separately from production. If the alarm or RX
path fails, retain the failure, revise the hardware approach and rerun this gate
before production SIO work. A slower-rate pass is useful evidence, not a waiver
of the 125-kbaud requirement.

## Slice 2: current native I/O contract

**Complete.** The [ABI qualification](../qualification/io-abi.json) confirms all
three layouts, ten call shapes, signed results and rejection of every production
device import. The current Task ABI version is unchanged; slice 3 coordinates
the first production bindings and version update.

Generate the ten import declarations, classic command/error constants and
IOF_QUICK. Qualify the design's proposed IORequest 26/2, IOStdReq 42/2 and
IOSIOReq 52/2 sizes/alignments, native far pointer fields and 32-bit lengths,
offsets, units, flags and timeout. Preserve flattened classic prefixes and
Message.mn_Length as CARD. The emitted compiler layout is authoritative.

Generate the SIO transaction command, direction/profile fields and device error
constants without pretending that the driver exists. Define private guarded
packets only where the later slices need them. Validate service selectors against
Task, signal, heap, port and diagnostic families. Record the actual native
argument padding, result locations and stack effects. Coordinate one updated
reported Task ABI when the first production I/O bindings land in slice 3.

**Acceptance:** emitted raw/optimized probes cover every field, array stride
and call shape; request fields spanning bank boundaries; nonzero pointer banks;
equal low addresses in different banks; CheckIO-style pointers with low word
zero; adjacent canaries; maximal full-width arguments; and signed io_Error
results including -1, -2 and a positive SIO error. Do not zero-extend BYTE errors
to INT. Production imports still reject as unimplemented. Package checks reject
stale generated files, collisions, bad padding and successful test-stub bindings.

**Evidence:** proposed `docs/qualification/io-abi.json`, including compiler
interfaces, final generated/image hashes and unchanged or explicitly updated
memory reservations. Layout arithmetic or a host-only test is insufficient.

## Slice 3: allocation, resident opens and immediate dispatch

**Complete.** See [lifetime and immediate dispatch](../history/device-io-sio-implementation.md#slice-3-request-lifetime-and-immediate-dispatch)
and the [qualification record](../qualification/io-lifetime.json).

Bind CreateIORequest/DeleteIORequest and OpenDevice/CloseDevice. Create uses
ordinary PUBLIC|CLEAR memory, accepts 16..65535 bytes with a non-null reply port,
initializes an inactive Message and preserves the requested mn_Length. Delete
uses that length, accepts null, and does not close a device or free a buffer/port.
Reject detected invalid context/record extent before accessing absent fields.

Implement a static resident table with exact-name lookup, validated unit/flags,
short native dispatch and explicit open counts. Failed open leaves a harmless
close state without leaking resources. Preserve borrowed bindings across multiple
separately initialized requests; Close requires those requests collected before
the owning open is released. Do not add automatic request tracking to enforce
caller-owned lifetime.

Bind BeginIO, SendIO and CheckIO. Use an immediate test device with supported,
unsupported and failed commands. BeginIO preserves flags; SendIO sets all flags
to zero. A permitted quick operation leaves IOF_QUICK set and completes without
reply; every non-quick completion goes through ReplyMsg exactly once. CheckIO
observes status without unlinking. No request is read after reply publication
on a nonblocking return path. DoIO, WaitIO and AbortIO remain unbound until slice 4.

**Acceptance:** raw/optimized heap and signal totals match before/after;
allocation exhaustion and rejected sizes leave no partial resource; 16-byte
allocations cannot lead to out-of-bounds I/O-tail accesses; undersized extensions
report BADLENGTH through the defined path. Exercise null deletion, valid static
requests, exact names, missing devices, nonzero high unit/flag words, repeated
opens, failed-open close and borrowed requests. Test errors, flags and reply
types, PA_IGNORE/PA_SIGNAL, a separate reply-owner task and reuse before SendIO
returns. Use valid lifetimes; do not claim arbitrary duplicate-close/stale-pointer
detection. Require context, bank ownership and guard restoration.

**Evidence:** proposed `docs/qualification/io-lifetime.json`. Test-only resident
entries are absent from ordinary builds; production sio.device remains absent.
Document the seven available generic imports and the current ABI tag.

## Slice 4: queued replies, specific waits and abort

**Complete.** See [queued completion](../history/device-io-sio-implementation.md#slice-4-queued-completion-and-cancellation)
and the [qualification record](../qualification/io-queues.json).

Add a queued test device with one worker, known active pointer and a finite
test-controlled completion event. All queue changes use protected task policy.
Remove a pending head and publish active/preparing state with its cancellation
latch in one transaction. A cancellation during preparation must survive the
later descriptor-publication step. Do not assume this device's queue policy is
a rule for every future Exec device.

Implement WaitIO as a caller-context loop over a private guarded check/collect
operation and the existing Wait. Remove the specified complete request directly;
leave unrelated reply messages untouched, including those ahead of it. Never
clear the signal between checking and waiting. Mark WaitIO-collected messages
NT_FREEMSG; leave GetMsg behavior unchanged. CheckIO and repeated observation do
not transfer ownership. Document that GetMsg and WaitIO are alternative collection
paths for one submission, not consecutive steps.

Implement DoIO by setting exactly IOF_QUICK, dispatching, and collecting only
when deferred. Implement generic AbortIO dispatch with no result or blocking;
the test driver removes a known queued request or latches active cancellation.
Terminal completion wins at one serialized publication point, so each deferred
submission replies once. A normal completion may win an abort race.

**Acceptance:** execute in raw/optimized mode with immediate/queued success,
quick refusal, errors, coalesced/stale/shared signals, an unrelated message at
the reply head, out-of-order replies and completion before WaitIO. Force arrivals
between check and Wait, NMI during wait publication, abort while queued/preparing/
active/terminal and after collection, and reply/reuse before the submitter returns.
Verify direct removal without scans, no early buffer reuse, exact io_Error results,
no unrelated message loss and progress of another task during DoIO/WaitIO.

Reject IRQ/NMI/reentrant and I=1 calls through bounded fault tests; WaitIO/DoIO
also reject wrong-owner/PA_IGNORE reply ports. Check nested Forbid restoration
on both immediate and blocking paths. Preserve full context/DP ownership and
caller stack headroom; the IRQ in a race test can signal, but cannot manipulate
port links. Run targeted Task/signal/port regressions for the shared helpers.

**Evidence:** proposed `docs/qualification/io-queues.json`. All ten generic
imports now have executable evidence with test devices. No real SIO claim follows.

## Slice 5: production hardware ownership and bounded primitives

Port the passing slice-1 mechanisms into the actual Task platform adapter.
Implement receive, output-ready, output-complete and alarm routing through both
native and emulation IRQ entry. Preserve the complete saved contexts, hidden
register halves, stack/domain boundaries and NMI-aware scheduling guard. Chain
unowned sources, including simultaneous pending interrupts.

Implement the selected alarm/clock contract, bounded buffer/checksum operations,
descriptor publication, cancellation latch, terminal commit and direct worker
signal. Prepare long descriptor fields with IRQs enabled while inactive; publish
only a fully initialized descriptor in a short protected handoff. Stop all
references to caller memory before terminal publication. Drain old sources and
deliveries before descriptor/binding reuse; generation checks supplement this
quiescence rather than replacing it.

Extend the OS boundary with exclusive SIO ownership across transfers/recovery.
Serialize acquisition against OS entry and reject/defer conflicting ROM SIO
before entering ROM. Save/restore owned serial/alarm vectors, register shadows,
PIA bits, enable bits and CRITIC; merge unrelated changes. Never read a write-only
register alias as saved configuration. Provide bounded release and OS stage-two
service opportunities, including error paths. No call to SIOV services a request.

**Acceptance:** a Task-kernel fixture performs actual buffered TX/RX and alarm
timeouts using the production primitives, with native/emulation callbacks and
the known worker signal. Force NMI during partial descriptor writes, IRQ during
claim/release, early/late alarms, stray completion and pending source at reuse.
Verify no stale buffer access, no recursive policy entry, full restoration and
no missed unowned interrupt. Test failed claim during OS activity with unchanged
ownership, correct release with an originally nonzero CRITIC, and resumed OS
service with an originally clear CRITIC.

Repeat relevant byte/alarm timing after moving the code into the real kernel;
slice-1 timings cannot qualify a changed entry path. Qualify all introduced
native stack peaks and mapped code/data extents. If assembly has compiled
wrappers or policy callers, exercise their raw and optimized builds.

**Evidence:** proposed `docs/qualification/sio-adapter.json`. No ordinary
resident sio.device entry is published yet.

## Slice 6: one worker and complete queued transactions

**Implemented.** See [queued transaction evidence](../qualification/sio-transactions.json).
The test-only worker uses the production request, port and signal paths.
Recovery and ordinary registration remain gated by slice 7.

Implement the SIO worker and per-unit records, using the design's single private
FIFO and request/completion signal pair. Admit and initialize the worker before
test registration; rollback task, signal, port and storage failures. Open has no
wire traffic. Multiple unit IDs/opens must share this worker and one active bus
transaction. Clear active ownership and publish a reply in one guarded step.

Validate IOSIOReq, configured disk IDs $31–$38, zero open flags/io_Offset,
direction, profile, complete address extent, payload limits and timeout range.
Use widened arithmetic before forming a far cursor. Implement NONE/READ/WRITE
transaction sequences, command/payload checksums, delayed phase alarms and
payload-only io_Actual. Receive result-plus-data without an intervening worker
wake, drain expected data after a device Error, and wait for the last TX byte
to actually finish before changing direction or releasing the bus.

Start the active timeout at COMMAND assertion, not submission. Every enabled
phase already has a bounded failure/cleanup path; slice 7 completes the full
public cancellation/recovery contract before exposure. Use profile rules from
slice 1, with no silent baud downgrade, invented ACK or automatic write retry.
Before the next descriptor starts, retire the terminal latch and restore
CRITIC. Under the dedicated Exec policy, clean completion needs no OS-service
sleep; error recovery retains its separate quiet interval and offline checks.
A signal bit is not a completion counter.

**Acceptance:** through test registration, run full OpenDevice/SendIO/WaitIO and
DoIO request cycles against the pinned disk/responder, including read-back of
writes to disposable test media. Use multiple clients/units, queued bursts,
ordinary and LINEAR upper buffers, cross-bank request fields/cursors and zero/
oversize/invalid-direction/profile inputs. Compare wire bytes and returned data,
error/count fields, FIFO starts and exactly-one replies. Verify other tasks make
progress and the worker sleeps between work. Confirm no allocation/port call
inside IRQ and no extra task, signal or buffer allocation per request.

**Evidence:** proposed `docs/qualification/sio-transactions.json`, including
raw/optimized results and the exact tested profiles. Public driver registration
stays disabled outside the fixture until slice 7.

## Slice 7: cancellation, recovery, shutdown and publication

**Implemented.** See [recovery qualification](../qualification/sio-recovery.json),
including raw/optimized failure injection and the ordinary read-only example.

Complete queued, preparing and active AbortIO paths. Preserve cancellation across
preparation/arming and serialize it against terminal publication. If normal
completion wins, retain its result; accepted cancellation returns ABORTED only
after all references to caller storage have retired. An inactive request is not
re-enqueued or replied by AbortIO. No cancellation undoes an issued write.

Cover every protocol failure and timeout with the design's error mapping and
first-cause rule. Enforce absolute active deadlines with wrap-safe clock handling,
including silent phases, without waiting for the worker to execute. Record the
maximum cancellation-observation and timeout-enforcement lateness for the profile.

Separate returned-buffer safety from bus recovery. After returning a terminal
request, recovery may use private discard state, never that request or buffer.
Prove a profile recovery safe before starting another transaction. If it fails,
latch the bus offline, return BUSUNAVAILABLE to queued/new work and continue to
exclude ROM SIO. Reopen cannot clear the offline state. Implement a bounded,
qualified reset/recovery or an explicit platform-reset-required exit; do not
invent an unqualified public reset command or silently return unsafe ownership
to ROM.

Complete startup rollback and shutdown ordering: stop admission, settle/collect
requests under the application's lifetime protocol, quiesce sources/callbacks,
drain pending wakes, release the bound producer, then release ports/signals and
remove the worker. Closing an open does not tear down a shared resident worker
needed by other opens. Reject known invalid bound-worker removal; do not add a
hidden ledger claiming to detect every client lifetime violation.

**Acceptance:** inject queued/preparing/active/terminal abort races, absent
peripheral, NAK, Error-plus-data, bad checksum, framing/overrun, short/extra data,
late byte/alarm after retirement, clock wrap and recovery failure. Check exact
once-only completion and error precedence. Poison/reuse a collected buffer and
prove no later ISR writes it. Verify queue progress or explicit offline replies,
no ambiguous reopen recovery, restored unrelated OS state, guarded shutdown,
resource totals and successful restart from a qualified clean state.

Publish sio.device only after these raw/optimized cases and its normal wire
transactions pass. Add a small `examples/device-io.act` using a caller-owned
reply port and request, asynchronous submission/collection, and correctly ordered
close/delete. Default the example to read-only use; write tests use disposable
media. Run it on the same public build that users will receive.

**Evidence:** proposed `docs/qualification/sio-recovery.json`. Record the
profile's supported operations and recovery limits, along with ordinary build
registration and the example. Concurrent eight-task timing is still pending.

## Slice 8: concurrent qualification and final integration

**Implemented.** See [concurrent qualification](../qualification/sio-concurrency.json)
and [integration regressions](../qualification/io-sio-regressions.json). Timing is
qualified for kernel bank 1; bank 3 has functional coverage only. STOCK810's
profile timeout was increased to two seconds after a cold-device timeout; byte
and phase deadlines retain their original limits.

Start with four public tasks, then admit all eight public tasks before releasing
the workload barrier. In the eight-task fixture, root + SIO worker + six clients
uses exactly eight contexts; idle remains additional. Root supplies background
allocator/registry/compute activity while clients submit/collect finite bursts.
Include multiple reply ports sharing signal bits, at least two outstanding
requests per participating client, multiple configured units and both wait styles.
Do not add hidden helper tasks or replace simultaneous capacity with sequential
task creation.

Run actual command/read/write traffic at stock speed and the 125-kbaud target.
Use the largest accepted payload for each profile and sustained sequences of
legal transactions without mandatory clean-completion sleeps. A 65,535-byte diagnostic stream
does not become a legal sector transaction; use it only as a separately scoped
buffer-pump stress case. Interleave cancellations/timeouts in functional stress,
and keep deliberate fault stalls separate from normal timing runs.

Include allocator fragmentation/CLEAR, port bursts, long-name registry lookups,
Signal/Wait, Sleep/Yield, bounded Forbid sections and the supported unowned IRQ
and ROM activity. Declare workload counts, queue depths and maximum Forbid/OS
deferral bounds before accepting timing. Check progress during active transfers,
not only after the last reply. Record separately:

- RX arrival-to-read and TX ready-to-refill, byte loss/gaps and actual baud;
- phase-window/alarm jitter, command and final-bit turnaround;
- maximum IRQ-masked interval and OS stage-two deferral;
- IRQ completion-post-to-worker, next-request start and client collection;
- request identities/counts, queue fairness, background progress and heap/signal/
  bank ownership totals, with complete stack/DP guards.

**Acceptance:** raw/optimized functional coverage includes kernel banks 1 and 3
and capacities four/eight. Run concurrent timing in both compiler modes at both
capacities for each profile being advertised; every timing claim names its tested
kernel bank and machine/peripheral configuration. A functional bank-3 run does
not qualify bank-3 timing. Require zero byte loss and missed byte/phase deadlines,
bounded timeouts/recovery and continuing background/OS progress. Observed maxima
remain measurements, not universal worst-case guarantees.

Use a passive observer and replay each accepted timing image unchanged on the
pinned uninstrumented emulator. Compare bytes, outcomes and progress; record
functional and timing verdicts separately. Include failing controls for missed
RX/TX/phase deadlines and malformed qualification records. Run the relevant
Task/signal/port/heap/Lists, loading, native context and OS-coexistence regressions,
reporting exactly which cases are newly executed.

**Evidence:** proposed `docs/qualification/sio-concurrency.json` and
`docs/qualification/io-sio-regressions.json`. Update README, roadmap, design
status, this plan and the implementation record to the actual accepted scope.
Do not call this complete if eight-task timing or the 125-kbaud profile fails.
DOS and physical-hardware qualification remain separate milestones.

## Storage, reproducibility and completion

Use the existing [1 MiB functional pin](../../toolchain/altirra-1m.json),
[8× upper-RAM serial pin](../../toolchain/altirra-signals-1m.json) and
[passive observer pin](../../toolchain/altirra-concurrency-observer.json) as inputs
to the new peripheral profile. The older 64 KiB serial probe configuration alone
cannot qualify upper-RAM transfers. Verify actual ROM/emulator binaries, resolved
memory/CPU/video settings, disabled serial acceleration, peripheral identity,
firmware and media hashes. Record any local override explicitly.

Each evidence record contains source/generated/final-image hashes, compiler and
ABI identity, optimization mode, task capacity, kernel bank, case names, explicit
completion limits, raw observations and pass/fail scope. Keep bridge credentials
and raw private bridge logs out of committed records. Normalize host text line
endings before parsing text fixtures; preserve binary/media bytes exactly.

Give every native entry/helper measured or checked stack depth, including
nested IRQ/NMI headroom. Keep code/state in upper RAM except justified native
stack/DP or ROM-vector requirements. The planning baseline was a 4,096-byte
upper helper reservation containing 3,368 bytes normally or 3,482 with the pump.
Slice 5 enlarged that upper reservation to 8,192 bytes; the final production
helper occupies 6,271. Extents are reserved before heap registration, and final
packaged bindings/overlaps are checked.

The baseline complete bank-zero reservations are:

| Reservation | Four public tasks | Eight public tasks |
| --- | ---: | ---: |
| Fixed runtime, excluding OS | 11,824 | 10,560 |
| Root | 1,856 | 2,080 |
| Each other public task | 1,856 | 1,568 |
| Private idle | 1,856 | 1,056 |
| Runtime, including 36,864 OS bytes | 57,968 | 61,536 |
| Loading, including OS | 58,560 | 57,232 |

Target zero growth in fixed/per-task bank-zero reservations; the SIO worker uses
one existing slot. Any justified growth must retain eight-task capacity and
pass renewed headroom/layout checks. Every slice reports complete before/after
loading/runtime reservations, fixed and per-task deltas, guards, alignment,
unused reserved capacity and separate diagnostic costs, including a zero delta.
The original documentation-only plan reserved **zero additional bytes**. The
implemented upper-RAM costs and unchanged bank-zero totals are recorded per slice.

The milestone is complete only when all eight slices have their own commits and
passing evidence, all ten generic imports and the public example execute, and
actual queued SIO passes its normal/error/recovery and concurrent timing gates.
The next work is DOS/block integration above this qualified interface, without
claiming filesystem or physical-device support from these emulator results.
