# Cheap native Task semaphores

[Plan index](README.md) · [Task API](../reference/tasks.md) ·
[Gateway and platform](../reference/platform.md#cop-gateway) ·
[Native fast paths](../history/kernel-fast-path-implementation.md) ·
[MagiC mapping](../architecture/magic-exec-mapping.md)

Status: implemented through NS0–NS5 at the development tier, 2026-11-15. Design basis: Exec816 `2f25db70` and pinned MagiC
`28cfdd29aa16fef692cc287bad3046b44ddcce3d`. This design is delivered by the linked implementation plan. The
[current contract](../reference/semaphores.md) and
[execution record](../history/native-semaphores.md) describe the supported API
and measured results.

The [implementation plan](native-semaphore-implementation-plan.md) sequences
NS0–NS5 from a measured baseline through native ownership/waiting, C bindings,
asynchronous boundaries and development acceptance.

## Purpose and model

Provide an exclusive, recursive, Task-owned semaphore with a short native
uncontended path and FIFO ownership handoff. Ordinary Tasks and Task-context
driver code use the same operations. A semaphore protects a resource while its
owner remains normally preemptible; competitors sleep without involving a
server Task.

Use classic Amiga Exec's `InitSemaphore`, `ObtainSemaphore`, `AttemptSemaphore`
and `ReleaseSemaphore` API model: recursive exclusive ownership, balanced
release and a blocking obtain. The [Amiga obtain contract][amiga-obtain] and
[release contract][amiga-release] establish those semantics. This is an
Exec816 source interface with native layouts, not an Amiga binary ABI.

MagiC demonstrates the desired internal structure. Its
[`_beg_update`][magic-obtain] changes the owner/count directly inside AES;
[`free_semaphore`][magic-release] transfers ownership to the oldest waiter
before making it ready. Its unchanged slider setter only nests that lock and
compares a field when Smart Redraw is enabled. Exec must supply its own explicit
IRQ/NMI-safe entry rather than import MagiC's supervisor-mode preemption rule.

The justification for a combined public kernel operation is concrete: a library
composition needs at least `Forbid` and `Permit` gateway entries around every
ownership transition, plus separate blocking/wake services under contention.
The native service can identify the caller from the admitted kernel context,
commit the ownership transition once, and park or ready the affected Task in
that same activation. It needs no GUI policy or driver-specific selector.

## Cost contract

Design the common path first:

| Case | Required work |
| --- | --- |
| Obtain a free semaphore | Compare owner, establish owner/depth and increment caller's distinct-owned count. |
| Obtain recursively | Compare owner and increment depth. |
| Attempt while another Task owns it | Return zero without changing the object or queues. |
| Release a nested hold | Decrement depth. |
| Final release without waiters | Clear depth/owner and decrement caller's distinct-owned count. |
| Final release with waiters | Pop FIFO head, transfer ownership and ownership accounting, then make that Task ready. |

Each obtain/attempt/release makes one public `COP #$50` request. Quiescent
uncontended operations finish in assembly before the Action! dispatcher or
kernel-stack transition. They perform no allocation, public `FindTask`,
`Forbid`, `Permit`, `Wait` or `Signal` call, queue scan, global registry lookup,
resource callback, snapshot publication or GUI readiness query.

Reuse the existing complete-frame validation and fast-return protocol. Pending
ticks, timer work and IRQ wakes may still require post-operation Poll; common
late-work return trampolines remain permitted. Neither a completed operation
nor an ownership increment may be replayed to process that work. One public
request is not a promise to suppress required kernel housekeeping.

Blocking and ownership handoff may enter shared scheduler helpers inside the
same gateway activation. Optimizing those less common cases must not enlarge
the free/recursive path into a general object-management dispatcher.

## Public surface

Proposed C declarations, using the existing Exec calling convention:

```c
struct SignalSemaphore { UWORD ss_Private[6]; };

void EXEC_CALL InitSemaphore(struct SignalSemaphore *semaphore);
void EXEC_CALL ObtainSemaphore(struct SignalSemaphore *semaphore);
LONG EXEC_CALL AttemptSemaphore(struct SignalSemaphore *semaphore);
void EXEC_CALL ReleaseSemaphore(struct SignalSemaphore *semaphore);
```

`InitSemaphore` initializes caller-owned, unpublished storage and allocates
nothing, following the [Amiga initialization model][amiga-init]. Implement it
as an ordinary library routine, with no COP. Static/heap storage in upper RAM
is preferred; a live stack object is permitted when its owner keeps the entire
activation alive until all users have finished.

Obtain returns with ownership, possibly after sleeping. Attempt returns exactly
one on acquisition, including recursion, or zero when another Task owns the
semaphore; it never queues. Use the classic LONG-shaped
[attempt result][amiga-attempt], with native A/X result marshalling. Release
balances exactly one successful obtain/attempt. The initial depth limit is
65,535; depth/count exhaustion and wrong-owner/extra release fault before
mutation, as synchronization misuse. Busy Attempt is an ordinary zero result.

There is no semaphore allocation/discovery API, registry, name, handle
generation or destructor. Initialize once before publication; do not copy,
move, reinitialize or free a live object. Callers keep its storage and all
borrowed resource data alive through their users' operations. Reinitialization
requires externally established quiescence.

The opaque 12-byte record is two-byte aligned; its public fields are not
application controls. The kernel trusts valid initialized storage and live
caller pointers. It does not perform heap membership searches, object-tag
validation or reciprocal-link audits on every acquisition. Preserve gateway
shape, stack/domain checks and actual synchronization-state checks.

## Records and memory budget

Proposed object layout, with full native three-byte pointers:

| Offset | Bytes | Field |
| ---: | ---: | --- |
| 0 | 3 | Owner Task pointer; null when free. |
| 3 | 1 | Reserved zero for word alignment. |
| 4 | 2 | Recursive depth. |
| 6 | 3 | FIFO head Task pointer. |
| 9 | 3 | FIFO tail Task pointer. |

Size is **12 bytes**, alignment two, with no hidden allocation. Private fields
are generated from the machine-readable ABI during implementation. Do not put
C huge pointers directly into this record; the public word-array form fixes
its size independently of C's four-byte default pointers. Support valid records
spanning a CPU-bank boundary through full-address accesses.

A Task can be blocked in only one synchronous obtain. While semaphore-waiting,
reuse its public `tc_Node` links for the semaphore FIFO. It is then absent from
the scheduler ready queue. Pop it from the semaphore queue before calling the
existing Ready helper. IRQ wake nodes are already separate from `tc_Node`.
This avoids allocating a waiter or reserving an additional linked-list node.

Use five currently unused upper-RAM bytes in each existing 64-byte
`TaskControl` record:

| Offset | Bytes | Proposed field |
| ---: | ---: | --- |
| 50 | 2 | `semaphoreOwned`: number of distinct semaphores owned. |
| 52 | 3 | `semaphoreWait`: semaphore being awaited, otherwise null. |

Offsets 55–63 remain padding. Recursion changes the object's depth, not
`semaphoreOwned`. Add a distinct private SEMAPHORE_WAIT state/reason using the
existing state/reason bytes; public Task state remains `TS_WAIT`. Initialize
these fields at Task admission/reuse. No new public Task fields are needed.

This layout is allocated in [tasks.json](../../abi/tasks.json),
not permission to change generated fields by hand. No other use of these
padding fields was found in the inspected implementation; recheck that fact
when the ABI slice lands.

| Reservation | Design target |
| --- | --- |
| Fixed/root/kernel/idle bank zero | **0 added bytes**. |
| Each public Task's bank zero | **0 added bytes**, including guards, alignment and spare capacity. |
| Public Task record | Remains 62 bytes; managed stride remains 64. |
| Private Task context | Remains 64 bytes; five padding bytes gain meaning. |
| Semaphore object | 12 caller-owned bytes, including its alignment byte; ordinary allocator rounding is separate. |
| Waiter/signal/port/Task allocations | Zero per operation and per semaphore. |
| Activation scratch | Target the existing 20-byte native fast-service scratch below the saved 13-byte COP frame. |
| Native code | Use existing upper code capacity first; measure emitted use and report any capacity change explicitly. |

Do not enlarge stack/DP pools to hide call-depth growth. Retire native scratch
before entering compiled scheduler policy or restoring another Task. The draft
changes no runtime reservations; implementation must verify actual maps and
stack headroom, including asynchronous nesting.

## Ownership transitions

All transitions execute under the existing guarded kernel activation.

**Obtain or Attempt:** identify the current Task/context once at entry. If it is
the owner, check depth overflow and increment. If free, check owned-count
overflow, set depth one and owner, and increment the Task's owned count. If
owned by a peer, Attempt returns zero. Before queueing an Obtain, check the
caller's distinct-owned count has room for the eventual grant. Then append it
at the FIFO tail, record `semaphoreWait`, publish private SEMAPHORE_WAIT/public
TS_WAIT, and select another runnable Task through the existing scheduler.

No signal bit is allocated, cleared or consumed. Semaphore waits have their
own private wait reason and do not call public Wait. Signal posts while blocked
remain in `tc_SigRecvd` for a subsequent ordinary signal wait. Existing
WakeMatch must continue to match only SIGNAL_WAIT: a signal must not grant a
semaphore or put a node on both queues.

**Release:** verify ownership and positive depth. If depth exceeds one,
decrement it and return. Otherwise this is final release: decrement the
outgoing owner's distinct-owned count. With no waiter, clear depth/owner and
return. With a waiter:

1. Detach the oldest Task from the semaphore FIFO and maintain head/tail links.
2. Set the incoming owner and depth one; increment its owned count and clear
   its `semaphoreWait`/wait reason.
3. Finish all semaphore access, then publish that Task READY through the shared
   scheduler helper, including existing queued-wake retirement.
4. Request scheduling through the ordinary safe-exit rules. Do not replay the
   caller's release if pending work requires Poll.

The queued Task's owned count cannot increase while it is blocked; the capacity
check at enqueue therefore remains valid at handoff. The kernel inserted that
still-live waiter itself and needs no repeated Task admission or registry
lookup to grant it ownership.

Ownership is committed before readiness. A new arrival cannot steal the grant
from the FIFO head, even if a different ready Task runs first. An awakened
Obtain resumes its saved continuation already owning the semaphore; it does
not loop through another public acquire. Recursion by the current owner is
permitted despite queued peers. Resource FIFO order does not change Exec's
scheduler policy or establish priority inheritance.

Finish descriptor accesses before making a recipient runnable or entering a
rescheduling return. A recipient may run before the releasing public call
returns; the old activation must not subsequently dereference that descriptor.

## IRQ/NMI and entry rules

Reuse the [current platform protocol](../reference/platform.md#vbi-preemption)
and [critical-section structure](../history/kernel-critical-sections.md).
`SWITCHING` covers frame validation, intermediate S/D changes, semaphore and
Task-only queue edits, scheduler continuation and return. IRQ/NMI never obtain
or release these semaphores and never traverse the semaphore FIFO.

IRQ service may continue once entry is stable because it cannot observe or
mutate these Task-only links. NMI may record pending work but cannot start a
second policy activation. Preserve the existing atomic wake-node helpers for
their IRQ-shared records. Do not extend an IRQ blackout across the semaphore's
resource lifetime; `SEI` alone is not an NMI exclusion protocol.

Blocking Obtain follows Wait's rules for Task scheduling exclusion: preserve
the caller's Forbid depth across suspension/resumption. If acquisition would
block with the caller's saved I bit set, fault before queue mutation, matching
the existing masked-Wait restriction. Free/recursive acquisition, Attempt and
Release retain ordinary admitted Task-context masking/restoration behavior.
The service never increments the caller's Forbid depth itself.

The final native return uses the existing pending tick/timer/wake checks and
restore-only redirect/trampoline protocol. Blocking and ready-publication
continuations must retire their local scratch and publish a complete saved
frame before scheduler entry. Preserve D/DBR, register widths, flags, stack
ownership and the ordinary defined result registers. No new COP signature,
private interrupt stack or unchecked direct entry is introduced.

## Lifetime and unsupported behavior

Prevent `RemTask`, including default self-removal, while `semaphoreOwned` is
nonzero or `semaphoreWait` is nonnull. Check this before existing removal work
can unlink a Task or release its pool. During direct handoff, waiting protection
is replaced by ownership protection in the same guarded activation. No public
RetainTask/ReleaseTask call or location-bound lease object is needed per hold.

This is an explicit addition to the current removal gates and a deliberate
Exec816 lifetime rule, consistent with its live-lease restrictions. A simple
owned count suffices because v1 never enumerates or automatically releases a
departing Task's semaphores. Owners release their resources before exit;
blocked callers wait for normal handoff. Caller storage must remain valid.

V1 provides exclusive recursive locking only. Shared readers, counting permits,
timeouts, interruptible/cancellable obtains, owner-death recovery, cross-Task
release, semaphore lists, public name lookup and priority inheritance are
unsupported. A pending break signal does not abort Obtain. Lock ordering and
deadlock avoidance remain caller responsibilities. Semaphores do not protect
data concurrently accessed by IRQ/NMI handlers; drivers keep their documented
interrupt-shared protocols.

The signalless wait state and reuse of `tc_Node` deliberately differ from
Amiga's documented stack-resident waiter records. They avoid waiter storage and
signal handling for this bounded exclusive native subset. MagiC's APPL queue is
the closer structural reference; scheduler mechanics remain Exec's.

## ABI and implementation placement

Add a machine-readable `abi/semaphores.json` for public size/alignment,
private field offsets, imports, result shape and three service selectors.
Allocate selector values after checking both public and private service maps;
keep `COP #$50`, existing service meanings and the OS's `$00` bridge intact.
Extend the current generators rather than copying constants between C,
Action! and assembly. Record the Task-context fields and wait vocabulary in
`abi/tasks.json`, keeping its stride and public Task layout unchanged.

Expose the same functions through EXEC/native bindings, `<exec/semaphores.h>`,
`<proto/exec.h>` and the resident C provider. Use the existing pointer argument
shape and full LONG result convention. Record the feature-version change and
rebuild affected imports/provider consumers together; change the packet tag
only if its existing call layout contract actually changes. Keep the pinned
compiler and one current implementation.

Put the native operation beside
[`fast-services.s`](../../platform/altirraos/fast-services.s). Share its safe
entry/completion machinery. Blocking/ready continuations belong with
[`taskpolicy.act`](../../lib/exec/taskpolicy.act), reusing Ready, Select,
Switch and wake retirement. A kernel-internal helper is an implementation
detail of this general public service, not a separate AES gateway.

## GEM integration boundary

First establish the primitive independently with tiny Tasks. Do not immediately
replace UPDATE, MCTRL, the scene gate and display grants with one semaphore.
They protect different resources and have different lifetimes.

A later AES slice can use recursive acquisition for already-owned window
setters and a focused logical UPDATE lock. It must explicitly preserve or
migrate older-window ordering, capture/MCTRL rules, physical continuations and
registration teardown. In particular, the current presenter can retire client
policy on another Task's behalf; a Task-owned semaphore cannot be silently
released by that presenter. Establish an owner-side exit protocol before
removing existing cleanup paths.

Never block obtaining a semaphore while holding the scene/display resource
that its owner needs to release it. Keep paint/cache accounting, input routing
publication and actual rendering outside the generic primitive. The existing
[inline cursor design](gem4xe/gem-mouse-plan.md#inline-cursor-completion)
remains a separate library change. A cheaper lock does not itself remove the
multi-millisecond work currently attached to UPDATE or establish viewer latency.

## Evidence required before adoption

Use development checks and the recorded compiler/ROM/emulator configuration,
with one small fixture and runtime-selected cases. No QED, demo refresh or
release matrix belongs to this primitive's initial acceptance.

- Check raw/optimized C/Action! public layout, three-byte argument and LONG
  result probes; use optimized emitted code for functional and timing cases.
- Exercise free/recursive acquisition, nesting release, busy/successful Attempt,
  three-Task FIFO handoff, a newcomer attempting to barge, and multiple owned
  semaphores. Check owner/count/queue and public/private Task state together.
- Cover bank-crossing semaphore and Task records, wrong-owner/extra release,
  count/depth exhaustion without partial mutation, and pool reuse after release.
  Prove removal rejects owners/waiters, including a granted-but-not-yet-run
  waiter, and succeeds after ordinary release.
- Force IRQ/NMI at enqueue/state publication, pop/owner transfer, ready insertion
  and native return boundaries. A contended masked Obtain faults without a
  queue edit; outer Forbid depth survives a blocking obtain. Signal bits posted
  before/during the wait remain pending afterward, and no wake duplicates a
  scheduler/sem node. Preserve guards and normal OS restoration.
- Run a small semaphore owner plus background Counter and one bounded native
  device-completion case. The Counter must run while ownership is held; normal
  IRQ completion must remain live through short metadata operations.

Compare against an equivalent minimal Forbid/Permit library semaphore with a
cached, already-admitted Task identity, so the baseline does not include an
avoidable FindTask scan. Reuse the same owner/depth/FIFO semantics. Establish
ordinary Task leases, waiter storage and any baseline reply signals outside
the timing window; keep all participants alive for both measurements. The
native path still pays its own ownership-count updates, making the baseline
conservative. Check native removal protection separately rather than teaching
the comparator to write private kernel metadata. The comparator is fixture
code, never a second production API/profile.

Measure complete public acquire/release pairs and recursive pairs, including
wrappers, charged Task CPU, native interrupts and off-Task time separately.
Record fast completions, post-operation dispatch, request COPs, code size,
scratch/headroom and IRQ-masked intervals. Quiescent native calls must avoid
general dispatch; busy Attempt must neither queue nor wait; blocking Obtain
must resume from its original invocation. Use a provisional performance gate
of at least 25% less charged CPU for both free and recursive pairs than the
minimal composition, reporting actual distributions rather than claiming a
predicted microsecond cost. Revisit the design if that small prototype misses
the gate.

After the primitive passes, plan and measure one AES migration separately.
Reuse unchanged MGVIEW/Counter APPs where their ABI permits. Report end-to-end
latency independently of primitive CPU savings.

The original draft used source/ABI review and documentation checks only.
The linked execution record now documents emitted-code development acceptance,
including the unchanged reservations and the cost gate. Hosted release
qualification and AES migration remain separate work.

[amiga-init]: https://developer.amigaos3.net/autodocs/exec.library/InitSemaphore.html
[amiga-obtain]: https://developer.amigaos3.net/autodocs/exec.library/ObtainSemaphore.html
[amiga-attempt]: https://developer.amigaos3.net/autodocs/exec.library/AttemptSemaphore.html
[amiga-release]: https://developer.amigaos3.net/autodocs/exec.library/ReleaseSemaphore.html
[magic-obtain]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L1438-1494
[magic-release]: https://gitlab.com/AndreasK/Atari-Mac-MagiC-Sources/-/blob/28cfdd29aa16fef692cc287bad3046b44ddcce3d/MagiC/KERNEL/AES/SRC/AESEVT.S#L1508-1557
