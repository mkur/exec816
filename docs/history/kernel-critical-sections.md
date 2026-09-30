# Interruptible Task policy

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/overview.md) and [history index](README.md).

The Task kernel permits serial IRQs during validation, scheduling, ready-list
updates and timed-wake processing. Only the native entry/restore boundary and
small transactions shared with IRQ producers mask interrupts. The public Exec
API, FIFO scheduling and direct target delivery are unchanged.

This protocol began with the second latency follow-up slice. The
[concurrency baseline](signals-concurrency.md) found millisecond blackouts
across whole kernel calls, including Yield and Sleep. Shortening only the wake
drain could not address those paths.
The [COP fast paths](kernel-fast-path-implementation.md) now use the same guard
for native Forbid, Permit and GetMsg, before the general Action! dispatcher.

## Entry, policy and return

`E816_SWITCHING` excludes scheduler reentry for the entire kernel activation.
It is independent of the processor's I flag:

1. Native entry saves the complete task frame with I=1. COP signature decoding
   uses four temporary stack bytes, so a
   rejected or forwarded COP cannot overwrite an interrupted policy's DP.
2. Entry asserts SWITCHING. If the saved caller allowed IRQs, it enables them
   before validating the frame's stack/DP owner, tick bookkeeping and changing
   to kernel S/D. Validation reads immutable pool bounds and uses local stack
   scratch; it cannot switch tasks. A rejected frame releases this activation's
   guard with I=1 before restoring or faulting. An interrupt saves and
   restores whichever S/D pair is active, including intermediate pairs during
   this guarded transition. IRQ posting uses activation-local scratch; NMI
   records ticks and runs the existing OS adapter. Neither may enter policy.
3. Forbid, Permit and GetMsg first execute their native operation using 20 bytes
   of activation-local scratch below the saved frame. With IRQs masked at the
   final decision, pending ticks, timer work, IRQ wakes or unprotected caller
   rescheduling enter Poll with the completed result. Otherwise the native
   handler retires its scratch and restores the caller directly. A tick arriving
   after that decision remains pending. The operation is never replayed.
4. Other services, and completed fast calls requiring Poll, enter Action policy
   with IRQs enabled. SWITCHING protects context selection,
   compiler scratch, public task state and the ready list against another
   policy activation. IRQs never inspect those partially updated lists.
5. After the policy returns, native code sets I and validates the selected
   frame. If a wake arrived after the last drain, it dispatches Poll using that
   frame before returning. Otherwise it installs the selected stack, clears
   SWITCHING and restores the complete context through RTI. The existing NMI
   ownership checks cover partial restoration.

A caller that entered with I=1 stays masked throughout its call. This remains
outside the serial timing acceptance workload. Wait with I=1 faults before
changing signal state. Forbid still prevents task switching while allowing
IRQ delivery and readiness processing. A blocking Wait retains its Forbid
nesting for continuation resumption.

The final pending-wake check and restore are one masked operation. Rechecking
in Action alone would leave a window in the compiler epilogue. During the
native retry, each matching target leaves signal-waiting state; an IRQ cannot
refill that target's wake node until a task runs and waits again. No user task
runs inside this retry.

## Atomic operations

[signal-atomic.s](../../platform/altirraos/signal-atomic.s) supplies private native
mechanisms called by [Task policy](../../lib/exec/taskpolicy.act). Each checks its stack
reservation and preserves the incoming I bit with PHP/SEI/PLP. Argument setup
and result cleanup run outside the masked transaction. Ordinary compiler ABI
calls carry far Task/context pointers and full 32-bit masks.

| Operation | Work that excludes IRQ posts |
| --- | --- |
| `SignalChange` | Read the previous received mask and apply `(old & ~mask) \| (bits & mask)` across both words. Used by SetSignal, Signal posting and allocation's pending-bit clear. |
| `WaitBegin` | Consume matching received bits, or publish the wait mask, reason and waiting state together. |
| `WaitComplete` | Consume the selected waiter's matching bits and clear its wait mask/reason. Later posts remain pending for its next Wait. |
| `TakeWake` | Validate and detach one pending head, mark it claimed and update the cached pending flag. |
| `WakeMatch` | Test the latest received/wait masks and publish private READY before releasing a drain claim. |
| `CancelWakeNode` | Unlink a known queued node and update the cached pending flag. |

Generic Lists operations, reciprocal Task/context validation, ready-list
insertion and selection stay in Action. The native queue operations exist
because IRQ appends can interrupt those compiler-generated multi-byte writes;
they are private mechanisms, not a second public Lists implementation.

Serial claim/release also mask their small ownership transaction and preserve
incoming I. A binding is prepared while inactive, then activated atomically.
Release quiesces the serial source before its binding can be cleared. Removing
a Task with an active bound producer remains invalid.

## Detached wake ownership

The existing context byte `queued` has three states, generated from
[tasks.json](../../abi/tasks.json): zero means absent, `WAKE_LINKED=1` means linked
in the wake MinList, and `WAKE_CLAIMED=2` means detached but owned by the drain.
No field or allocation was added.

An IRQ always ORs its bits into `tc_SigRecvd`. It appends a matching waiter only
when `queued` is zero. The kernel atomically claims a head, then validates its
Task association with IRQs enabled. A post during that validation adds bits
without linking the same node again. `WakeMatch` makes the final mask test:

- On a match, it publishes private READY before clearing the claim. Further
  IRQ posts accumulate bits but cannot requeue this task. Policy then updates
  public state and appends `tc_Node` to the ready list.
- Without a match, it releases the claim while still masked. A later matching
  post can append a fresh wake.

Task-context Signal uses the same private READY publication before cancelling
an existing wake node. The ready node and wake node remain distinct. Delivery
visits known pending targets; timed Sleep retains its separate expiry scan.

## Validation and limits

The [qualification record](../qualification/kernel-critical-sections.json) pins
the compiler, ROM, emulator, observer and source hashes. It repeats all five
4,096-byte concurrency workloads in raw and optimized code, with identical
uninstrumented replays. Byte deadlines determine acceptance; a longest I=1
interval can include a refill performed by that IRQ and is not itself a miss.

All ten workloads pass with zero late refills and zero byte gaps. In the mixed
workload, worst refill falls from 1,450.283 to **59.771 µs** raw and from
1,320.028 to **60.898 µs** optimized. The optimized mixed longest I=1 interval
falls from 1,306.495 to **68.863 µs**, about a 19× reduction.

Six additional 65,535-byte transfers cover Yield, Signal/Wait and mixed work
in both modes, each with an identical uninstrumented replay. Across all
**434,154 measured refills**, there are zero misses or byte gaps. The worst
refill is **73.304 µs**, leaving 5.638 µs against the tested deadline. These
are observed maxima, not a global interrupt-latency bound.

| Workload | 4,096 bytes, raw | 4,096 bytes, optimized | 65,535 bytes, raw | 65,535 bytes, optimized |
| --- | ---: | ---: | ---: | ---: |
| Compute control | 60.898 µs | 60.898 µs | — | — |
| Yield | 68.793 µs | 60.898 µs | 71.048 µs | 65.409 µs |
| Signal/Wait | 59.771 µs | 60.898 µs | 72.176 µs | 73.304 µs |
| Timed Sleep | 59.771 µs | 60.898 µs | — | — |
| Mixed | 59.771 µs | 60.898 µs | 69.920 µs | 72.176 µs |

Table entries are the worst ready-to-refill latency in each run.

The new [atomic fixture](../../tests/programs/signals_atomic.act) places
`tc_SigRecvd` at `$04:FFFF`, checks full-width operations and adjacent guards,
and forces a second distinct IRQ post while a wake is claimed. It verifies
both bits return from Wait, no duplicate queue entry or recursive scheduling,
and a rejected COP inside that IRQ preserves kernel DP scratch and SWITCHING.
Separate probes inject real NMI entry between mask/state writes. These
deliberately stalled race probes are excluded from timing measurements.

All **116 Task/signal cases** pass, including raw/optimized masks, waiting,
removal/reuse, caller-masked behavior, invalid calls, full queues, native flag
combinations and NMI entry points 9–18. The two new entry points cover partial
COP save and stack-local signature lookup. Fifty package/parser tests pass.

Eight capacity cases cover ordinary eight-task operation and full pending-wake
queues in raw/optimized builds at kernel banks 1 and 3, including an IRQ
asserted while masked and serviced between drains. Fourteen shared
single/cooperative/preemptive/banked/Lists regressions also pass. Functional
Task tests use the pinned 1×/1 MiB profile; the shared launch regressions also
retain their 64 KiB profile.

The measured profile remains PAL, 8× CPU, fast ROM, 1 MiB and the pinned native
AltirraOS ROM, with normal VBI and scoped serial CRITIC ownership. Divisor 14
gives 126,674.821 baud and a 78.942286 µs refill deadline. This qualifies the
diagnostic TX pump with concurrent four-task kernel work. It does not qualify
per-byte worker delivery, arbitrary OS I/O/timer callbacks, eight-task long
concurrent transfers, RX, RAM buffers, SIO protocol or physical hardware.

```sh
python3 tools/test_signal_concurrency.py --compiler-dir build/actionc \
  --workload compute --workload yield --workload signals --workload sleep \
  --workload mixed --count 4096 --require-deadline
python3 tools/test_signals.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
python3 tools/test_task_capacity.py --compiler-dir build/actionc \
  --bridge-dir build/altirra-irq-bridge
```

## Memory budget

Reserved bank-zero delta is **0 bytes**, fixed, per task and diagnostic.
Native helpers use 12 activation-local bytes plus saved D/P, a checked peak of
15 bytes; NMI injection builds reserve eight more. COP signature decoding uses
four temporary bytes within existing interrupt headroom. No stack, DP, guard,
state arena or metadata reservation grows. Native code uses the existing
upper-RAM signal-code extent: the diagnostic pump image uses 1,823 of its
reserved 4,096 bytes, up from 765. The public Task and private context stay 62
and 64 bytes respectively.

Complete reservations, including guards, alignment and unused capacity:

| Reservation | Four tasks | Eight tasks |
| --- | ---: | ---: |
| Fixed runtime, excluding OS | 11,824 | 10,560 |
| Root | 1,856 | 2,080 |
| Each other public Task | 1,856 | 1,568 |
| Private idle | 1,856 | 1,056 |
| Runtime, excluding OS | 21,104 | 24,672 |
| Runtime, including OS | 57,968 | 61,536 |
| Loading, excluding OS | 21,696 | 20,368 |
| Loading, including OS | 58,560 | 57,232 |

The OS reservation remains 36,864 bytes. See the
[capacity budget](../architecture/task-capacity.md#complete-bank-zero-budget) for pool addresses
and loading/runtime lifetime accounting.
