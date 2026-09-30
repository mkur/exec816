# Signals and Wait: classic Exec design

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../reference/signals.md) and [history index](README.md).

Status: implemented in the current Task kernel (`--tasks`); see the
[implementation record](signals-implementation.md) and [eight-task configuration](../architecture/task-capacity.md).
The [Task API](../reference/tasks.md) includes these calls. Functional signal/IRQ
qualification passes; general worker-per-byte delivery fails 125 kbaud, and
concurrent kernel work remains a timing limit for SIO.

Keep the classic five calls, per-task 32-bit masks and wait-for-any behavior.
Implement signals before the [allocator](../reference/memory.md): static
Task records suffice, and IRQ-to-task notification is the first building block
for asynchronous SIO. Message ports, queued I/O and the
[eight-task baseline](platform-contract.md#task-capacity-requirement) have
separate contracts; the latter is implemented with static pools. Signals carry notifications; request queues carry the work.

Delivery is direct: test the named target and retain that target in an intrusive
pending-wake queue if an IRQ cannot safely make it ready yet. Neither posting
nor draining searches other tasks. The queue replaces the earlier all-waiters
scan; the [delivery review](signals-delivery-review.md) records the decision.

Before the full API, the [serial latency proof](sio-latency-poc.md) measures a
hardcoded IRQ/post/wait/refill path with one worker and one busy/idle context.
It meets the 125 kbaud target only with the tested native IRQ route, fast ROM
access and scoped SIO critical mode. Carry its platform constraints into the
next adapter slice before building this API on top of it.

## Public API

All calls belong to `EXEC` in the generated module. `LONGCARD` represents classic `ULONG` exactly: an unsigned 32-bit value.
Task pointers remain native 24-bit pointers.

| Call | Result | Contract |
| --- | --- | --- |
| `AllocSignal(BYTE signalNum)` | `BYTE` | Allocate one bit in the calling task. Pass 0–31 for a particular bit, or `$FF` for no preference. Return its number, or `$FF` on failure. |
| `FreeSignal(BYTE signalNum)` | Procedure | Release a bit allocated by the caller. `$FF` is a harmless no-op, following Exec V37 and later. |
| `Signal(Task POINTER task, LONGCARD signals)` | Procedure | Post the specified bits to a live task; make a matching signal waiter eligible to run. |
| `SetSignal(LONGCARD newSignals, LONGCARD signalMask)` | `LONGCARD` | Atomically replace selected received bits in the calling task; return the entire previous received mask. |
| `Wait(LONGCARD signalSet)` | `LONGCARD` | Return and consume pending bits matching the set; block if none match. |

The reference contracts are the classic autodocs for
[AllocSignal](https://developer.amigaos3.net/autodocs/exec.library/AllocSignal.html),
[FreeSignal](https://developer.amigaos3.net/autodocs/exec.library/FreeSignal.html),
[Signal](https://developer.amigaos3.net/autodocs/exec.library/Signal.html),
[SetSignal](https://developer.amigaos3.net/autodocs/exec.library/SetSignal.html)
and [Wait](https://developer.amigaos3.net/autodocs/exec.library/Wait.html).
Native `BYTE` is unsigned, so `$FF` encodes classic signed-byte -1, just as
priority fields use explicit signed-byte representations. A bit number is not a
mask: test allocation failure before forming an unsigned 32-bit `1 << number`.
Bit 31 and `$FFFFFFFF` are ordinary mask values, not errors.

### Allocation and reserved bits

Each task has its own pool. Two tasks may allocate the same number independently.
Allocation is bit bookkeeping and requires no memory allocator. Success sets
the allocation bit and clears any old received bit atomically. Failure leaves
both masks unchanged. The no-preference selection order is not an API promise.

Initially reserve bits 0–15 with `tc_SigAlloc = $0000FFFF`; bits 16–31 provide
the sixteen application signals. Keep the classic reserved namespace rather
than reusing absent Amiga subsystems' numbers. In particular `SIGB_SINGLE = 4`
and `SIGB_DOS = 8`; DOS break bits CTRL_C through CTRL_F retain numbers 12–15.
Generate bit numbers and 32-bit masks in their owning headers when those
interfaces are introduced. These reservations follow the
[system signal convention](https://wiki.amigaos.net/wiki/Exec_Signals#Reserved_System_Signals),
the [Task header](https://developer.amigaos3.net/autodocs/include_h/exec/tasks.h)
and [DOS header](https://developer.amigaos3.net/autodocs/include_h/dos/dos.h).
Reserved names do not imply a DOS process, console-break producer, blitter or
exception service exists. Drivers initially allocate application bits for their
workers; the later DOS process contract owns its reserved-bit usage.

`AllocSignal` returns `$FF` for a reserved, allocated or out-of-range number
other than the no-preference sentinel. `FreeSignal` releases ownership; callers
must not rely on it clearing pending notifications. Reallocation clears them.
Freeing a reserved bit, an out-of-range number other than `$FF`, or a bit the
caller did not allocate is misuse. Stop every producer before freeing a bit;
allocation cannot distinguish a late notification from a new use of that bit.

The allocation mask is a namespace ledger, not a filter on delivery or waiting.
`Signal`, `SetSignal` and `Wait` operate on the supplied full-width masks,
including reserved bits used by their documented subsystem owner. Ordinary
applications must allocate their own bits and must not steal system bits.

### Posting, querying and consuming

`Signal(task, bits)` atomically performs `task.tc_SigRecvd |= bits`. It does not
clear bits and repeated posts coalesce. A running or ready target retains the
bits for later use. A signal waiter becomes ready when its received and waited
masks intersect. Posting zero changes nothing. Pass a live Task pointer;
`NULL` is not shorthand for self in Signal. Use `FindTask(NULL)` for that.

For example, `Wait(SERIAL_DONE | TIMEOUT)` wakes on either bit. It does not
require every requested event to arrive. An IRQ records a matching blocked
target for waking; the target becomes `TS_READY` at the first safe policy
boundary. READY means eligible to run, not necessarily selected next.

For `SetSignal(new, mask)`, with all arithmetic unsigned and 32 bits:

```text
old = current.tc_SigRecvd
current.tc_SigRecvd = (old & ~mask) | (new & mask)
return old
```

The read and update form one atomic operation. `SetSignal(0, 0)` is the supported
snapshot operation. Direct reads of public multiword fields can tear on the
65816; direct writes to active signal state are unsupported.

`Wait(mask)` returns `received & mask`, clearing exactly the returned bits and
preserving unrelated pending bits. It returns immediately if that intersection
is already nonzero. Otherwise it suspends the caller until a match exists.
There is no wait-all mode, timeout argument, result status or separate reset
call. In this subset `Wait(0)` parks indefinitely until task removal; it is
neither a yield nor a poll, since no signal can match an empty mask.

A blocking Wait consumes its result when completing the wait continuation for
resumption. Further matching posts while the task is ready can therefore join
the returned set; a post after consumption remains pending for the next Wait.
No counted-event guarantee is provided. Consumers drain their associated work
queue on a wakeup and tolerate a wakeup whose work was already handled.

## Task layout and lifetime

A Task is the public descriptor for one thread of execution: its identity,
scheduling state, stack addresses, signal masks and application metadata. Its
stack, direct page and private scheduler record are separate allocations; the
Task record size is not the total memory cost of a live task.

Insert the following fields after `tc_TDNestCnt` and before `tc_SPReg`, retaining
the relative order in the classic Task header:

```action
LONGCARD tc_SigAlloc,tc_SigWait,tc_SigRecvd,tc_SigExcept
```

| Field | Meaning in this design |
| --- | --- |
| `tc_SigAlloc` | Allocated and reserved bits. |
| `tc_SigWait` | Requested mask while a signal Wait is outstanding; reset on completion. |
| `tc_SigRecvd` | Posted, not yet consumed bits. |
| `tc_SigExcept` | Reserved, required zero; SetExcept and signal exceptions remain unsupported. |

Keeping the fourth classic signal field costs four bytes in upper RAM and avoids
omitting it from an otherwise complete signal-field group. Exception handlers,
trap fields and switch/launch hooks remain separate future work. Do not silently
accept a nonzero exception mask or advertise a SetExcept stub.

The caller prepares a zeroed Task as today. Successful AddTask initializes the
reserved allocation mask, zero wait/received/exception masks and private wait
state before publishing the task. This first subset does not accept custom
preallocated signal masks at admission. Root gets the same initialization;
private idle is not a public signal target. Failed admission leaves caller
storage unchanged. A task allocates its application bits after it starts and
publishes its Task pointer and mask to producers through a synchronized startup
handshake.

### Direct association with private scheduler state

Append a kernel-owned `ADDRESS tc_ExecPrivate` extension after `tc_UserData` in
the Task layout. AddTask initializes it to the task's private context
record; applications initialize it to zero before admission and must not read
or modify it while admitted. Keep the classic fields in their existing relative
order and leave `tc_UserData` available to its owner. This opaque three-byte
extension is part of the current layout; the five signal call signatures retain
their classic meaning.

The private record already retains its public Task pointer. The two links give
constant-time association in both directions: task-context Signal obtains its
record directly, and selection from the ready list's `tc_Node` does the same.
Validate the context link against the generated pool bounds/record alignment
and check its live state and reciprocal Task pointer before using it. Do not
search the context pool. Admission still validates the complete writable Task
extent; this association does not make arbitrary or stale pointers safe.

A qualified IRQ binding retains both the Task and its private context pointer,
plus the signal mask. Resolve and validate that binding during registration,
before enabling its producer. The IRQ uses this stable binding without lookup.
This is private adapter state, not a new public handle-based Signal API.

### Wait state and removal

Use public `TS_WAIT` for signal waits, as well as the existing timed Sleep.
Private bookkeeping distinguishes no wait, a Sleep deadline and a signal Wait;
zero `tc_SigWait` alone cannot distinguish Sleep from `Wait(0)`. FindTask must
include signal-waiting tasks. They retain their execution context, native stack
and private direct page, and continue to count against capacity.

RemTask cancels any outstanding wait, removes ready linkage if present and
unlinks the known private pending-wake node if queued, under the same protected
transaction as removal publication. Clear the queue flag, wait state and
`tc_ExecPrivate` before making the private context reusable. It does not resume
the removed task or synthesize a Wait result. Signal allocation has no external
heap object to free. Reusing a public Task still requires complete preparation
and admission; it must not inherit a predecessor's notifications.

The caller must keep a target alive throughout Signal. Forbid can protect a
task-to-task lookup/use sequence, but it does not protect an IRQ producer.
Before freeing a signal or removing its target, disable or detach the producer,
retire any in-flight handler, and remove its retained binding. Only then may
the Task storage or context be reused. Looking up a live pointer cannot detect
a stale producer whose old target address has been reused.

The public platform API is now `EXECPRODUCER.Bind`, `Release` and `Drain`.
Bind requires a retained target; the binding protects its recipient and acquiring
Task until release and draining finish. Bound signal bits cannot be freed during
that interval. The [producer contract](../reference/resident-drivers.md#public-platform-producer)
defines the single AltirraOS serial producer and its limitations. Registered
resident stop bits likewise remain allocated until UnregisterResident.

## Scheduling and calling contexts

| Context | Supported calls in the first signal profile |
| --- | --- |
| Native task, IRQs enabled | All five, including within Forbid. |
| Native task, IRQs masked by caller | Nonblocking calls preserve the mask; Wait is rejected before changing state. |
| Qualified maskable device IRQ callback | Signal only, through the dedicated adapter entry described below. |
| NMI, arbitrary ROM interrupt callback, OS service or reentrant kernel call | No public signal calls. |

Unsupported contexts and invalid live-target/free operations use the existing
diagnosed kernel-misuse fault convention. Do not invent an error mask for Wait
or SetSignal. Invalid AllocSignal requests have the ordinary failure result.
The nonblocking operations must not enable IRQs or schedule while the caller's
saved I bit is set.

### Wait within Forbid

A blocking Wait relinquishes the processor even with a nonzero Forbid depth.
Keep that depth in the suspended task's private record and public nesting field;
it must not prevent other tasks from running. On resumption the caller has the
same depth and needs the same number of Permit calls. An immediately satisfied
Wait does not release scheduling exclusion. This follows the explicit
[Forbid contract](https://developer.amigaos3.net/autodocs/exec.library/Forbid.html).

Forbid therefore cannot preserve shared-state invariants across a blocking Wait.
The dispatcher must select another task based on its own exclusion state, without
passing the outgoing waiter's lock depth through the normal no-switch test.
`tc_IDNestCnt` remains reserved at `$FF`: public Disable/Enable is still deferred.
Unlike classic Wait's Disable integration, this version rejects caller-masked
IRQs, even if a matching bit is already pending. A CPU I bit alone is not an
Exec interrupt-disable nesting implementation.

### Ready order and existing extensions

A matching signal waiter joins the ready tail once. Signal requests a scheduling
decision at the first safe exit, independently of the next VBI tick. The current
task's Forbid depth, masked IRQs or a live OS/kernel/interrupt activation can defer
that decision; the pending request must survive the deferral. Priority remains
stored but ignored under the existing round-robin policy. The target is not
guaranteed to execute immediately or before the signalling task returns.
Task-context Signal publishes the target's ready transition before returning,
including under Forbid. It acts on that target directly and cancels its queued
wake node if an earlier IRQ already queued it; it need not drain unrelated
targets. IRQ wake processing runs at the first safe policy entry;
Forbid alone defers switching, not that processing. OS/kernel stack safety can
defer both, with the notification retained throughout.

Deferred IRQ wakes enter the pending-wake queue in first qualifying post order;
duplicates retain their position. Draining takes its head and appends each
matching waiter to the ready tail. Task-context delivery can make its own target
ready before unrelated deferred entries. No global ordering between different
producers or guarantee of immediate preemption is part of Signal.

`EXECTASKS.Sleep(ticks)` remains a timed-delay extension with its current Forbid
restriction. Posting a signal to a sleeping task records the bits but does not
end its timed sleep. Yield and Poll retain their meanings. Later timer/device
completion signals can be combined in an ordinary Wait mask; do not add a
different public Wait API to anticipate timers.

## Atomicity and interrupt delivery

The 65816 cannot update a 32-bit signal mask in one instruction. Forbid is
insufficient because device IRQs still run, and SEI alone cannot exclude NMI.
The [implemented critical-section protocol](kernel-critical-sections.md)
refines the original whole-target transaction into smaller atomic operations
while retaining scheduler exclusion throughout policy.

1. Serialize kernel policy on its established stack/domain. Use bounded,
   IRQ-masked transactions for signal-mask updates, wait-state publication and
   wake links. Ready-list changes and task admission/removal remain protected
   by the scheduler guard; IRQs may run but cannot inspect those partial
   updates or enter policy. Preserve the caller's previous interrupt state.
   No task switch may expose a partial transaction.
2. NMI may record its existing tick/reschedule indication, but may not inspect
   signal masks, modify task lists or dispatch during a protected transaction
   or stack transition. Preserve the platform's transition checks; do not rely
   on the CPU IRQ mask to exclude NMI.
3. A qualified IRQ Signal entry uses its known target binding, ORs the received
   bits and tests only that target. If its private state is blocked in a signal
   Wait and `tc_SigRecvd & tc_SigWait` is nonzero, append its private node to the
   pending-wake queue unless already queued. The mask update, test and queue
   publication form one bounded transaction. Running/ready targets, timed Sleep
   and nonmatching signal waits retain the bits without being queued. Zero-bit
   Signal is a no-op. The entry never edits scheduling lists, dispatches, calls
   the ordinary COP wrapper or borrows compiler scratch. Its private frames may
   use the interrupted stack's reserved IRQ headroom; it never resets S to an
   active kernel stack top.
4. At an eligible outer interrupt return or kernel scheduling boundary, process
   the pending-wake queue directly. Atomically detach and claim its head, then
   recheck that target's live association with IRQs enabled. Atomically test
   its latest signal-wait state/mask and publish private READY before releasing
   the claim. Complete public state and ready-list edits under the scheduler
   guard. Leave received bits and the outstanding wait mask intact for Wait's
   eventual return. Never search other tasks to rediscover the target.

The received mask itself holds IRQ posts; a second per-task 32-bit mailbox is
not required. SetSignal, allocation initialization and Wait's test/consume use
the same exclusion, so a racing post is ordered before or after each operation,
never half-applied. NMI may occur between the two 16-bit accesses but cannot
observe or mutate the transaction. Far accesses must carry across bank boundaries
and must not assume the Task is in bank zero or in the interrupted task's DBR.

### Pending-wake queue

Use a private FIFO `MinList`, with a separate doubly linked `MinNode` and a
`wakeQueued` state byte in each private context record. The node has a generated fixed
offset, so its address gives the context directly. Do not reuse `tc_Node`: it
belongs to scheduling-list membership and must remain independent of pending
delivery. The previous/next links allow constant-time cancellation of any known
queued task, including RemTask, without searching for its predecessor.

The representation follows the existing Exec-style list layout, but the IRQ
entry needs bounded assembly operations with qualified scratch/stack ownership.
Calling the ordinary public Lists wrappers from an IRQ is not thereby permitted.
Queue changes use the same IRQ exclusion and NMI deferral as the mask update.
In particular, NMI must not inspect even an apparently empty queue while a
multi-byte link is being published.

Required invariants:

- `wakeQueued` distinguishes absent, linked and claimed states. A claimed node
  is detached but owned by the current drain. A context has at most one pending
  entry or claim. Repeated posts OR more bits without appending while linked or
  claimed. Capacity is the number of admitted signalable tasks; no separate
  ring can overflow and no allocation occurs in the IRQ.
- A pending entry names a task to recheck; it is not a second signal mailbox
  or a READY state. The target remains publicly `TS_WAIT` until safe delivery.
  Wait completion alone consumes the matching received bits.
- Detaching a head and claiming it are indivisible with respect to posts.
  Releasing the claim and the final mask/state decision are also indivisible.
  A post during the claim joins the pending bits; a post after a successful
  wake observes private READY and retains its bits. If the recheck declines to
  wake a still-blocked task, a later matching post can enqueue it again.
  This claim permits validation and ready-list work with IRQs enabled, avoiding
  the original whole-target blackout without losing or duplicating a wake.
- Task-context delivery or removal can unlink the known pending node directly.
  Producers must be quiesced before removal; reuse cannot inherit a queue node,
  signal bits, context link or retained IRQ binding from the previous task.
- Queue nonemptiness is the authoritative pending-work indication. Any cached
  fast-entry flag must be maintained in the same queue transaction, including
  removal of the final entry. A later enqueue must survive that clear.

Drain one target at a time. When the interrupted/calling context permits IRQs,
allow IRQ service during policy work between the small native transactions.
NMI and nested IRQ exits must still defer scheduler reentry and switching.
An IRQ can append work, but cannot recursively drain it. Preserve a caller's
masked-I state; such a call has no serial latency guarantee. The adapter must
qualify these interrupt-permitting boundaries; merely adding a queue while
retaining an IRQ-masked whole-drain loop does not satisfy the latency contract.

Complete an eligible drain before returning to task selection, allowing IRQ
service between target transactions as above. No task runs and reenters Wait
during that drain, so each live task can be delivered at most once in the pass.
Deferred entries must survive an ineligible OS/kernel exit and be processed at
the first eligible exit without requiring a new VBI tick. Never enter idle with
undelivered wake entries. Draining k queued tasks costs O(k), including any
entries that fail revalidation, and k can equal the live task count. Enqueue,
dequeue and cancellation of one known entry are O(1); this is not a claim that
waking every task has constant total cost. Measure each masked transaction and
the complete post-to-worker path, including work arriving during the drain.

### Keep unrelated scans out of signal delivery

Selecting a ready task removes the ready head and uses `tc_ExecPrivate` to
obtain its context. No Task-to-context lookup scan belongs in this path. Likewise,
signal delivery must not invoke an unconditional all-slot timed-sleep
`Wake()` scan. Timer expiry is separate work: process due sleepers on a tick or
deadline, using timer bookkeeping with its own measured interrupt bound.
Coincident timer and signal work must still meet the combined latency bound.

The dispatcher uses direct association and a timer-pending gate, with an
upper-RAM count of timed sleepers. The VBI pending-byte operation is O(1), but
the full dispatch path is not; measured masked transactions still exceed the
125 kbaud byte deadline. Task enumeration, admission validation and future priority ordering are
separate concerns; this design removes searches from the named-target signal
and ready-selection path without claiming every kernel service is scan-free.

### Preventing lost wakeups

The Wait transaction tests the pending intersection and either consumes it or
publishes both the wait mask and blocked state before dispatch can proceed.
There must be no interval in which an IRQ post is missed between the test and
becoming a waiter. A post before this transaction is found by the test; a post
after publication tests the published state and queues the known target. The
publication transaction must include the private wait reason, mask, blocked
state and scheduling-list changes. No IRQ may observe half of that transition.
A ready waiter retains its continuation state until its result is consumed into
the saved return registers.

Before selecting idle, process the pending-wake queue. The final idle transition
must also close the check-to-WAI race: an IRQ between the last check and WAI
must either dispatch its newly ready task on return or cause idle to recheck
without sleeping. Do not rely on a later VBI to repair a missed signal wake.
With no matching signal, an idle system should remain asleep rather than spin.

Queue a blocked target only on a matching signal. A post that arrives while the
target is still running need not create a wake entry: the following atomic Wait
test will find it. A post during timed Sleep cannot create one either; the
received bits remain available after the timer wakes the task. The state test
must distinguish timed Sleep from signal Wait, including `Wait(0)`.

### AltirraOS boundary and latency

Keep `EXEC.Signal` as the public operation. Task callers use a generated native
import; approved IRQ callbacks use a platform binding to its bounded IRQ entry.
These are two execution paths for the same semantics, not two public signal
models. The platform binding must specify register arguments, preserved state,
stack/headroom and direct-page ownership before a driver can use it. Native
and OS emulation IRQ paths require explicit qualification; an arbitrary ROM
callback is not automatically an approved native callback.

Save and restore the complete interrupted context, including hidden accumulator
bits, width flags, D, DBR, S and PBR. No switching may suspend a live handler or
OS activation. If Signal interrupts kernel or OS work, record the notification
and arrange delivery at its first eligible return. The existing
[platform protocol](../reference/platform.md#vbi-preemption) remains authoritative
for stack transitions and OS coexistence.

The current policy runs with IRQs masked on the kernel domain, and serialized
ROM services can postpone scheduling. A signal test alone does not establish
acceptable SIO latency. Qualify maximum IRQ-masked time and worker wake latency
across task services, the later allocator and retained OS calls. The allocator's
long scans/clears must follow its IRQ-permitting design; wrapping synchronous
ROM SIO in a task does not make a driver asynchronous.

The [latency results](sio-latency-poc.md#measurements) now establish that generic
ROM serial IRQ dispatch and full ROM VBI exceed the worker-per-byte deadline
at 125 kbaud in the tested profile. Direct native delivery plus fast ROM and
CRITIC passes the minimal experiment. Preserve scoped ownership/restoration of
that OS flag, account for postponed stage-two VBI work, and remeasure as the
public API replaces the probe. The result is not a blanket signal-latency or
asynchronous SIO qualification.

## Native ABI and memory budget

Generate the complete Task type, size, offsets, service selectors and native
call layouts from [tasks.json](../../abi/tasks.json). Development ABI changes
require rebuilding callers; there are no compatibility profiles. Coordinate
allocator integration with this current layout instead of using obsolete
prototype metadata as authority.

Use the pinned compiler's native argument layout and full `LONGCARD` return in
A/X. Do not squeeze a mask into CARD, SIZE, a pointer or the selector register.
The task gateway still uses `COP #$50` and preserves the OS's `$00` service.
Qualify generated stubs and saved-frame results, including bit 31, in raw and
optimized emitted code before assigning the profile's public version.

Four masks add 16 logical bytes per public Task. Appending `tc_ExecPrivate` adds
three payload bytes plus one additional padding byte. Emitted ABI probes verify
**62 bytes instead of 42** (the earlier mask-only proposal was 58). ADDRESS and
LONGCARD fields have two-byte alignment, and this record's size rounds up to an
even number. The opaque link is at offset 58, occupies bytes 58–60, and leaves
byte 61 as tail padding. The previous 61-byte estimate omitted that padding.
The [raw/optimized layout probes](../qualification/signals-abi.json) establish
this size, offsets and bank-crossing accesses. Public Task placement must not acquire a bank-zero restriction
for cheaper mask access.

The logical storage delta, including public Task padding but before
private-record padding or reuse of private reserved fields, is:

| Storage | Fixed bytes | Bytes per public task | At 8 / 12 / 16 tasks |
| --- | --- | --- | --- |
| Four public signal masks | 0 | 16 | 128 / 192 / 256 |
| Public opaque context link | 0 | 3 | 24 / 36 / 48 |
| Additional public Task alignment padding | 0 | 1 | 8 / 12 / 16 |
| Private pending-wake MinNode | 0 | 6 | 48 / 72 / 96 |
| Private queued flag and wait reason | 0 | 2 | 16 / 24 / 32 |
| Pending-wake MinList header | 9 | 0 | 9 / 9 / 9 |
| Total | 9 | 28 | 233 / 345 / 457 |

Prefer upper RAM for the queue header, nodes and additional private metadata as
well as the Task fields. A doubly linked node costs three bytes more per task
than a singly linked node, buying constant-time cancellation without a
predecessor search or delaying context reuse. The opaque context link buys direct
association while retaining the caller-owned Task and private context split.
These choices do not require bank-zero storage. Existing private context-to-Task
links are not new costs; an IRQ binding's cached context pointer adds three
logical bytes per binding beyond its Task pointer and signal mask. No signal
node is needed for private idle; count any unused idle record padding if the
implementation uses a uniform pool.

Reuse suitable private reserved fields where justified, and generate the final
layout rather than assuming these logical additions equal reserved growth. A
larger context stride or pool alignment must be counted in full. Signals need
no extra task, per-task direct page, per-task stack or heap allocation. Any IRQ
adapter stack/domain reservation or extra headroom must be measured separately.
Report fixed and per-task reserved bank-zero deltas, including guards, alignment
and unused capacity, under the
[bank-zero rule](../reference/platform.md#bank-zero-memory-budget).
This documentation change reserves **0 additional bank-zero bytes**.

## Deviations and reasons

| Area | Difference from classic Exec | Reason / status |
| --- | --- | --- |
| Native representation | 24-bit Task pointers, Action! unsigned BYTE sentinel encoding, native calls and record padding. Masks remain 32 bits. | Required by the 65816/compiler ABI; no Amiga binary compatibility claim. |
| Private context association | Append opaque `tc_ExecPrivate` after the classic Task subset. | Three bytes per Task avoid lookup scans with the existing caller-owned Task/private-context split. This is an implementation choice, not an inherent CPU requirement; call signatures and `tc_UserData` ownership stay unchanged. |
| Interrupt calling | Signal is initially available only to qualified maskable IRQ callbacks; no NMI or arbitrary OS-handler calls. The known target enters a private pending-wake queue; scheduling-list work is deferred to a safe boundary. | Required by the current adapter's stack/domain and nonreentrant OS constraints, not a general 65816 prohibition on interrupt-time list edits. General interrupt support needs additional qualification. |
| Disable/Wait | Wait with caller-masked IRQs is rejected; Disable/Enable nesting is not implemented. | Temporary subset, not a fundamental 65816 limit. Avoid pretending hardware I implements classic Disable. |
| Exceptions | `tc_SigExcept` is present but zero-only; no SetExcept or exception callbacks. | Deferred subsystem; plain notifications and blocking suffice for the first driver/port work. |
| Scheduling priority | Stored priority does not determine wake/preemption order. | Previously accepted scheduler simplification; not required by the CPU. |
| Admission | Signal fields start zero and AddTask installs the fixed reserved mask; custom preallocation is unsupported. | Fits the current caller-prepared Task subset and gives a defined initialization path. More flexible admission can be added separately. |
| Misuse diagnostics | Invalid targets, unsupported contexts and invalid frees have defined faults; invalid AllocSignal numbers fail. | Consistent with current Exec816 Task diagnostics in a trusted address space; this does not make stale pointers safe. |
| Timed delay | Existing Sleep is separate and is not interrupted by signals. | Preserves the established extension; classic Wait retains its one-mask signature. |

The bit count, five call names, argument order, coalescing, pending-bit behavior,
wait-for-any consumption and Forbid restoration need no target-driven deviation.
The internal ready representation need not reproduce ExecBase's physical lists;
the public Task state and observable API behavior must agree with this note.

## Implementation slices and acceptance

The [implementation plan](../plans/signals-wait-implementation-plan.md) expands these
stages into separately executable commits, with platform prerequisites, affected
files, storage/layout probes and capacity/timing qualification gates.

Commit each executable slice separately and update callers and tests with it.
A task-only milestone must not advertise IRQ-safe Signal.

Prerequisite: retain the [latency proof](sio-latency-poc.md) and establish the
bounded native IRQ/platform path it requires before these full-API slices.

1. **ABI and mask bookkeeping.** Generate the revised Task layout and call
   shapes, including the opaque context link and private queue storage; implement
   admission/reset, AllocSignal, FreeSignal and SetSignal.
   Test independent task pools, sixteen allocations/exhaustion, requested and
   reserved bits, `$FF`, reallocation clearing, unchanged failure state, full
   old-mask returns, and bit 31. Validate complete far-record writable extents,
   reciprocal context association, unchanged caller fields on failed admission,
   and cleared context links on removal/reuse.
2. **Task-to-task Signal and Wait.** Implement atomic wait/consume, ready
   transitions, nested Forbid restoration, idle and removal/reuse. Cover posts
   before Wait, between test/publication boundaries, while blocked and while
   ready; multiple matching/unrelated bits; coalescing; self-post; Wait(0);
   all tasks waiting; timed Sleep isolation; FindTask; cancellation; and rejected
   masked-IRQ Wait without mutation. Replace ready-selection lookup with direct
   association and separate timed-sleep processing from signal delivery. Bound
   completion in both compiler modes.
3. **IRQ delivery and deferral.** Implement and qualify the platform entry,
   intrusive pending-wake queue, IRQ-return scheduling and idle handshake.
   Inject IRQ/NMI at mask accesses, every multi-byte queue-link publication and
   stack/state transitions. Cover both orders of concurrent clear/post; duplicate
   posts before/during/after dequeue; first/last entry handling; FIFO delivery;
   cancellation at head/middle/tail and immediate context reuse after producer
   quiescence. Test task-context Signal taking over an already queued target,
   all tasks queued, unrelated tasks untouched, and revalidation that cannot
   ready a timed sleeper or a removed/already-ready task. Cover Forbid, masked
   callers, kernel/OS deferral, IRQ service between drain transactions and wakeup
   without a new VBI tick. Check no recursive drain on nested IRQ/NMI exit and
   no pending work lost when an IRQ posts at the final empty/idle transition.
   Check all interrupted M/X combinations, complete register restoration,
   private domains, stack guards and OS coexistence on the pinned platform.
4. **Integration evidence.** Run raw/optimized end-to-end worker notification
   tests with far and bank-crossing Task records and queue nodes, sustained posts
   and bounded progress. Compare one signalled target with increasing numbers
   of unrelated waiters, then all-target bursts and coincident timer expiry.
   Inspect emitted code for hidden lookup/timer scans and record maximum masked
   transaction time separately from total IRQ-to-worker latency. Record
   ABI/toolchain/platform provenance and full reserved memory deltas.
   Repeat capacity-dependent checks at eight tasks when milestone 7 lands, then
   at each qualified 12/16-task configuration. Current four-task tests do not
   establish those capacities or SIO transfer deadlines.

The next higher-level slice is message ports with queued requests/replies:
enqueue the payload before signalling, and let receivers drain the queue before
waiting again. Drivers preallocate IRQ-side state. Queue synchronization and
IRQ-safe enqueue are separate contracts; the current public Lists library is
not thereby made IRQ-safe. Build the SIO worker and DOS/filesystem worker on
those contracts, without a task per drive or a signal bit per request.
