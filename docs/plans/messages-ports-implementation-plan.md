# Messages and ports implementation plan

Status: all six slices complete, 2026-09-19. The
[design note](../reference/ports.md) defines the public contract and its
deviations from classic Exec; this plan defines executable boundaries and
acceptance. Each completed slice links its executable qualification evidence.

Deliver messages and ports before queued device I/O and DOS. Keep the initial
**task-only port-call restriction**: an IRQ posts a completion signal through
the existing adapter, and a task performs ReplyMsg. Public IRQ queue operations,
PA_SOFTINT, device APIs and DOS remain separate work. Eight-task functional
operation is required; eight-task concurrent serial timing remains explicitly
deferred and is not an entry condition for this milestone.

## Scope and working rules

Implement all nine native `EXEC` imports: PutMsg, GetMsg, ReplyMsg, WaitPort,
CreateMsgPort, DeleteMsgPort, AddPort, RemPort and FindPort. Support caller-prepared
and heap-allocated records, private/public ports, PA_SIGNAL/PA_IGNORE, native
24-bit links and the existing full Node/List representation. Preserve FIFO
messages, priority-ordered public discovery, uncounted signals, non-removing
WaitPort and explicit send/reply lifetime.

Do not introduce handles, payload copying, queue-capacity errors, an allocation
per send, a worker per port, automatic Task cleanup or a private-port ownership
table. Keep mn_Length as a 16-bit descriptor length; larger payloads use a far
pointer and LONGCARD length in an application-defined body. Existing Task
admission and stack/DP pools remain unchanged.

Implement policy in Action!, using native code for the ABI/context boundary.
Follow the [platform contract](../reference/platform.md) and
[critical-section protocol](../history/kernel-critical-sections.md). With an I=0 caller,
queue and registry work runs with IRQs permitted under E816_SWITCHING. Never
hold SEI over a list operation or name scan, recursively enter policy through
public Signal, or suspend an activation on the shared kernel stack.

Use the compiler revision recorded in [actionc.json](../../toolchain/actionc.json),
currently `e7266982c22527040dfc2a46508be8475581fe8f`. Compiler defects belong in
actionc with focused regressions and an explicit pin update. Preserve one
current Task implementation, COP #$50 and OS COP #$00. Change generated
definitions, callers and tests together when the current ABI changes.

Each slice must run its changed behavior as emitted raw and optimized code,
publish its evidence and be committed before the next major slice. Test-only
ABI shims and race hooks must not become production fallbacks. Until a service
lands, its production import must reject rather than bind to a successful stub.
Run relevant checks per slice and the wider integration matrix at the end.

## Slice sequence

| Slice | Executable result | Proposed commit boundary |
| --- | --- | --- |
| 1. Native contract | Nine import shapes, record layouts and constants execute through ABI probes | `Define classic Exec message and port ABI` |
| 2. Send, receive and reply | PutMsg/GetMsg/ReplyMsg work on manually prepared ports with direct notification | `Implement task-context message queues and replies` |
| 3. Waiting | WaitPort loops safely on the existing Wait, retaining caller-owned continuation state | `Implement race-safe WaitPort` |
| 4. Port lifetime | CreateMsgPort/DeleteMsgPort manage upper-RAM storage and the caller's signal | `Implement message port creation and deletion` |
| 5. Public discovery | AddPort/RemPort/FindPort use a generated upper-RAM registry | `Implement named message port discovery` |
| 6. Integration | Ownership, interrupt races, eight-task operation and four-task serial timing pass | `Qualify messages and ports under concurrent kernel work` |

Slices 2–3 use static ports and allocated signals, so they can execute before
CreateMsgPort exists. Slice 4 provides complete private-port use. Slice 5 adds
discovery without changing the queue representation or private-port contract.

## Repository integration

| Location | Planned work |
| --- | --- |
| Proposed `abi/ports.json`, `tools/generate_ports.py`, `lib/exec/exec-port-types.inc`, `lib/exec/port-call-types.inc` | One current schema for records, constants, import shapes and guarded helper packets; generated Action!/assembly definitions and stale-file checks. |
| [generate_tasks.py](../../tools/generate_tasks.py), [tasks.json](../../abi/tasks.json) | Include the generated port API in the actual Task `EXEC` module, coordinate selector/tag validation and exclude new internal helpers from task-entry discovery. |
| [taskpolicy.act](../../lib/exec/taskpolicy.act), [task-signals.inc](../../lib/exec/task-signals.inc), proposed `lib/exec/task-ports.inc` | Guarded queue/registry operations, reusable signal posting without an immediate switch, initialization and misuse handling. |
| Proposed `platform/altirraos/ports.s`, [tasks.s](../../platform/altirraos/tasks.s) | Checked native bindings and caller-context wrappers for WaitPort/Create/Delete; use compiled Action! helpers where suitable. |
| [native_program.py](../../tools/native_program.py), [generate_memory.py](../../tools/generate_memory.py), [generate_heap.py](../../tools/generate_heap.py), [banked_image.py](../../tools/banked_image.py) | Reserve the registry before image layout, bind final helper addresses, validate extents and retain complete build provenance. |
| Proposed `tools/test_ports.py`, `tools/ports_model.py`, `tests/test_ports_package.py`, `tests/programs/ports_*` | Reuse existing build, emulator, guard and far-memory helpers; add independent queue traces, context/lifetime tests and bounded race probes. |
| [test_signal_concurrency.py](../../tools/test_signal_concurrency.py), [signals_concurrent.act](../../tests/programs/signals_concurrent.act) | Add port and registry workloads without increasing the four-task fixture's capacity; retain identical uninstrumented replays. |

These new paths are proposed files, not existing implementations. Expose only
the nine agreed public calls; a private head check, delete preflight or compiled
caller helper is not another application API. The Task builder generates its
own EXEC module, so editing only `lib/exec/exec.act` is insufficient.

Generated kernel helpers must not become admissible application entry points,
and kernel registry storage must not enter application writable bindings. Port
records themselves must work in caller-owned heap RAM as well as static image
storage: do not reuse Task admission's image-only Writable check as a port
ownership test. Addressability, queue membership and live allocation ownership
are distinct; no TypeOfMem check proves all three.

## Slice 1: native API, constants and layouts

Completed: [ABI qualification](../qualification/ports-abi.json) records raw/optimized
layout and call probes, rejection of all nine unimplemented production imports,
two Task-core regressions and 64 host checks. MsgPort is 27 bytes aligned to one;
Message is 16 bytes aligned to two. Bank-crossing fields, native pointer banks,
array strides, bit 31 and OS/guard restoration pass. Full fixed/per-task
bank-zero reservations remain unchanged. Production queue bindings are slice 2.

Define the design's records and constants without enabling unfinished services.
Qualify expected MsgPort size/alignment 27/1 and Message 16/2, all field offsets,
array strides and embedded full Node/List prefixes. Do not round every record
to an even size merely because the current Task-layout generator does so;
the pinned compiler's emitted layout is authoritative.

Generate all nine declarations/import shapes, pointer-or-null results and void
results, NT_MSGPORT/NT_MESSAGE/NT_FREEMSG/NT_REPLYMSG, PF_ACTION and the three
named actions. Preserve existing node constants without conflicting definitions.
Keep Message.mn_Length as CARD and mp_SigBit as a number, with full-width signal
mask formation in the eventual caller/helper code.

Define the guarded service and private helper packets needed by subsequent
slices. Check selectors against the core, Task, signal, memory and private IRQ
adapter families; do not assume nine public imports need nine distinct COP
operations. Record actual native argument padding, pointer-result bank handling,
stack requirements and interrupt effects. Assign the updated reported Task ABI
tag when the first production port bindings land in slice 2.

**Acceptance:** raw/optimized probes execute each call shape and field access,
with nonzero bank bytes, equal low addresses in different banks, maximal CARD
values, arrays, boundary-spanning fields and adjacent canaries. Test MsgPort's
byte alignment and Message's qualified alignment separately. Package tests
reject stale definitions, narrowed pointers, bad offsets, selector collisions
and accidental production bindings. Existing Task/API generation remains valid;
bank ownership and complete bank-zero reservations do not change.

**Evidence:** proposed `docs/qualification/ports-abi.json`, including compiler
identity, interface metadata, source/generated/image hashes and emitted results.

## Slice 2: task-context queue operations and direct notification

Completed: the [queue qualification](../qualification/ports-queues.json) records
the public bindings, FIFO/reply traces, cross-bank forwarding/reuse, native
contexts, controlled misuse and forced IRQ/NMI link-write races. Targeted
signal regressions and complete unchanged bank-zero budgets accompany it.

Bind PutMsg, GetMsg and ReplyMsg using manually initialized upper-RAM ports.
Validate the native domain, widths, current tag, packet extent and supported
arrival action before touching queue state. Reject invalid PA_SIGNAL targets
through the existing direct Task/context association; do not search tasks.
PA_IGNORE must not inspect a signal target or form a mask from its unused bit.

Under the existing guard, set the message type, finish AddTail links, and only
then post to the known receiver. GetMsg uses RemHead, returns null for an empty
queue and preserves type/metadata and stale removed links. ReplyMsg selects
NT_REPLYMSG and the supplied reply port; null reply ports set NT_FREEMSG without
queueing, notification or freeing storage. Keep message priority out of FIFO
ordering and never copy the body or allocate inside these operations.

Refactor the current SignalTask path carefully: its existing helper can call
Switch immediately. Extract an internal posting operation that updates received
bits and the known target's ready/wake state without scheduling midway through
a caller's queue transaction. Public Signal must retain its existing observable
behavior, including direct readiness under Forbid and cancellation of an already
queued IRQ wake. Port operations schedule only after links and notification
are complete, using the existing dispatch finish and native pending-wake recheck.

Use the existing native mask/wake transactions; no new IRQ-shared message list
is introduced. IRQ/NMI may interrupt partial port writes but cannot traverse
them or start another policy activation. Preserve caller I/Forbid state and
return contexts; I=1 non-waiting calls must not enable IRQs or switch tasks.

**Acceptance:** compare FIFO send/get/reply traces against an independent model
of message identities, queues and protocol ownership, not copied link code.
Cover multiple senders, PA_IGNORE and PA_SIGNAL, notification on an already
nonempty queue, coalesced signals, bit 31, empty GetMsg, null replies, forwarding,
private pending lists, repeated reuse and a LINEAR payload larger than 64 KiB.
Verify exact once-only delivery and no payload changes by the kernel. Arrange
a reply/reuse before the original sender's PutMsg returns and verify the wrapper
does not read the transferred message after publication.

Exercise invalid actions, null arguments and a removed signal target as bounded
misuse cases; require no enqueue before a detected validation failure. Do not
promise reliable detection of duplicate enqueue or stale address reuse without
a ledger. Reject port calls from a real IRQ without damaging interrupted kernel
DP/guard state. Run targeted Signal/Wait, pending-wake and full-context regressions
for the internal-post refactor, including real IRQ/NMI entry between link writes.

**Evidence:** proposed `docs/qualification/ports-queues.json`. Record public API
bindings and the updated single ABI tag. All six remaining public imports still
reject until their slices land.

## Slice 3: WaitPort on the existing Wait

Completed: the [WaitPort qualification](../qualification/ports-wait.json) records
raw/optimized queue peeks, stale/shared bits, Forbid restoration, an injected
arrival in the empty-check/Wait gap, NMI during wait publication and misuse.
The native continuation uses only the caller's existing stack reservation.

Implement a short private guarded head check that validates a PA_SIGNAL port,
mp_SigTask equal to the caller and I=0, including when the queue is nonempty.
It returns head-or-null without unlinking. Its public wrapper loops on that
check and the existing Wait with the port's unsigned 32-bit mask. Keep the
port pointer and continuation on the calling task's stack/DP; release every
kernel activation before blocking. Do not add a Task wait reason, waiter list,
shared cursor or a new signal-consumption rule for ports.

Never clear a signal between the empty check and Wait. Preserve the existing
blocking-Wait behavior inside nested Forbid, including restoring the same depth
on resumption. Document that an immediate nonempty result does not consume a
signal or transfer ownership: GetMsg still removes the message. Another task
using GetMsg under an agreed handoff can invalidate a borrowed peek result.

**Acceptance:** force arrivals before the initial check, after an empty check
but before Wait, during wait publication, while blocked and just after wake.
For the task-only producer, use test scheduling checkpoints at safe boundaries;
an IRQ can post a spurious/shared bit but must never enqueue a test message.
Cover bursts, already-nonempty ports without a pending bit, stale signals with
empty queues, shared-bit ports, combined port/other-event masks and wrong-owner,
PA_IGNORE and caller-masked misuse. Test I=1 rejection for both empty/nonempty
ports and exact Forbid-depth restoration. Prove other tasks progress while a
caller is blocked, with no lost queue entries or kernel-stack continuation.

**Evidence:** proposed `docs/qualification/ports-wait.json`, recording injected
interleavings and bounded completion. Keep deliberately stalled probes out of
serial timing workloads.

## Slice 4: creation, deletion and explicit lifetime

Completed: the [lifetime qualification](../qualification/ports-lifetime.json)
records raw/optimized allocation and signal failure rollback, exact accounting,
stale-bit reuse, Forbid/masked callers, deletion misuse, finalized helper thunks
and the public request/reply example. No additional bank-zero reservation was
needed.

Implement CreateMsgPort as a caller-context operation using the public allocator
and signal services. Allocate ordinary PUBLIC|CLEAR storage, then allocate a
signal for the current task; free the storage if the signal allocation fails.
If memory allocation fails, return null without touching signals. Initialize
NT_MSGPORT, null name, priority zero, PA_SIGNAL, owner/bit and an empty message
List, including its metadata, before returning the pointer. Do not register it.

Use the qualified size rather than a hardcoded Amiga size: the expected 27-byte
request consumes 32 heap bytes. No pointer is externally published during
partial setup. Keep acquisition/rollback state invocation-local and preserve
caller I and Forbid nesting. No allocation or initialization runs on a suspended
shared kernel stack.

DeleteMsgPort(null) does nothing. For a nonnull port, check the current owner,
valid retained signal and empty queue before releasing either resource; then
release its signal and use the matching FreeMem size. PA_IGNORE after an inactive
mode change must still release the original owned signal. Require the caller to
have stopped producers, settled dequeued requests and removed any public name.
Do not infer CreateMsgPort provenance or registry membership from stale links,
add a hidden allocation prefix, or scan private ports to claim full validation.
The public-registry precondition becomes relevant in slice 5.

Manual ports retain explicit manual cleanup. RemTask does not call DeleteMsgPort,
reply outstanding messages or repair a forcibly interrupted creation. A valid
handoff can retain a message/buffer after its allocating task exits, but a
PA_SIGNAL destination and the creator of a dynamically allocated port must
remain alive until their producer/deletion obligations are finished.

**Acceptance:** exercise allocation failure, signal exhaustion after successful
allocation, exact rollback of free totals and signal allocation masks, repeated
create/delete, null deletion, wrong owner and nonempty queue faults before
resource release. Verify stale pending bits are cleared on signal reallocation,
not assumed cleared by FreeSignal. Test ordinary and SIGNAL-to-IGNORE lifetime,
static/manual ports, several ports per task, orderly producer shutdown and
outstanding requests/replies. Reclaim messages only after the agreed terminal
reply has been dequeued. Add a raw/optimized public request/reply example,
proposed as `examples/messages.act`, with complete cleanup and failure handling.

**Evidence:** proposed `docs/qualification/ports-lifetime.json`, including
resource accounting and native wrapper stack peaks.

## Slice 5: public registry and safe discovery

Completed: the [registry qualification](../qualification/ports-registry.json)
records the bank/capacity matrix, restart, name/order cases, safe rendezvous,
IRQ/NMI link races and trusted cleanup with corrupt registry links. The
registry adds 16 upper bytes and no bank-zero reservation.

Reserve a separate full List in the configured kernel-bank prefix before final
image placement: 11 active bytes, expected 16 reserved including padding.
Generate its address/extent for Action!, assembly, maps and packaging. Coordinate
with the existing bank table and heap prefix, moving the emitted-code origin
as needed; do not hardcode bank 1, reuse another list, or add a bank-zero pointer
cache. Reject image/metadata overlaps and keep registry storage outside heap
regions and application writable bindings.

Initialize the registry before application admission on every launch. Its
storage belongs to the kernel image reservation, not a heap allocation or new
bank owner. Normal shutdown follows application quiescence; fault/launch cleanup
must not walk potentially corrupt port/name/message chains to release banks.
Check restart and initialization-failure handling against the existing trusted
heap-claim shutdown path.

Implement AddPort on an inactive caller-prepared port: set NT_MSGPORT, initialize
the message List and Enqueue mp_Node in descending signed priority with FIFO
ties. Support unnamed entries and duplicate names. FindPort uses first exact
case-sensitive match; RemPort unlinks its known node without clearing messages,
freeing resources or revoking retained pointers. IRQs remain enabled during
registry scans. Do not add a uniqueness policy or mandatory registry scan to
PutMsg, ReplyMsg, GetMsg, WaitPort or DeleteMsgPort.

Require Forbid across FindPort and immediate use, or FindPort/AddPort when an
application needs unique registration. Internal serialization protects a scan,
not a returned pointer after Permit. AddPort reinitializes its queue, so a
removed port may be registered again only after becoming inactive; do not use
republication as a way to rename a live queue.

**Acceptance:** validate resolved maps and ownership at kernel banks 1 and 3,
four/eight-task capacities, raw/optimized, including empty startup and restart.
Test signed priority extremes, ties, duplicate/unnamed entries, empty strings,
case/prefix misses, long and cross-bank names. Interleave named lookup/send and
removal with real preemption while preserving the outer Forbid contract.
Verify RemPort leaves queued requests usable and established clients can still
send under a valid retained-pointer agreement. Test drain/quiesce/delete and
inactive re-registration without claiming AddPort can diagnose every active
or already-linked port. Extend the example to show safe named rendezvous.

**Evidence:** proposed `docs/qualification/ports-registry.json`, with full map
and budget accounting. All nine public APIs are implemented; integrated
qualification is recorded in slice 6.

## Slice 6: concurrent lifetime, interrupt races and timing

Completed: [concurrency qualification](../qualification/ports-concurrency.json)
covers the complete IRQ-signal-worker-reply path, the eight-task bank/mode matrix,
17 ports, retained messages and blocked-caller removal. Four-task transfers of
4,096 and 65,535 bytes pass raw/optimized timing and identical-image replay.
[Selected regressions](../qualification/ports-regressions.json) and the
[implementation record](../history/messages-ports-implementation.md) state the measured
limits, exact test scope and unchanged bank-zero reservations.

First run a bounded end-to-end fixture: client request, worker GetMsg, actual
POKEY completion IRQ, existing bound signal, worker Wait resumption, ReplyMsg
and client reply removal. Another runnable task must progress during the wait.
Use the existing diagnostic byte pump and preallocated state; do not grow this
fixture into a device ABI, production RAM-buffer driver, RX or DOS implementation.
No IRQ may call a port API even in a test advertised as supported operation.

Exercise eight simultaneously admitted tasks with a startup barrier before
exchanges begin, using both kernel banks 1 and 3 in raw/optimized builds.
Combine multi-client requests, replies, shared-bit ports and explicit allocation
lifetimes. More ports than tasks must work without more contexts. Include
messages retained after their allocating task exits under a valid handoff,
and port-owner shutdown only after all producers and outstanding work settle.
Check queue identities, once-only replies, signal/heap totals and bank ownership.

Inject real IRQ and NMI between partial queue and registry writes. IRQs exercise
the existing signal post/pending-wake path; tasks cannot observe partial links.
Include rejected IRQ/reentrant port calls, wake arrivals during dispatch exit,
caller removal during a blocked wait after external quiescence, full saved
contexts and stack/domain guards. Do not test undefined stale-pointer access
as if the public API promised recovery. Tests for intentional misuse terminate
through the bounded controlled-fault path separately from normal lifetimes.

Then extend the existing four-task timing fixture with request/reply bursts,
shared-signal drains, registry traffic and mixed allocator/CLEAR work. Exercise
growing message queues and public registries, including long shared name
prefixes; record exact lengths, port/message counts, outstanding depth and
iterations completed before the final refill. Keep the existing signal/sleep/
yield and allocator controls. Do not add a fifth task to hide contention.

Run 4,096- and 65,535-byte transfers for the added workloads in both compiler
modes on the pinned 8× profile. Use the passive observer, then replay each
identical XEX/workload on the uninstrumented emulator and compare functional
results. Require zero hardware refill misses and byte gaps, correct completion,
worker progress, intact guards and no resource leaks. Repair timing regressions
before declaring completion; keeping IRQs enabled alone is not evidence of
meeting the deadline.

Report hardware-ready-to-refill latency against the pinned approximately
78.94 µs deadline, maximum IRQ masking, IRQ completion-post-to-worker resumption,
and completion-post-to-client reply removal. The existing allocator's 30.842 ms
worker-delay observation is context, not a newly acceptable bound for a driver.
No RX/turnaround budget has been qualified. If a later driver requires an
unattainable worker turnaround, shorten serialized work or separately design
interrupt-safe queue/buffer advancement; do not silently enable IRQ port calls.

**Acceptance:** the above plus relevant Task, signal, memory, Lists, banked
loading and native/cooperative/preemptive regressions. Record the exact selected
cases; distinguish newly executed checks from historical evidence. Functional
eight-task success does not complete the deferred eight-task baud qualification.

**Evidence:** proposed `docs/qualification/ports-concurrency.json` and
`docs/qualification/ports-regressions.json`, with functional and timing verdicts
reported separately. A functional pass must not conceal a timing failure.

## Memory budget, records and completion

Use the [1 MiB functional pin](../../toolchain/altirra-1m.json),
[8× serial pin](../../toolchain/altirra-signals-1m.json) and
[passive observer pin](../../toolchain/altirra-concurrency-observer.json). Verify
actual binaries and machine settings. Each record includes the compiler and
native ABI, ROM/emulator hashes, optimization mode, kernel bank/task capacity,
source/generated/final-image hashes, case names, resource counts, explicit
timeouts/frame limits and outcomes. Publish parsed observations and hashes;
keep bridge authentication data and raw bridge logs out of committed records.
Normalize host text line endings before newline-sensitive fixture parsing.

Add named suites to the proposed `tools/test_ports.py` as slices land, reusing
existing harness support. Host model/generation tests supplement target
execution. Every native wrapper needs measured/checked call depth and stack
headroom, with final packaged bytes checked against resolved bindings. The
current shared native-helper reservation is finite; if port wrappers enlarge
it, update maps, collision checks and qualification rather than assuming space.

The implementation target is zero added fixed/per-task bank-zero reservation.
The registry adds expected upper-RAM storage of 16 bytes; CreateMsgPort consumes
32 heap bytes per instance plus an existing signal bit. Neither number creates
another Task or implies a new per-task arena. Use final maps, including code
growth into additional banks, for actual heap capacity and reservation costs.

Baseline complete bank-zero reservations from the
[allocator record](../history/memory-allocation-implementation.md):

| Reservation | Four public tasks | Eight public tasks |
| --- | ---: | ---: |
| Fixed runtime, excluding OS | 11,824 | 10,560 |
| Root | 1,856 | 2,080 |
| Each other public task | 1,856 | 1,568 |
| Private idle | 1,856 | 1,056 |
| Runtime, including 36,864 OS bytes | 57,968 | 61,536 |
| Loading, including OS | 58,560 | 57,232 |

For every slice, report complete before/after loading and runtime reservations,
fixed and per-task deltas, guards, alignment, slack and diagnostic costs. Active
bytes inside an existing reservation are not newly available memory. Any growth
needs a measured reason and renewed capacity/headroom qualification. This
documentation-only plan itself reserves **zero additional bytes**.

All six slices are complete with separate commits and executable evidence. All
nine public APIs and the example follow the design; the README, roadmap and
implementation record state the measured qualification scope.
Queued device I/O is the next design/implementation milestone, followed by DOS.
Public IRQ ports, soft interrupts, dynamic Task storage and eight-task concurrent
serial timing remain explicit follow-up work, with no compatibility profiles
or successful placeholders for deferred behavior.
