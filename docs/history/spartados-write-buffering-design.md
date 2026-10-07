# SpartaDOS write buffering

[History index](README.md) · [Roadmap](../roadmap.md) ·
[Current write contract](../reference/filesystem-writes.md)

This preserves the design prepared before SB0–SB5 implementation. Its cost
model describes the earlier four-sector publication path. See the
[implementation plan](../plans/spartados-write-buffering-implementation-plan.md)
and [implementation and measurement record](spartados-write-buffering.md) for
completed development evidence and actual behavior.

Improve sequential file extension by retaining changed allocation and file
metadata across the payload groups of one DOS Write request. Write payloads
to disk immediately, then settle their metadata before replying. Keep the
four-sector cancellation checkpoints, the existing filesystem worker and the
current meaning of a confirmed Write result.

Start with this bounded change before considering metadata retained between
Write calls until Flush or Close. That later step changes public completion
semantics and needs a separate decision. MyDOS keeps its current write path.

## Cost before buffering and native references

For ordinary SDFS extension, [TakeGroup](../../lib/fs/fsalloc.act) writes the
bitmap and sector 1 free count. [Extend](../../lib/spartados/sdfswrite.act)
then writes the payloads, sector map and directory length. A four-sector group
normally costs four payload writes and four metadata writes. Map transitions
and directory records crossing sectors cost more.

The [existing measurements](../history/write-performance.md) show that the
filesystem contributes most of COPY's write cost. Increasing the command's
buffer to 16 KiB reduces DOS calls, but the filesystem still repeats those
metadata writes inside each call. The general sector cache retains confirmed
bytes; it does not coalesce writes.

BW-DOS 1.5 provides a useful native reference. PRIDEL changes an allocation bit,
marks its buffer dirty through ZMENEN and adjusts the in-memory free count.
Buffer replacement calls SIO_W_BUF; close updates drive metadata and drains
dirty buffers for that drive. The close loop selects buffer slots rather than
enforcing a bitmap, map and directory dependency order. These sources support
buffering, not a claim that every SpartaDOS implementation writes a bitmap
exactly once per file. See the pinned
[allocation and buffer manager](https://github.com/HolgerJanz/BW-DOS/blob/e65d60e8176649e0fb5e705665a73f91c1aeb524/1.5/SOURCES/XBWFMS.ICL)
and [close path](https://github.com/HolgerJanz/BW-DOS/blob/e65d60e8176649e0fb5e705665a73f91c1aeb524/1.5/SOURCES/XBWCIO1.ICL).

One bitmap sector represents 1,024 sector numbers on 128-byte media or 2,048
on 256-byte media. File maps hold 62 or 126 payload pointers respectively.
Allocation bits still change for every sector; physical metadata writes occur
at explicit publication boundaries.

For an illustrative 16 KiB extension on 256-byte media, assume 64 new payload
sectors fit within the current map and one bitmap page, with a directory record
contained in one sector. Exclude creation, Open and Close:

| Physical writes | Earlier groups | Proposed request buffering |
| --- | ---: | ---: |
| Payload | 64 | 64 |
| Bitmap | 16 | 1 |
| Sector 1 free count | 16 | 1 |
| Sector map | 16 | 1 |
| Directory length | 16 | 1 |
| Total | 128 | 68 |

This is a write-count model, not a measured speedup. Actual counts depend on
map position, fragmentation, bitmap boundaries and directory placement.

## Metadata retained during one Write

The filesystem worker owns one active batch for its current SDFS Write packet.
The batch ends before that packet is replied to or another packet is selected.
It therefore needs neither per-file sector buffers nor a general dirty cache.

Retain one private bitmap page, its sector identity and the working free count.
Use the existing mutation workspace's map buffer for the current file map.
Keep the pending length and allocation count with the working file cursor.
Record dirty flags, bytes staged since the last publication, and a snapshot of
the last confirmed position, extent and traversal state.

Preflight each group using the working bitmap and free count. Reserved sectors
must become unavailable in that working state before another group searches
for space. Add map pointers only for payloads whose complete group succeeded.
Use the retained dirty map when locating the next position in the same page;
reloading an older copy from BLOCKIO would lose pending pointers.

Keep directory traversal separate from the retained file map. RowIO currently
uses the same map scratch while locating a directory record. Publish the file
map before entering RowIO, then invalidate its working identity and reload it
if extension continues. Never retain a pointer into shared scratch across a
routine which repurposes that scratch.

The existing BLOCKCACHE remains a cache of confirmed disk bytes. Allocation
and map access inside the active batch consult the working copies first.
Physical publication uses the existing BLOCKIO invalidation and verified-write
path. Dirty working copies must never be inserted into the clean cache.
Correctness must also hold with CACHE-BLOCKS set to zero.

## Ordered metadata publication

A checkpoint settles one batch using this order:

1. Collect all submitted payload writes. Newly allocated payloads receive their
   caller bytes in one write; add no preliminary zero-sector write. Preserve
   current partial-sector and padding behavior.
2. Write the changed allocation bitmap page, recording the new sectors as used.
3. Read sector 1 into existing scratch, change its free count and write it.
   Preserve the rest of that short boot sector.
4. Write the changed file map with its completed payload pointers.
5. Publish the directory length while keeping the native incomplete flag set.
   Complete both sectors when the 23-byte record crosses a sector boundary.
6. Promote staged bytes and cursor state to the confirmed prefix, advance the
   mount's metadata epoch and clear the batch's dirty state.

Every dependent write waits for verified completion. A published map must not
refer to newly allocated sectors whose bitmap bits are still free on disk.
Publishing directory length comes after the allocation and map it describes.

Force a checkpoint before replacing the bitmap page or file map, before using
the existing map-growth path, at request completion, and when stopping early
for BREAK or an ordinary capacity error. Map transitions retain their current
immediate path: reserve and initialize a new map before linking it, then
publish its payload and extent. Resume buffering in the new map afterwards.
An allocation scan must settle a dirty bitmap before replacing its page, even
when it has not yet found a candidate on the next page.

Partial existing-sector writes and ordinary overwrites keep their current
completion path. Drain pending extension metadata before entering that path,
then establish a fresh confirmed boundary. Create, Open, truncate, directory
growth, delete and rename retain their existing mutation protocols.

## Results and cancellation

Distinguish bytes whose payload has been written from bytes whose required
metadata has been confirmed. Only the latter count advances
operation.completed and becomes a public Write result. A full successful
Write still means all its required writes have received peripheral confirmation.
No dirty metadata survives a successful or normally canceled reply.
Locate the next caller bytes using the confirmed count plus the staged count;
the confirmed counter alone no longer identifies the next payload group.

Between payload groups, allow other Tasks to run and pump filesystem control
messages. The four-sector limit bounds payload work before checking BREAK;
it does not force metadata publication after every group. Once a group starts
physical mutation, finish that group before handling cancellation.

If BREAK arrives with staged groups, stop accepting more payload, settle their
metadata and return the confirmed prefix with ERROR_BREAK. BREAK before the
first physical mutation leaves disk unchanged. If the entire requested payload
was accepted and its final checkpoint succeeds, return full success, preserving
the existing rule for late cancellation. Validate the whole request's mapped
buffer and 24-bit extent before mutation, retaining the current admission
rules. Disk full during a valid request settles any staged prefix before
returning its causal error.

[FSABORT](../../lib/fs/fsabort.act) currently replies to canceled Writes
directly. It must route an active buffered SDFS Write through its drain state
before replying or invalidating working buffers.
[FSWRITEIO.Checkpoint](../../lib/fs/fswriteio.act) must likewise direct pending
cancellation to a drain instead of immediately reporting a mutation error.
Apply the same rule to every early reply path. Do not keep service.committing
set for the whole request, which would suppress cancellation. Set it only while
finishing a submitted payload group or an ordered metadata checkpoint.

Track pending physical mutation independently of that cancellation flag.
The current per-group reset of service.changed must not hide unconfirmed
physical changes from later error handling. Expected logical errors select a
drain and reply; a physical failure selects mount invalidation.

## Errors and interrupted writes

If data or metadata completion fails or becomes uncertain, retain the causal
I/O error, invalidate the mount and its caches, and discard working metadata
after all submitted I/O is collected. Do not retry an uncertain write or free
its reservations speculatively. Report only the prefix confirmed at an earlier
complete checkpoint; a failed first checkpoint can therefore return -1 even
when payload bytes reached the disk. Restore the public cursor to that prefix
and invalidate its unconfirmed traversal state.

A metadata checkpoint can cover more payloads than the current four-sector
commit, so a later failure can report a shorter confirmed prefix than it does
today. Update the documented commit-unit bound when implementing this design;
the rule that returned bytes have settled metadata remains unchanged.

A transport error during a cancellation drain takes precedence over BREAK.
Terminal Close still consumes its handle on failure. Existing Process and
shell cleanup must preserve an earlier error and report a later Close error
when it is the only failure.

Publication is not atomic and adds no journal. RESET before bitmap publication
can leave unreferenced payload bytes in sectors still marked free. RESET after
bitmap publication can leave lost allocation, an incorrect free count, or map
contents beyond the last published length. Records may be torn. The incomplete
flag remains the indication of an unfinished writer; lightweight mounting does
not establish that such media is safe to write again. Recovery remains an
external check or restoration of a known-good image.

## Flush and Close

In the first version, each Write drains before replying. Flush therefore keeps
its existing behavior and leaves the incomplete flag set. Only the final Close
of a shared writable backing clears that flag, after confirming its published
extent. Inherited handles retain their existing writer lease and shared cursor.

If metadata is later retained between Write calls, Flush must settle the
handle's dependencies while retaining its lease and incomplete flag. Last
Close must settle data, allocation, maps and length before clearing the flag
in a final confirmed write. Writing a split record with the flag cleared in
its first sector must not expose an incomplete length in its second sector.

That later design must define what Write acceptance means, how late errors are
reported, and ownership/coherence across multiple writers and mounts. It also
needs retained state beyond one packet. Those semantics are not introduced by
the initial request-scoped design.

## Memory and integration

Keep all sector buffers and batch state in the existing worker's upper-RAM
mutation allocation. Reuse its 256-byte data, map and scratch buffers and
23-byte record. Budget at most 384 additional requested bytes: 256 for a bitmap
page and up to 128 for identities, dirty flags, counts and confirmed snapshots.
There is no full sector 1 buffer; its working free count is a scalar.

The current mutation allocation is 878 requested / 880 rounded bytes. The
proposed ceiling is 1,262 requested / 1,264 rounded bytes, an increase of at
most 384 rounded heap bytes with the current eight-byte rounding. This is one
shared cost whenever the mutation workspace is allocated, including a MyDOS-only
writable configuration if the same record is enlarged. Per-mount and per-open
sector-buffer costs remain zero. Allocate storage at worker startup; allocation
failure must precede writable handle publication and file mutation.

Target reserved bank-zero changes are 0 fixed runtime, 0 root/kernel, 0 per
public Task, 0 idle and 0 boot-only bytes, counting guards, alignment and unused
pool capacity. Existing stacks, direct pages and Task slots are reused. Measure
emitted stack peaks and resident code growth before accepting the implementation;
these budgets are design limits, not implementation measurements.

Keep buffering policy in the filesystem backend and common filesystem worker.
No public kernel operation, command import or disk-format change is required.
Public Write, Flush and Close signatures and completion semantics remain the
same. Rebuild the resident system and matching commands for integration.

## Validation and delivery

Implement this as one current SDFS path with explicit publication boundaries.
Use the existing write fixtures and performance harness with frozen baseline
images; do not retain a second runtime implementation for comparisons.

Development acceptance needs:

- Both sector sizes, cache disabled and enabled, fragmented allocation, bitmap
  boundaries, full/new maps, split directory records and a partial final sector.
  Verify exact bytes, free counts, map ownership and unrelated file preservation
  through the independent host audit and selected native DOS read-back.
- Read/Write/Seek and append after reopen, inherited writers, alternating writes
  to separate files and mounts, directory enumeration epochs and cleanup. No
  dirty state or borrowed pointers may survive packet retirement.
- Physical BREAK before mutation, between payload groups and during metadata
  drain; disk full after a staged prefix; failures/lost completion at each
  publication stage; terminal Close errors and mount-offline behavior. Confirm
  exact reported prefixes and continued ownership retirement.
- Diagnostic RESET cuts at the ordering boundaries, inspected by the host audit.
  These cases establish the documented damage envelope, not automatic recovery
  or sector-atomicity guarantees.
- Focused raw/optimized probes for changed emitted record layouts or compiler
  interfaces. Run functional, lifetime and performance integration optimized,
  retaining stack/domain guards and OS-restoration assertions.

Measure physical reads and verified writes by payload, bitmap, header, map and
directory, plus guest time from source Open through destination Close. Compare
the same real COPY artifact, 16 KiB buffer, source bytes and target layout;
include cold/warm source cases and accurately timed 128/256-byte SDFS targets.
The illustrative 64-sector case should reach its modeled 68 writes under its
stated conditions. Record boundary costs and BREAK latency separately. A lower
write count alone does not establish a hardware speedup or qualify transport
profiles. Keep the existing MyDOS deadline issue outside this change.

After executable checks, update the write contract, mutation protocol and
development record together, then refresh the matching demo packages. Full
release qualification remains a separate activity under the
[testing policy](../contributing/testing.md).
