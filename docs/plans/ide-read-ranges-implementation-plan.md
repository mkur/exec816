# Bounded IDE read ranges implementation plan

[Implementation plans](README.md) · [Design](ide-read-ranges-design.md) ·
[Roadmap](../roadmap.md) · [Testing policy](../contributing/testing.md)

Status: RR1–RR2 pass development checks; RR3–RR4 remain. See the
[execution record](../history/ide-read-ranges.md).
Implement and commit one executable slice at a time. The design
sets the scope: at most four native 512-byte IDE sectors, shared staging,
validated regular-file maps and no change to DOS Read results. Existing-file
overwrite batching stays deferred. Demo builds and publishing are separate work.

## RR1 Device command

Add READ_SECTORS=14 and MAX_READ_SECTORS=4, increment the device ABI revision,
record completion/cancellation semantics in abi/ideplus.json and regenerate the
shared definitions. Extend extent admission to read ranges. Use the existing
ReadInto path with a count argument: one ATA READ, one DRQ/PIO step per sector,
and terminal status. Keep discovery and READ_SECTOR at count one.

Retain driver-owned queue/claim/abort policy and PBI word-pair protection.
Successfully drain issued reads before an aborted reply. An ATA error after an
issued READ_SECTORS marks the controller offline; admission errors and drained
aborts do not. Keep timeout/absence behavior and READ_SECTOR's error policy.

Extend the bounded-range fixture/runner for raw reads of 1/2/3/4 sectors, raw and
APT units, partition edges, invalid lengths/offsets, destination bank carry,
queued/active abort, terminal and later-sector failures. Check one reply, guards,
media unchanged, controller retirement and ownership cleanup. Use one small
raw/optimized interface probe; ordinary lifecycle cases run optimized. Run the
generator check and host suite. Update the current device reference.

Bank-zero reservation delta: 0 fixed / 0 per-Task / 0 idle bytes. No controller,
request, stack or DP allocation grows. Record the emitted worker call bound.

## RR2 Adapter and cache

Add a distinct 2048-byte transfer-buffer capacity and use it only to allocate/free
the adapter buffer; SECTOR_BUFFER_BYTES remains 512. Add a cache presence query
that checks every piece without copying, replacing or changing counters.

Implement BeginFetchRange with an in/out count and FinishFetchRange. Reuse the
ordinary single-sector hit path for a cached first sector. On a first-sector
miss, stop before any later cached sector and issue only the consecutive misses.
Check availability before all hits. Count served hits/admitted misses once per
sector. Exact successful completion publishes each staged sector independently;
failure publishes none and retains current invalidation. The scratch tag names
only the first sector. Sources/destinations and requests stay owned until exact
terminal collection. SIO remains single-sector.

Add focused emitted adapter checks using real IDE media for cache boundaries,
first hits, partial cache pieces, cache-disabled reads, exact lengths, offline
rejection and reuse. Cover allocation failure/cleanup for the enlarged buffer
and one existing SIO adapter case. Update allocation-fault transforms and the
block/cache references. Keep record layouts and cache capacity unchanged.

Upper allocation delta: +1536 bytes for the existing shared buffer. Bank-zero
delta stays 0 fixed / 0 per-Task / 0 idle; no Task pool or cache arena grows.

## RR3 Filesystem range selection

Add CARD neededCount to Workspace beside neededSector. Update all sector-needing
backends together so ordinary metadata/MyDOS/SIO requests explicitly set one;
reset the count when operations begin/retire. Dispatch ranges through FSIO and
retain the actual count returned by the adapter until the consumer runs.

SDFS selects at most four adjacent, nonzero references from the already validated
current map only for aligned complete regular-file sectors on IDE. Stop at the
requested extent, EOF, partial sectors, holes, fragmentation or map boundaries.
After full successful completion, Consume copies the group once and advances
the operation by exactly its bytes. Preserve sparse clearing, single-sector
partial reads, existing failure positions/results and BREAK checkpoints before
consumption. Directory/bootstrap reads and file measurements stay single-sector.

Extend emitted SDFS checks through the real adapter for contiguous and fragmented
maps, sparse holes, map transitions, partial heads/tails, small requests, EOF,
mixed cache state and disabled cache. Inject failed ranges and BREAK before
consumption, checking application bytes, Read results/IoErr, cursor position,
subsequent operations, exact reply retirement and guards. Add a small
raw/optimized internal layout/access probe; run functional coverage optimized.
Rebuild affected fixtures and update the SDFS/block references.

Workspace grows by two record bytes; record its actual old/new emitted sizes and
eight-byte-rounded allocations. Combined extra upper heap reservation must stay
within +1536..+1544 bytes. No per-handle/per-mount growth; bank-zero delta remains
0 fixed / 0 per-Task / 0 idle, including guards/alignment/unused capacity.

## RR4 Measurement and completion

Reuse the completed FP6 native COPY baseline and compact evidence. Build the new
loaded IDE COPY once, then reseed media for matched cold and warm runs. Extend
the existing observer for an isolated regular-file read into a non-console sink;
compare identical baseline/current scenarios rather than console rendering.
Distinguish ATA commands from PIO sector spans and logical cache accesses.

Record elapsed frames, gateway calls, command counts, cache statistics, exact
bytes/allocation audits, emitted code growth, IDE worker stack bound and observed
filesystem stack headroom. Include one matched accurately timed SIO copy against
the existing baseline. Keep the pinned compiler/ROM/BIOS/emulator inputs and
record observer changes. Require fewer commands and measured improvement on
cold contiguous IDE reads, with no unexplained warm/SIO regression. Reuse stable
builds; do not repeat unrelated boot/GUI or release qualification matrices.

Write a compact development result and an execution record, link them from the
plan/history indices, and update the roadmap/design status. Run the host suite,
generator check and changed-document content/link checks. Commit the completed
slice. Report actual development scope, remaining limits and memory costs;
these results do not qualify physical hardware or a release.
