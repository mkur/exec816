# SIO client library

[Reference index](README.md) · [Device I/O](device-io.md#siodevice) ·
[Program loading](program-loading.md)

`SIO` is an ordinary caller-context library for native and loadable Action!
programs. Its three imports use the existing public Exec request/reply operations;
they add no kernel selector, worker or driver queue. Byte layouts and signatures
come from [sio-client.json](../../abi/sio-client.json).

| Call | Result and ownership |
| --- | --- |
| `Open(unit, flags, session)` | Signed INT error; zero establishes the caller-owned session. Allocates a reply port/request and opens sio.device. Failure releases partial acquisitions. |
| `Transfer(session, transaction)` | Signed INT device error; copies the actual byte count and collects the exact reply before returning. |
| `Close(session)` | Releases an idle session's binding, request and port. It does not stop the shared SIO driver. |

`SIO.Session` is eight opaque caller-owned bytes. Retain it on the creating Task,
use it only after successful Open, and Close after all transfers return. Open
initializes fresh storage; do not reopen a live session. Requests and ports stay
internal. Correct live storage and ownership are caller responsibilities.

`SIO.Transaction` is 24 bytes: command/AUX1/AUX2/direction at offsets 0–3,
profile at 4, options at 6, timeout at 8, length at 12, far data pointer at 16,
padding at 19, and returned actual at 20. Timeout/length/actual are LONGCARD;
profile/options are CARD. Keep the data buffer live through Transfer. The driver
validates wire shape, profile and timeout once.

Options zero observes the caller's current DOS foreground BREAK before submission,
returning `IOERR_ABORTED` without I/O when already interrupted. A submitted frame
is always collected, including after BREAK. The command can then stop between
frames. `SIO.COMMITTED` skips the pre-submission interruption check for an operation
that must complete its next frame. The helper does not consume BREAK, reset an
active exchange, retry or change baud. A Task without a foreground scope waits
only for completion. `SIO.ERROR_NO_MEMORY` (10) denotes local allocation failure;
other errors retain their signed device representation.

Example acquisition and transfer:

```action
USE SIO
SIO.Session session
SIO.Transaction packet
BYTE ARRAY status(4)

; After Open returns zero, fill the transaction and retain status until return.
packet.command=$53
packet.direction=SIO.SIODIR_READ
packet.profile=SIO.SIO_PROFILE_STANDARD19200
packet.options=0
packet.timeout=0
packet.length=4
packet.data=status
```

SIO-enabled builds publish the current native program imports. SIO-disabled builds
retain the library interface and return Open failure without touching serial
hardware. The native program ABI is version 18; rebuild commands and providers
together. The C program ABI remains version 17 because its existing interfaces
are unchanged; a C SIO convenience library is not part of this interface.
