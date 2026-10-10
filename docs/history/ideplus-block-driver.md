# IDE Plus block driver development

[History index](README.md) · [Implementation plan](../plans/ideplus-block-driver-implementation-plan.md)

## IP0 — transport separation

The block adapter uses IOStdReq and a small transport dispatcher. SIO retains
its commands, profiles, reply ownership and cancellation. Mount identity includes
a backend byte at offset 45 of the unchanged 46-byte descriptor. Offline handling
invalidates only mounts using that controller; RAM volumes remain independent.
IDE configurations are rejected until the driver is connected.

Development checks with pinned actionc `6510ea1` passed optimized fixture and
real-SIO block reads/cache/cancellation, verified persisted SIO sector writes,
a persisted SpartaDOS 256-byte-sector file create/append smoke check,
and raw/optimized emitted mount layout probes. Eight mount-generator host tests
passed. Evidence is in `build/development/ideplus-ip0/`. This is development
coverage, not hosted-system qualification.

Reserved bank-zero delta: **0 bytes fixed, 0 per Task, 0 idle**; guards, alignment
and reserved pool capacities are unchanged. Request storage remains 52 bytes.
The extra volume backend uses upper-memory record space only.

The filesystem write fixture had outgrown its 2 KiB upper static-data arena and
its injected path buffer overlapped emitted code. It now uses the demos' 4 KiB
static-data arena and puts paths at `$2D1000`, outside the kernel image.

## IP1 — native raw reads

The generated resident route starts a driver-owned worker only for IDE opens.
IDENTIFY admits ATA master/LBA28/512-byte media. GET_GEOMETRY and raw reads use
bounded readiness polling and timer sleeps. Startup failure releases heap,
signals, timer bindings and Task leases. Active reads drain on cancellation.
The [device contract](../reference/ideplus-device.md) defines the pinned PBI/IRQ/
NMI ownership protocol and unsupported configurations.

Optimized emitted development checks pass known first/last raw reads, a far
buffer spanning `$2DFFF0–$2E01EF`, bad bounds, raw-write rejection, peer progress,
selection restoration, heap balance and guarded completion. Board absence
finishes without a leaked worker. Fixture and pin:
`tools/test_ideplus.py`, `toolchain/altirra-ideplus.json`; evidence:
`build/development/ideplus-ip1/raw/`. A small raw/optimized emitted probe also checks geometry layout.
NMI boundary injection and timing remain IP5
work; no physical hardware or hosted-platform qualification is claimed.

Reserved bank-zero delta remains **0 fixed / 0 per Task / 0 idle bytes**. Upper
resident metadata reserves 1,024 bytes (including unused capacity/alignment),
plus active heap buffer 512 bytes and ordinary timer resources. Emitted driver
Action! routines occupy 16,655 bytes in this focused optimized build; native
helpers occupy existing upper service-code capacity. One existing small Task
pool is consumed during open; its reservation and guards are unchanged.

## IP2 — APT partition reads

Mapped-unit discovery is bounded to fifteen slots and sixteen headers. Physical
extents, IDs, sector-1 offsets, links and overlapping mappings are checked before
publishing the set. Failed discovery clears every mapped descriptor. Raw unit 0
remains available when only the table is unsupported.

Two independent host fixture checks and ten optimized emitted cases pass:
direct, even-byte, MBR-contained, chained and even-byte chained tables; unknown
revision, cycle, overlap, overflow and invalid offset rejection. Native reads
cover all four packings at both 128/256 bytes, both packed neighbours, final
logical sectors, short boot prefixes and far buffers. Media remains byte-exact,
heap ownership balances and stack/domain guards remain intact. Evidence:
`build/development/ideplus-ip2/`. This is development coverage only.

Reserved bank-zero delta: **0 fixed / 0 per Task / 0 idle bytes**. Descriptors
use the previously reserved upper arena; no second physical buffer or retained
partition table was added. The bounded visited-LBA list uses 64 bytes on the
existing worker stack during discovery, without increasing its reservation.
