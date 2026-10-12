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
passes persisted-byte and allocation auditing on Generic 57600. Its explicit
512-block cache setting equals the current 64 KiB default; production settings
and timing comparisons remain unchanged. File-only test selection also skips repeated
root listings; ordinary namespace cases retain those assertions. A broad 71 KiB
128-byte case was stopped during repeated listings. The Fastest 125 kbit/s variant
wrote correct persisted bytes but failed reading sector 105 with SIO checksum
error 4; this is not a successful transport qualification. Host checks: 448.

## MP5: established admission

| Removed repeated work | Established owner/lifetime | Checks retained |
| --- | --- | --- |
| Current read sector geometry/ancestry | Open admits start; Validate admits each next link before payload acceptance; Advance consumes that link. Restart reuses immutable start/ancestors. | Fresh trailer, ordinal, EOF/count, bounded visits/cycles and next-link admission. |
| Pairwise directory-lock ancestry scan | Root/Decode/Descend validate resolution; CreateDir descends its reserved extent; InitLockState publishes it. Parent reconstruction uses Descend again; leases prevent removal/rename under live descendants. | Mount identity/type/live lock, constant-size depth/root/start/parent shape and corrupt on-disk descent. |
| Current reclaim sector geometry/ancestry | Delete/Truncate finish selected-file validation and CountRoom before detaching reachability. Serialized mutation and writer/namespace leases protect that snapshot. | Newly read trailers/next links, fresh allocation bits, free-bit/count transitions and I/O completion. |
| Preliminary full-tail read during append | A valid terminal cursor already locates full EOF. | Extend rereads the old tail after initializing reserved sectors, before publishing its new link. |

No persistent admission flags or chain index were added. The geometry flag is
an explicit private argument used only by the protected reclaim walk; normal
validation/write paths remain conservative. Reclamation still reads successors
and checks mutable allocation state; it does not reuse the earlier preflight
bitmap page.

Optimized 128-byte parser, maximum/deep relative paths and corrupt ancestry
passed. Cache-disabled public write/preflight/overwrite/append/remount passed.
Write BREAK/completion error, Delete/Truncate completion error and post-write
BREAK passed through the real adapter with unrelated-file and allocation checks.
Host checks: 448. The matched operation fixture reduces creation payload visits
33→17 without changing its four-sector extension or physical write ordering.

## MP6: final measurements

The [final record](../development/mydos-performance-final.json) retains paired
counts, input/image hashes, the compiler/ROM/emulator pins, saved-media audits
and exact execution scope. The baseline is the MP0 frozen library snapshot;
the 256-byte and IDE comparisons rebuild those libraries with the same current
fixtures, platform and media geometry as their final counterparts. The IDE
runner's `--library-baseline` option selects this comparison without selecting
the older driver's 256-byte media profile.

Accurate Generic 57600 SIO COPY uses the same 23,872-byte source, 16 KiB command
buffer, 64 KiB cache, target contents and observers on both sides. PAL frames
exclude command loading; observer overhead is included.

| COPY case | PAL frames before → after | Physical reads before → after | Physical writes before → after |
| --- | --- | --- | --- |
| Cold creation | 3,879 → 3,858 | 99 → 99 | 341 → 340 |
| Warm creation | 2,982 → 2,950 | 2 → 2 | 341 → 340 |
| Cold replacement | 9,001 → 7,010 | 290 → 290 | 720 → 530 |
| Warm replacement | 8,066 → 6,074 | 193 → 193 | 720 → 530 |

Replacement takes 22.1% less time cold and 24.7% less time warm, with 26.4%
fewer physical writes. Fresh creation improves little: data, link and directory
publication still dominate. COPY's gateway observer is a wrapping 16-bit
counter, so its raw values must not be interpreted as total kernel-call counts.
The bounded operation fixture's counts do not wrap.

Operation measurements use the same 8,000-byte file, default cache and observers,
with rotational delay disabled on both sides. These separate structural/cache
cost from accurate floppy throughput; one-frame changes are not stable speedup
claims. The final record includes physical reads/writes, logical fetches,
bitmap loads, chain visits, cache hits, gateway calls and frames separately.

| Operation/metric | 128-byte sectors before → after | 256-byte sectors before → after |
| --- | --- | --- |
| Writable Open bitmap loads, including CountRoom header | 65 → 2 | 33 → 2 |
| 63 same-sector seeks: payload fetches/visits | 63 → 0 | 63 → 0 |
| 100 small forward seeks: chain visits | 908 → 16 | 473 → 8 |
| Unknown END after position 2,064: chain visits | 128 → 47 | 64 → 23 |
| Known END then one-byte read: payload fetches | 65 → 1 | 33 → 1 |
| Truncate physical writes | 130 → 67 | 66 → 35 |
| Delete physical writes | 3 → 2 | 3 → 2 |
| CreateDir physical writes | 25 → 17 | 25 → 17 |
| Remove directory physical writes | 17 → 9 | 17 → 9 |
| Repeated listing chain visits | 76 → 76 | 41 → 41 |

The final shared SDFS 256-byte SIO mutation case passes its full namespace,
overwrite, append, reclamation and remount audits. Matched SDFS 512-byte IDE
COPY remains 74 PAL frames (1.48 seconds), 20 ATA reads and 27 writes, with no
preparation/readback phases. No regression is observed in that workload.

### Code and storage

These are native routine-body bytes in the identical instrumented operation
images, excluding constant data and packaged/release size. The performance
changes increase code size; they are not a footprint reduction.

| Module | Before | After | Difference |
| --- | ---: | ---: | ---: |
| MYDOS | 7,973 | 7,466 | −507 |
| MYDOSFILE | 10,735 | 11,440 | +705 |
| MYDOSWRITE | 14,831 | 15,128 | +297 |
| FSALLOC | 13,480 | 13,935 | +455 |
| FSCORE | 743 | 687 | −56 |
| FSRELATIVE | 6,054 | 6,195 | +141 |
| FS83 | 3,116 | 3,116 | 0 |

All routine bodies in the diagnostic image total 847,159→848,097 bytes:
**938 more bytes**. The three MyDOS modules together add 495 bytes.

| Upper-RAM storage | Requested / heap-rounded bytes, unchanged |
| --- | --- |
| Shared workspace | 174 / 176 |
| Mutation state, including four 512-byte sector buffers | 2,214 / 2,216 |
| SDFS backend scratch, also allocated in a MyDOS-only worker | 730 / 736 |
| Shared operation | 44 / 48 |
| Per-file backing, including its inline 110-byte cursor | 114 / 120 |

AllocMem rounds to eight bytes and adds no per-allocation prefix. The 42-byte
entry and 28-byte backend cursor storage are inline records, not extra buffers.
Default cache payload remains 512 blocks of 128 bytes (64 KiB); sector staging
remains 2,048 bytes and the adapter sector buffer remains 512 bytes. No fixed,
per-Task or idle bank-zero reservation changes, including guards, alignment and
unused capacity. Task/DP/stack pools stay unchanged.

In the matched 128-byte operation runs, the largest touched Task stack watermark
falls from 538 to 522 bytes; the kernel watermark is 260→267 bytes, with no
interrupt-reserve bytes touched. Domain guards, ownership cleanup and runtime
stack checks pass. Watermarks are lower bounds on observed use, not proven
worst-case stack depth.

### Validation and follow-ups

Final host checks: **448 passed**. Focused optimized emitted-code checks across
MP1–MP6 cover both MyDOS sector sizes, bank-crossing record copies, maximum/deep
relative paths and corrupt ancestry, trailer/link/count/cycle errors, bitmap
page A/B/A traversal and allocation-bit rejection, partial groups, cache-disabled
mutations, allocation at $FFFF with wraparound, files over 64 KiB, cancellation
and completion-error ownership, and shared SDFS SIO/IDE behavior. Persisted
successful images pass independent content/allocation audits. Raw emission was
not repeated: this work changes neither compiler semantics nor the public ABI.
This is development evidence, not release or real-hardware qualification. The
unsuccessful 125 kbit/s probe and stopped broad case remain recorded under MP4.

Repeated listings still walk file chains with no physical reads; a bounded
completed-byte-length cache is the next CPU-cost opportunity. Grouped
CreateDir/reclaim bitmap publication could further reduce physical writes, but
needs explicit ordering and cancellation rules. Lazy SDFS scratch allocation
could save 736 rounded bytes in MyDOS-only configurations; mutation-buffer
consolidation remains deferred until its scratch lifetimes are audited.
