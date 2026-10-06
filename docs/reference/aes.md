# AES application service

[Reference](README.md) · [C application guide](../guides/aes-applications.md) ·
[Development record](../history/aes-server.md)

The optional AES endpoint runs in the existing desktop presenter. It uses
ordinary Exec messages; it adds no Task or kernel gateway. The native desktop
and retained Control Panel remain independent clients of their existing service.

The current source profile in [gem.h](../../c/include/gem.h) implements
`appl_init`, `appl_exit`, `appl_write`, `evnt_mesag`, `evnt_timer`,
`evnt_multi`, `evnt_multi_moblk`, `wind_update` and the corresponding `aes_call(AESPB *)`
operations.
Other opcodes return zero with `ExecAESDiagnostic() == AES_UNSUPPORTED`.
This is a rebuilt Calypsi source interface, not a GEM binary ABI or a complete
AES implementation. Window, resource, form and VDI workstation calls are pending.

Startup retains the endpoint returned by `AESBOOT.Port()` until every C Task
has detached. Each application wrapper calls `ExecAESAttach(endpoint)` before
its GEM entry and `ExecAESDetach()` before ordinary Task removal. Detach calls
`appl_exit` if needed, collects its reply, then deletes the private port/context.
Failure to detach must prevent Task/image retirement. There is no forced client
recovery or discovery by name in this profile.

Each attached Task owns private parameter arrays, a request and reply port;
there is no process-global GEM parameter block. Four applications can register
at once. Successful init returns a positive signed 16-bit ID; repeated init on
the same live binding returns that ID. Exit returns one. Failed init returns
minus one. GEM IDs are never reused within a service lifetime. Native identities
and request sequences are separately checked 32-bit values; exhaustion fails
before reuse, reserving the last sequence for exit.

Registration also publishes a caller-owned receive port and sixteen 32-byte
message records in the service's shared endpoint directory. This directory works
across separate C binding instances. Its lookup, publication holds and recycling
use short Task-side `Forbid` guards; interrupts do not access it. Exit withdraws
admission, waits for existing publishers without blocking the presenter, drains
the port and acknowledges retirement before the caller frees its storage.
HY1 prepares these endpoints; public messaging still uses the service FIFO until
the atomic HY3 migration in the [hybrid plan](../plans/gem4xe/hybrid-aes-implementation-plan.md).

`appl_write(id, 16, words)` copies eight words into the destination's FIFO.
Each registration has sixteen entries. Success means accepted; a full queue
returns zero with `AES_RESOURCE`, without replacing an older message or waiting
for space. Other lengths and invalid pointers fail with `AES_MALFORMED`;
unknown/retired IDs fail with `AES_IDENTITY`. The sender may reuse its buffer
after return. Borrowed pointer payloads and long messages are unsupported.

`evnt_mesag(words)` returns one after copying the oldest queued message, or
blocks the application through its private reply port until a message arrives.
Other applications and the presenter continue. Exit discards any queued messages.

`evnt_timer(lo, hi)` reconstructs an unsigned 32-bit millisecond duration and
returns one when its absolute VBI-clock deadline expires. Conversion uses the
reported 50/60 Hz rate, rounds upward and adds one tick to prevent early expiry.
Standalone zero delay therefore waits at least one tick. Overflow returns zero
with `AES_OVERFLOW`. This operation runs in the caller, without presenter RPC or
request-sequence advancement. The named wrapper and parameter-block opcode use
the same helper.

`evnt_multi` supports `MU_MESAG`, `MU_TIMER` and their combination. It returns
all selected conditions ready at one decision, consuming at most one message.
Zero-duration `MU_TIMER` is immediately ready and submits no alarm; use it with
`MU_MESAG` to drain the queue without blocking. Unsupported event bits or an
empty mask fail as a whole with `AES_UNSUPPORTED`. This profile returns zero
in the six mouse/keyboard output words; input-event reporting is future work.
Rectangle/button inputs have no effect when their event bits are absent.

A clock/device failure returns zero with `AES_TIMER_ERROR` for affected timed
waits, preserving queued messages. A failed timer binding does not automatically reopen or retry. The caller
can retire and reinitialize its registration to obtain a fresh binding. Message-only and native GUI service remain available.

`wind_update` arbitrates recursive update and mouse-control ownership between
registered AES clients. `BEG_UPDATE` acquires update ownership and its implicit
mouse hold together; `BEG_MCTRL` adds an explicit mouse hold. Matching END calls
remove only their corresponding hold. Wrong-owner release returns zero with
`AES_IDENTITY`; nesting overflow returns `AES_OVERFLOW` without changing either
hold. `0x100` on a BEGIN call tries without waiting, returning zero with `AES_OK`
if unavailable. A normal contended BEGIN waits in arrival order among eligible
callers; an existing mouse owner can upgrade without waiting behind a dependent
peer. Exit releases every owned hold. Message and timer service continue.

Update ownership also excludes native console painting/scrolling, widget
feedback, background repair and cache capture. Mouse ownership defers native
widget gestures, focus and geometry changes; an explicit mouse hold alone
allows console painting. Acquisition waits for already admitted drawing and
hardware/scene tokens to retire. Pending acquisitions stop new conflicting work,
so continuous output cannot starve an application lock. The service holds no
Layers token while an application owns a lock.

Input capture and the serialized cursor path continue. Sixteen copied pointer
records retain deferred gestures, coalescing adjacent motion; overflow reports
input loss and cancels the gesture after release. Keyboard widget events retain
the existing bounded queue. Unlock or owner exit resumes retained controls,
gestures and damage without another input edge. Blocked paint alone does not
keep the presenter runnable. Device completions and cancelled console writes
can retire while drawing is excluded.

`global[0]` is zero to avoid advertising a complete AES version, `[1]` is four,
`[2]` is the application's ID, `[10]` is four display planes, and other words
are zero. The binding exposes transport/resource errors through
`ExecAESDiagnostic()` without inventing successful GEM return values.

Registration retains the owner's Task lease and validates its original packet,
owner and reply-port relationship on subsequent calls. Requests and buffers
remain caller-owned storage, lent until the single reply is collected. This is
a cooperative shared-memory ownership contract, not memory protection against
malicious applications. Normal service shutdown refuses live registrations.

Each client lazily opens `timer.device` for standalone timer waits, with a
private reply port and two 38-byte records: a clock query and borrowed alarm.
It publishes outstanding ownership before `SendIO`, collects exactly its reply,
and closes the original open before freeing those records on exit. Up to four
client opens and the temporary presenter open fit within the device's eight-open
limit; competing users can still exhaust capacity. Setup failure releases every
acquired resource and leaves message-only calls usable.

During HY2, the presenter still owns combined waits. It opens `timer.device` on
`UNIT_VBLANK` once, with a private signal
port and two 38-byte records: the original clock query and a borrowed absolute
alarm. The transport collects or cancels/collects the alarm before reuse or
shutdown, then closes the original open. A setup failure releases its acquired
resources and leaves message service available. Per-client absolute deadlines
share that single alarm. Queued completion and cancellation replies retain their
wake path until collected; future timer I/O never blocks the presenter.
Readiness is reconsidered after admissions or terminal alarm replies. Unchanged
future waits do not reread the clock on unrelated GUI turns. Pointer capture and
cursor service run between AES admissions and after active event processing;
widget commits remain after native control admission. Existing GUI lock gates
still apply. These boundaries add no idle wake or periodic input poll.
Native and AES requests share at most four admissions per turn, alternating the
first endpoint on ordinary turns. When painting or a widget gesture can advance,
at most three native requests precede the existing paint quantum, then one AES
request is admitted after it. Both phases share the four-request limit; AES is
not deferred across an entire repaint. Timer completion and event matching run
outside that intake budget, including a boundary after console work so an
expiry during drawing need not wait for another presenter turn.
The presenter services captured input before controls when signalled and after
actual paint work. Widget model changes stay after native control admission.
Each turn gives GUI painting its existing bounded quantum before new console
output. Ready paint may continue without a voluntary Yield; VBI preemption
provides Task fairness, and blocked work retains the ordinary signal wait path.
When painting releases the scene with a native control already pending, one new
console-output quantum may be deferred to admit that control. An eligible output
quantum must run before another such deferral, preserving writer progress.

The generated [wire ABI](../../abi/aes-server.json) is private to this source
profile. Rebuild bindings and service together. Current implementation and
development evidence are tracked in the
[hybrid implementation plan](../plans/gem4xe/hybrid-aes-implementation-plan.md).
