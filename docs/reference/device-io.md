# Device I/O and SIO

[Reference index](README.md) · [Resident driver contract](resident-drivers.md)

Exec exposes the familiar request/reply device model through `EXEC`. Public calls
run in ordinary Task context with IRQs enabled. Blocking continuations run on the
caller's stack; they do not retain a kernel activation while waiting.

The resident [timer.device](timer.md) supports VBI delays and wide monotonic
deadlines without a worker Task. C declarations are in `<exec/io.h>` and
`<proto/exec.h>`; the Calypsi launcher binds the ordinary caller-context I/O path.

## Public calls

| Call | Contract |
| --- | --- |
| `CreateIORequest(port, size)` | Allocate a request with a valid reply port; return NULL on failure. Size is 16–65,535 bytes, but device operations require their full record. |
| `DeleteIORequest(request)` | Free a created, idle request. NULL is harmless; there is no implicit abort or close. |
| `OpenDevice(name, unit, request, flags)` | Bind a resident device/unit; return zero on success. |
| `CloseDevice(request)` | Release one successful open after collecting every request that borrows its binding. |
| `BeginIO(request)` | Dispatch with io_Flags unchanged. |
| `SendIO(request)` | Set all io_Flags to zero and dispatch for reply completion. |
| `DoIO(request)` | Set exactly IOF_QUICK, dispatch and collect if queued; return the error. |
| `CheckIO(request)` | Return NULL while pending, otherwise the same pointer. Do not collect. |
| `WaitIO(request)` | Wait for and collect this particular request, returning its error. |
| `AbortIO(request)` | Request cancellation; completion must still be collected. |

Exact records, constants and selectors are in [io.json](../../abi/io.json) and
[exec-io-types.inc](../../lib/exec/exec-io-types.inc). `io_Error` stores a signed
byte; DoIO/WaitIO return its sign-extended INT value. Generic errors are negative;
SIO-specific errors use positive codes. Names are NUL-terminated bytes.

WaitIO and DoIO require the caller's live PA_SIGNAL reply port. Nonblocking
submission can use another Task's agreed port or PA_IGNORE, with an explicit
collection protocol. OpenDevice validates the full request extent, unit and
flags; mere Message-sized allocation does not make a device request valid.

Established requests are trusted caller-owned objects. The caller supplies
valid storage, retains its open binding and reply port, and observes the
submission/collection rules. Ordinary I/O does not repeat request-extent,
reply-port-owner or live-handle checks through the kernel and resident layers.
Invalid, stale or wrongly owned requests are API misuse with unspecified
behavior; a clean rejection is not promised. The system provides no memory
protection between applications.

Creation/open admission and normal device errors remain: allocation failure,
unsupported commands or options, command-specific lengths, queue exhaustion
and hardware failure. Native Task/context and stack guards remain, as do the
port transactions and driver synchronization that implement completion.

## Completion and lifetime

A quick completion is allowed only when IOF_QUICK was supplied. It completes
inline and sends no reply. Deferred work clears IOF_QUICK. Every non-quick request,
including an immediate error, completes with exactly one reply.

Keep the descriptor, data buffer, reply port and device binding alive until
collection. Publication can allow another Task to run before SendIO returns;
do not treat return from submission as ownership returning to the sender.
WaitIO collects only the requested reply and leaves unrelated messages alone.
A client may collect through GetMsg instead, but must not collect the same
completion twice. CheckIO is observational, not a dequeue.

Exact reply collection and queue access share the IRQ-protected native port
transactions. CheckIO observes the byte-wide completion type; terminal fields
are written before publication. Drivers may complete through the admitted
[native ReplyMsg binding](ports.md#native-interrupt-reply), while public
Action!/C device calls remain Task-only.

AbortIO does not wait for safe retirement. Cancellation can race with normal
completion. Wait/collect afterwards before reusing buffers or closing the binding.
Extra requests may borrow a successfully opened binding while its owner remains
open; copying that binding does not acquire another OpenDevice reference.

## sio.device

Open `sio.device` with wire device ID `$31`–`$38` as the unit and flags zero.
Use the extended record in [sio.json](../../abi/sio.json). `SIOCMD_TRANSACTION`
selects a wire transaction; its separate `sio_Command` contains the peripheral
command, for example `$52` for READ. io_Data/io_Length describe the transfer;
io_Offset must be zero.

| Profile | Supported transaction size |
| --- | --- |
| FASTEST125 | Up to 128 bytes, plus exactly 256 for READ ($52) or verified WRITE ($57). |
| GENERIC57600 | Up to 128 bytes, plus exactly 256 for READ ($52) or verified WRITE ($57). |
| STOCK810 | Up to 128 bytes. |
| HAPPY1050 | Restricted no-data transactions. |

These are explicit peripheral/timing profiles, not automatic baud negotiation.
Profile selection also bounds timeout and command forms. Disk geometry and the
peripheral must agree; see the [block adapter](block-io.md). A nominal speed is
not qualification for every emulator or physical drive.

One SIO worker owns bus transactions; native IRQ code moves time-sensitive bytes.
Task-side callbacks use the [resident driver boundary](resident-drivers.md), with
short protected ownership updates and public Exec calls. The platform's IRQ/NMI
protocol covers descriptor publication and retirement. There is no public dynamic
device loader, ROM fallback or transparent retry layer. An uncertain timeout can
leave the bus offline until reset; cached data cannot bypass that state.

See [filesystem execution](../architecture/filesystems.md), the
[platform SIO boundary](platform.md#native-sio-ownership) and
[historical I/O design](../history/device-io-sio-design.md) for the implementation
rationale and revision-specific timing evidence.

The interrupt-reply integration is development-tested under the default nominal
57.6k profile. The loaded 125k refill timing gate remains open (including a
port-only regression); see the [measured envelope](../history/interrupt-reply.md).
Do not infer high-speed acceptance from functional transfer success.
