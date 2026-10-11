# Filesystem and DOS performance

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[Filesystem writes](../reference/filesystem-writes.md) ·
[Platform memory budget](../reference/platform.md#bank-zero-memory-budget) ·
[Testing policy](../contributing/testing.md)

Status: implementing; FP0 measurement tools and retained IDE baseline are
ready. See the [execution record](../history/filesystem-dos-performance.md).
Implement one executable
slice at a time, record its development results and memory costs, and commit
before starting the next slice. This plan does not authorize publishing a demo
or release.

Reduce CPU work in ordinary reads, writes and cached operations on both SIO and
IDE Plus. Start with the existing DOS ABI, serialized filesystem worker, sector
cache and driver request lifetimes. Keep COPY's 16 KiB buffer.

## Design decisions

An implementation plan is sufficient for FP0–FP5: these use existing memory
primitives, remove repeated work and preserve public semantics. FP6 first adds
a short design appendix to this plan before changing cache representation,
transfer buffer ownership or the IDE range interface. A separate general
filesystem design document is unnecessary.

Keep these contracts throughout:

- Successful Write settles its required payload and metadata before replying.
  No dirty metadata survives between Write requests. Preserve SDFS publication
  order, confirmed prefixes, incomplete flags and terminal Close handling.
- Keep groups of at most four new payload sectors and their existing BREAK
  checkpoints. Control messages continue to pump during committed I/O.
- Devices own queues, active requests, cancellation and shutdown. Use ordinary
  public Exec primitives; add no private combined driver/kernel services.
- Correct API use and live application buffers are caller responsibilities.
  Establish internal resources at creation/open instead of repeatedly proving
  their RAM mapping. Retain operational errors, ownership transitions and
  synchronization. Stack/domain guards and IRQ/NMI coordination stay intact.
- Preserve sparse reads, partial-sector updates, odd lengths and far-pointer
  carry. Initialize new payload bytes once; fill only the unused tail. Keep
  directory/map initialization and format-required MyDOS trailers.
- Keep lightweight mounts. Do not add fsck, whole-volume ownership scans,
  journals, additional workers or compatibility implementations.

## Baseline and attribution

The investigation at Exec816 `bd8c31a` used the compiler selected by
[actionc.json](../../toolchain/actionc.json), the ROM/emulator/BIOS configuration
in [altirra-ideplus.json](../../toolchain/altirra-ideplus.json), PAL 8× CPU,
native 512-byte SYS/WORK partitions, a 64 KiB sector-cache payload and no primes.
COPY transferred 23,872 bytes using its 16 KiB buffer. Timing covers source Open
through destination Close, excluding command loading and driver initialization.

| Observation | Current IDE COPY |
| --- | ---: |
| Guest elapsed time | 151 frames / 3.02 s |
| Physical reads / writes | 54 / 61 |
| Payload reads / writes | 47 / 47 |
| Metadata reads / writes | 7 / 14 |
| Gateway calls / Task switches | 2,580 / 306 |
| Forbid / Permit pairs | 851 |
| Cache hits / misses / evictions | 48 / 54 / 4 |

The matching driver-only payload copy took 0.98 s for 47 reads and 47 writes.
It omits filesystem metadata and lifecycle work, so the difference is not an
exclusive filesystem-time measurement. Ready returned on the first status read
in every observed case; no timer sleeps or volatile-cache flushes occurred.
Bitmap buffering already works: this COPY made three bitmap writes.

Local artifacts are in `build/ide-copy-performance/analysis.json` and its
referenced outputs. FP0 promotes the compact evidence and reproducible observers;
large images and traces remain under `build/`. The bridge truncates CPU profile
addresses, so its existing profile cannot assign exclusive upper-bank routine
percentages. The per-service breakpoint trace matches the gateway counter;
debugger-paused runs supply counts, not throughput.

## FP0 — Preserve measurements and add shared-path coverage

Extend [IDE measurement](../../tools/measure_ide_write_performance.py) and
[SIO measurement](../../tools/measure_write_performance.py), rather than adding
a second benchmark framework. Retain the current IDE machine code and fresh
media as the comparison baseline. Record hashes, cache settings, guest frames,
physical requests, copied bytes and gateway counts. Keep observer overhead
explicit and replay without intrusive observers when reporting timings.

Add matched cold-source and warm-source copies to fresh destinations. Use one
primary SpartaDOS SIO case with accurate Generic 57600 timing and a focused
MyDOS case. Cover 128/256-byte SIO and 512-byte IDE functionally where changed;
do not run a release matrix for each slice. Include an existing-file writable
Open case separately from fresh creation, since its validation cost differs.

Retain successful output bytes, allocation audits, cleanup and guards alongside
performance records under `docs/development`, with an execution page linked
from `docs/history/README.md`. Reuse the captured baseline when inputs match.

## FP1 — Use native bulk copies

Replace the payload loops in
[SDFSFILE.Consume](../../lib/spartados/sdfsfile.act) and
[MYDOSFILE.Copy](../../lib/mydos/mydosfile.act) with `A816MEMORY.Move`.
Select `A816MEMORY.Clear` once for a sparse SDFS span instead of branching for
each byte. Copy exactly the requested span; exclude MyDOS's three trailer bytes.

Replace the staging loop in
[BLOCKIO.BeginStore](../../lib/io/blockio.act) with `A816MEMORY.Move`, retaining
the source-equals-scratch case. Use the existing native fill primitive for
unused tails and metadata zeroing in changed routines; do not restore preliminary
zero-sector writes. Add no handwritten assembly or compiler special cases.

Check zero, odd and partial lengths, sector edges, sparse reads, overlapping
Move semantics where applicable, and buffers crossing a 64 KiB boundary.
Reuse the [sector-copy fixture](../../tests/programs/sector_copy.act), MyDOS
file checks and block-store checks. Run a loaded IDE COPY and one SIO COPY;
physical request counts and publication order must remain unchanged. Report
copy-loop timing separately from whole-COPY throughput.

## FP2 — Validate resources once

Trace each ordinary Read/Write from
[DOSCALLS](../../lib/dos/doscalls.act) through the handler and block adapter.
Write down which layer owns each check before deleting it. Pass the resolved
DOS slot, object and mount through helpers; remove the duplicate FromHeader
lookup on Write and repeated immutable handle/binding checks downstream.

Remove mapping checks of private buffers already established by allocation,
including BeginStore's filesystem staging buffer. Remove repeated public-buffer
mapping walks across DOS, filesystem and driver layers under the caller
responsibility rule. Retain negative lengths, supported commands, geometry and
sector bounds, read-only/offline errors, transfer lengths and actual completion.
SIO may still validate protocol/profile constraints at the request boundary.

Keep mount references, writer leases, active request ownership, removal guards
and reply collection. Update current callers and tests together; do not add a
trusted/untrusted compatibility profile. Update the authoritative references
where caller responsibilities were previously described differently.

Run focused DOS transfer/inheritance/Close and block/SIO driver checks, including
short transfers, physical errors, concurrent ownership and cleanup. Retain
guards and OS restoration. Wrong-use checks deliberately removed from the
contract should not remain advertised as supported error cases.

## FP3 — Invalidate only affected filesystem metadata

Separate scratch-map validity from directory/extent-cache invalidation in
[SDFS](../../lib/spartados/sdfs.act) and
[FSWRITEIO](../../lib/fs/fswriteio.act). A payload-sector write must not discard
an unrelated volume's completed directory measurements. Preserve read maps
whose sectors and volume incarnations are unaffected.

Invalidate affected metadata before publication can expose changed bytes.
Extent/namespace changes still invalidate the affected mount's measurements;
ExNext's existing mount-wide mutation epoch remains unchanged. Keep exact
sector invalidation in BLOCKCACHE before writes. Failed or uncertain mutation
still invalidates the mount and its caches broadly.

Retain a writer's current staged map and allocation state while their ownership
and identity remain valid. Avoid re-fetching/re-validating a known map merely
because another payload completed. Keep map/bitmap replacement drains intact.

Check alternating SYS reads and WORK writes, same-volume changes, map transitions,
warm DIR/Examine before and after mutation, generation reuse, cache-disabled
operation and failed publication. Verify exact lengths, block counts, dates and
enumeration errors; a stale cache hit is a failure. Existing directory and SDFS
buffering fixtures supply these cases.

## FP4 — Make selected-file validation cheaper

In [SDFSWRITE.Validate](../../lib/spartados/sdfswrite.act), replace the quadratic
comparison against all preceding pointers with an in-place O(n log n) sort and
adjacent comparison of each map's populated references. Reuse the idle mutation
data buffer: a 512-byte map has at most 254 references, requiring 508 bytes.
Leave the original map intact and preserve the current per-map duplicate-check
scope. Introduce no whole-volume ownership table or per-file allocation.

Retain the current bitmap page during allocation checks instead of repeatedly
copying/reloading it for every bit. Give that temporary validity an explicit
lifetime; map reads, scratch reuse, mutations and volume changes retire it.
Preserve sparse-writer rejection, map links, allocated-bit errors and bounded
chain traversal. Reuse validated current-page facts within a writer's lease.

MyDOS has no equivalent quadratic map check. Preserve its required chain walks
for trailer/extent discovery and reclamation. Reuse existing cursor and known
extent facts only where lifetime and mutation state establish their validity.

Measure writable Open for a populated map and a map-spanning file separately.
Check duplicates at different slots, malformed links, allocation errors and
ordinary replacement/append. Record comparisons, bitmap fetches and guest time;
fresh-destination COPY must not acquire additional scans or physical reads.

## FP5 — Reduce driver coordination crossings

In the IDE and SIO workers, combine shutdown checking and dequeue/active-request
publication under one Forbid/Permit pair. Inspect other immediately adjacent
driver-owned transitions for the same opportunity. Keep queue removal and
active publication atomic with AbortIO; preserve STOP wakeups and draining.

Do not remove exclusion solely because GetMsg/ReplyMsg have their own atomic
queue operations: surrounding driver state can require a wider transaction.
Never hold Forbid or an IRQ mask across physical I/O. Preserve the native gateway
fast paths and stack/context checks. Any public ABI proposal requires a reusable
operation, not a private shortcut for one driver.

Use targeted cancellation/shutdown/preemption cases around claim, first
submission and reply, plus the unchanged COPY benchmark. The primary acceptance
is fewer gateway calls for the same request trace, with byte, ownership and
bounded-completion checks passing. Report elapsed time independently.

## FP6 — Design and measure remaining data-path changes

After FP1–FP5, add a short design appendix here for each remaining change that
measurements justify. Set buffer ownership, cache-budget accounting and error
semantics before implementing it. Use separate executable sub-slices:

1. **Direct complete-sector transfers.** Remove redundant filesystem/block/IDE
   staging where a submitted caller span remains valid and immutable until
   reply. Keep partial-sector assembly, MyDOS trailers and final-tail filling.
   Define cache publication from the actual completed source; preserve failure
   invalidation and lifetime through cancellation. SIO already uses the block
   buffer directly and must not gain an IDE-style bounce buffer.
2. **Sector-sized cache entries.** Compare reducing the current piece bookkeeping
   against storing one tag per physical sector. Select one implementation and
   migrate all consumers. Preserve the configured byte budget, mixed volumes,
   short boot sectors, generation identity, write invalidation and the no-cache
   path. Benchmark both cached reads and write publication before choosing.
3. **Bounded IDE ranges.** Carry consecutive SDFS extents into bounded requests
   when useful after the preceding fixes. Define partial completion, io_Actual,
   cancellation and metadata dependencies in machine-readable ABI inputs and
   current references. Keep the four-payload extension bound initially. SIO
   continues to issue standard single-sector wire commands; do not invent a
   multi-sector SIO protocol. Update callers and emitted fixtures together.

For each sub-slice, require a measured improvement in its target workload and
no unexplained regression in the other transport. If a proposed cache/range
change has no material benefit after the simpler fixes, record the result and
leave that implementation pending. Do not change successful Write's settlement
contract to reduce the already buffered metadata-write count.

## Memory and completion

FP0–FP5 target **0 additional fixed, per-Task and idle reserved bank-zero
bytes**, counting guards, alignment and unused capacity. Reuse current upper
buffers; FP4's validation references fit the existing 512-byte data buffer.
Record code size, actual stack bounds and any small upper-record changes per
slice. Do not enlarge Task pools as a performance shortcut.

FP6 must publish its upper-RAM payload/metadata and per-request costs before
implementation, retain the configured cache budget and target the same zero
bank-zero delta. New or enlarged reservations require justification against the
platform budget. Keep compiler inputs at the recorded pin; compiler defects
belong in actionc with focused regressions.

Use the development tier: host checks after coherent code edits and the smallest
optimized emitted-code cases affected by each slice. Raw/optimized pairs apply
only when a compiler/ABI boundary actually changes. Reuse stable artifacts and
observers; do not repeat unrelated boot, GUI or full release matrices.

Finish with matched cold/warm IDE and representative accurately timed SIO
copies, populated-file Open, and warm listing checks. Independently audit bytes
and allocation; report physical requests, kernel calls, timing, memory and
remaining limits by slice. Update the execution record and relevant references.
These development results do not qualify physical hardware or a release.
