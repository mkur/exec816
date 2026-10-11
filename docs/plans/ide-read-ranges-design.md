# Bounded IDE read ranges

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[IDE device](../reference/ideplus-device.md) ·
[Block adapter](../reference/block-io.md)

Status: accepted for implementation through the
[RR1–RR4 plan](ide-read-ranges-implementation-plan.md). Existing-file overwrite
batching is deferred.

Read up to four consecutive 512-byte IDE sectors with one device request and
one ATA command. Use the filesystem worker's shared staging buffer, publish only
successful complete reads, and preserve the DOS Read interface. The first target
is cold sequential reads of regular SpartaDOS files, including COPY.

## Motivation and scope

The completed [filesystem performance work](../history/filesystem-dos-performance.md#fp6c-bounded-ide-writes-and-final-checks)
reduces cold IDE COPY to 89 PAL frames (1.78 seconds), with 54 READ commands and
27 WRITE commands. Writes now combine contiguous new payloads; reads still
transfer one sector per request. Four adjacent uncached sectors can use one
READ instead of four, reducing command setup and request exchanges. Payload PIO
still transfers all four sectors. The throughput gain must be measured.

Apply ranges only to regular SDFS files on uniform 512-byte IDE mounts. Metadata,
directories, MyDOS, SIO, partial sectors and sparse holes retain their current
paths. Read only bytes covered by the current DOS request and the known file
extent; there is no speculative read ahead. COPY keeps its 16 KiB buffer.

## Device request and completion

Add `READ_SECTORS`, proposed command 14, and `MAX_READ_SECTORS=4` to
[ideplus.json](../../abi/ideplus.json), with a new ABI revision and generated
definitions. Keep READ_SECTOR and the IOStdReq layout unchanged. The raw physical
unit and readable APT units use the same range rules.

| Field or outcome | Proposed contract |
| --- | --- |
| `io_Offset` | First zero-based sector within the opened unit. |
| `io_Length` | 512, 1024, 1536 or 2048 bytes. |
| `io_Data` | Caller-owned writable span, retained through terminal reply collection. |
| Success | Full requested `io_Actual`, after every payload and terminal ATA status. |
| Failure or accepted abort | Zero `io_Actual`; destination may have changed and its contents are invalid. |

Validate the full extent before issuing ATA: reject empty, misaligned, oversized
and unit-crossing requests. Use subtraction for the remaining unit capacity to
avoid offset overflow. Buffer validity and lifetime remain caller obligations;
do not add RAM-map walks at each layer.

Program the existing LBA28 address/count registers once, issue ATA READ, wait
for each sector's DRQ, and call the existing native ReadWords primitive at
successive 512-byte destination offsets. Check terminal status after the last
sector. APT discovery and IDENTIFY retain their private 512-byte buffer.

## Shared staging and worker ownership

Grow only the adapter's allocated transfer buffer from 512 to 2048 bytes. Add a
separate transfer-buffer capacity constant: `SECTOR_BUFFER_BYTES` remains 512
because it also sizes file maps, mutation buffers and cache piece limits.
There is one staging buffer per filesystem service, shared by every mount and
handle. Allocate it once during service creation, including SIO-only sessions;
avoid another buffer, lazy allocation, or a new boot option.

Add a CARD `neededCount` beside `neededSector` in the shared filesystem
Workspace. Every backend explicitly requests one sector unless the regular-file
SDFS path selects a range. Initialize and retire this count with the operation
so metadata, cancellation and subsequent requests cannot inherit an old range.

The proposed BeginFetchRange operation takes the first sector and a count by
reference; it may reduce that count for cache boundaries. FSIO retains the
actual submitted count in neededCount for FinishFetchRange and the payload
consumer. A single-sector caller keeps the current BeginFetch/FinishFetch path.
The adapter owns one outstanding request; neither its buffer nor request can be
reused before exact reply collection, including cancellation and shutdown.

After successful completion, cache each sector from its corresponding staging
offset. The existing scratch tag may identify the first sector only; do not add
a second cache representation for the whole range. The immediately following
consumer uses neededCount to copy the validated range with one native Move and
advance completed/remaining bytes. An unsuccessful range copies no new bytes
to application storage and publishes no cache entries.

## Selecting sectors and using the cache

SDFS selects a candidate range from its already validated current map. Begin
with the current logical sector and include at most four references while:

- The file position is aligned and each sector lies wholly inside the remaining
  request and file extent.
- Every reference is nonzero and its physical sector is exactly the preceding
  sector plus one, using widened arithmetic for bounds.
- Every reference belongs to the same validated map page. Stop before the next
  map page, a sparse hole or a fragmented extent.

Use a single-sector request if fewer than two sectors qualify. Existing map
validation, ancestry checks and traversal bounds establish file structure;
range selection does not rescan the volume or weaken those checks. Sparse
sectors continue to clear the requested application bytes without disk I/O.

Check controller availability before serving any scratch/cache hit. If the
first sector is cached, serve it through the current path and reduce neededCount
to one. Otherwise, shorten the candidate before the first later cached sector
and fetch only the consecutive misses. A small cache presence helper checks all
pieces using the current tags, without copying data, changing replacement state
or charging speculative hits/misses. Count actual cache hits and admitted
sector misses once per sector. A disabled cache permits the full candidate.

For example, with four adjacent sectors and the third cached, fetch sectors one
and two together, serve three from cache, then reconsider four. Do not reread
the cached sector or create a scatter request. Cache payload capacity,
128-byte pieces, generation identities and replacement policy stay unchanged.

## Cancellation and transport errors

Keep queue, active-request and retirement policy in the IDE driver, using the
existing public Exec primitives. Queued/preparing cancellation may prevent
command issue. Once ATA READ is issued, drain the complete bounded range; do
not abandon an intermediate DRQ. An ordinary raw AbortIO can mark the issued
read aborted, but its reply waits for draining and reports zero actual bytes.
The filesystem's conditional TryCancel still declines issued ATA work.

After collection, the filesystem observes BREAK at its existing worker boundary
before consuming the new group. Earlier copied bytes retain the current Read
cancellation result and position semantics. Ordinary read errors retain the
existing DOS error/result behavior; this design introduces no partial transport
prefix, retry, or single-sector fallback after an issued range fails.

Timeout or absent media keeps the current offline/cold-reset policy. An ATA
error after range issue also requires cold reset: the driver must not accept
another request with uncertain remaining DRQ state. Local rejection and a
successfully drained abort leave the controller usable. READ_SECTOR's existing
error policy stays unchanged. Invalidate the affected volume's retained sectors
on failed completion; an offline controller retires its other mounts through
the current FSIO path. Physical errors take precedence over pending BREAK.

Keep the existing 250-tick deadline for each hardware wait. A four-sector read
has at most six waits: initial ready, four DRQ waits and terminal ready. Task
preemption and existing PBI word-pair IRQ/NMI protection remain in place; hold
no scheduler exclusion, selected PBI window or interrupt mask across the range.
Control messages continue to pump during the wait. No new worker or kernel
gateway operation is needed.

## Memory and code budget

| Resource | Proposed change |
| --- | --- |
| Shared upper transfer buffer | +1536 bytes, including its full unused capacity. |
| Shared upper Workspace | One CARD (+2 record bytes), rounded by the existing allocator. |
| Additional upper heap reservation | +1536 to +1544 bytes with current eight-byte heap alignment; record the emitted layout and actual rounded delta. |
| IDE controller buffer, request, per-mount and per-handle storage | No growth. |
| Cache payload and tags, COPY buffer | No growth. |
| Fixed, per-Task and idle reserved bank-zero bytes | 0 additional bytes, including guards, alignment and unused capacity. |
| Task stack/DP pools and Task count | No growth. |

Report emitted code growth and the complete IDE worker stack bound, including
interrupt reserve and dispatch margin. Measure filesystem stack headroom too;
do not enlarge Task pools to make the new path fit. Allocation failure uses
normal service startup failure and cleanup; do not add a second runtime profile.

## Validation and acceptance

Use the [development tier](../contributing/testing.md). Extend the existing IDE,
block-adapter and SDFS fixtures, reusing emitted builds and observers. Cover
1/2/3/4-sector reads, exact unit edges, invalid lengths and offsets, far destination
carry, fragmented maps, sparse holes, map transitions, partial heads/tails,
EOF, mixed cache hits and cache-disabled operation. Inject a later-sector error,
terminal failure, timeout, queued/active cancellation and selected NMI entries.
Check untouched application bytes for rejected/failed groups, cache publication,
one terminal reply, guards, cleanup and safe request/buffer reuse.

Use optimized behavioral and performance runs. Keep raw/optimized coverage small
and limited to the changed generated interface/internal layout boundaries;
do not duplicate full disk scenarios in raw mode.

Compare matched cold/warm IDE COPY against the completed performance baseline,
and isolate large regular-file reads with a non-console consumer. Record ATA
commands separately from PIO sector spans, gateway calls, frames and cache
statistics. Cold contiguous workloads must issue fewer reads and show a measured
improvement; warm cached reads and a representative SIO copy must show no
unexplained regression. Audit bytes independently and retain the actual pinned
compiler, ROM, BIOS, emulator and media inputs. Refresh demos only in a later
slice; development results do not qualify a release or real hardware.

Direct reads into application buffers, speculative read ahead, cross-map
gathering, ranges larger than four sectors, write buffering between DOS requests
and existing-file overwrite batching remain outside this design.
