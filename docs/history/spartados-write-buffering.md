# SpartaDOS request-scoped write buffering

[History index](README.md) · [Current write contract](../reference/filesystem-writes.md) ·
[Implementation plan](../plans/spartados-write-buffering-implementation-plan.md) ·
[Development evidence](../development/spartados-write-buffering.json)

SB0–SB4 are complete at the development tier. SB5 delivery is pending. The
runtime change is committed in `73384e3` and `657cfcb`; lifetime/failure coverage
is in `db8cc95`. The frozen writer is `5fd47b6c54b476bec804c78c798c8b9ded67c4b6`.

## Implementation

One filesystem worker retains a private bitmap page, free count, current file
map and confirmed cursor snapshot during one SDFS Write packet. Payload writes
remain immediate. Four-sector work groups keep control/BREAK checkpoints;
they no longer force publication of the same metadata after every group.

A drain writes completed payloads' allocation bitmap, sector 1 free count,
file map and directory length in that order. The writer's incomplete flag
remains set until terminal Close. Only a completed drain promotes staged bytes
to the confirmed result and advances the metadata epoch. Request end, BREAK,
logical exhaustion and replacement of dirty bitmap/map state require a drain.
Existing-sector writes and map growth retain their immediate path, settling a
pending batch first. Every Write settles before reply; BLOCKCACHE retains only
confirmed bytes. Flush/Close and MyDOS's write path are unchanged.

Allocation bits become unavailable in the private working bitmap after the
payload group completes. A BREAK before its first submission leaves the group's
unused reservations free. A physical failure restores the confirmed cursor and
returns only the earlier published prefix, offlines the mount and invalidates
cached metadata. It cannot undo bytes already written. A physical error takes
precedence over BREAK. Once the entire request is accepted and drained, a late
BREAK still permits full success.

## Matched COPY measurements

All rows copy the same 23,872-byte LONG.TXT using the same 16 KiB command
artifact and fresh target layout. Measurement runs from source Open through
terminal destination Close, excluding command loading, printing and keyboard
injection. Warm cases deliberately read the source first. Both implementations
use actionc `6510ea1d148c93edea595be8a5afa9630d5a75e3`, optimized native emission,
stack guards, eight public Task slots, the pinned paced Altirra bridge and
AltirraOS 3.44 65816 ROM. Accurate Generic 57600 media, nominal 57.6 kbaud and
PAL timing are enabled; guest seconds are PAL frame deltas divided by 50.
These are emulator measurements, not real-drive results or qualification.

| Target sectors | Source | Frozen seconds | Buffered seconds | Frozen writes | Buffered writes | Buffered bytes/s |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 256 bytes | Cold | 101.04 | 62.24 | 196 | 108 | 383.55 |
| 256 bytes | Warm | 82.52 | 43.74 | 196 | 108 | 545.77 |
| 128 bytes | Cold | 167.52 | 97.70 | 409 | 233 | 244.34 |
| 128 bytes | Warm | 149.70 | 80.30 | 409 | 233 | 297.29 |

Cold cases have 101 physical reads: 97 source reads (2 directory, 1 map,
94 payload) and 4 target reads (2 directory, 1 bitmap, 1 header). Warm cases
have only the four target reads. Source bytes and pre-run target hashes match
between implementations. All submitted writes have verified completion;
persisted bytes and independent whole-volume allocation audits pass.

| Target | Writer | Payload | Bitmap | Header | File map | Directory | Total writes |
| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |
| 256 bytes | Frozen | 94 | 25 | 25 | 25 | 27 | 196 |
| 256 bytes | Buffered | 94 | 3 | 3 | 3 | 5 | 108 |
| 128 bytes | Frozen | 187 | 55 | 55 | 58 | 54 | 409 |
| 128 bytes | Buffered | 187 | 11 | 11 | 14 | 10 | 233 |

The focused 16 KiB Write on 256-byte media falls from 128 to **68** verified
writes: 64 payload writes and one each for bitmap, header, map and directory.
The ordered trace and final media pass with the general read cache disabled
and at its default size. This count assumes one map page, one bitmap page and
a directory record contained in one sector; Open/Close are excluded.

A 128-byte map holds only 62 payload pointers. The measured COPY spans several
map pages and retains the old map-growth path, explaining the additional
metadata traffic above. The maximum observed worker step costs 8 requests /
150 PAL frames on 256-byte media and 9 requests / 178 frames on 128-byte media.
With a split directory record, the 128-byte cold COPY takes 104.28 seconds and
246 writes: 187 payload, 12 bitmap, 12 header, 14 map and 21 directory. Against
the ordinary layout that is 13 more writes and 6.58 guest seconds; the changed
layout also affects creation/publication boundaries, so it is not a universal
per-row timing penalty. Its largest observed step costs 10 requests / 199 frames.

Bitmap-boundary extension is checked on independently generated 720 KiB media
with alternating occupied bits across the page boundary. Crossing a dirty page
adds a dependency drain before replacement. The 256-byte focused 16 KiB case
costs 72 writes: 64 payload and two each for bitmap, header, map and directory,
with both publication sequences in order. This boundary count is from fast-media
functional tracing, not the accurately timed COPY comparison. Larger 128/256-byte
boundary cases also cover map transitions and read-back/remount.

## Cancellation and failures

On accurately timed 256-byte Generic 57600 media, the selected physical BREAK
checkpoints measure:

| BREAK checkpoint | Accepted prefix from a 2,000-byte Write | Write-reply latency |
| --- | ---: | ---: |
| First payload in flight | 1,024 bytes | 156 PAL frames / 3.12 s |
| Before the next payload group | 1,024 bytes | 82 frames / 1.64 s |
| Final bitmap drain in flight | Full 2,000 bytes; success | 77 frames / 1.54 s |

The payload case includes completion of four payload writes plus dependent
metadata; the between-group case still drains accepted data. These are observed
paths, not a bound for arbitrary geometry, retries, directory splits or map
transitions. Existing per-I/O deadlines remain unchanged.

Selected emitted regressions cover first/middle/last payload failure, bitmap,
header, map and both halves of a split directory record; failures after an
earlier confirmed prefix; BREAK with a lost physical completion; inherited
writer retirement; Close/cleanup error precedence; alternating files and mounts;
cache-off bitmap boundaries; and unrelated media preservation. The small
cross-bank state-layout probe passes raw and optimized emission. Each case
checks applicable stack/domain guards, borrowed-pointer retirement and OS
context restoration. The SB4 host suite passes all 396 tests.

Five actual emulator cold RESET cuts occur after verified payload, bitmap,
header, map and directory writes, before normal cleanup. The disposable media
shows, respectively, unreferenced payload, leaked allocations/stale free count,
leaks with matching count, map pointers beyond the published length and the
full new length with its incomplete flag still set. No resident recovery is
added. These cuts do not simulate torn sectors or prove power-loss durability.
Persisted boundary media is read through a fresh emitted Exec filesystem
reader; this is not an original SpartaDOS CIO interoperability claim.

## Memory and scope

The single shared worker workspace grows from 878 requested / 880 rounded
bytes to 1,190 / **1,192** bytes: **312 additional reserved upper-RAM bytes**.
It adds one 256-byte bitmap and 56 bytes of state/snapshot and stays below the
384-byte growth ceiling. There are no new workers, per-open sector buffers or
per-mount sector buffers. Fixed, root/kernel, each public Task, idle and boot
bank-zero reservation deltas are all **zero**, including guards, alignment and
unused capacity.

In the eight-Task development profile, fixed runtime reservations are 10,528
bytes; public Task totals are 1,824, five times 1,312, and twice 2,848 bytes;
idle reserves 800 bytes. Runtime totals are 25,408 excluding OS reservations
and 56,128 including them; loading totals are 21,872 / 52,592. These totals are
profile-specific, not universal demo budgets.

With matched instrumentation, optimized resident executable bytes rise from
736,301 to 744,418 (**8,117 bytes**). The smaller focused executable independently
shows the same delta, 666,619 to 674,736. The measured filesystem worker touches
586 of its existing 1,024-byte stack, versus 582 before; 182 bytes remain above
the existing interrupt floor. Test-only caller buffers and the performance
harness's 8 KiB trace reserve are excluded from production workspace costs.

Frozen inputs are private measurement overrides; they are not a production
compatibility implementation. The local compiler build changes host Cargo
optimization only, with its pinned source unchanged. Evidence records exact
source, emitted image, observer, media and ROM hashes and machine configuration.
Full release matrices have not been run. Existing loaded FASTEST125 and accurate
256-byte MyDOS transport timing gates remain open; this work changes neither
SIO deadlines nor platform compatibility policy. Cross-Write buffering, recovery,
journaling and real-hardware qualification remain separate work.
