# Verified-write deadline for MyDOS

[History index](README.md) · [Device I/O contract](../reference/device-io.md#siodevice) ·
[Filesystem write contract](../reference/filesystem-writes.md) ·
[Development evidence](../development/mydos-write-timeout.json)

The accurate-media MyDOS write timeout is fixed in sio.device. Generic 57600
verified WRITE (`$57`, direction WRITE) now defaults to a two-second active
deadline and admits explicit deadlines up to that limit. Ordinary Generic
reads, PUT and no-data operations retain one second. STOCK810 retains two
seconds; FASTEST125 and HAPPY1050 retain their existing limits.

## Cause and change

The [earlier COPY record](write-performance.md) captures a 16 KiB COPY failing
after all 256 payload bytes are transmitted. The driver timed out before the
drive's verified completion, offlined the bus and required reset. Both frozen
and updated MyDOS implementations exhibited it.

A smaller regression reproduces the transport failure independently of a
filesystem. It lets the motor stop for 200 PAL VBI ticks between writes to
sectors 720, 360 and 4. Before the change, WRITE 360 transmits its command,
256-byte payload and checksum, receives command/data ACKs, then expires at
1,002.4 ms without Complete. With the change it receives Complete at about
1,059.8 ms and the subsequent read verifies every persisted byte. The 128-byte
case also needs about 1,059.8 ms, so the allowance belongs to the mechanical
operation rather than only double-density sectors or MyDOS.

The pinned Generic drive model includes roughly half a second for motor startup,
5.3 ms per seek step, rotational positioning and another rotation for verified
WRITE. A fast serial link does not remove these mechanical delays.
[TimeoutLimit](../../lib/io/siodriver.act) selects the operation's default and
maximum in the driver. Explicit smaller values remain unchanged. The existing
round-up conversion produces 495 timer periods for two seconds; the absolute
clock still starts at COMMAND assertion and never restarts at ACK or payload.
Byte/phase timing, IRQ handling, retries, cancellation and reset policy are
unchanged. No filesystem-specific override or retry is added.

## Development coverage

Optimized native checks use the clean pinned compiler
`6510ea1d148c93edea595be8a5afa9630d5a75e3`, pinned AltirraOS816 ROM, PAL,
native 8× CPU and 4 MiB RAM. The separate host compiler build changes Cargo
optimization only. Evidence records source, emitted image, observer, emulator,
ROM and media identities. This is emulator development coverage, not release
or physical-drive qualification.

- Cold-motor 128/256-byte writes and read-back on accurately timed Generic
  media, exact whole-ATR comparison, cross-bank transfer guards, heap/ownership
  restoration and unchanged ordinary read deadline.
- Eight invalid timeout/operation combinations rejected before hardware;
  absent-drive default/explicit STOCK810 and Generic verified-write deadlines;
  Generic read default and an explicit 20,205 µs verified-write deadline.
  Expiry is within 36 µs after the rounded deadline, with no retained caller
  buffer or extra transaction. Unsafe timeouts still require reset.
- A damaged WRITE checksum receives ACK but never Complete in the pinned fault
  model: it times out with the two-second descriptor, offlines the bus and
  leaves media unchanged. A terminal device error after physical mutation
  remains an error; its request retires, the independent read still works and
  persisted bytes match the expected failure outcome.
- The real loadable COPY with a 16 KiB buffer copies a 49,159-byte binary to
  accurately timed 256-byte MyDOS. Every submitted write has verified completion;
  independent byte and whole-volume allocation audits preserve the unrelated
  KEEP.BIN file. It completes in 188.94 guest seconds with 201 reads and 353
  verified writes, measured from source Open through destination Close.
  Native guards, ownership and OS restoration pass.

All 396 host tests and generated I/O-definition checks pass. The rounding
algorithm and public request layout are unchanged; no raw
matrix or full release matrix is run.

## Memory

Fixed and per-Task bank-zero reservation changes are **zero**, including guards,
alignment and unused capacity. No buffers, workers or upper-RAM allocations
are added. Optimized SIODRIVER code grows by 240 bytes: TimeoutLimit emits 157,
Prepare grows by 100 and SIOValidate shrinks by 17. Prepare's fixed frame grows
18→22 bytes and local invocation peak 28→32; SIOValidate grows 12→14 and
24→26, respectively. DeadlineTicks remains 361 code bytes with a 32-byte frame
and local peak. These local peaks are not whole-call-chain bounds; native stack
checks pass within the existing reservations.

The larger deadline is an upper bound, not a delay added to successful writes.
It permits mechanically valid completion after one second while preserving
bounded failure. Final release qualification must include the selected media,
transport and packaged images together.
