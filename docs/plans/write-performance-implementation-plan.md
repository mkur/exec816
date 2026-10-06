# COPY buffers and filesystem write performance

Status: WP0–WP5 implemented at the development tier. The
[implementation record](../history/write-performance.md) and
[execution evidence](../development/write-performance.json) record measured
costs and scope. The permitted latency adjustment selects four sectors after
testing eight. The accurate 256-byte MyDOS transport timeout remains a separate
follow-up; no transport deadline or retry policy changes are included.

The plan below preserves the proposed scope: give COPY a 16 KiB transfer buffer
and reduce physical I/O needed to extend MyDOS and SpartaDOS files. Keep
synchronous DOS calls, verified sector writes, bounded cancellation and the
existing shared worker.

Follow the [write contract](../reference/filesystem-writes.md),
[mutation ordering](filesystem-write-protocol.md),
[program loading contract](../reference/program-loading.md),
[platform memory budget](../reference/platform.md#bank-zero-memory-budget)
and [development testing policy](../contributing/testing.md).

## Problem and chosen scope

[COPY and TEE](../../examples/commands/command-transfer.inc) currently use one
512-byte array for reading and writing. The preview's LONG.TXT is 23,872 bytes:
47 nonempty COPY chunks, 94 source sectors on 256-byte SYS, and 187 destination
sectors on the 128-byte WORK disk.

SpartaDOS extension normally writes the allocation bitmap, free count, a zeroed
data sector, its map link, the actual data, and the directory length for each
new sector. That is roughly 1,122 writes for this file before map growth and
open/close overhead. This is a code-derived estimate, not a measured baseline.
[MyDOS Write](../../lib/mydos/mydoswrite.act) also walks the chain from its first
sector on every call, so sequential copying can repeatedly traverse old data.

Implement both requested improvements:

- **COPY transfers up to 16,384 bytes per Read/WriteAll pair.** LONG.TXT needs
  two nonempty transfers, followed by the ordinary EOF read. This reduces DOS
  messages and changes between source reads and destination writes. Physical
  SIO still transfers individual sectors; a larger buffer does not itself
  coalesce those transactions or establish a hardware speedup.
- **File extension commits at most eight payload sectors per unit.** Coalesce
  allocation/map/entry updates within that unit, initialize new sectors once
  with their actual contents, and retain sequential traversal state. Large
  requests remain interruptible between units.

Use the classic synchronous Amiga-style DOS Read/Write completion model above
the existing filesystem and device workers. Batching is private filesystem
policy; it adds no Exec gateway, public DOS provider or driver-specific kernel
service. Keep one current implementation and rebuild affected commands.

This slice introduces no background flusher, persistent dirty cache, asynchronous
COPY, double buffering, whole-file allocation, fsck, new disk format or changed
SIO command. TEE retains its 512-byte buffer. Namespace operations keep their
current ordering and cancellation policy. Mounting remains lightweight.

## Storage and completion decisions

Declare COPY's buffer as ordinary loadable-command global/BSS storage. The
existing o65 loader allocates it in the upper heap before Main runs and frees
it with the image. Do not put it on a Task stack, in bank zero or in the resident
shell. No new allocation provider or adaptive buffer-size option is needed.
An image-allocation failure must occur before COPY opens/truncates its target.
Check the compiler's object profile: the array must be BSS, without 16 KiB of
serialized zeros added to the disk command. The current 512-byte array already
uses that representation.

Make the internal transfer helper accept a buffer pointer and capacity. COPY
owns a 16 KiB array; TEE owns a 512-byte array. Remove the old shared fixed array
from the include, so COPY does not also retain an unused 512-byte buffer.
Keep its existing counted-binary transfer, short-write, causal IoErr, source
sharing, APPEND and terminal Close behavior.

The filesystem consumes the borrowed caller buffer directly while the DOS
Write packet is pending. Reuse its three 256-byte staging buffers, 23-byte row
and ten sector-reservation slots. Eight payloads need at most nine reservations
when a new SDFS map is needed. Avoid an eight-sector payload array or a second
16 KiB filesystem buffer.

Bulk extension groups are bounded by remaining caller bytes, eight payload
sectors, available space and format metadata boundaries. Clip SDFS groups at
the current map's remaining slots and allocation groups at one bitmap/VTOC
page. Use the improved single-sector path for partial existing-sector updates,
map transitions and other awkward boundaries. Fragmented data sectors are
allowed; contiguity is not a COPY requirement.

Preflight can choose a smaller group when fewer sectors are available or
addressable. It must not report disk full merely because eight cannot be
reserved when a smaller confirmed prefix can still be written. Preserve
MyDOS ten-bit address limits and local consistency checks.

Before the first mutation, honor BREAK without changing disk. After submission,
collect all required replies and finish that group's dependencies before
honoring BREAK. Advance position, entry length/count, operation.completed and
the enumeration epoch only after the group's required writes are confirmed.
The last completed group still succeeds with a pending BREAK.

The current documented one-sector cancellation unit becomes **up to eight
payload sectors plus dependent metadata**. This is an intentional policy
change to reduce metadata traffic; it must be documented and measured. A
16 KiB COPY buffer does not make 16 KiB the protected unit. Reads retain their
existing cancellation behavior. No interrupt mask or scheduler exclusion
spans I/O, and committed transfers keep pumping control messages.
Record the maximum physical-request count per group and its timeout bound,
alongside observed BREAK latency with accurate disk timing. Reduce the fixed
group cap before completing WP4 if its measured normal-operation latency is
unacceptable; do not hide it by disabling rotational timing.

Flush and last Close retain the synchronous contract. There are no dirty
sectors or unused speculative reservations left over after a successful Write
reply. The native incomplete flag stays set until final Close. On a failed or
uncertain write, invalidate the mount/cache, report the earlier fully confirmed
prefix and causal error, retire I/O/handles and require external recovery.
Part of the failed group may have reached disk. Do not promise atomicity,
rollback, power-loss durability or safe retries.

## Executable slices

### WP0: freeze the baseline and measure I/O

Build and save the current 512-byte COPY and filesystem artifacts under a
development output directory, with source/compiler/ROM/emulator/media hashes.
Retain artifacts as comparison evidence, rather than maintaining old production
code paths. Pin the compiler from [actionc.json](../../toolchain/actionc.json).

Add a focused copy benchmark using existing emitted-code, shell and persistence
observers. Count real submitted READ/WRITE requests, bytes, cache hits/misses
and evictions, and time source Open through destination Close. Record guest
PAL frames/cycles separately from host/tool time. Time command loading separately
or exclude it consistently; keyboard injection and console printing are not
copy throughput.

Use identical source bytes, disk layout, free space and machine settings for
each before/after case. Give each run fresh disposable writable media. Record
cold and deliberately warmed source-cache cases, and distinguish creating a
new destination from overwriting a populated file. Keep accurate Generic 57600
timing enabled for performance runs; fast-media functional runs are separate.

Primary case: the supplied LONG.TXT from 256-byte SYS to 128-byte WORK. Include
a larger binary case, both 128/256-byte geometries and a representative MyDOS
copy. Preserve input bytes exactly. Collect actual write-phase counts before
setting a numerical throughput claim.

### WP1: the 16 KiB COPY buffer

Change [command-transfer.inc](../../examples/commands/command-transfer.inc),
[COPY](../../examples/commands/copy.act) and [TEE](../../examples/commands/tee.act)
to use the caller-owned buffers and capacity parameter described above.
Use the existing COMMAND imports and loader policy without an ABI revision.

Exercise actual emitted command bodies and a loaded COPY with lengths 0, 1,
511/512/513, 16,383/16,384/16,385 and a multi-buffer binary file. Cover final
partial reads, short writes, saved read/write errors, APPEND, source/destination
alias conflicts, BREAK and late Close failure. Place a diagnostic upper buffer
across a 64 KiB boundary to check far-pointer carry. Check load failure and
cleanup without truncating output or retaining image storage. Keep a TEE smoke
case for mirroring and its unchanged buffer size.

Repeat WP0's primary measurements with the original filesystem. Report the
buffer-only benefit separately from later filesystem improvements.

### WP2: initialize new SpartaDOS data once

Separate ordinary file-payload growth from zero-initialized directory growth
in [sdfswrite.act](../../lib/spartados/sdfswrite.act). For a new payload sector,
assemble its caller bytes and zeroed unused tail in the existing data buffer,
write that complete sector, then publish its map pointer and directory length.
Remove the preliminary zero-sector write. Continue initializing directory
storage and map pages before making them reachable.

Keep one-sector commit units in this slice. The normal new-data case should
drop from six writes to five; map transitions and split directory rows have
additional dependencies. Confirm the new order through actual I/O, persisted
bytes and allocation audits. Exercise first/partial sectors, append, map growth,
and lost completion after initialization, linkage and length publication.

### WP3: retain sequential traversal state

Use the existing 28-byte backend cursor storage for MyDOS's validated current
sector/ordinal and SDFS's current map. A successful sequential write updates
that cursor instead of restarting at the file's first sector/map. Keep cursor
validity tied to the retained file backing, exclusive writer and live mount.

Advance and validate the next link/map locally. Restart on backward Seek,
incompatible read/write transitions, truncation or failure where needed.
Preserve ancestry, loop/range/allocation checks, MyDOS used-byte/ordinal trailers
and SDFS back-links. Do not retain pointers into a shared staging buffer or
enlarge every open file just to cache sectors.

Check append after reopen, alternating Read/Write/Seek, overwrite suffixes,
inherited positions, fragmented chains, map boundaries and malformed touched
links. Sequential traversal work should grow with the file's sector count,
rather than repeatedly walking the entire prefix. Measure CPU and physical
reads independently; warm cache hits alone do not establish this improvement.

### WP4: batch bounded file-extension metadata

Add internal grouped allocation to [fsalloc.act](../../lib/fs/fsalloc.act),
then use it in the ordinary file writers. Preserve the single serialized owner
and the namespace allocator's existing exact/contiguous requirements.

For SDFS, reserve the group's bits/count, initialize every new payload, publish
the updated map once, then publish the final directory length once. Clip at
map/bitmap boundaries; the single-sector path handles map creation/transition.
For an ordinary eight-sector group within one existing map, aim for eight
payload writes plus bitmap, header, map and entry: twelve rather than forty-eight.

For MyDOS, reserve the group's allocation, initialize each payload and trailer
with its final successor, connect the initialized chain to the previous tail,
then publish the new directory sector count. Preserve sixteen-bit links and
existing ten-bit ordinal encoding. When VTOC bits and free count occupy the
same sector, update both in one read/modify/write; otherwise confirm both
sectors. Do not link any uninitialized successor.

Group only new sequential extension; existing overwrites and partial tails
remain on the safe single-sector path. The common
[WriteStep](../../lib/fs/fswrite.act) reports/checkpoints between completed
groups, not between their dependent physical writes. Every successful group
settles its allocation and file metadata before a reply or next group.

Cover group sizes 1..8, map/VTOC boundaries, fragmented allocation, disk full
mid-request, ten-bit limits, split directory rows and cache disabled. Inject
BREAK before mutation, during the group and between groups. Inject lost
completion at allocation, first/middle/last payload, chain/map publication and
entry publication. Update fault observers to the actual new phases rather
than reusing old physical-write ordinals without checking their meaning.

### WP5: integration, measurements and preview

Run the selected optimized emitted command/filesystem regressions through the
existing [command](../../tools/test_write_commands.py),
[file operation](../../tools/test_filesystem_write.py),
[edge](../../tools/test_filesystem_write_edges.py) and
[lifetime](../../tools/test_filesystem_write_lifetime.py) runners. Include
inheritance, stop/drain, terminal Close errors, mount-offline behavior and a
usable shell. After persistence/reopen, independently compare file bytes and
run the [allocation audit](../../tools/filesystem_audit.py). Use original MyDOS
and SpartaDOS DOS read-back for selected changed allocation/linkage paths on
both sector sizes. Keep unchanged namespace behavior covered by focused cases.

Compare four controlled combinations: old/new COPY buffer with old/new
filesystem artifacts under the unchanged public ABI. Use one private benchmark
source image containing both command artifacts so disk placement is identical;
ship only the current COPY. Report time, effective throughput, physical
reads/writes, CPU work, BREAK latency and memory for each case. Make any speedup
claim only against matched measured inputs. Real-drive/accelerator timing needs
separate recorded hardware checks.

Refresh the user's bitmap shell without primes through
[build_demo.py](../../tools/build_demo.py), with OF816, the five-second autoboot,
matching system/WORK disks, pinned ROM/licenses and both old/new cartridge forms.
Exercise actual COPY SYS:LONG.TXT WORK:LONG.TXT, CMP, APPEND, BREAK and EXIT;
audit the persisted WORK image. Verify the final ZIP's files and checksums.
Keep manifests, benchmark media and test output outside it. Do not publish.

Update the write contract's group boundary when WP4 lands, and the mutation
ordering/reference, toolbox, plan index and roadmap as appropriate. Save a
history page and development JSON with measured costs, phase/failure outcomes,
input/artifact hashes and the executed scope; then mark this plan complete.

## Memory and validation gates

| Storage | Planned change |
| --- | --- |
| COPY upper-RAM buffer | 512 → 16,384 bytes: +15,872 bytes per loaded COPY image |
| TEE upper-RAM buffer | Unchanged 512 bytes |
| Shared mutation workspace | Reuse buffers/reservations; target at most +32 requested/rounded upper-heap bytes for group scalars |
| Per-file/per-mount objects | Target zero growth; reuse backend cursor storage |
| Fixed runtime/root/kernel/public-Task/idle/boot bank-zero reservations | **0 additional bytes in every slice** |

Count guards, alignment and unused reserved capacity. Report actual initialized
data/BSS placement, rounded heap use, code growth and filesystem-worker/Process
stack high-water marks. Keep existing Task/stack/DP/provider reservations.
Do not silently enlarge them if a checked build exceeds its limits.

Use the development tier: host/content/link checks and focused optimized
emitted tests for changed behavior. Use small raw/optimized probes if cursor
layouts, far-pointer behavior or another compiler-facing contract changes;
diagnose compiler defects in actionc rather than special-casing an Exec routine.
Do not duplicate full functional matrices in raw mode. Keep stack/domain guards,
register restoration, OS coexistence, bounded completion and request/ownership
retirement assertions relevant to the changed paths.

Completion requires the 16 KiB buffer, measured reduction in physical writes
and sequential traversal work, unchanged binary results and ownership/error
semantics, documented and measured bounded BREAK behavior, persisted/native
read-back evidence, unchanged bank-zero reservations, and the verified local
bitmap/cartridge preview. Release qualification and hardware speed claims
remain separate.
