# timer.device design

[Implementation plans](README.md) · [Device I/O](../reference/device-io.md) ·
[AES server design](gem4xe/aes-server-design.md)

Foundation sequencing and its timer adoption gate are specified in the
[interrupt ReplyMsg implementation plan](interrupt-reply-implementation-plan.md).

Status: implementation/design record, 2026-10-05. TD0–TD3 are implemented without a worker Task. The
[current timer contract](../reference/timer.md) and
[execution record](../history/interrupt-reply.md) describe development evidence
and the 57.6k loaded envelope; TD4/AES and 125k timer-load timing remain open.

## Decision

Provide a resident `timer.device` for asynchronous one-shot delays, monotonic
clock reads and absolute monotonic deadlines. Applications and drivers submit
ordinary I/O requests, wait on existing signals and collect ordinary replies.
Keep `EXEC.Wait` and the scheduler's signal-wait semantics unchanged. No
`WaitTimed` operation, AES-specific kernel service or per-client timer Task is
required.

Use classic Amiga Exec as the public model: `OpenDevice`, `SendIO`, `CheckIO`,
`WaitIO`, `AbortIO` and `CloseDevice`. The timer driver owns admission, pending
requests, deadline order, cancellation and lifetime. The platform supplies the
clock. The kernel continues to own generic Tasks, messages and signals.

The selected direction is **no timer worker Task**, after the proposed
[interrupt-context ReplyMsg foundation](interrupt-reply-design.md) passes its
generic queue, NMI and lifetime checks. Current Exec816 cannot yet do this:
message operations remain Task-only. The dependency extends generic native
publication and deferred interrupt service; it does not add timer policy to the
scheduler. Its new contracts must be implemented before timer expiry uses them.

## Existing constraints and alternatives

The [resident driver boundary](../reference/resident-drivers.md) runs driver
callbacks on the submitting Task's stack, outside kernel dispatch. Callbacks
may complete immediately or enqueue work, but cannot remain suspended to wait
for hardware. The [port implementation](../../lib/exec/task-ports.inc) explicitly
excludes IRQ access to message queues. Ordinary `ReplyMsg` is not an ISR entry.
The current [signal contract](../reference/signals.md) provides fixed hardware
producers, not a general timer completion source.

Classic Amiga permits `ReplyMsg` from interrupts; Exec816 does not yet implement
that part of the model. We control the VBI path and can restrict early NMI to
clock/pending publication, then service native timer work at a safe boundary.
The ReplyMsg foundation defines that boundary and protects the receiving queues
as well as the interrupt-side append. [Amiga ReplyMsg contract][amiga-reply]

| Approach | Consequence |
| --- | --- |
| Native driver without a worker | Selected direction after interrupt ReplyMsg and controlled NMI continuations are tested independently. No worker stack or periodic Task wake. |
| One worker using existing `Sleep(1)` while requests are pending | Alternative if the interrupt foundation is not pursued; costs one Task and periodic active wakeups. It is not a second implementation profile to maintain. |

Do not hide timer completion in scheduler policy, run driver callbacks under
SWITCHING, depend on the GUI's event loop, or make application calls poll to
discover that requests have expired. Completion must happen while the caller
is asleep and while the GUI is absent. Private idle is not a timer worker:
CPU-bound applications can prevent it from running.

## Initial public interface

Open `timer.device`, `UNIT_VBLANK`, flags zero. This unit uses the platform VBI
clock; its name does not claim Amiga hardware or binary compatibility. Other
units and flags fail admission. The first profile is deliberately small:

| Operation | Request and behavior |
| --- | --- |
| `TR_ADDREQUEST` | Relative duration as normalized unsigned seconds/microseconds. Complete once the conservatively rounded deadline is due. Zero duration means the next VBI tick. |
| `TD_READCLOCK` | Return a coherent unsigned 64-bit tick count and its nominal ticks-per-second rate. This is an Exec816 device command, not an E-clock or wall-clock claim. |
| `TD_WAITUNTIL` | Wait until a supplied absolute tick count is reached. A deadline already reached is immediately eligible for completion. This is an Exec816 device command using the same clock as `TD_READCLOCK`. |

The absolute form avoids repeatedly adding rounding delay when a service
rearms its earliest deadline. It is still a one-shot request, not a repeating
timer. A clock read is observational: consecutive reads in one VBI interval
may return the same value. Neither clock reads nor relative requests adjust
system time.

Initially unsupported: high-resolution POKEY timing, Amiga E-clock emulation,
wall/calendar time, `TR_GETSYSTIME`/`TR_SETSYSTIME`, periodic callbacks, arbitrary
interrupt vectors and application entry from interrupt context. Resource
exhaustion is a reported failure, not permission to drop a timer.

The Amiga reference defines `TR_ADDREQUEST` using an extended request and
seconds/microseconds, with abort followed by collection. Its VBLANK unit has
coarse resolution. Exec816 retains that request model, but its new clock/deadline
commands and Task-only entry rules are explicit platform differences.
[Timer overview][amiga-timer], [TR_ADDREQUEST][amiga-add]

### Records and generated definitions

Propose these native layouts, to be fixed and verified by emitted-code probes
before implementation is accepted:

| Record | Fields after the existing 26-byte IORequest | Proposed total |
| --- | --- | --- |
| `TimerRequest` | `seconds: LONGCARD`, `microseconds: LONGCARD` | 34 bytes, alignment 2 |
| `TimerClockRequest` | `ticks_hi: LONGCARD`, `ticks_lo: LONGCARD`, `ticks_per_second: LONGCARD` | 38 bytes, alignment 2 |

`TR_ADDREQUEST` requires `TimerRequest`; `TD_READCLOCK` and `TD_WAITUNTIL` require
`TimerClockRequest`. The rate is output for reads; callers do not select a clock
by writing it into a wait request. Keep pending deadlines and links in separate
driver storage, not public fields that the caller might inspect as a result.
Reject truncated records and address-space wrap before touching extended fields.

Add a machine-readable timer ABI input and generated Action!/C/assembly
definitions, plus a resident route in [io.json](../../abi/io.json). Numeric
command/unit assignments are fixed there, not duplicated as handwritten
constants. Native pointers and C huge pointers retain the
[C bridge](../guides/calypsi-c.md) distinction. Existing device calls and COP
selectors are reused. Prove record access in both compiler modes.

## Clock and deadline semantics

Maintain a 64-bit boot-relative VBI count in upper platform RAM from native
runtime clock initialization until shutdown. Opening, closing or restarting the
timer service does not reset it. Keep the existing 16-bit `E816_VBI_COUNT` and
its consumers unchanged; do not widen that bank-zero field in place.

The new count is incremented directly from the established VBI tick path,
including VBI during OS calls and long Task descheduling. Extending the low
16-bit count when a client eventually runs would lose whole wraps. Preserve
the ROM VBI chain, register widths, hidden accumulator byte, DP, bank registers
and page-one stack requirements. No timer queue work belongs in that path.
See [platform VBI rules](../reference/platform.md#vbi-preemption) and
[current VBI entry](../../platform/altirraos/preemptive.s).

Provide a bounded native snapshot routine used by the driver. Scheduling
exclusion alone does not stop the NMI writer. Use a publication version around
the wide clock write and validate that version around the read; exclude Task
switching during the short copy and prove the copy cannot span a complete
version wrap on the pinned machine. Retry only in Task context; NMI must never
spin waiting for an interrupted reader. Test carries and interruption between
every published word. No public kernel clock selector is needed: `TD_READCLOCK`
calls this routine from the resident driver.

The first rate is the pinned platform's nominal 50 or 60 ticks/second, captured
at startup and returned by the clock query. Do not silently assume PAL for an
NTSC configuration or allow the rate to change during a service lifetime.
This is time measured in video ticks, not a calibrated microsecond clock.

For a positive relative duration, capture count `C` during BeginIO and compute:

```text
delta = seconds * rate + ceil(microseconds * rate / 1,000,000)
deadline = C + delta + 1
```

Require `microseconds < 1,000,000`. The final tick accounts conservatively for
the unknown position within the current VBI interval. Thus a positive delay
does not expire early relative to the declared tick clock; rounding can add
less than two tick periods before scheduling/completion latency. For zero
duration use `C + 1`. Do not silently impose this minimum on absolute deadlines:
`TD_WAITUNTIL` uses the supplied tick value directly.

Use checked wide arithmetic; reject overflow before queuing. The full unsigned
32-bit GEM millisecond range fits, as does the proposed relative seconds field
under the 64-bit clock. Publish a caller-local conversion helper so AES and other
clients calculate the same conservative absolute deadline once. If an absolute
deadline is already due, return success without manufacturing another delay.

The count does not intentionally wrap during a boot session. Define overflow as
a clock fault, never an unnoticed return to zero. On a detected clock fault,
reject new timing work and complete outstanding requests with a device error.
This is distinct from the routine 16-bit legacy tick wrap, which must continue
working. No accuracy guarantee applies across deliberately disabled VBI; late
Task dispatch with continuing VBI must retain elapsed ticks correctly.

## Driver execution and synchronization

All open records, pending slots, sorted deadline links and cancellation state
are upper-RAM driver data. Task-context BeginIO/AbortIO/Open/Close and a bounded
native timer continuation share them. The raw VBI handler only updates the
clock and records pending source work while timers are armed. It does not walk
requests or publish replies. Native continuation dispatch follows the generic
[controlled NMI protocol](interrupt-reply-design.md#controlled-nmi-and-native-continuations).

Forbid serializes Task-side entry, but does not exclude native continuation
work. Acquire a stable driver edit gate before preparation; continuations that
see it retain pending work and return. Publish link/state changes in short
IRQ-masked transactions, then release the gate with the generic pending-work
handoff. No interrupt spins on the gate. This driver protocol is separate from
port-list protection and from the clock's NMI-safe snapshot protocol.

Start with eight open records and sixteen simultaneously pending timers across
all clients. Deadline ordering is ascending, with FIFO order for equal deadlines.
A fixed slot table bounds scans, insertion and failure handling; allocate its
storage at service startup and never allocate in an interrupt. Exhaustion
completes the rejected request with a defined timer error. An application may
have more than one timer, subject to the shared bound.

For future timing work, BeginIO validates and copies inputs, obtains a pending
slot and publishes its deadline under that protocol. It clears IOF_QUICK before
publishing deferred ownership. Clock queries and already due absolute requests
need no pending slot. Duration begins at admission. Never reread caller input
while the request is pending, or retain a caller pointer in raw NMI state.

The native timer continuation reads the coherent clock and the ordered head.
It commits at most four due completions per invocation, retaining pending source
work if more are due. A future head ends the batch without scheduling a Task.
Publish an armed flag after consistent queue state; raw VBI uses only that flag
to request service. An empty queue disables timer-source notifications while
the monotonic clock continues advancing. One native head check per active VBI
is an initial cost to measure; there is no timer Task wake or busy idle loop.

Each completion detaches its pending slot and commits the result before calling
the native ReplyMsg entry. Do not run compiled Action!/C driver code from the
continuation or enter the ordinary COP/device wrappers. Use audited native
helpers with bounded stack use. The generic adapter handles source fairness,
safe IRQ opportunities and pending-work progress; it does not interpret the
timer's deadline queue. A short protected operation must hand pending expiry
to its exit path rather than force it to await another VBI.

Abort and already due submissions can complete in their Task-context callbacks.
Deferral leaves the request owned by the driver, not hidden in a second reply
queue. Never process an unbounded expiry burst with interrupts masked; test
the four-completion budget and the sixteen-request backlog against SIO and
pointer timing before accepting those limits.

## Completion and cancellation

Follow the current [I/O completion contract](../reference/device-io.md#completion-and-lifetime).
Every non-quick submission produces exactly one reply, including rejected
commands and admission errors. An immediate `TD_READCLOCK` or an already due
absolute request may honor IOF_QUICK when supplied. `SendIO` always requests a
reply. `TR_ADDREQUEST`, including zero, is deferred and clears IOF_QUICK.

On successful `TR_ADDREQUEST`, set the returned duration to zero. On aborted
requests, do not claim that the duration represents time remaining; the error
is authoritative. A successful absolute request does not imply exact dispatch
at its target tick. Query the clock separately when measuring lateness.

The terminal decision is serialized by the driver edit/commit protocol for
native expiry and Task-context abort:

| Observed state | AbortIO result |
| --- | --- |
| Queued or due, without a committed terminal result | Remove it, commit `IOERR_ABORTED`, and publish its one reply. A due deadline alone does not win the race. |
| Success or failure already committed/published | Leave the existing result and reply unchanged. |
| Collected/idle | No pending timer is cancelled. Resubmission starts a new lifetime only after collection. |

The driver does not leave a half-claimed request outside protection. Detach all
driver references and release the pending slot before calling `ReplyMsg`.
Never access the descriptor after publishing the reply; the recipient may
collect, reuse or free it immediately. A deadline crossing during BeginIO,
AbortIO or reply publication cannot independently complete the request: raw
NMI records time/work, and the native continuation obeys the driver edit gate.

`AbortIO` is not collection. Callers still use `WaitIO` or explicitly dequeue
the particular reply before reuse, free or CloseDevice. `CheckIO` observes
completion and does not dequeue it. Do not cancel all requests sharing a signal
bit or clear that bit as a cancellation mechanism. Other devices and unrelated
messages may share the same reply port.

## Open, close and native source lifetime

Use the existing static resident device dispatch and public Task leases for
open owners. Serialize first opens and publish readiness only after driver
storage and native source state are initialized. Concurrent first opens share
one device instance. No AddTask, worker signal allocation or resident Task
registration is needed. Failure unwinds admission without returning a binding.
Any allocation/setup belongs outside the bounded publication transaction.

For the initial timer profile, Open requires the caller's live PA_SIGNAL reply
port and retains that Task through the open record. Additional requests may
borrow that open's device/unit handles and reply port; copying handles does not
acquire another open reference. Sharing with another submitting Task requires
an explicit storage/lifetime agreement. Reply-port substitution and PA_IGNORE
timer opens are outside this first profile, though generic Exec I/O permits
broader arrangements.

Close requires collection of every request borrowing that binding, including
replies already queued. Queue emptiness inside the driver cannot prove caller
collection. Keep the current I/O lifetime precondition; do not add an implicit
abort, port scan or asynchronous Close. No generic collection hook is presumed.
After Close releases the open reference and owner lease, idle request storage
can be deleted according to the generic contract.

Explicit stop refuses live opens or unsettled requests. Last Close may retire
an otherwise unused instance: close admission, disable native source requests,
quiesce/drain pending continuation state, and only then release driver storage.
The generic source guard prevents retirement while a continuation is running.
Retain code/state and reply endpoints until that handoff completes; never clear
a source flag and assume an already captured continuation has disappeared.
Restart publishes a new instance generation so stale source work cannot act on
new opens. The clock remains live until platform shutdown even while closed.

There is no driver policy in Task removal. Freeing a bound reply port or exiting
with live opens violates the ownership contract. Forced cleanup after a crashed
client is separate lifecycle work; a timer cannot safely reply into freed memory.

## AES use

AES owns application event masks and deadlines. `timer.device` knows only I/O
requests and tick targets. Open one device binding and allocate one asynchronous
absolute-deadline request, plus a separate idle clock-query record. Never reuse
the active timer descriptor to read the clock.

1. Convert a new application duration to an absolute deadline once.
2. Arm `TD_WAITUNTIL` for the earliest pending deadline.
3. Use ordinary `Wait` on AES/native requests, input, drawing completion and
   the timer reply signal. Drain queues and inspect retained state after wakes.
4. Reevaluate all application waits against the current clock. A message and
   timer may satisfy one `evnt_multi` together; produce one AES reply.
5. If the earliest deadline changes, abort and collect the old request before
   preparing the new one. Already completed replies are collected normally.

Unrelated input does not require cancellation/rearming of an unchanged earliest
deadline. When there are no timed clients, retire the alarm. Native timer-source
work becomes idle if no other device client has timers. A stale reply-port
signal is harmless: collected request state and the queues decide what exists.
The GUI pump must not block waiting for a future alarm via DoIO. In this driver,
AbortIO removes an unsettled request synchronously, so subsequent collection
does not wait for another tick; it may only collect that terminal result.

For compatibility, handle zero-duration `MU_TIMER` in `evnt_multi` immediately
in AES without submitting a timer. GEM4XE's standalone `evnt_timer(0)` instead
waits one tick and maps to the zero relative request. Preserve that distinction
from the donor's [event implementation][gem-events]. The timer does not impose
a per-frame gate on input, button feedback, drawing or other AES replies.

## Memory and cost

Design target: no enlarged fixed bank-zero reservation, no larger existing Task
pools and no per-client stack/DP. The wide clock, pending table, open records,
native source records and client requests live in upper RAM. Count all actual
generated sizes, alignment and unused slots before implementation acceptance.

No timer Task is admitted. Compared with the worker alternative, one ordinary
slot and its **1,312 bytes of already reserved stack/guards/DP capacity** remain
available. This does not shrink the bank-zero map. Measure native completion
plus nested NMI against the existing interrupt stack reserve; review a complete
reservation delta if it does not fit. See the [Task budget](../architecture/task-capacity.md).

The native source uses no Task signal of its own. Client reply ports use the
normal per-Task signal namespace and may already exist. Record source metadata,
publication guards and all upper-RAM storage.
The VBI clock hook must fit the existing adapter reservation or place its body
in upper code, with only a bounded entry stub near the current path. Check
linker extents; do not assume padding is enough.

Measure separately: VBI clock increment cost with no opens, native head-check
cost with one long timer, simultaneous-expiry batches, submission/abort cost,
deadline-to-reply and reply-to-caller latency. Run with CPU load, SIO traffic and
native button feedback. There is no hard real-time completion bound while
OS work, protected driver edits or other activity defers safe service or Task
dispatch. Forbid alone does not suppress native interrupt completion. Clock
resolution, rounding and scheduling lateness are separate reported quantities.

## Executable slices

| Slice | Acceptance |
| --- | --- |
| TD0: foundation and resident admission | Generic interrupt ReplyMsg/continuation checks pass first; generated layouts and commands, open/close, invalid input and rollback through real C/Action! calls; no timer Task admission. |
| TD1: wide platform clock | Coherent reads, carries, PAL/NTSC rate, legacy 16-bit wrap and clock continuity without an open device; interrupted native/OS entry and context restoration. |
| TD2: asynchronous requests | Native source activation, relative/absolute deadlines, exact one-reply completion, quick-read behavior, queue/full errors, equal-deadline ordering and progress without GUI/input traffic. |
| TD3: cancellation and lifetime | Abort against native expiry, edit-gate handoff, immediate request reuse, shared reply-port traffic, borrowed bindings, first-open races, source retirement/restart and failure rollback. |
| TD4: AES and cost evidence | One earliest-deadline request serves several simulated AES clients; simultaneous events, zero-timer distinctions, unchanged input wake path, CPU/SIO load, stack and memory accounting. |

Use [development-tier checks](../contributing/testing.md): host validation and
focused emitted-code tests, with raw/optimized ABI/context probes and optimized
behavior/performance cases. Keep an independent deadline oracle and inject
interrupts at publication/carry/retirement boundaries. Cover full GEM 32-bit
millisecond conversion without waiting days by seeding controlled clock states;
retain real VBI/OS coexistence tests separately. Check all stack/domain guards,
register restoration and bounded completion. Pin ROM, emulator, compiler,
video mode and observers in results.

Before TD4 acceptance, demonstrate active timer progress under CPU load, no
timer-source continuation while idle, bounded completion bursts and no mandatory
extra tick after releasing a protected edit. The common clock still advances
with no opens. Generic interrupt work is a prerequisite, not inferred from
successful timer tests or silently folded into the timer driver.
Demo refreshes, if requested, use the standard OF816 packaging workflow; no
refresh or release qualification follows from writing this design note.

Actual bank-zero reservation delta for this documentation change: **0 bytes
fixed, 0 bytes per Task**. Avoided worker occupancy and native stack fit remain
proposed outcomes, not measured implementation results.

[amiga-timer]: https://developer.amigaos3.net/autodocs/timer.device/
[amiga-add]: https://developer.amigaos3.net/autodocs/timer.device/TR_ADDREQUEST.html
[amiga-reply]: https://developer.amigaos3.net/autodocs/exec.library/ReplyMsg.html
[gem-events]: https://github.com/slaapliedje/gem4xe/blob/e413c39d2f8e1bec8fe16596f610b923de4a0ae9/src/aes/event.c#L950
