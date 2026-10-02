# Native input ownership and events

[Reference index](README.md) · [Signals and producers](signals.md) ·
[Console](console.md) · [Implementation evidence](../history/gem-input.md)

`INPUT` is the reusable, exclusive keyboard-capture library. The console and the
interactive GEM application use the same implementation. It owns hardware capture
and route identities; consumers own text translation, focus and interaction.
It adds no Task, private kernel service or COP signature. The public C surface is
[exec/input.h](../../c/include/exec/input.h); exact generated records and constants
come from [input.json](../../abi/input.json). Configuration version is 2; rebuild
callers when updating from version 1.
Standalone C images bind the eight-entry native table through
[input-bridge.inc](../../c/calypsi/input-bridge.inc) before admitting C callers,
as shown by the [interactive launcher](../../tests/programs/gem_interactive_launcher.act).
This is an ordinary library bridge, not a dynamically discovered input service.

## Records and admission

Records use little-endian fields and two-byte alignment. Each record, including
configuration and output scalars, must fit within one writable upper-RAM CPU-bank
extent. Bank zero, odd addresses, bank crossings, absent/read-only memory and
values beyond 24 bits fail before narrowing. The C bridge validates full huge
pointers. Heap storage and its complete lifetime remain the caller's obligation
in Exec's shared address space.

| Record | Bytes | Contents |
| --- | ---: | --- |
| InputLease | 32 | Task lease, acquisition generation, published route, wake mask, state and reserved fields. Zero before Acquire; otherwise opaque and address-stable. |
| InputConfig | 32 | Version, source, wake mask, keyboard filters/flags, pointer protocol/port, initial position, inclusive bounds and zero reserved fields. |
| InputEvent | 24 | Acquisition and route u32; tick u16; kind/flags u8; code/qualifiers u16; x/y i16; buttons/reserved u16. |

Only `SOURCE_KEYBOARD=2` is admitted at the M2 boundary. `SOURCE_POINTER=3`
configuration is validated, but Acquire returns UNSUPPORTED until its capture
backend is installed. Supply a
nonzero wake mask whose bits are already allocated to the current Task. Acquire
copies configuration, retains the consumer and its signal binding, and activates
capture only after admission succeeds. It starts with route zero, which discards
unaddressed input. An existing consumer returns BUSY without changing ownership.
Lease states are FREE, ACQUIRING, ACTIVE and RELEASING. Do not copy, move or alter
a live lease; a copied record or stale acquisition fails identity validation.

Configuration permits zero to two filters. Each active mask is nonzero, with no
value bits outside that mask; unused pairs and reserved fields are zero. The
only flag is `CAPTURE_BREAK=1`. A matching raw scan becomes durable cancellation,
without an additional ordinary KEY. GEM selects Escape `$1C/$3F` plus BREAK;
console selects Ctrl-C `$92/$BF` plus BREAK. IRQ work matches raw codes and latches
routes; it never translates characters or invokes application callbacks.

Keyboard configurations require bytes 16–31 to be zero. Pointer configurations
require the keyboard fields at 8–15 to be zero, `pointerProtocol=POINTER_ST=1`
at offset 16 and `pointerPort=1` at 18. Signed 16-bit `initialX`, `initialY`,
`maxX`, `maxY` occupy offsets 20, 22, 24 and 26. Bounds are inclusive, start at
zero, and must contain the initial position; negative values are malformed.
The reserved u32 at offset 28 is zero for both sources. Unknown source, protocol
or port returns UNSUPPORTED; malformed fields/version return BAD_ARGUMENT before
hardware changes.

## Calls and ownership

The Action! operation names below have `Input`-prefixed C equivalents. All execute
in ordinary native Task context. Acquire, Take and Release belong to the consumer.
Other calls may execute in another Task through the same retained, address-stable
lease. This explicit shared authority supports console focus/foreground policy;
it does not transfer consumption rights. Bounded Forbid sections and native
publication guards serialize state with Task switching, IRQ and NMI.

| Call | Contract |
| --- | --- |
| `Acquire(lease, config)` | Admit one consumer without waiting for another owner. Copy configuration and retain ownership before enabling capture. |
| `CreateRoute(lease, flags, outTag)` | Reserve one of sixteen route slots; flags must be zero. Return a nonzero, nonrepeating tag. |
| `PublishRoute(lease, tag)` | Select an admitted route, or zero to stop addressed capture. Queued records retain their captured identities. |
| `RetireRoute(lease, tag)` | Release an unpublished route only after queued records and notices no longer refer to it; otherwise BUSY. |
| `Discard(lease, tag)` | Discard ordinary captured records and loss for the route, preserving cancellation. Arrivals after the clear boundary survive. |
| `Pending(lease, outMask)` | Observe DATA=1, LOSS=2 and CANCEL=4. This does not authorize clearing a wake or consuming work. |
| `Take(lease, event)` | Copy and acknowledge one event: cancellation first, then loss, then ordinary input. EMPTY leaves the output unchanged. |
| `Release(lease)` | Stop capture, purge routes/records, retire producer wakes and release ownership. Only success permits reuse of the lease, signal or storage. |

Status values are OK=0, EMPTY=1, BUSY=2, BAD_ARGUMENT=3, INVALID_OWNER=4,
EXHAUSTED=5, UNSUPPORTED=6 and NO_MEMORY=7. Failed admission unwinds its partial
ownership. Existing leases are located by their address in fixed source
descriptors before complete identity validation. Acquisition uses one monotonic
32-bit allocator shared by all sources; each source retains its own generation,
capture state, route slots and notices. Routes use
`(epoch << 4) | slot` with a 28-bit epoch. Both refuse exhaustion before wrap.
Release purges the old acquisition before its storage can serve another consumer.

## Capture, loss and cancellation

The resident ring has 64 eight-byte raw records: scan byte, kind, capture tick
and route. A full ring drops the new ordinary record and latches explicit loss.
Sixteen route mailboxes retain cancellation and loss independently of ring space.
Take acknowledges one mailbox atomically; a later arrival remains pending.
The full acquisition identity is attached when Take creates the 24-byte event.
Release's purge boundary makes that safe across reacquisition.

| Kind | Code and fields |
| --- | --- |
| KEY=1 | Raw scan byte in code, SHIFT=1 and CONTROL=2 in qualifiers; capture tick is valid. Translation and Caps state belong to the consumer. |
| POINTER=2 | Code zero; x/y position and resulting buttons. Reserved for normalized backends; native keyboard Take does not produce it. |
| BUTTON=3 | Changed-button mask in code, resulting state in buttons. Initially LEFT=1 is the only defined button. |
| LOSS=4 | RAW=1, NORMALIZED=2 or HARDWARE=3 in code. Consumers abandon incomplete gestures. |
| CANCEL=5 | BREAK=1 or KEY_FILTER=2 in code. Delivery survives ordinary queue overflow and Discard. |

Flags are TICK_VALID=1 and INJECTED=2. Unused fields and unknown bits are zero.
Durable mailboxes do not invent a capture time: their timestamp is zero and
TICK_VALID is clear. Timestamps use Exec ticks, not milliseconds. Compute unsigned
16-bit elapsed intervals below half the range; do not use injected timestamps
as evidence of physical keyboard latency.

Signals are notifications, not queue contents. After a bounded drain, keep the
consumer runnable while Pending reports work; otherwise remaining records could
be stranded after their wake bit was consumed. Wait only after observing every
work source, without clearing notifications across that observation boundary.

Native capture services serial IRQ work first, shares SKCTL through the platform
ownership protocol and restores the prior keyboard vectors/masks on release.
IRQ/NMI never traverse console instance records or arbitrary application data.
The console maps generic tags to its focus/foreground records in Task context.

## Interactive subset and limits

The [GEM application](../../ports/gem4xe/interactive/README.md) adds its own
32-record normalized queue. Adjacent motion may coalesce only with identical
acquisition, route and button state. Overflow latches LOSS separately, drops the
incomplete sequence and requires a fresh released-button state before rearming.
A press arms one enabled control; matching release over it activates once.
Loss, cancellation or release elsewhere disarms it. Diagnostic pointer producers
copy validated records and stop before application storage retires; production
ships without those producers or injection entry points.

Physical mouse hardware, donor POKEY timer sampling, AES events, timed waits and
arbitrary registered ISR callbacks are unsupported. [I6 evidence](../development/gem-input-i6.json)
measures native keyboard-to-visible-update maxima of 12 raw / 11 optimized PAL
ticks for the recorded small-redraw workload during physical SIO, including wrap
controls. This is focused development evidence on the pinned emulator, not a
general latency guarantee or hosted-system qualification.

Capture reuses its existing 560-byte reservation plus 128 bytes of existing
upper Task-arena slack. No additional input Task or reserved bank-zero memory is
introduced: fixed, each public Task and private-idle deltas are zero, counting
guards, alignment and unused reserved capacity.
