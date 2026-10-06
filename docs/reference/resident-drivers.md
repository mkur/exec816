# Resident driver boundary

This is the contract selected by S1 of the
[SIO migration](../plans/sio-driver-boundary-implementation-plan.md). S2/S3 implement the
request and lifetime boundaries described below.
The existing [device API](device-io.md#public-calls) is unchanged.

[timer.device](timer.md) uses the same caller-context resident routing, with
driver-owned deadlines/cancellation and a bounded native continuation instead
of a worker Task. Forbid serializes Task peers; a separate native edit gate
protects its pending table. It replies through the general native port binding,
with no timer-private kernel operation. SIO/console/display keep their existing
completion protocols.

## Calls and execution context

The built-in dispatch description assigns each resident an immutable route ID,
device identity, name and typed caller-context entry points. It is generated
from the I/O ABI input. OpenDevice's admission gateway returns either an error
or an internal route tag. Established Close, BeginIO and AbortIO calls select
the callback directly from `io_Device` in the caller-side library, without a
routing COP. SendIO and DoIO use that same BeginIO dispatch. No driver callback
runs with SWITCHING held. Routing is static; arbitrary runtime vectors and
dynamic driver registration are unsupported. The immediate test resident uses
the same caller-side dispatch.

| Entry | Signature | Responsibility |
| --- | --- | --- |
| Open | `INT (name, LONGCARD unit, IORequest pointer request, LONGCARD flags)` | Validate driver options, acquire one unit reference, bind handles, return a signed error. |
| Close | `PROC (IORequest pointer request)` | Release the settled open reference and clear its handles. |
| BeginIO | `PROC (IORequest pointer request)` | Accept or reject submission, preserve caller-prepared flags, queue or complete exactly once. |
| AbortIO | `PROC (IORequest pointer request)` | Cancel queued/preparing/active work according to the device contract; terminal work is unchanged. |

Entry points run on the original Task's stack and DP with IRQs enabled. The
generic caller wrapper holds Forbid across routing, request preparation and
the bounded callback. Open's worker-start rendezvous occurs before this region and uses a signal wait
that preserves any Forbid nesting inherited from the application.
Callbacks may nest public nonblocking calls, including Forbid/Permit and
PutMsg/ReplyMsg/Signal; they must not wait for hardware or suspend while shared
state is partial. The wrapper releases exclusion after callback return and
never rereads an asynchronously published request. No saved kernel activation
or shared compiler workspace survives across a callback.

Public native entry stubs check Task context; compiled helpers retain checked
stack frames. Operations that still enter the kernel check native packet bounds.
Creation/open perform initial admission; subsequent calls trust the caller's request, device/unit
binding and reply ownership. There is no per-call Bound callback or repeated
request/port validation. Driver callbacks check command-specific requirements
and operational state. SendIO clears all flags, BeginIO preserves them and DoIO sets
IOF_QUICK. Completed quick calls return a copied signed error; queued DoIO enters
the existing exact-request collection loop after releasing exclusion. CheckIO
observes the byte-wide completion type in the caller without exclusion or
dequeue; exact collection retains its kernel transaction.

The queued diagnostic device retains its kernel queue protocol behind TEST_BEGIN,
TEST_ABORT and TEST_CLOSE. Those selectors are rejected in production, and their
caller imports are generated only for the test profile. Request preparation is
shared with ordinary resident submission. The obsolete routing entry points and
separate diagnostic SendIO/DoIO selectors are removed; rebuild affected images.
Public API signatures and request layouts are unchanged.

Console lifecycle uses public Task admission, leases and signal rendezvous too;
see the [console refactor](../plans/console-refactor-plan.md).

## SIO state and synchronization

Reuse the existing upper-RAM resident, units, Task record and request port.
The bus stores a public worker Task pointer, generation, removal lease and waiter
list within its existing 64-byte reservation.
No second pending queue, active pointer or descriptor is introduced.

| State | Readers/writers |
| --- | --- |
| Open counts and unit handles | Caller-context Open/Close; driver stop reads under the same exclusion. |
| Pending port/list | BeginIO, worker claim and queued abort, under Forbid. IRQ/NMI never inspect it. |
| Active pointer, preparing/active phase, cancelled flag | Worker claim/start/finish and caller abort under Forbid; lifecycle reads to reject busy shutdown. |
| Worker identity, ready/stop/offline state | Driver startup/worker/stop code under Forbid; offline observation follows the native descriptor contract. Boot initialization is before publication. |
| Descriptor preparation and buffers | Worker only, while no frame is active. Native Start publishes the frame. |
| Descriptor IRQ fields | Existing native Start/Cancel/Retire/Recovered protocol; Forbid alone is not hardware exclusion. |
| Diagnostic snapshots | Read driver state under Forbid; no private-layout access by new application APIs. |

Claim is `Forbid; GetMsg; publish active/preparing; Permit`. Cancellation must
never see an unlinked request without active ownership. All pending messages
retain NT_MESSAGE. Descriptor preparation and buffer work run outside exclusion.
Preparing-to-active publication is protected; a cancellation latched in that
window survives native Start. Public AbortIO can cancel an active frame, while
the filesystem's conditional abort declines an already-started frame. Its
existing error precedence, committed cursor and reset-required outcomes remain.

Finish copies results while ownership is held, clears active/phase/cancelled,
then publishes exactly one ReplyMsg. There are no request accesses after that
publication. Quick completion uses NT_FREEMSG and no reply. Empty queue checks
never clear signals before Wait; notifications already pending remain durable.

The SIO control protocol and its selector are removed. Task policy neither
selects a SIO worker nor reads its queue, active pointer or shutdown state.
Immutable resident-name initialization remains part of generated bootstrap data.

## Task admission and lifetime

Workers use ordinary AddTask and the registered zero-argument entries in
`abi/tasks.json`. The driver tries eligible public stack pools under Forbid;
AddTask retains the normal pool and Process-lease checks. The registered
SIODRIVER.Worker entry checks that the calling Task owns the driver's current
startup lease; an unrelated duplicate invocation returns without touching hardware.
Helpers in the same registered module are not admitted as Task entries.

The public Task API reports version `$0800`. Its unchanged native packet tag
is `$0600`; the packet format tag and available-feature version are separate.
All calls below use COP `$50`, execute in Task context with IRQs enabled, and
return BYTE 1 for success or 0 for a rejected state. Invalid execution context
faults. Their selectors and record layouts are generated from `abi/tasks.json`.

| Call | Contract |
| --- | --- |
| `RetainTask(task, lease)` | Acquire one removal hold on a live Task. Fail without mutation for an inactive Task, an already-active lease or an exhausted hold count. |
| `ReleaseTask(lease)` | Validate the lease's address and Task incarnation, consume it exactly once and release its hold. Duplicate, copied or stale releases fail without changing the current Task. The final release permits removal; it does not remove the Task. |
| `RegisterResident(stopMask)` | Classify the caller as a resident with a nonzero allocated notification mask. Root/idle contexts, duplicate registration and unallocated masks are rejected. |
| `UnregisterResident()` | Restore ordinary application classification. Reject a caller that is not registered. Removal also clears registration after resource checks pass. |

A TaskLease occupies 12 bytes and must start zero-initialized. Exec owns its
Task pointer, incarnation and address identity while active. Lease records may
reside in writable image storage, public heap memory or the caller's live stack.
Do not copy, reset or free an active lease. Retention does not retain arbitrary
request buffers or replace their ownership rules. The per-slot incarnation
increases on admission; an exhausted incarnation permanently rejects that slot
instead of wrapping. Holding a lease rejects both explicit removal and normal
Task return. Use Forbid when final release and removal must be indivisible.

When no nonresident Task remains, Exec signals every registered resident without
interpreting device state. Registering the last ordinary Task as a resident
signals immediately. Further removals may repeat the notification; recipients
must tolerate coalesced or repeated signals. A registered stop bit cannot be
freed before unregistering. Each driver interprets the notification and decides
when its own resources are idle. This is an Exec816 integration extension,
not a claim of classic Amiga ABI compatibility.

SIO allocates request, completion and residency bits 31/30/29. A lease protects
its worker before binding, throughout operation and after producer release.
Startup and stop callers allocate a temporary signal and retain themselves while
stack-resident waiter records are published. Publication and waiting use public
Signal/Wait, preserving caller Forbid nesting without polling or lost wakeups.
Initialization failure unwinds signals, registration, producer binding and the
worker hold before removing the Task and waking startup waiters.

Stop rejects open references, queued requests or active work before changing
admission. It waits for actual retirement of the captured driver generation.
A new worker may reuse the old Task record or stack pool; that does not extend
an old Stop call's wait. Final cleanup, notification, lease release and self
removal run under Forbid. Waiters resume only after removal. Snapshot/Start/Stop
reap the retired public Task record; no SIO-specific scheduler hook is needed.

Automatic shutdown requests stop and waits for open references to close. The
last Close wakes the worker. DOS and console also register for generic resident
notifications and apply their own cleanup rules. Their remaining service policy
is outside this SIO migration.

## Public platform producer

`EXECPRODUCER.Bind(task, bits)`, `Release()` and `Drain()` are public platform
facilities with generated selectors 58/59/60. The current AltirraOS adapter
supports one serial producer. Other IRQ sources and arbitrary handler vectors
are unsupported. The native adapter remains the only IRQ-side publisher.

Bind requires a live retained target and a nonzero allocated mask. It returns 0
if admission fails, including a producer already acquired or not yet drained.
The binding retains both recipient and acquiring Task against removal. Release
quiesces serial sources; Drain completes pending wake references before clearing
the released binding. The acquiring Task or recipient may release and finish
draining it. Keep the target lease until Drain completes, then free signals or
remove the Task. Bound signal bits cannot be freed earlier. Drain may also process
pending wakes while the producer remains active; it does not release that binding.
Release/Drain on an already empty binding are harmless.

The native Start/Cancel/Retire/Recovered engine and IRQ/NMI publication protocol
remain unchanged. A device must retire its hardware operation before releasing
the producer; Forbid alone does not quiesce hardware.

## Storage

Hold count, incarnation and resident mask use ten previously unused bytes of each
64-byte upper-RAM TaskControl. Two adjacent bytes remain padding within S1's
12-byte budget. Each retaining resource owns its 12-byte lease; SIO's fits its
existing bus reservation, and temporary waiter leases occupy caller stack frames.
No fixed or per-Task bank-zero reservation grows, including guards, alignment
and unused capacity. No upper arena reservation grows either.

## Deterministic checks

S1's ordinary-Task fixture attempts a switch between dequeue and active
publication, delivers a request signal before Wait, then reuses and frees replies
immediately. S2 retains preparing/active/terminal cancellation checkpoints and
adds interruption at claim/reply ownership boundaries. S3 covers before binding,
after release, concurrent opens, stop/open, last-client exit and slot reuse, plus
ordinary-Task holds, copied/stale leases and resident notification semantics.
All tests retain exact ownership, stack/domain guards and OS restoration.

## Console lifetime

Console uses the same public Task facilities with a single existing worker.
Startup/stop waiters retain their callers while stack records are published.
The final notification, worker lease release and self-removal run under Forbid;
waiters resume after removal. Window creators, presentation owners and successful
opens hold ordinary Task leases. The worker's ready-state admission and opaque
unit/captured-route validation remain separate checks.

The private console Control protocol and its scheduler removal hooks are gone.
Keyboard Bind/Release and its producer-retention hook remain private platform
operations: the public producer API still admits only serial hardware. Console
adds no new gateway operation and no fixed or per-Task bank-zero reservation.
Its fixed upper state grows by 48 bytes; each extra instance's rounded allocation
grows by 16 bytes. See the implementation record for complete memory accounting.
