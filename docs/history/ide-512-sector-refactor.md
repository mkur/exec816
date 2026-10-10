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
