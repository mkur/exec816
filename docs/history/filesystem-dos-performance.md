# Filesystem and DOS performance execution

[Plan](../plans/filesystem-dos-performance-implementation-plan.md) ·
[Historical records](README.md) · [Testing policy](../contributing/testing.md)

Development checks use the pinned compiler and AltirraOS ROM. These results
are emulator development evidence, not hardware or release qualification.
All slices retain 0 additional fixed, per-Task and idle bank-zero bytes,
including guards, alignment and unused capacity. Stack pools are unchanged.

## FP0: baseline and observers

The [retained baseline](../development/filesystem-performance-baseline.json)
records the exact compiler, ROM, emulator, BIOS and media inputs. Loaded COPY
moves 23,872 bytes through its 16 KiB buffer. Cold IDE takes 151 PAL frames
(3.02 s), 54 reads, 61 writes and 2,580 gateway calls. Warm source takes
122 frames (2.44 s), 4 reads and the same 61 writes. Both independently pass
persisted-byte and allocation audits. Timing excludes command loading and
controller initialization; observers add calls and counters, so comparisons
must use matching observers.

`measure_ide_write_performance.py --from-build DIR --warm-source` replays the
retained native image against newly generated media. The shared SIO observer
now accepts the transport-neutral IOStdReq and reads its SIO extension only
in SIO measurements. Both tools collect native gateway/Task-switch deltas.
The release-host compiler binary uses the same pinned inputs and emits the
same optimized target code; it is not a compiler override.

Reproduce the SIO baseline with a current source image containing COPY16 and
LONG.TXT:

```sh
python3 tools/measure_write_performance.py --source-image SOURCE.atr \
  --filesystem sdfs --size 256 --buffer 16384 --create-only --output DIR
```

The SIO case uses accurate Generic 57600 timing and fresh destinations for
cold/warm source runs. Large images, traces and complete build inputs remain
under `build/filesystem-performance/`. Host checks: 447 passed.

The uninterrupted SDFS copy loop takes a median 2,252.3 µs for 128 bytes,
968.0 µs for 55 bytes and 4,504.2 µs for 256 bytes in the isolated emitted
fixture. The current compiler shares its return epilogue; the observer accepts
one or two RTL exits and still verifies its single byte-loop boundary.

## FP1: native transfers

SDFSFILE, MYDOSFILE and BLOCKIO now use the existing native Move primitive.
Sparse spans and unused new-sector tails use Clear; no preliminary zero-sector
writes were added. MyDOS trailers and partial-sector bytes remain intact.

The transfer portion of Consume is 167.3 µs for 128 bytes, 86.2 µs for 55
bytes and 311.2 µs for 256 bytes. Loaded IDE COPY falls from 151 to 111 frames
(3.02 to 2.22 s), retaining exactly 54 reads and 61 writes. Accurate SIO
256-byte COPY changes from 1,953 to 1,941 frames, retaining 101 reads and
108 writes; mechanical timing dominates. Baseline MyDOS 128-byte writes take
3,922 frames with 99 reads and 341 writes; it is a different format/workload,
not a throughput comparison with SpartaDOS.

Optimized emitted checks pass for SDFS 128-byte sparse/partial reads, MyDOS
256-byte reads/seeks/corruption/trailers and 70,003-byte far buffers, and real
block writes including an external buffer crossing a bank boundary, short
boot sectors, cache-disabled operation, failed completions and persisted
neighbours. The old MyDOS host provider now reuses existing test-only bank-zero
scratch, avoiding far-write injection while native code spins. Its unmapped
address case uses bank $40; bank $10 is valid in today's 4 MiB profile.

[Compact results](../development/filesystem-performance-results.json) retain
code size and hashes. Production records/buffers and stack reservations are
unchanged: bank-zero delta 0 fixed / 0 per-Task / 0 idle. Guards and Task
cleanup pass; these are bounded checks, not exact worst-case stack proofs.

## FP2: one transfer admission

DOS still resolves an owned handle once and retains its mount before queuing.
Write no longer calls FromHeader twice. The filesystem handler consumes that
resolved object; it no longer searches the same ownership list or checks the
same immutable mount binding again. Caller buffers are live objects by API
contract. DOS, RAM/MyDOS/SDFS reads, common write admission, block staging and
SIO no longer repeat RAM-map walks. SIO keeps direction/profile/timeout and
wire-length validation. Geometry, busy state, read-only/offline errors, exact
completion, references, leases, cancellation and reply collection remain.

Optimized loaded IDE COPY passes with 54 reads / 61 writes, 110 frames and
2,528 gateway calls. The queued Generic 57600 SIO fixture passes its protocol,
concurrency, reply-reuse, cleanup and guard checks. The current-kernel DOS
transfer fixture passes 10 assertions for NIL, negative counts, zero transfers,
Close and context cleanup. The older headless NIL runner lacks today's generated
console dependencies and was not used as evidence; its removed wrong-use
assertion counts are updated. Host checks: 447 passed.

Validation ownership is documented in [DOS](../reference/dos.md#transfer-ownership)
and [block I/O](../reference/block-io.md). No record layout, buffer, fixed,
per-Task, idle or stack reservation changes; bank-zero delta remains zero.

## FP3: affected-sector and mount invalidation

FSWRITEIO distinguishes regular payload stores from metadata publication.
SDFS invalidates the exact changed map tag and, for metadata, only the matching
volume incarnation's directory and extent measurements. Uncertain mutations
still retire scratch/extent state broadly and disable the affected mount.
BLOCKCACHE continues exact sector invalidation before submission. Namespace
mutation epochs and successful Write settlement are unchanged.

Optimized SDFS 256-byte checks retain a real measured extent and map across
another volume's metadata publication and an unrelated payload write; touching
the measured map forces a miss and a fresh measurement. Existing generation
reuse, bounded cache eviction and no-cache paths also pass. Alternating settled
128/256-byte writes across two filesystems pass persisted-byte/allocation audits
and guards. Loaded IDE COPY is 109 frames with the same 54 reads / 61 writes;
its retained map avoids one block-cache fetch. Host checks: 447 passed.

No cache payload/record, upper buffer, Task stack or bank-zero reservation grew.
The writer's staged map still outranks clean cache data; bitmap replacement
drains remain in place.

## FP4: bounded selected-file validation

Writable Open sorts a copy of each map's populated references in the existing
mutation data buffer, then checks neighbours. The original map stays intact;
the duplicate-check scope is unchanged. A nonrecursive heap sort replaces the
quadratic loop. Allocation checks explicitly retain the current bitmap page
within validation, replacing it when a reference crosses to another page.
The writer also reuses its leased, staged current map during subsequent writes.

A full 254-reference map opens in 23 PAL frames, down from 75. A 133,127-byte
file spanning two maps opens in 24 frames, down from 77. Physical requests
remain 5 reads / 2 writes and 6 / 2 respectively, including Close. Logical
reads fall from 273 to 19 and 282 to 20. Separate count-only builds record
3,678 sort comparisons versus 32,131 old-loop comparisons; those instrumented
builds are not timing evidence. Fresh COPY remains 54 reads / 61 writes and
takes 108 frames.

Optimized emitted checks pass for malformed links, sparse writers, early/late
duplicates, allocation-bit errors, bitmap-page transitions, replacement and
append. Independent media audits and guards pass. The largest observed Task
stack use is 600 bytes within the unchanged 1,536-byte reservation; this is
observed headroom, not a worst-case proof. Host checks: 447 passed.

The sort uses at most 508 bytes of the existing 512-byte upper data buffer.
No records, allocations, stack pools or bank-zero reservations grow:
0 fixed / 0 per-Task / 0 idle additional bytes.

## FP5: driver-owned claim transaction

IDE and SIO workers now hold one Forbid/Permit pair through stop checking,
dequeue and active-request publication. Their internal helpers require the
worker's exclusion. A pending Stop still drains accepted work; its intermediate
state alone does not mean the worker may exit. Physical I/O and waits remain
outside the transaction. No public kernel operation or driver-private gateway
was introduced.

Loaded COPY retains 54 reads / 61 writes, while gateway calls fall from 2,547
to 2,122. It takes 107 frames versus 108: crossings improve substantially;
this workload's wall-time change is small. Optimized IDE checks pass mixed SIO
I/O, cancellation, busy shutdown and injected NMI boundaries 1 and 7. SIO checks
pass concurrent Open, stop with an open binding, stop/restart and last-application
shutdown. Guards and ownership cleanup pass; busy-stop intentionally checks the
fatal removal guard. Host checks: 447 passed.

The IDE worker's emitted call-bound analysis is 732 bytes including the
256-byte interrupt reserve and 16-byte dispatch margin, leaving 292 bytes in
its unchanged 1,024-byte reservation. Records and buffers stay unchanged:
bank-zero delta 0 fixed / 0 per-Task / 0 idle.

## FP6a: direct complete-sector buffers

The [design appendix](../plans/filesystem-dos-performance-implementation-plan.md#fp6-design-appendix)
defines source borrowing and failure semantics. The adapter submits its actual
source, publishes clean-cache bytes before retiring the borrow, and tags scratch
only when scratch was submitted. IDE PIO reads/writes use io_Data directly.
SpartaDOS complete aligned writes bypass merge/staging; partial updates, new tails
and MyDOS trailer assembly keep their private buffers. Failed raw read destinations
are invalid even with zero actual bytes; the current fixtures check that contract
and retain neighbour guards.

Loaded IDE COPY falls from 107 to 100 frames with the same 54 reads / 61 writes.
Accurate SIO takes 1,940 cold frames with 101 reads / 108 writes; warm source takes
1,011 frames with 4 reads / 108 writes. IDE mutation, map transition, bitmap
transition/no-cache, raw protected/failing writes, cancellation, timeout, flush
failure and NMI boundary checks pass. SIO block stores verify borrowed far buffers,
post-reply reuse, short sectors, no-cache and failed completion. MyDOS 128-byte
replacement/append passes independently audited media checks. Host checks: 447
passed. The IDE worker bound is 752 bytes in its unchanged 1,024-byte reservation.

The isolated cache observer measures actual Read and Store, with 32 samples of
each 128/256/512-byte size and identical-image replay. Baseline hit medians are
395/772/1,493 µs; publication medians are 402/796/1,554 µs. Cache bookkeeping
therefore warrants the next measured slice. Passive full-bank IDE timing also
finds substantial request/dispatch overhead: 115 exchanges estimate 1.13 s of
uninterrupted aggregate time, versus 0.40 s in PIO. These inclusive estimates
are not exclusive profiles, nor a prediction of range throughput. They justify
implementing and measuring bounded write ranges for contiguous new payloads.

All existing controller, mutation, cache and adapter buffers remain the same
size. Bank-zero delta is 0 fixed / 0 per-Task / 0 idle; no Task pool grows.
