# Bounded IDE read ranges development record

[History](README.md) · [Design](../plans/ide-read-ranges-design.md) ·
[Implementation plan](../plans/ide-read-ranges-implementation-plan.md)

The RR1–RR4 slices implement bounded regular-file reads using the existing
filesystem worker and IDE Plus driver. Development evidence uses the compiler
pin in [actionc.json](../../toolchain/actionc.json) and the ROM, BIOS and emulator
inputs in [altirra-ideplus.json](../../toolchain/altirra-ideplus.json). Large native
builds and disposable media remain under build/ide-read-ranges. Compact results
are in [ide-read-ranges.json](../development/ide-read-ranges.json).

## RR1 Device command

Device ABI revision 4 adds READ_SECTORS=14 and a four-sector maximum without
changing request layouts. Native PIO fills each destination sector, then checks
terminal status. Failed/aborted reads publish zero actual bytes; issued range
ATA errors require cold reset. Discovery and single-sector operations keep
their existing behavior.

The small raw/optimized fixture passes 1/2/3/4-sector APT reads, raw-unit reads,
exact partition ends, invalid lengths/offsets, queued repeated abort, bank carry,
neighbour guards, unchanged media, one reply and ownership cleanup. Optimized
fault injection after three PIO spans and after the final span confirms zero
valid bytes, the expected modified destination prefix and offline retirement.
Optimized lifetime cases pass mixed SIO traffic, active abort/draining, timeout
and NMI boundaries 4/7. Host checks: 447 passed; generator check passes.

The emitted IDE worker bound is 758 bytes including the 256-byte interrupt
reserve and 16-byte dispatch margin, within its unchanged 1024-byte stack.
Fixed, per-Task and idle reserved bank-zero deltas are all zero, including
guards, alignment and unused capacity. No controller/request/buffer or pool
grew in this slice. Development checks do not qualify hardware or a release.

## RR2 Adapter and cache

The shared transfer buffer is now 2048 bytes; sector/map/cache-piece capacities
remain 512 bytes. BeginFetchRange reduces its in/out count on a first hit or
before a later cached sector. Contains probes all pieces without changing cache
statistics. Exact completion publishes individual sectors, retains only the
first scratch tag and releases the request borrow. Failed/short completion
publishes nothing and invalidates the volume.

The optimized real-IDE adapter fixture passes mixed cache hits, exact miss
accounting, partial-piece rejection, full cold ranges, invalid extents,
cache-disabled reads, short completion, offline scratch rejection and cleanup.
The enlarged-buffer allocation-failure fixture and the existing real SIO adapter
fixture pass. Host checks: 447 passed. The existing write observer follows the
new ReadInto signature.

Additional upper allocation is exactly 1536 bytes in the existing shared buffer.
No record, controller buffer, cache arena, Task pool or per-handle allocation
grows. Reserved bank-zero deltas remain 0 fixed / 0 per-Task / 0 idle bytes.

## RR3 Filesystem range selection

Workspace carries the admitted count beside its needed sector. All backends
explicitly request one sector for metadata/MyDOS work; operation startup,
retirement and payload consumption reset the count. SDFS groups only complete,
aligned regular-file payloads from its current validated IDE map. It stops at
request/EOF limits, holes, fragmentation and map boundaries, and the adapter
shortens the group at retained sectors. Request/map bounds are computed once
before looking ahead, avoiding repeated multiplication on warm cache hits.

Focused optimized emitted checks use real 512-byte IDE media and an independently
audited 130567-byte file. They cover contiguous, fragmented and sparse maps,
map transitions, partial heads/tails, small requests, EOF, mixed cache state and
disabled cache. Test-only completion injection supplies a terminal error after
staging, or delivers foreground BREAK before the first/second group is consumed.
The assertions check exact application bytes, results/IoErr, cursor position,
retired request/packet ownership, subsequent reads, guards and unchanged media.
The terminal-error case tests filesystem propagation; RR1 covers actual driver
failures and active abort/draining. Small raw/optimized layout/access probes and
the existing 256-byte SDFS fixture also pass. Host checks: 447 passed.

Workspace grows from 172 to 174 bytes; both use a 176-byte rounded allocation.
Combined extra upper reservation is therefore exactly 1536 bytes. No per-handle,
per-mount, Task stack, DP, guard or pool reservation grows. Reserved bank-zero
deltas remain 0 fixed / 0 per-Task / 0 idle bytes.
