# IDE Plus 2.0 block driver implementation plan

Status: implementation in progress. IP0–IP4 are implemented;
IP5–IP6 remain pending. See the [development record](../history/ideplus-block-driver.md).

Follow the [contributor instructions](../../AGENTS.md),
[platform contract](../reference/platform.md),
[resident driver boundary](../reference/resident-drivers.md) and
[development testing policy](../contributing/testing.md).
Implement and commit one executable slice at a time, recording validation and
memory costs before continuing.

## Outcome and limits

Add a resident `ideplus.device` that accesses IDE Plus through native ATA PIO.
Mount supported APT partitions alongside existing SIO disks and RAM:. MyDOS and
SpartaDOS continue using the shared filesystem block adapter; their allocation,
write ordering and namespace policies remain filesystem responsibilities.

Deliver read-only access first, then explicitly enabled, verified writes. Use
the classic Amiga Exec device model: driver-owned requests, queue, worker,
cancellation and lifecycle, coordinated through public Task, port, signal and
I/O facilities. No IDE-specific kernel service is needed.

The initial target is one IDE Plus 2.0 revision E controller at configured PBI
ID 0, one ATA master with 512-byte physical sectors and LBA28 addressing, under
the pinned AltirraOS 65816 platform. The installed BIOS 2.1 is the starting
firmware fixture, not a runtime API dependency. Pin its exact bytes and the
emulator/device configuration before making executable claims.

Initially support the normal fifteen APT drive mapping slots, DOS partitions,
and 128/256-byte filesystem sectors within the existing 65,535-sector limit.
Keep the current mount-slot capacity. Other controller revisions, ATA slaves,
LBA48, 512-byte filesystem sectors, hot removal, partition editing, floppy
drawers, BIOS drive swapping and runtime firmware calls are outside this plan.
IDE-backed SYS: and changes to the OF816/boot-drive selection contract are a
separate follow-up. Existing demos keep their SIO system and work disks.

## Existing coupling to remove

The [block adapter](../reference/block-io.md) is currently bound to SIO:

- [BLOCKTYPES](../../lib/io/blocktypes.act) stores `IOSIOReq` pointers.
- [BLOCKIO](../../lib/io/blockio.act) opens `sio.device`, validates SIO units and
  profiles, and prepares READ `$52` / verified WRITE `$57` requests.
- [BLOCKWIRE](../../lib/io/blockwire.act) calls the SIO conditional cancellation
  helper while collecting replies.
- [FSINIT](../../lib/fs/fsinit.act) and the
  [mount generator](../../tools/generate_dos_mounts.py) assume physical mounts
  identify SIO units; duplicate checks do not include a transport identity.

Introduce a small internal transport dispatcher for SIO and IDE Plus. Keep one
filesystem worker, one reusable transfer request and its 256-byte buffer/cache.
Each volume still owns its device-open request. Do not add another generic
block worker, a dynamic driver framework or a second filesystem cache.

## Selected interface and ownership

### Device requests and units

Use the existing `IOStdReq` prefix and generated resident dispatch in
[io.json](../../abi/io.json). Define device command numbers, geometry layout,
flags and hardware constants in machine-readable inputs with generated Action!
and assembly definitions. Do not overload standard byte-offset READ/WRITE
semantics with sector numbers.

| Operation | Contract |
| --- | --- |
| Device-specific READ_SECTOR | `io_Offset` is a zero-based sector index in the opened unit; complete one sector or an admitted short boot-sector prefix. |
| Device-specific WRITE_SECTOR | Same addressing, with verified durable completion; unavailable until IP4. |
| Device-specific GET_GEOMETRY | Return sector size, sector count, access flags and controller generation. |
| CMD_UPDATE | Flush supported ATA volatile writes, or succeed when there are none. |

Unit 0 exposes the master disk's physical 512-byte sectors for read-only
diagnostics. Units 1–15 correspond directly to supported active APT mapping
slots; their geometry is logical. Raw writes and filesystem mounting of unit 0
are unsupported. No implicit BIOS D1: substitution is applied.

The filesystem adapter converts its one-based sector number to `sector - 1`.
For 256-byte volumes, sectors 1–3 still transfer only 128 bytes, but each occupies
its normal APT logical container. The packed ATR byte-offset formula does not
apply to ATA partitions. Preserve the untransferred boot-sector bytes.

Establish units and immutable geometry at OpenDevice. BeginIO checks supported
commands, lengths, sector bounds and operational state; it trusts the caller's
live request, buffer and established handles. Exactly one terminal completion
is published, and no request is touched after its reply.

### Driver and hardware

Use one ordinary resident worker, started only when IDE access is requested.
Callbacks enqueue or complete immediately and never wait for ATA. The worker
serializes the controller, including an entire read/modify/write operation.
Use public lifecycle leases and resident notifications, following the existing
SIO model, without copying its POKEY transport engine.

Start with polled PIO. Bound every identify, ready, DRQ, completion and failure
wait. After a short readiness poll, sleep through timer.device/Wait while other
Tasks run. Record timeout constants and measure polling delay; never spin with
Forbid, IRQs disabled or SWITCHING held while waiting for hardware.

Keep the IDE interrupt source disabled while Exec owns the controller. Pin and
document PBI selection, its OS shadow, high-byte latch access and restoration.
The emulator's register path reads the advancing low byte at `$D110`, then its
latched high byte at `$D100`; writes stage the high byte before committing the
low byte. Use a native helper for these pairs and far-buffer movement.

Cover the selected PBI window and latch pair against IRQ **and NMI**, restoring
the prior selection before sleeping or calling public services. Prefer short
native transactions and measure their maximum interruption delay. SEI alone
is insufficient. Do not access the board's flash/RAM bank selectors, RTC or SDX
controls. Do not assume an ATA reset/device-control register is implemented
merely because alternate-status reads exist. Unresolved ownership or reset
semantics block that capability rather than introducing a ROM SIO fallback.

### Memory

Target **0 additional fixed, per-Task and idle reserved bank-zero bytes**,
including guards, alignment and unused capacity. Use the existing adapter
reservation and public Task pools; keep new resident state in upper RAM. Leave
`$010000–$01FFFF` untouched.

One active IDE worker consumes one existing Task slot. Prefer a 1,024-byte
worker stack with its existing 32 guard bytes and 256-byte DP; the stack's
256-byte interrupt reserve is already included. Prove its full call-depth bound
before admission. Do not grow pools or silently consume a large-stack slot if
that budget fails. An unavailable Task slot produces a normal open failure.

Allocate one 512-byte controller buffer, reused for IDENTIFY, APT reads, logical
sector packing and write verification, plus bounded unit/lifecycle metadata.
Keep the existing filesystem buffer and cache. Report resident code, total
upper-RAM allocations, stack high-water marks and reserved bank-zero deltas per
slice; additional reservations require an explicit revised budget.

## Implementation slices

| Slice | Deliverable | Suggested commit |
| --- | --- | --- |
| IP0 | Separate filesystem transport binding while preserving SIO | `Separate block I/O transport binding` |
| IP1 | Native IDE Plus worker, IDENTIFY and raw reads | `Add native IDE Plus read-only device` |
| IP2 | Bounded APT discovery and logical partition reads | `Add IDE Plus APT partition units` |
| IP3 | Read-only filesystem mounting and diagnostics | `Mount filesystems through IDE Plus` |
| IP4 | Verified logical writes with durability and write protection | `Add verified IDE Plus partition writes` |
| IP5 | Failure, cancellation, lifecycle and coexistence evidence | `Validate IDE Plus recovery and coexistence` |
| IP6 | Optional development demo and user documentation | `Package an IDE Plus development demo` |

### IP0 — Separate the block transport

1. Add an explicit backend to volume/mount identity and a small dispatcher for
   geometry, open, request preparation, availability and conditional cancel.
   Use the common request prefix, with reusable storage large enough for both
   transports. Preserve exact reply collection and current SIO cancellation.
2. Add the backend byte to the mount descriptor's existing trailing padding,
   aiming to retain its 46-byte size. Generate matching definitions and update
   all encoders, consumers and layout fixtures together. Keep one current wire
   format; source configs without `device` continue selecting SIO by default.
3. Separate common 128/256-byte filesystem geometry from SIO unit/profile rules.
   Compare duplicate physical bindings using backend plus unit. RAM remains a
   distinct filesystem backend without a block request.

Exit: existing SIO read/write, cache and cancellation cases pass focused
optimized emitted-code checks. A small raw/optimized probe verifies any changed
layout/bridge. No IDE mount can be accepted before its backend exists.

### IP1 — Native physical read support

1. Pin a dedicated IDE Plus emulator configuration, ROM and BIOS hashes, and a
   disposable raw disk fixture. Keep ordinary platform pins unchanged.
2. Add the resident route, registered worker entry, native PIO adapter and
   driver-owned startup/open/queue/stop state. Publish readiness only after
   hardware ownership and IDENTIFY succeed. Unwind partial startup fully.
3. Implement GET_GEOMETRY and single-sector READ_SECTOR for raw unit 0. Admit
   only supported physical geometry/addressing; use bounded status polling,
   correct ATA word ordering and exact 512-byte completion.
4. Specify the PBI/IRQ/NMI protocol and prove interruptions at selection/latch
   boundaries. Absence, busy timeout and ATA errors complete without hanging.
   A timeout marks the controller offline; do not promise software recovery
   until its hardware mechanism is established.

Exit: emitted code reads known physical sectors, including a far buffer crossing
a CPU bank boundary, while a peer Task advances. Guards, context and OS/PBI
selection are preserved. Raw writes remain rejected.

### IP2 — APT partition units

1. Discover APT directly at LBA 0 or in its supported protective MBR container.
   Decode the table's low-byte storage variant and follow only the bounded chain
   needed for the fifteen mapping slots. Check signatures, revisions, entry
   counts, links, capacity and overflow; reject loops and unsupported layouts.
2. Build immutable descriptors for supported active DOS slots, respecting
   physical start/count, physical sector-1 offset, mapping mode and access flags.
   Leave table sectors and metadata leaders untouched. Empty, reserved or
   unsupported slots fail cleanly on open.
3. Implement all four documented logical packing modes and their 128-byte
   variant. Derive logical capacity from physical extents and mapping, then
   cross-check filesystem geometry. Reject oversized mounts rather than
   truncating them. Detect duplicate/overlapping mapped extents before two
   filesystem bindings can introduce incoherent caches.

Exit: independent host fixtures cover packing and malformed tables; focused
emitted reads match known logical bytes, including first/last sectors and both
logical neighbours of a packed physical sector. All mapped units are read-only.

### IP3 — Filesystem integration

1. Accept `device: "ideplus.device"` and unit 1–15 in mount source configuration.
   Keep explicit `sectors`, `sector_bytes`, filesystem format and access policy;
   compare them with GET_GEOMETRY at attachment. SIO profiles apply only to SIO.
   Initially require `access: "readonly"` for IDE mounts.
2. Update FSINIT and the existing configured-slot mount/unmount management path.
   Keep system-drive overrides SIO-only and preserve the existing SYS:/C:/S:
   setup. No general interactive partition editor or arbitrary mount syntax is
   added.
3. Extend boot mount messages, `MOUNT` and `DEVICES` diagnostics to identify the
   device/unit and controller availability. Cache hits must still check the
   owning controller's state. An offline IDE controller invalidates its volumes
   without disabling healthy SIO or RAM volumes.

Exit: LIST/CAT and command loading read MyDOS and SpartaDOS partitions through
real ATA requests; SIO and RAM remain usable alongside them. Detach/remount
changes generations and invalidates retained data. No filesystem algorithm is
modified to know ATA geometry.

### IP4 — Safe writes

1. Enable WRITE_SECTOR only when controller write protection, APT flags and
   Exec mount policy all allow it. Reject unsupported or protected writes before
   media mutation; do not silently downgrade an explicit writable mount.
2. Read the containing physical sector, merge only the requested logical bytes,
   write it and verify the target bytes. Keep the whole operation under one
   controller request ownership, preventing another request between read and
   write. Preserve neighbouring logical sectors, unused bytes and short boot
   tails. No blanket zero-fill or deferred dirty physical cache is introduced.
3. Establish durable completion: disable ATA write caching through a supported,
   verified mechanism, or flush each accepted write before reporting success.
   If neither is available, reject writable admission. CMD_UPDATE supplies an
   explicit flush too. Filesystem data/map/bitmap/directory ordering must not be
   weakened by a volatile ATA cache.
4. Cancel before issuing a mutating ATA command when possible. Once issued,
   finish durability/verification and report the actual outcome; cancellation
   cannot undo that write. Never retry an ambiguous accepted write. Record the
   ATA status/error and invalidate affected volumes on an uncertain outcome.
   Publish the full logical byte count and replacement cache data only after
   successful completion; an uncertain write is an error, not a confirmed prefix.

Exit: create, copy, append, rename, delete and directory creation survive
detach/remount on both filesystems, with independent persisted-image audits.
Neighbour sentinels remain exact. Selected injected write/flush/verify failures
exercise the existing filesystem failed-mutation policy and confirmed results.

### IP5 — Cancellation, lifetime and concurrent use

1. Exercise queued cancellation, cancellation during preparing/RMW read,
   accepted-write completion, read draining, timeouts and repeated aborts.
   The block adapter's conditional cancel declines committed work. Every path
   settles exactly once before request/buffer reuse or close.
2. Verify open references, startup leases, stop rejection while busy, last-close
   retirement, allocation rollback and worker-slot reuse. A stale controller
   generation cannot access a newly opened unit or satisfy a cached read.
3. Run a focused mixed workload with IDE COPY, serial SIO activity and console
   or GUI/peer progress. Inject VBI/NMI at native PBI/latch boundaries. Exercise
   admission at the existing eight-Task limit without increasing reservations.
4. Measure logical throughput, readiness polling CPU use, longest native
   interruption suppression and peer/input latency with realistic ATA waits.
   Report observed limits; improve batching only where measurements justify it.

Exit: failures finish within recorded bounds and do not strand ownership or
disable unrelated devices. ATA waits leave scheduling available. No executable
compatibility or performance claim exceeds the pinned checks actually run.

### IP6 — Development demo and documentation

1. Publish the implemented device/block contracts in reference, setup in guides
   and results in history, updating their indexes. Document supported APT
   layouts, writable admission, offline/reset requirements and remaining limits.
2. Prepare an optional IDE development profile with a disposable APT disk and a
   read-only mount by default. Document recreating/attaching that fixture; keep
   generated disk and test evidence out of the distributable boot ZIP.
3. Build through [build_demo.py](../../tools/build_demo.py), retaining OF816,
   the five-second autoboot, matching system disk, pinned ROM, licences and
   checksums. Check compressed cartridge capacity before continuing packaging;
   stop if it does not fit. Keep standard demo defaults unchanged.
4. Run only the affected development checks during implementation. A public
   release or platform qualification requires the separate release tier on
   frozen inputs; physical Antonia/IDE Plus hardware needs separate evidence.

Exit: the optional development setup is reproducible and the final record states
its exact validation tier, inputs, memory costs and unqualified behavior.

## Primary implementation references

- [IDE Plus vendor downloads](https://drac030.krap.pl/en-kmkjz-pliki.php) and
  [BIOS 2.x configuration guide](https://drac030.krap.pl/ide-plus-config-screen-reference-2.0.pdf).
- [APT specification](https://drac030.krap.pl/APT_spec.pdf): authoritative table,
  partition and logical sector mapping rules used by IP2/IP4.
- AltirraSDL `src/Altirra/source/kmkjzide.cpp` and its ATA block implementation:
  inspect and pin the source matching the actual emulator build for register
  semantics. Emulator behavior alone does not establish hardware support.

Use the compiler revision in [actionc.json](../../toolchain/actionc.json).
Compiler or emulator defects belong in their owning repositories with focused
regressions; do not add Exec-specific workarounds to this driver.
