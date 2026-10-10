# IDE 512-byte sector refactor development record

[Implementation plan](../plans/ide-512-sector-refactor-plan.md)

## I512-0 — Independent media

The pinned Altirra SDFS producer now creates uniform 512-byte ATR staging
volumes with a one-sector boot region. Identity normalization preserves the
complete first sector. A shared ATR sector view supports the existing floppy
layout and uniform sectors; MyDOS still rejects 512-byte media.

Development checks: two IDE image-builder cases and five existing allocation
audit cases pass. The new case independently extracts a file extending beyond
one 254-entry map page, checks header geometry and audits allocation. The
pinned real IDE Plus BIOS lists distinct SYS and WORK contents on the new
512-byte APT. No XEX launch was attempted in this slice.

Evidence: `build/development/ide-512/i512-0/`, including producer hashes,
raw image/mapping and `bios/results.json` with the BIOS/ROM/emulator pin and
directory screenshots. These are development artifacts, not distribution files.
Runtime bank-zero reservation change: **0 fixed, 0 per-Task and 0 idle bytes**,
including guards, alignment and unused capacity; this slice changes host tools.

## I512-1 — Shared sector storage

BLOCKIO's scratch sector and the SDFS map are now 512 bytes. The shared mutation
workspace has four 512-byte sector arrays; its emitted size is 2,214 bytes,
an increase of 1,024. Total shared buffer payload growth is **1,536 upper-RAM
bytes**, without per-file buffers or a larger cache allocation. Cache tags use
zero-based pieces; a hit requires all one, two or four 128-byte pieces before
copying into the destination. Short sectors continue using every cache set.

Development checks pass: raw/optimized emitted record access and far copy,
optimized block adapter fixture (including the existing full 64 KiB working
set, disabled cache and errors), all four independently missing pieces of a
512-byte sector, crossing destination guards, invalidation and cache-metadata
allocation rollback. Evidence is under `build/development/ide-512/i512-1/`.
The pinned compiler revision is unchanged; the cache runner uses its release
host binary. Runtime bank-zero reservation change remains **0 fixed,
0 per-Task and 0 idle bytes**, including guards/alignment/unused capacity.

## I512-2 — Native transfers and filesystem reads

IDE discovery now exposes only uniform 512-byte mappings. Read/write requests
require exactly 512 bytes; full-sector writes stage the caller bytes directly,
then retain terminal status, required flush and complete verification. Packed
address/copy paths are removed. The mount generator and adapter admit profile 0,
boot layout 0 and SDFS only on IDE. The SDFS reader recognizes revision 2.1,
its native boot signature and one-sector boot region. Filesystem write admission
remains closed until I512-3; device-level writes are checked separately.

Development checks pass: fourteen APT cases (including unsupported 128/256
slots beside valid mappings), durable/protected/failed native writes, rejected
short requests, IDE SYS selection without SIO, floppy MyDOS/SDFS and RAM
coexistence, geometry rejection, and a 130,567-byte file traversing two map
pages. Mixed cancellation/peer activity, timeout, flush failure, verification
failure and an injected NMI boundary pass with ownership cleanup and stack
guards. Evidence: `build/development/ide-512/i512-2/`.

The emitted IDE worker call bound is 730 bytes including the 256-byte interrupt
reserve and 16-byte dispatch margin, within the existing 1,024-byte stack.
Observed small-worker peaks in the mixed case are at most 353 bytes.
Comparing optimized APT fixtures, IDE driver routines change from
27,544 to 25,990 bytes (-1,554); this is driver code only,
not a whole-kernel size claim. Fixed controller metadata and buffers retain
their existing sizes. Runtime bank-zero reservation change: **0 fixed,
0 per-Task and 0 idle bytes**, including guards/alignment/unused capacity.

## I512-3 — Filesystem mutation

SDFS-512 write admission is enabled. Metadata initialization clears the admitted
sector length, including each complete new map; MyDOS callers supply their
floppy size. Allocation scan origins and wraparound follow the format's boot
reservation. Four-sector batching and payload → bitmap → header → map → length
publication remain unchanged, with no extra data-sector zero-fill pass.

Optimized development checks pass for persisted create, read-back, append,
overwrite, truncate, rename, directory creation/deletion and remount. Independent
allocation/content audits cover a directory row beginning at byte 506, a
130,567-byte write crossing the 254-pointer map boundary, and allocation across
4,095/4,096 with the sector cache disabled. Sector-1 bytes outside the free count
remain exact, including its boot code and reserved tail. MyDOS-256 and SDFS-256
floppy mutation regressions pass. IDE-only admission/protection, failed write,
verification corruption, cached-read denial and independent RAM/console survival
pass. The IDE-only startup script and disk-command check also passes.

The extracted IDE demo's cancelled COPY persists an exact confirmed prefix;
PRIMES, timer ticks and VBI continue during it, and another command loads afterward.
Evidence: `build/development/ide-512/i512-3/` and
`build/development/ide-512/i512-4/copy-break-cart/`.

The map-boundary mutation observes at most 584 bytes touched in the filesystem
worker's 1,024-byte stack, leaving 184 bytes above its interrupt floor; all
stack/domain guards pass. FSALLOC and FSWRITEIO optimized routine totals in
the read and mutation fixtures change by +429 and +32 bytes respectively;
this comparison covers those modules, not whole-kernel growth. The 2,214-byte
mutation workspace rounds to 2,216 bytes at the heap's eight-byte alignment.
Buffer growth remains exactly +1,536 allocated upper-RAM bytes across the three
existing allocations, because each increase is a multiple of eight. No new
allocation headers, workers or per-file buffers are introduced. Runtime
bank-zero reservation change: **0 fixed, 0 per-Task and 0 idle bytes**, including
guards/alignment/unused capacity.

## I512-4 — Demos and firmware boot

Both IDE-only and mixed standard-console demos are rebuilt. IDE-only uses a
4 MiB APT with protected SYS unit 1 and writable WORK unit 2, each 1,440 × 512
bytes, native BPS flags, existing starts/leaders and matching EXEC816.XEX in SYS.
The mixed profile retains floppy SYS/WORK and independently formats its IDE
filesystem at 512 bytes. Refresh rejects old packed native builds, and updates
the IDE guide before recreating its package. Existing user media is not converted.

The extracted IDE-only package includes both Atarimax variants. Development
checks cover real cartridge boot, OF816, IDE command loading, persistent WORK
mutations and BREAK during COPY alongside PRIMES/timer/VBI activity. The mixed
package boots and loads HELLO from IDE while SIO and RAM remain available.
Capacity is checked before packaging: combined XEX sizes are 328,817 bytes
(IDE-only) and 334,748 bytes (mixed), leaving 703,374 and 697,443 bytes under the
cartridge payload limit. Build output, manifests and test media remain outside
the distribution ZIPs.

**ID5 is closed for the pinned native-512 emulator setup.** The actual BIOS 2.1
menu loader reads SYS:EXEC816.XEX, reaches OF816 INITAD with native loading
paused, completes the five-second countdown (249 PAL frames), resumes payload
loading, reaches the kernel/IDE shell, loads a disk command and exits normally.
The serial-output watch records zero writes through the menu-load/kernel path.
This uses physical menu keys, not Altirra's direct-XEX hook. Return is released
promptly after file selection to prevent keyboard repeat cancelling autoboot.
This does not establish automatic power-on disk boot or hardware compatibility.

### Matched loaded COPY

Fresh SYS/WORK images contain the same 23,872 source bytes, identical 16 KiB
COPY command binary and 512-block cache budget. Both builds use actionc
`6510ea1d148c93edea595be8a5afa9630d5a75e3` and the same pinned emulator,
AltirraOS ROM, BIOS, ATA-master configuration and timing. The frozen pre-refactor
snapshot is a development comparison input only. Command loading is excluded:
the interval runs from COPY's source Open through destination Close. Private
observers count actual ATA command sites and successful filesystem verification;
independent persisted-content/allocation audits pass.

| Measurement | Packed 256-byte baseline | Native 512-byte sectors |
| --- | ---: | ---: |
| PAL frames | 505 | 196 |
| Guest seconds | 10.10 | 3.92 |
| ATA reads | 317 | 115 |
| ATA writes | 108 | 61 |
| Preparation reads | 108 | 0 |
| Verification reads | 108 | 61 |
| Verified writes | 108 | 61 |
| ATA flushes | 0 | 0 |

This instrumented emulator case is about 2.58× faster. Every write still has
one verification read; the pinned emulated medium advertises no volatile cache,
so neither case needs a flush. Cached-device successful FLUSH and physical
hardware speed remain outside this evidence.

Evidence: `build/development/ide-512/i512-4/`, including `copy-before/`,
`copy-after-same-profile/`, firmware results, extracted cartridge/mixed checks,
capacity records and the two `exec816-demo.zip` packages. The full host suite
passes **427 tests**; validation remains the development tier, not release or
hosted-platform qualification. Relative to the earlier matching IDE-only demo,
optimized resident routine code changes from 956,160 to 956,133 bytes (-27),
and compressed native XEX from 304,107 to 303,735 bytes (-372). The shared
upper-buffer allocation increase remains +1,536 bytes. Existing worker stack,
DP and guard reservations are unchanged; both packaged IDE worker call bounds
remain 730/1,024 bytes. Runtime bank-zero reservation change: **0 fixed,
0 per-Task and 0 idle bytes**, including guards/alignment/unused capacity.
