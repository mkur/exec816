# Signals and Wait: delivery-path review

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

Status: design decision adopted in [signals-wait-design.md](../reference/signals.md),
implemented in the [current Task kernel](signals-implementation.md). This review originally proposed alternatives to
an all-waiters scan. The chosen mechanism is now direct delivery with an
intrusive pending-wake queue. The five classic calls, 32-bit masks, coalescing
and wait-for-any semantics remain unchanged. The revised Task ABI also includes
an opaque context link; its storage cost and deviation are explicit below.

## Decision: retain the known target

`Signal(task, bits)` already names the target. No other task's signal mask is
relevant to deciding whether that target should wake. Recording only a global
work flag and later scanning every waiter discards information we already have.

The selected path is:

1. OR the bits into the named target's `tc_SigRecvd`.
2. Test that target's blocked signal-wait state and mask intersection.
3. In an IRQ, append its private pending-wake node once if it should wake.
4. At the first safe policy boundary, take the pending head, recheck that target
   and make it READY by appending it to the ready tail.
5. Select the next runnable task from the ready head with direct context access.

The IRQ does not change scheduling-list membership or publish `TS_READY`.
The deferred target remains `TS_WAIT`; READY is published at safe delivery and
does not promise immediate execution. A running or ready target retains posted
bits without a wake entry. Timed Sleep remains separate. A signal Wait wakes
on any requested bit: `Wait(SERIAL_DONE | TIMEOUT)` needs either event, not both.

Task-context Signal already owns the safe policy domain. It makes its known
target ready before returning, even under Forbid, and directly cancels that
target's pending entry if an earlier IRQ queued it. Forbid can delay switching;
it does not require delaying that ready transition.

## Queue representation and cost

Use a private FIFO MinList and one private doubly linked MinNode plus queued
flag per task. It is separate from `tc_Node`, which belongs to scheduling lists.
The private node's fixed offset identifies its context without a search.
Repeated posts retain the node's position and coalesce in the received mask.
There is no ring overflow or IRQ-time allocation: each task has at most one
entry. Previous/next links permit constant-time removal of a known queued task,
including cancellation in the middle of the queue.

Enqueue, dequeue and cancellation of one known entry are O(1). Draining k
entries is O(k), and k can equal the live task count. The gain is that unrelated
tasks are never inspected. Bound each IRQ-masked target transaction and allow
IRQ service between drain transactions with scheduler reentry still excluded.
Changing the container alone does not bound a whole-drain masked interval.

The [critical-section implementation](kernel-critical-sections.md) now uses
the existing queued byte to retain a claim after detaching a head. This allows
validation and ready-list work with IRQs enabled. Only the mask/state and link
operations exclude IRQs; a repost during the claim coalesces without adding a
duplicate node. The public API and direct-target design remain unchanged.

The detailed [queue protocol](signals-wait-design.md#pending-wake-queue) covers
atomic publication, duplicate suppression, dequeue/repost races, target
revalidation, cancellation/reuse and the idle/WAI handshake. These are explicit
correctness obligations; the queue is not a reason to assume the races away.

The bitmap/ring alternatives are not selected. A global OR of all wait masks
is also unnecessary: signal numbers are task-local, so that aggregate loses the
target relationship, produces irrelevant matches and needs extra maintenance.

## Remove hidden searches from the delivery path

The scheduler at the time of this review used `tc_Node` for ready membership. It also
scanned private contexts in `Lookup()` and scanned timed sleepers in `Wake()` on
every dispatch. The tick pending byte is constant time; the full dispatcher
was not. See the [pre-signal policy](https://github.com/mkur/exec816/blob/499f1b0/lib/taskpolicy-v2.act).
The current policy uses direct context links and gates timer scans on pending ticks.

The revised ABI appends an opaque three-byte `tc_ExecPrivate` link after the
classic Task subset. This gives task-context Signal and ready-head selection
direct access to the private context; the context already points back to its
Task. IRQ registration retains that association in a stable binding before
enabling the producer. The public Signal signature remains Task-pointer based,
and `tc_UserData` stays application-owned.

This extension is a documented implementation choice for our caller-owned
Task/private-context split, not a mandatory 65816 feature. The proposed public
Task is expected to occupy 62 bytes rather than the earlier mask-only 58: the
three-byte context link adds four bytes after ABI alignment. The previous
61-byte estimate missed the final padding byte. The
[memory budget](signals-wait-design.md#native-abi-and-memory-budget) accounts for
the context link, separate queue nodes, queue header and private flags, with
upper RAM preferred. This documentation update reserves no bank-zero storage.

Timed-sleep expiry is separate work and must not cause an all-slot scan on each
signal delivery. Coincident timer work still needs a measured interrupt bound.
Admission checks and explicit enumeration may search; they do not justify a
search to deliver to an already known task.

## Relationship to classic Exec

Classic Signal names one Task, retains posts for later use when appropriate and
can be called from interrupts. The [Signal autodoc](https://developer.amigaos3.net/autodocs/exec.library/Signal.html)
defines that contract. The uniprocessor path in the compatible
[AROS implementation](https://github.com/aros-development-team/AROS/blob/master/rom/exec/signal.c)
updates and tests that task, removes its scheduling node and makes it ready.
It does not search all tasks' signal masks.

`tc_Node` is a full Node, not a MinNode. Unlinking a known node is O(1), but
[priority-ordered Enqueue](https://github.com/aros-development-team/AROS/blob/master/rom/exec/enqueue.c)
can search the ready list. Do not describe the entire classic wake operation
as necessarily constant time. Exec816 currently ignores stored priorities and
can append directly to the ready tail.

Our deferred scheduling-list edit follows the current adapter's stack/domain,
NMI and nonreentrant OS constraints. The 65816 does not inherently prohibit
interrupt-time list operations. Keeping a bounded posting entry separate from
scheduler policy is the chosen protocol; it never requires forgetting the target.

## Latency evidence and build order

The [latency spike](sio-latency-poc.md) has run. On the emulated 8× PAL profile,
the minimal worker-per-byte path reached a 66.537 µs worst observed refill
against a 78.942 µs deadline at 126.675 kbaud. Passing required direct native
IRQ delivery, fast ROM access and scoped CRITIC suppression of VBI stage two.
The observed 12.405 µs margin belongs to that minimal workload; it does not
qualify this queue, full Signal, a larger scheduler or DOS.

Next establish the bounded native IRQ adapter and scoped SIO/OS ownership,
retaining the probe as an acceptance check. Implement the
[signal implementation plan](../plans/signals-wait-implementation-plan.md)
with direct delivery, then qualify at eight tasks and each later 12/16-task
configuration before claiming those capacities. Compare one active target with
many unrelated waiters, all-target bursts and coincident timer work, using raw
and optimized emitted code. Message ports and complete driver integration follow.

For the production driver, keep urgent byte movement in the IRQ and notify a
worker about buffered work or block/phase completion. With priorities ignored,
being READY does not guarantee that a worker runs before the next byte deadline.
Continue small driver experiments as the layers grow: receive overrun, real
peripheral replies, turnaround, checksums, timeout and cancellation remain
unqualified. A queue improvement is not proof that those questions are settled.
