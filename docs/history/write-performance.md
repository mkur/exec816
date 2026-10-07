# COPY buffers and filesystem write performance

> Implementation record for WP0–WP5, based on the working tree at `328baef`.
> See the [write contract](../reference/filesystem-writes.md),
> [mutation ordering](../plans/filesystem-write-protocol.md) and
> [execution record](../development/write-performance.json).

The later [SpartaDOS buffering record](spartados-write-buffering.md) supersedes
the SDFS per-group publication path measured here; these WP measurements remain
tied to their original revision.

COPY owns a 16,384-byte upper-heap BSS buffer. TEE keeps 512 bytes; their shared
transfer routine accepts a pointer and capacity. Command loading allocates and
clears ordinary BSS before Main opens the destination. Unloading frees it.
There is no new allocator, provider or ABI revision, and no serialized 16 KiB
zero block in the command.

SpartaDOS initializes a new payload once with its actual bytes and a zeroed
unused tail, then publishes its map pointer and length. The redundant preliminary
zero-sector write is removed. Map and directory initialization stays intact.
Both writers retain their existing backend cursor. MyDOS reuses its bounded
chain/loop checks; SDFS retains a validated map and its back-link. Backward seeks
restart traversal, and shared staging buffers never become retained pointers.
Final review corrected the retained SDFS hop counter when creating a map; an
emitted-code assertion checks it across multiple map pages. This changes no I/O
dependencies, object size or cancellation unit.

New sequential extensions group allocation and publication across at most
**four payload sectors**, clipped at one bitmap/VTOC page and the current SDFS
map. Fewer available sectors produce a smaller confirmed prefix. Partial existing
sectors, overwrites and map transitions keep one-payload units. MyDOS's first
VTOC combines free bits and count in one write. Namespace exact/contiguous
allocation is unchanged. Every successful group settles allocation, payload,
links and entry metadata before advancing the confirmed byte count and epoch.

The plan initially allowed eight sectors and required reducing that cap if
accurate BREAK timing was unacceptable. A real on-wire cancellation took 204 PAL
frames (4.08 s) with eight, versus 141 frames (2.82 s) with four. The fixed limit
is therefore four. A physical Ctrl-C during loaded bitmap COPY returned in 187
frames (3.74 s), including command cleanup, with an exact nonempty persisted
prefix, a consistent allocation audit, a subsequent HELLO and clean EXIT.
The final preview's longer COPY/APPEND/BREAK walkthrough returns in 208 frames
(4.16 s). These are observed paths, not a universal latency guarantee.

## Matched measurements

The benchmark loads the real command before measuring source Open through
destination Close. Each case uses fresh disposable media, identical source
bytes/layout and target free space, the pinned compiler/ROM/emulator, PAL 65C816
at 8×, Generic 57600 and accurate disk timing. The comparison source disk holds
both command artifacts at fixed locations. Loading, keyboard input and printing
are excluded; host elapsed time is recorded separately.

The primary file is the packaged 23,872-byte LONG.TXT, from 256-byte SYS to
128-byte SDFS WORK. Times below are guest seconds from PAL frames.

| Case | Old FS, COPY 512 | Old FS, COPY 16 KiB | New FS, COPY 512 | New FS, COPY 16 KiB |
| --- | ---: | ---: | ---: | ---: |
| Cold source, create | 477.06 | 456.46 | 166.94 | 167.54 |
| Cold source, overwrite | 598.22 | 576.64 | 291.70 | 287.10 |
| Warm source, create | 438.20 | 438.62 | 148.24 | 149.90 |
| Warm source, overwrite | 558.12 | 558.34 | 270.04 | 268.58 |

Creating the file drops from **1,140 to 409 verified writes**; overwriting drops
from **1,518 to 787**. Physical reads are unchanged: 101/105 for cold
create/overwrite and 4/8 when warmed. Logical mutation reads for creation fall
from 3,028 to 752. The combined cold-create change is about 2.85× faster;
on this 128-byte target, the filesystem accounts for most of that gain. The
larger buffer alone saves about 4.3% cold and gives no measured warm-create gain.
It changes 47 nonempty COPY transfers into two, without combining SIO sectors.
The matched matrix was captured before that final map-growth counter correction;
the execution record identifies those artifacts and a final cold-create check.
That final check takes 167.76 s, with the same 101 reads and 409 verified writes.

For a 256-byte SDFS target, the new filesystem takes 138.14 s and 288 writes with
COPY 512, versus 101.04 s and 196 writes with COPY 16 KiB. The larger request can
now fill four-sector groups instead of two. Both cases issue 101 physical reads.

The 49,159-byte binary MyDOS comparison with COPY 512 takes 812.12 s, 314 reads
and 1,072 writes on the frozen filesystem, versus 320.88 s, 201 reads and 584
writes on the new one. Mutation payload visits fall from **28,584 to 289**, and
logical mutation reads from 58,340 to 1,066. These count traversal work separately
from physical cache misses; they are not CPU-cycle measurements. Fast-media
COPY 16 KiB persists the same binary exactly, with 104 payload visits and 353
writes. Its elapsed time is excluded from accurate-media comparisons.

The accurate 256-byte MyDOS COPY 16 KiB case fails reproducibly in both frozen
and new filesystems. SIO transmits all 256 payload bytes, then times out awaiting
verified WRITE completion at the existing one-second deadline. The bus remains
offline and shutdown parks with `$FF93`, requiring reset. This is recorded as a
transport timing limit, not a successful benchmark or hardware qualification.
The plan leaves transport profiles, deadlines and retry policy unchanged.

An ordinary four-sector SDFS group uses eight writes instead of twenty-four.
Map transitions need more; the primary benchmark observes at most nine writes
per unit. With cache disabled and a split directory entry, a map-transition
unit reaches **10 writes and 29 total physical requests**. The existing Generic
deadline is 248 × 4,041 µs per request: summing those active deadlines gives
29.063 s of transport allowance for that path, excluding queue/CPU overhead.
This is distinct from measured successful BREAK latency. No interrupt mask or
scheduler exclusion spans these requests.

## Memory and code

WP0–WP5 each add **0 fixed runtime, 0 root/kernel, 0 per public Task, 0 idle and
0 boot-only reserved bank-zero bytes**, including guards, alignment and spare
capacity. Task stacks, direct pages, provider tables and fixed upper reservations
are unchanged. FileBacking stays 114 bytes, Mount 78, Service 460, and the shared
mutation workspace 878 requested / 880 rounded bytes. Backend cursors stay 28
bytes; there is no per-file growth or second large filesystem buffer.

| Emitted cost | Before | After | Change |
| --- | ---: | ---: | ---: |
| COPY BSS requested | 837 | 16,709 | +15,872 bytes |
| COPY BSS rounded allocation | 840 | 16,712 | +15,872 bytes |
| COPY disk command | 4,740 | 4,723 | −17 bytes |
| FSALLOC routine code | 6,900 | 9,112 | +2,212 bytes |
| MYDOSWRITE routine code | 11,496 | 14,495 | +2,999 bytes |
| SDFSWRITE routine code | 18,043 | 22,279 | +4,236 bytes |

Total resident native routine growth is 9,447 upper-RAM bytes; MYDOSFILE's public
Visit helper changes visibility without growing its code. TEE's buffer remains
512 bytes. The filesystem stack uses 628 bytes in the cache-disabled bitmap
boundary check; normal packaged SDFS uses 586 bytes in its
existing 1,024-byte stack. These leave 140/182 bytes above the 256-byte interrupt
floor. Loaded COPY, root, kernel, idle and other Task guard checks pass without
enlarged reservations. The split-row observer reaches 637 bytes in the existing
1,024-byte filesystem stack, leaving 131 bytes above that floor. Watermarks
describe these executed paths.

## Development checks and local preview

The record includes 364 host checks; focused optimized COPY/TEE command cases;
small raw capacity/far-pointer probes; real loaded commands and allocation
failure before target truncation; persisted file operations; requested extension
sizes 1..8 with the four-sector cap; cache-disabled bitmap/VTOC and map boundaries;
fragmented/ten-bit allocation and low-space partial groups; terminal Close
errors, inherited positions and stop/drain; BREAK before, during and between
groups; and lost completion at allocation, payload, linkage and publication,
including errors after an earlier confirmed group. Failure injection occurs
after a real transport reply and does not simulate a physical drive fault.

Independent allocation/byte oracles and selected original MyDOS 4.50/SpartaDOS
X 4.50 read-and-update round trips cover both sector sizes. Earlier executable
slices and the eight-sector prototype remain separate evidence. Uncertain
groups can leave incomplete entries or lost allocation; no rollback or resident
repair is promised.

The unpublished local preview is
`build/release-preview-write-performance/assets/exec816-demo.zip`. It contains
the bitmap shell without primes, OF816 with five-second autoboot, matching
SYS/WORK disks, pinned AltirraOS ROM/licenses, both Atarimax CAR forms and raw
BIN. XEX and both cartridges pass boot/commands/guards/ownership/EXIT checks;
the XEX additionally exercises LONG.TXT COPY, CMP, APPEND, WC and physical BREAK.
The ZIP's payloads, cartridge headers and complete checksums are verified.
Manifests, private benchmarks and test output stay outside it. Full release and
real-hardware qualification remain separate.
