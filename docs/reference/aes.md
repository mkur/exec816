# AES application service

[Reference](README.md)

The optional AES endpoint runs in the existing desktop presenter. It uses
ordinary Exec messages; it adds no Task or kernel gateway. The native desktop
and retained Control Panel remain independent clients of their existing service.

The current source profile in [gem.h](../../c/include/gem.h) implements
`appl_init`, `appl_exit`, `appl_write`, `evnt_mesag`, `evnt_timer`,
`evnt_multi`, `evnt_multi_moblk` and the corresponding `aes_call(AESPB *)`
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
with `AES_OVERFLOW`.

`evnt_multi` supports `MU_MESAG`, `MU_TIMER` and their combination. It returns
all selected conditions ready at one decision, consuming at most one message.
Zero-duration `MU_TIMER` is immediately ready and submits no alarm; use it with
`MU_MESAG` to drain the queue without blocking. Unsupported event bits or an
empty mask fail as a whole with `AES_UNSUPPORTED`. This profile returns zero
in the six mouse/keyboard output words; input-event reporting is future work.
Rectangle/button inputs have no effect when their event bits are absent.

A clock/device failure returns zero with `AES_TIMER_ERROR` for affected timed
waits, preserving queued messages. The service does not automatically reopen
or retry a failed timer. Message-only and native GUI service remain available.

`global[0]` is zero to avoid advertising a complete AES version, `[1]` is four,
`[2]` is the application's ID, `[10]` is four display planes, and other words
are zero. The binding exposes transport/resource errors through
`ExecAESDiagnostic()` without inventing successful GEM return values.

Registration retains the owner's Task lease and validates its original packet,
owner and reply-port relationship on subsequent calls. Requests and buffers
remain caller-owned storage, lent until the single reply is collected. This is
a cooperative shared-memory ownership contract, not memory protection against
malicious applications. Normal service shutdown refuses live registrations.

The presenter opens `timer.device` on `UNIT_VBLANK` once, with a private signal
port and two 38-byte records: the original clock query and a borrowed absolute
alarm. The transport collects or cancels/collects the alarm before reuse or
shutdown, then closes the original open. A setup failure releases its acquired
resources and leaves message service available. Per-client absolute deadlines
share that single alarm. Queued completion and cancellation replies retain their
wake path until collected; future timer I/O never blocks the presenter.

The generated [wire ABI](../../abi/aes-server.json) is private to this source
profile. Rebuild bindings and service together. Current implementation and
development evidence are tracked in the
[implementation plan](../plans/gem4xe/aes-server-implementation-plan.md).
