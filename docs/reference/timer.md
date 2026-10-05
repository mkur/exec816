# timer.device

[Reference](README.md) · [Device I/O](device-io.md) · [Implementation record](../history/interrupt-reply.md)

`timer.device` supplies asynchronous VBI delays through ordinary Exec device
I/O. It has no worker Task. Use `USE TIMER` in Action!, or `<devices/timer.h>`
with `<proto/exec.h>` in Calypsi C. Records and constants are generated from
[timer-device.json](../../abi/timer-device.json); these are source interfaces,
not Amiga binary layouts.

Open `UNIT_VBLANK` (1), with flags zero, on a request whose `PA_SIGNAL` reply
port belongs to the caller. The driver retains that Task until CloseDevice.
There are eight open bindings and sixteen pending requests across all clients.
Other units, wall-clock adjustment and sub-VBI timing are unsupported.

| Command | Record and behavior |
| --- | --- |
| `TR_ADDREQUEST` (9) | `TimerRequest` (34 bytes): IORequest, unsigned 32-bit `seconds`, unsigned 32-bit `microseconds`. Require microseconds below 1,000,000. Success clears both duration fields. |
| `TD_READCLOCK` (10) | `TimerClockRequest` (38 bytes): IORequest, unsigned 32-bit `ticks_hi`, `ticks_lo`, `ticks_per_second`. Returns a coherent monotonic 64-bit VBI count and rate. |
| `TD_WAITUNTIL` (11) | The same clock record; high/low supply an absolute target. Targets at or before the current clock complete immediately. The rate field is not an input. |

The clock advances even with no opens. Rate is 50 for PAL or 60 for NTSC,
captured from the pinned ROM's PALNTS setting at startup. It counts VBI events,
not measured wall-clock seconds. Overflow saturates the clock and latches an
error; it never silently wraps. An interrupted snapshot retries once, then
returns `TIMERERR_CLOCK` if neither copy is coherent.

Relative delays use `now + seconds*rate + ceil(microseconds*rate/1000000) + 1`.
The extra tick avoids an early completion at an unknown point in the current
frame; a zero relative delay therefore waits one tick. Arithmetic is checked
across all 64 bits. `TIMER.Deadline(clock, milliseconds)` similarly converts the
full unsigned 32-bit GEM millisecond range once, modifying only the snapshot's
high/low fields. It returns 1 on success or 0 on bad rate/overflow, preserving
the original deadline on failure.

`DoIO`/`BeginIO` quick reads, already-due absolute waits and immediate errors do
not enqueue a reply when `IOF_QUICK` is set. Accepting a deferred request clears
QUICK before ownership transfers. `SendIO` always uses normal reply/collection
semantics. Positive device errors are `TIMERERR_QUEUEFULL` (1),
`TIMERERR_OVERFLOW` (2), `TIMERERR_CLOCK` (3), `TIMERERR_BADTIME` (4).
Unsupported commands and short records use the existing signed Exec I/O errors.

Deadline ordering is FIFO among equal targets. A native callback completes at
most four due requests, allowing a hardware IRQ between replies; the common
dispatcher admits at most two callbacks per opportunity. A runnable Task may
leave excess work pending until its next interrupt or Exec exit. Idle creates
another bounded opportunity instead of waiting for an unrelated tick. Forbid
delays scheduling, but permits native completion. Arbitrary I=1 Task frames,
live OS activations and driver edit gates defer completion. These constraints
preclude a hard real-time deadline guarantee.

AbortIO detaches a still-pending request and replies exactly once with
`IOERR_ABORTED`. If expiry already committed, AbortIO is harmless and preserves
that result. Always collect with WaitIO or the reply port before reuse. A
borrowed request may copy an admitted binding's device/unit fields but must use
that binding's reply port. Use a separate idle request to read the clock while
an alarm is pending.

Close the original open request only after all borrowed requests are settled
and collected. The last close disables and clears the source before releasing
the Task lease. The clock continues across reopen. A Task lease does not retain
the port, its signal or request storage: freeing these while the driver owns a
request is misuse. Pending work causes CloseDevice to fault rather than abort
implicitly. Forced recovery of crashed clients is outside this interface.

Action! and C callers use their ordinary Task ABI. Only the resident's assembly
completion calls the [native ReplyMsg binding](ports.md#native-interrupt-reply).
AES can wait on this reply signal alongside messages/input using ordinary Wait;
no new kernel timed-wait operation is required. AES integration remains separate.

The measured loaded envelope is the demo's nominal 57.6 kbit/s SIO profile.
Sixteen simultaneous expiries plus port/serial load passed all 4,095 refill
deadlines. At 125 kbit/s, 4 KiB transfers passed, but extending to 16 KiB exposed
five missed deadlines with timers and three without, among 16,383 refills.
Data and replies remained correct. That profile
remains unsupported for this integration pending further
latency work. These are targeted development observations, not release qualification.
