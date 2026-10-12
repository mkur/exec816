# MyDOS performance implementation

[Plan](../plans/mydos-performance-implementation-plan.md) ·
[Historical records](README.md) · [Testing policy](../contributing/testing.md)

Development evidence uses the pinned compiler and AltirraOS ROM; it does not
qualify real hardware or a release. All slices add zero fixed, per-Task and idle
bank-zero bytes, including alignment, guards and unused capacity. Buffer and
Task stack reservations remain unchanged.

## MP0: baseline

The [baseline record](../development/mydos-performance-baseline.json) captures
matched instrumented COPY of 23,872 bytes through a 16 KiB buffer. Accurate
Generic 57600 timing gives 3,879 PAL frames, 99 reads and 341 writes for cold
creation; warm creation takes 2,982 frames, two reads and the same 341 writes.
Cold replacement takes 9,001 frames, 290 reads and 720 writes; warm replacement
8,066 frames, 193 reads and 720 writes. Command loading is excluded. Observer
calls contribute overhead; final comparisons use identical observers.

The operation fixture additionally isolates writable Open, seek, enumeration,
truncation, deletion and directory creation. It audits persisted allocation and
unrelated files and checks buffer and Task ownership guards. Large native images
and frozen library inputs remain under `build/mydos-performance/mp0/`.
Host development checks: 447 passed.

## MP1: copies and directory updates

FSCORE copies all 42 emitted entry bytes through native Move (63 routine bytes,
previously 119). Seed copies known path and ancestor spans; MyDOS Open and record
initialization use native memory operations. LoadEntry/StoreEntry retain the full
physical map sector in Mark, Rename and Delete. Slot retains it during creation;
allocation and payload initialization write scratch/data, never map.

Optimized public write checks passed on MyDOS 128/256 and SDFS 256, with saved
byte/allocation audits, remount, overwrite, append, rename, directory and legacy
empty cases. The maximum 255-byte relative path/depth-16 case and a complete
42-byte entry copy crossing both source and destination bank boundaries passed.
Host checks: 447. The older lock-name runner now requests deferred console
bindings and places its diagnostic kernel in bank 18 so its fixed D/E-bank
fixtures do not overlap the enlarged current image. This changes test placement,
not production reservations or the platform ABI.

## MP2: single VTOC publication

Change updates bit and free count together when the bitmap page is sector 360;
it validates both transitions before submitting the write. Distinct pages retain
bitmap-before-header ordering. No dirty state survives an operation.

The matched 128-byte operation fixture passes: CreateDir 25→17 writes, removal
17→9, Truncate 130→67 and single-file deletion 3→2. Full namespace, overwrite,
append and reclamation passed on 256-byte MyDOS with cache disabled and allocation
starting at sector 1970 (a later VTOC page). Persisted contents and allocation
passed the independent audit. Optimized create/mkdir completion errors,
delete/truncate BREAK and real on-wire Write BREAK passed at the first physical
write of each operation. Fault hooks now observe the common Store boundary for
single/range I/O; the runner reserves its current diagnostic image-data extent.
Host checks: 447. Shared separate-header SDFS regression is retained for MP6.

## MP3: bitmap lifetime and arithmetic

Selected-file validation retains scratch only inside that call; payload reads
use data, and every new validation starts uncached. Bitmap addressing uses
shifts/masks for admitted 128/256/512-byte geometry. Allocation scans retain the
byte/mask between consecutive candidates, reset on wrap, and checkpoint at
bounded chunks (at most 16 candidates, plus byte/page fetch boundaries).
Emitted Bitmap, ReserveBatch and TakeBatch no longer call division/remainder.

The operation fixture reduces writable Open bitmap loads 65→2: one selected
allocation page and one CountRoom header, retaining all 64 payload checks.
Optimized MyDOS page A/B/A traversal, allocation-bit error, fragmented directory
reservation, partial extension and cyclic corruption passed. A 65,535-sector
256-byte volume allocated at $FFFF, wrapped and passed saved-media auditing.
The playground producer's previously incomplete large ATR paragraph field was
fixed to encode its admitted maximum capacity; a host read-back/allocation test
covers that boundary. Shared SDFS 512-byte IDE create/overwrite/append/rename/
reclaim/remount passed. Host checks: 448.

## MP4: cursor reuse

Target uses a retained validated extent without fetching bytes, continues with
its successor for later targets, and restarts for earlier bases or invalid state.
Unknown END measures only remaining extents and retains its terminal cursor.
Reads still fetch their own matching payload. Write traverses accumulated bases
and uses position-minus-base; its 2,552-byte emitted body no longer divides or
reduces the whole-file position modulo payload size.

Matched 128-byte observations: 63 same-sector seeks fetch/visit zero sectors;
100 forward seeks visit 16 instead of 908; unknown END visits the remaining 47
instead of walking all 64 twice. Optimized 256-byte file parsing passed 1,306
checks/611 requests, including 70,003-byte reads, ten-bit/full-width references,
short/zero payloads, cycles, seek errors, cancellation and independent handles.
The stale NULL-output test was replaced with a real length-overflow error:
caller buffer validity is already the current API contract. Seek cancellation
now occurs before applying an extent, without assuming a second EOF walk.

A focused 66,000-byte public write/read/overwrite/append/rename/remount case
passes persisted-byte and allocation auditing on Generic 57600. It uses a larger
512-block test cache to bound transport time; production defaults and all timing
comparisons remain unchanged. File-only test selection now also skips repeated
root listings; ordinary namespace cases retain those assertions. A broad 71 KiB
128-byte case was stopped during repeated listings. The Fastest 125 kbit/s variant
wrote correct persisted bytes but failed reading sector 105 with SIO checksum
error 4; this is not a successful transport qualification. Host checks: 448.
