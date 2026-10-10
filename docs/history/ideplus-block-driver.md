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

## IP3 — filesystem mounting

Mount sources accept explicit IDE device/unit identity and profile 0. Attachment
compares GET_GEOMETRY bytes/count and rejects writable admission in this slice.
SYS/OF system-drive overrides remain SIO-only. Existing configured-slot mount
management, cache and filesystem algorithms are shared. Boot/MOUNT/DEVICES
diagnostics expose IDE bindings; inactive inspection does not probe hardware.

Reserved bank-zero delta: **0 fixed / 0 per Task / 0 idle bytes**. The mount
descriptor remains 46 bytes. Block access policy uses existing record padding;
no extra sector cache or request buffer is added. Diagnostic rows add two upper
bytes per configured mount, within the existing shell transfer buffer.

Focused checks use the same pinned compiler revision, now also supporting an
explicit optimized host compiler build (`release=True`). Its actual binary hash
and profile are recorded; emitted-code optimization remains an independent
setting. Default build-tool behavior is unchanged. This reduces build time
without changing language, ABI or compiler sources.

Optimized emitted checks read every file byte from both MyDOS and SpartaDOS
APT partitions and a simultaneous SIO volume, enumerate an IDE directory,
reject creation on read-only media, write RAM: and retire all ownership. The
APT and SIO images remain byte-exact. Eight existing and two IDE mount-source
host checks pass. Evidence: `build/development/ideplus-ip3/{mydos,sdfs}/`.
This is focused development coverage, not a release qualification.

## IP4 — verified writes

Mapped WRITE_SECTOR uses one serialized physical RMW/flush/verify operation.
Durability is admitted for cache-free IDENTIFY or advertised FLUSH CACHE;
protection and unsafe durability reject writable admission. Cancellation stops
preparing writes; accepted writes finish or become permanently offline. IRQ
ownership is retained on uncertain failure until cold reset.

Optimized emitted sector checks cover all eight size/packing combinations,
short boot prefixes, raw/APT protection, CMD_UPDATE and accepted ATA write
failure. Independent whole-media comparisons preserve neighbours, padding,
leaders and tables. Persisted MyDOS and SpartaDOS checks cover create/readback,
overwrite, append, truncate, empty files, rename/delete, directories and remount;
SpartaDOS crosses 16 KiB allocation/map boundaries. Evidence:
`build/development/ideplus-ip4/{sectors,filesystems}/`.

The emulator advertises no volatile write cache. These successful-write checks
exercise cache-free durability; they do not qualify successful FLUSH on physical
cached media. Flush/verify fault injection and cancellation follow in IP5.

Reserved bank-zero delta: **0 fixed / 0 per Task / 0 idle bytes**, including
all guards, alignment and unused pool capacity. No extra physical buffer or
metadata reservation was introduced. Observed IDE worker stack use is 313 bytes
in the persisted filesystem cases, with natural VBI and intact guards; this is
an observed lower bound, not a complete call-depth proof. The full bound is
recorded with IP5.

## IP5 — failure, lifetime and coexistence

Fourteen focused optimized emitted cases cover queued/repeated abort, preparing
RMW cancellation, active read draining, accepted-write abort refusal, shared
open references, busy-stop rejection, worker retirement/reopen generations,
exhaustion of all existing small Task slots, allocation-failure rollback,
bounded BSY timeout, flush rejection and verification failure. A peer performs
real serial SIO filesystem reads during the preparing IDE operation. Whole raw
images are compared independently and every normal retirement balances heap,
leases, signals and request/port ownership. Seven cases await a real VBI at
selection/shadow/restoration and read/write latch boundaries, preserving context,
selection, data and guards. Test hooks use existing upper arena capacity and
emit no production probe code. Evidence: `build/development/ideplus-ip5/`.

The allocation check rejects public AllocMem before allocation, then restores it
and successfully reopens. Flush rejection forces the FLUSH-required policy on
the emulator, whose ATA implementation rejects that command; verification failure
corrupts the settled reread buffer. Neither proves successful cached-media FLUSH.
The BSY case completes its complete startup/request/retirement sequence in 256
VBI ticks; each Ready deadline remains 250 ticks, with 32 short polls per sleep.

The build now verifies a context-specific emitted worker call graph before
packaging an image with small pools. Its timer binding excludes impossible
recursive IDE/SIO startup and non-timer dispatch paths. The ordinary call bound
is 458 bytes; adding the full 256-byte interrupt reserve and 16-byte dispatch
margin gives **730 of 1,024 bytes**, with 294 bytes headroom. The proof and its
explicit source/ABI assumptions are in `ideplus-stack-bound.json` beside builds.
Observed mixed-workload IDE stack use is 371 bytes; watermark measurements alone
are not the proof. Emitted driver Action! code occupies 27,544 bytes in this
focused optimized build. Resident upper metadata remains 1,024 bytes; active
heap payload is 512 + 27-byte timer port + 38-byte clock request, plus allocator
accounting. No second physical buffer/cache is allocated.

Four ordinary PIO read intervals measure 26 base-clock cycles each, including
bus stalls and diagnostic NOPs, on the pinned 8× PAL emulator. This is about
15 microseconds. The pinned history API omits PBR: the samples are tied to the
just-settled native reread and its instruction range, not an arbitrary bank
trace. These samples do not bound added ROM VBI time or physical hardware/input
latency. The sector-write fixture completes 2,560 logical written bytes plus
geometry/readback/lifecycle checks in 63 ticks; that whole-scenario rate is not
an isolated ATA throughput claim. A peer advances during real SIO work and the
bounded ATA sleeps. No physical speed or keyboard-latency qualification is made.

APT exclusions now include metadata leaders as well as reserved offsets, tables
and mapped data. Twelve emitted APT cases pass, including a metadata-default
header and a leader overlapping its neighbouring partition. Four packing/mount
host tests and generator checks pass. Request submission clears io_Actual before
queue publication, so repeated queued abort cannot retain an old success count.

Reserved bank-zero delta: **0 fixed / 0 per Task / 0 idle bytes**, including
all guards, alignment and unused pool capacity. This compares IDE-enabled and
ordinary builds with the same current Task profile; historical compaction
baseline deltas in build reports include pre-existing larger application pools.
All evidence remains development tier, not hosted-system qualification.
