# Native input ownership and events

[Reference index](README.md) · [Signals and producers](signals.md) ·
[Console](console.md) · [Keyboard evidence](../history/gem-input.md) ·
[Mouse evidence](../history/gem-mouse.md)

`INPUT` provides reusable, exclusive keyboard and ST/port 1 pointer sources.
The console and interactive GEM application use the same implementation. It owns hardware capture
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
extent. The C bridge checks bank zero, odd addresses, bank crossings and values
beyond 24 bits before narrowing full huge pointers. Acquire/Release audit memory
membership and identity; production ordinary calls trust valid storage and a live
registration. Absent/read-only output memory is rejected by diagnostic audits,
not promised safe rejection in production. Heap storage and its complete lifetime
remain the caller's obligation in Exec's shared address space.

| Record | Bytes | Contents |
| --- | ---: | --- |
| InputLease | 32 | Task lease, acquisition generation, published route, wake mask, state and reserved fields. Zero before Acquire; otherwise opaque and address-stable. |
| InputConfig | 32 | Version, source, wake mask, keyboard filters/flags, pointer protocol/port, initial position, inclusive bounds and zero reserved fields. |
| InputEvent | 24 | Acquisition and route u32; tick u16; kind/flags u8; code/qualifiers u16; x/y i16; buttons/motionInfo u16. |

The current INPUT version is 3. Rebuild callers with the generated bindings;
version-2 configurations are not accepted. `motionInfo` is zero for keyboard
and absolute-pointer events.

`SOURCE_KEYBOARD=2` and `SOURCE_POINTER=3` admit independent consumers. The
pointer backend decodes an ST mouse on joystick port 1, including its left
button. Supply a
nonzero wake mask whose bits are already allocated to the current Task. Acquire
copies configuration, retains the consumer and its signal binding, and activates
capture only after admission succeeds. It starts with route zero, which discards
unaddressed input. An existing consumer returns BUSY without changing ownership.
Lease states are FREE, ACQUIRING, ACTIVE and RELEASING. Do not copy, move or alter
a live lease. A retained Task reference does not retain arbitrary lease storage.
An old pointer to reused storage cannot independently prove its old acquisition.

Keyboard configuration permits zero to two filters. Each active mask is nonzero, with no
value bits outside that mask; unused pairs and reserved fields are zero. The
only flag is `CAPTURE_BREAK=1`. A matching raw scan becomes durable cancellation,
without an additional ordinary KEY. GEM selects Escape `$1C/$3F` plus BREAK;
console selects Ctrl-C `$92/$BF` plus BREAK. IRQ work matches raw codes and latches
routes; it never translates characters or invokes application callbacks.

Keyboard configurations require bytes 16–31 to be zero. Pointer configurations
require the keyboard filter fields and reserved word to be zero, `pointerProtocol=POINTER_ST=1`
at offset 16 and `pointerPort=1` at 18. Signed 16-bit `initialX`, `initialY`,
`maxX`, `maxY` occupy offsets 20, 22, 24 and 26. Bounds are inclusive, start at
zero, and must contain the initial position; negative values are malformed.
The reserved u32 at offset 28 is zero for both sources. Unknown source, protocol
or port returns UNSUPPORTED; malformed fields/version return BAD_ARGUMENT before
hardware changes.

Pointer `flags=POINTER_RELATIVE` selects timed relative delivery; otherwise flags
are zero. Relative configurations require all four coordinate/bound fields to
be zero. Bounds and screen policy then belong to the consumer. The flag is not
valid for keyboard acquisitions. Timed motion currently has development coverage
on the pinned PAL configuration; NTSC acceleration is not covered.

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
| `Discard(lease, tag)` | Keyboard: discard ordinary records and loss, preserving cancellation. Pointer: establish a durable RAW loss boundary that invalidates earlier samples and pending button output for this route. Later arrivals survive. |
| `Pending(lease, outMask)` | Observe DATA=1, LOSS=2 and CANCEL=4. This does not authorize clearing a wake or consuming work. |
| `Take(lease, event)` | Copy and acknowledge one event: cancellation first, then loss, then ordinary input. EMPTY leaves the output unchanged. |
| `Release(lease)` | Stop capture, purge routes/records, retire producer wakes and release ownership. Only success permits reuse of the lease, signal or storage. |

Status values are OK=0, EMPTY=1, BUSY=2, BAD_ARGUMENT=3, INVALID_OWNER=4,
EXHAUSTED=5, UNSUPPORTED=6 and NO_MEMORY=7. Failed admission unwinds its partial
ownership. Existing leases are located by their address in fixed source
descriptors once per operation. Acquisition uses one monotonic
32-bit allocator shared by all sources; each source retains its own generation,
capture state, route slots and notices. Routes use
`(epoch << 4) | slot` with a 28-bit epoch. Both refuse exhaustion before wrap.
Release purges the old acquisition before its storage can serve another consumer.

Take, Pending and route operations require the original live lease and valid
output storage. Take is
restricted to the acquiring Task; Pending may be explicitly shared. The owner
must stop shared callers and settle outstanding use before Release. Output
storage may change on every call, is never retained, and must not overlap the
lease or subsystem state. Misuse is not a supported production rejection probe.
A null or unregistered lease is rejected by the fixed source lookup; this does
not make arbitrary freed/corrupted pointers safe.

Build with `--input-diagnostics` in `tools/native_program.py` or the relevant
input test harness to include full ordinary-use audits. It defaults off and is
recorded as `input_diagnostics` in build provenance. Production omission happens
before raw/optimized compilation; both settings share the same queue algorithm.
Dynamic route validity, retained references, queue bounds and deferred-event
identities remain checked in production. Full memory and immutable identity
audits occur once in native Acquire/Release, including calls through C.
Acquire/Release and core Exec retention checks remain enabled in both settings.

## Capture, loss and cancellation

The keyboard ring has 64 eight-byte raw records: scan byte, kind, capture tick
and route. A full ring drops the new ordinary record and latches explicit loss.
Sixteen route mailboxes retain cancellation and loss independently of ring space.
Take acknowledges one mailbox atomically; a later arrival remains pending.
The full acquisition identity is attached when Take creates the 24-byte event.
Release's purge boundary makes that safe across reacquisition.

| Kind | Code and fields |
| --- | --- |
| KEY=1 | Raw scan byte in code, SHIFT=1 and CONTROL=2 in qualifiers; capture tick is valid. Translation and Caps state belong to the consumer. |
| POINTER=2 | Code zero; bounded x/y position and button state before any simultaneous button edge. |
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

Keyboard capture services serial IRQ work first, shares SKCTL through the platform
ownership protocol and restores the prior keyboard vectors/masks on release.
IRQ/NMI never traverse console instance records or arbitrary application data.
The console maps generic tags to its focus/foreground records in Task context.

## ST mouse capture

Timer 1 samples PORTA's low nibble and TRIG0 through the shared platform timer.
Normal capture is about 3,958.6 Hz on the pinned PAL machine (AUDF1 = 15).
Short SIO COMMAND and write-turnaround phases use AUDF1 = 7 for their fine
alarms, with pointer capture on alternate edges. Ordinary disk data transfer
returns to the normal rate. Rate changes and the existing SIO transaction-start
reset can perturb individual gaps; the supported envelope still requires every
measured gap below 1 ms. See the [timing protocol](platform.md#native-sio-ownership)
and [current measurements](../history/mouse-performance.md).
It does not program PIA direction, POTGO, trigger latching or SKCTL. Native and
ROM emulation interrupt paths use the same decoder; keyboard and SIO ownership
remain independent. Route zero continues tracking electrical phase and counters
without addressed output. A newly published route receives a position baseline;
consumers require a released-button observation before arming gestures.

The fixed capture reservation contains 64 private 28-byte samples and sixteen
24-byte durable route notices. In absolute mode one legal phase transition means
one coordinate unit, without acceleration, and Task code clips to configured
inclusive bounds. Unchanged samples produce no event. Adjacent motion coalesces
only within the same acquisition, route, epoch, button state, exact step vector
and interval class, up to 64 transitions per record.
Coalescing preserves the earliest outstanding tick. Button changes are barriers.
Movement and a simultaneous button edge expand to POINTER with the previous
buttons, followed by a retained BUTTON with the new state. Pending includes that
retained output, and retirement, Discard, loss and Release account for it.

Relative POINTER/BUTTON events set `RELATIVE` alongside `TICK_VALID`; `x/y` are
unclipped signed transition counts. The low five `motionInfo` bits contain an
interval class; `MOTION_DIAGONAL` marks simultaneous two-axis motion. Classes
0–15 use the inclusive upper age bounds in
[input-native.json](../../abi/input-native.json), measured in two-scanline PAL
quanta. `MOTION_RESET=16` marks unknown/zero duration, a saturated pause, baseline
or reversal. A retained BUTTON carries zero delta and zero metadata, so its
preceding movement is applied once. LOSS has no timing/relative flags or motion
metadata. Baselines carry zero delta and reset metadata.

Capture maintains saturating motion age from `VCOUNT` differences at existing
samples. It handles beam wrap under the established sub-millisecond capture-gap
contract, with a cheap idle path once age reaches 255 quanta. An entire missed
frame cannot be inferred from beam phase alone. Producer timing/direction history
survives ring draining; partial reads do not change later timing classes. The
public VBI tick remains separate. Capture selects no GUI gain and never waits
for a run to fill. Relative consumers apply their own transform before coalescing
events with different classes. See the [desktop acceleration design](../plans/gem4xe/mouse-acceleration-design.md).

Opposite quadrature phases and signed counter overflow produce HARDWARE loss;
a full raw ring produces RAW loss. A per-route notice epoch prevents older
samples or pending output from restoring a gesture after its loss. Loss retains
the first unacknowledged cause and the latest counter baseline. Epoch exhaustion
disables addressed capture until reacquisition, with durable loss and no wrapping
identity. Three or four transitions hidden between samples can alias legal or
unchanged phase values and cannot be detected from PORTA alone. M5 checks phases
spaced at least 1 ms apart, with a maximum sample gap below 276 µs in the selected
workloads. The existing controller's fastest qualifying quantization is
16 scanlines, about 972 transitions/second/axis; exactly 1 kHz was not directly
generated. Arbitrary host bursts are not guaranteed.

| Shared fields | Writers and serialization |
| --- | --- |
| Phase, button level, cumulative counters, epoch, disabled/baseline flags | Timer IRQ; claim, publication and Discard transactions save/set I. |
| Ring head, last motion counts, interval age and direction history | Timer IRQ. Take copies a complete sample and advances tail under saved I; no masked ring walk. |
| Route, acquisition and binding activation | Admitted Task/kernel publication under Forbid or SWITCHING plus saved I. IRQ reads fixed resident storage. |
| Notice payloads and loss mask | IRQ or Discard under saved I; Take copies and acknowledges one notice atomically. Notice identity/epoch remain after acknowledgement. |
| Coordinates, consumed counters/route/epoch and retained BUTTON | Consumer Task under Forbid. Pending is published last; native Take checks it against the retained notice epoch before copying. |

Task operations hold Forbid; short native copies/publication transactions save
and set I. The IRQ adapter preserves the full native context. Nested NMI retains
the interrupted I state, and IRQ_DEPTH/Forbid prevent a switch during the shared
transaction. IRQ capture never traverses application storage or allocates.

## Interactive subset and limits

The [GEM application](../../ports/gem4xe/interactive/README.md) adds its own
32-record normalized queue. Adjacent motion may coalesce only with identical
acquisition, route and button state. Overflow latches LOSS separately, drops the
incomplete sequence and requires a fresh released-button state before rearming.
A press arms one enabled control; matching release over it activates once.
Loss, cancellation or release elsewhere disarms it. Diagnostic pointer producers
copy validated records and stop before application storage retires; production
ships without those producers or injection entry points.

The GEM scene now acquires keyboard and ST/port 1 leases independently. It
validates the full mouse acquisition/route and current session before forwarding
records into its private queue. Each turn drains up to eight records from each
source. Mouse admission failure leaves keyboard controls usable and displays
`KeysOnly`; teardown retires the mouse association before releasing its lease
and signal. [M4 evidence](../development/gem-mouse-m4.json) covers physical clicks,
held-button close and partial admission rollback. [M5 evidence](../development/gem-mouse-m5.json) records a maximum sampling gap
of 275.946 µs in selected GUI/FASTEST125 tests, seven PAL ticks for cursor
updates and ten for small keyboard redraws. Legal phases must be at least
1 ms apart and button levels at least 10 ms long; faster bursts can alias.
Amiga/right-button protocols, AES events, timed waits
and arbitrary registered ISR callbacks are unsupported. [I6 evidence](../development/gem-input-i6.json)
measures native keyboard-to-visible-update maxima of 12 raw / 11 optimized PAL
ticks for the recorded small-redraw workload during physical SIO, including wrap
controls. This is focused development evidence on the pinned emulator, not a
general latency guarantee or hosted-system qualification.

Keyboard capture uses 560 bytes and a 144-byte descriptor. Pointer capture
reserves 2,560 bytes including two 16-byte guards and 224 bytes of unused
capacity, plus a 144-byte descriptor. The shared acquisition allocator uses four
bytes. All are inside the existing 64 KiB upper Task arena. No additional input
Task or reserved bank-zero memory is
introduced: fixed, each public Task and private-idle deltas are zero, counting
guards, alignment and unused reserved capacity.

The [registration/lifetime implementation record](../history/input-registration-lifetime.md)
describes development checks and measured costs of the current ordinary-call
contract. It does not establish a general latency guarantee.
