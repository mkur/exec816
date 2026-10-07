# SpartaDOS write buffering implementation plan

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[Design note](spartados-write-buffering-design.md)

Status: proposed; SB0–SB5 are not implemented. Follow the design note's
request-scoped buffering decision. Deliver one executable slice at a time,
run its development checks, record its costs and commit before starting the
next slice. This plan does not change the current write contract.

## Outcome and limits

Reduce SDFS sequential-extension metadata traffic by retaining one bitmap page,
the current file map and pending extent during a DOS Write. Write payloads
immediately; publish bitmap, free count, map and directory length in that order
before reporting their bytes as confirmed. Check cancellation between groups
of at most four payload sectors. Metadata publication and cancellation checks
have different boundaries.

Keep the existing serialized filesystem worker, verified SIO writes, clean
BLOCKCACHE and public DOS interfaces. MyDOS, namespace operations, map creation,
ordinary overwrites and partial existing sectors retain their current protocols.
Drain before switching to those immediate paths. Add no preliminary zero write
for new payload sectors. No dirty state survives a Write reply; Flush and final
Close keep their existing roles. Retaining metadata across Write calls until
Flush/Close, runtime fsck and recovery are outside this implementation.

The memory ceiling is one shared upper-RAM allocation of 1,262 requested /
1,264 rounded bytes, compared with today's 878 / 880 bytes. Add one 256-byte
bitmap and at most 128 bytes of bookkeeping and confirmed snapshots. Reuse the
data, map, scratch and directory-row buffers. Add no per-file or per-mount
sector buffers and reserve **0 additional bank-zero bytes**. If the shared
record grows, MyDOS-only writable configurations also pay that allocation cost.

The conditional performance target is **68 verified physical writes instead
of 128** for one 16 KiB extension on 256-byte media: 64 payloads plus one each
for bitmap, header, map and directory. All payloads must fit within the current
map and bitmap page, and the directory record must fit in one sector. Open,
creation and Close are excluded. Map transitions, split records and 128-byte
media have different counts; measured COPY timing is a separate acceptance gate.

## Working state and implementation locations

Keep batch state in [FSWTYPES.State](../../lib/fs/fswtypes.act), allocated by
[FSINIT](../../lib/fs/fsinit.act) before any writable handle is published.
Keep SDFS publication policy beside [SDFSWRITE](../../lib/spartados/sdfswrite.act).
Use small private helpers; introduce a separate module only if it reduces
dependencies without creating an allocator/writer import cycle.

| Area | Required change |
| --- | --- |
| [FSALLOC](../../lib/fs/fsalloc.act) | Search and reserve against the working bitmap/free count for buffered SDFS extension. Report a required page change before replacing a dirty page. Preserve the namespace and MyDOS allocator paths. |
| SDFSWRITE | Retain the current dirty map; write accepted payload groups; drain in dependency order; preserve immediate boundary paths. |
| [FSWRITE](../../lib/fs/fswrite.act) | Distinguish accepted payload, confirmed publication and drain progress. Select the next caller bytes using confirmed plus staged counts. |
| [FSABORT](../../lib/fs/fsabort.act), [FSWRITEIO](../../lib/fs/fswriteio.act) | Route cancellation and normal capacity errors through drain. Keep physical-failure handling and I/O retirement authoritative. |
| [FSPACKET](../../lib/fs/fspacket.act), [FSWORKER](../../lib/fs/fsworker.act) | Retire batch state before replying, reusing a packet or stopping the worker. Preserve the existing single active packet. |
| Existing write fixtures and performance harness | Observe publication stages and independently audit persisted media; compare frozen baseline artifacts. |

Establish the active mount, generation, file and sector identities when starting
the batch. Reuse established ownership; do not add repeated pointer/handle
validation or a public ABI operation. Snapshot only the confirmed position,
extent/count and backend traversal state needed for failure restoration.

Maintain these invariants throughout implementation:

- For a buffered extension, requested bytes equal confirmed bytes plus staged
  bytes plus bytes not yet accepted. Only confirmed bytes advance
  `operation.completed`; the next source offset includes staged bytes.
- Working allocation bits exclude every staged reservation from later searches.
  Allocation and map checks consult working copies before clean cached bytes,
  including with CACHE-BLOCKS=0.
- Four-sector groups protect submitted payload work. An ordered metadata drain
  protects its dependencies. Neither holds an interrupt mask or scheduler
  exclusion across I/O; both continue pumping control messages.
- `service.committing` is cleared between groups. Pending physical mutation is
  tracked independently; resetting `service.changed` must not hide it from an
  error path.
- Publish the file map before directory RowIO repurposes the shared map buffer.
  Invalidate that working map identity and reload if extension continues.
- Advance the metadata epoch and save a new confirmed snapshot only after the
  complete directory-length update, including both halves of a split record.
- A physical or uncertain completion failure collects submitted I/O, takes the
  mount offline, invalidates caches and discards pending state. It reports only
  the earlier confirmed prefix and restores its cursor. It does not retry an
  uncertain write or free allocations speculatively.

## SB0: freeze the baseline and add focused observation

Freeze the current runtime source and optimized artifacts before changing the
writer. Record the source revision and any local diff, compiler from
[actionc.json](../../toolchain/actionc.json), ROM/emulator pins, cache settings,
transport profile and media hashes. Keep artifacts and outputs under a development
build directory, outside distributed packages. Do not keep an old production path.

Extend the existing write fixture with a bounded single-Write case: 64 complete
256-byte payload sectors, one existing map with enough slots, one bitmap page
and a directory row contained in one sector. Record only the Write interval;
creation/Open/Close have separate counters. Use test-only observations to
classify submitted and verified writes by payload, bitmap, sector 1, map and
directory. The host oracle derives sector identities from the fixture/media,
rather than trusting the writer's own phase counters.

Use [measure_write_performance.py](../../tools/measure_write_performance.py) to
freeze a real 16 KiB COPY baseline on an accurately timed 256-byte SDFS target.
Preserve the command artifact and source image for the final matched comparison.
Extend only the needed observer/fixture capacity; existing lifetime fixtures
currently limit requests to 8 KiB, which cannot substitute for this 16 KiB case.

Acceptance: the focused baseline has 64 payload and 64 metadata writes under
the stated conditions, exact persisted bytes and a successful independent
[allocation audit](../../tools/filesystem_audit.py). Host checks and the
optimized observation run pass. Production memory changes are zero; record
diagnostic fixture storage separately.

Suggested commit: `test: freeze SpartaDOS write buffering baseline`.

## SB1: introduce the batch path with publication after each group

Add the bitmap buffer, scalar working free count, identities, dirty flags,
staged count and confirmed snapshot within the memory ceiling. Initialize/reset
them at workspace allocation and operation start. An allocation failure must
precede file mutation and retire the existing startup resources normally.

Implement the new SDFS extension path, initially draining after every existing
four-sector group. This establishes the new publication order and lifecycle
without yet retaining metadata across groups. It is a temporary implementation
checkpoint, not a runtime switch or a second compatibility path.

After a group's payload writes succeed, drain bitmap, sector 1 free count,
map and directory length. Read/modify the short sector 1 using existing scratch
and preserve its other bytes. Add map pointers only for a completed payload
group. Promote staged bytes and the cursor snapshot only after the last
directory write is verified. Centralize the success, BREAK and ordinary
capacity-error exits so they cannot bypass pending publication.

Update both FSABORT and FSWRITEIO.Checkpoint before enabling this path. Audit
indirect lookup/read/preflight failures as well as explicit reply sites. BREAK
with pending metadata selects drain; it must not be mistaken for a physical
mutation failure. Collect any live transport request before switching state.
A transport error during drain takes precedence over BREAK. Once all requested
payload has been accepted and drained, a late BREAK leaves full success intact.

Acceptance: optimized exact-byte/group tests, BREAK before mutation and during
payload/drain, bitmap/header/map/directory failures, split-record completion and
a MyDOS smoke case pass with independent media/prefix checks. The ordinary
64-sector case still has 128 writes, now in the new dependency order. Run a
small raw/optimized emitted probe for the changed record layout and snapshot
accesses. Report actual shared heap size, resident code and stack peaks; add
no Task, stack reservation or bank-zero bytes.

Suggested commit: `feat: publish SpartaDOS extension through an ordered batch`.

## SB2: retain metadata across groups within one Write

Remove the unconditional end-of-group drain from the current SDFS path.
Continue at most four payload sectors per worker step, then check BREAK and
pump control messages. Keep accepted and confirmed byte accounting separate;
avoid a zero-progress result being mistaken for completion while a drain is
pending. The caller's buffer remains borrowed until the ordinary packet reply.

Drain when the request is complete, canceled, out of space, or about to replace
its bitmap/map or enter an immediate write path. A bitmap scan reports the
boundary before reading another page over dirty state, even if no free candidate
has yet been found there. Drain, then resume the search. Clip preflight groups
to available space, current map slots and one bitmap page; a smaller feasible
group must not be rejected merely because four sectors are unavailable.

Keep map creation/transition on its existing immediate path: initialize the new
map/backlink before exposing its previous-map link and payload extent. Drain
before that path and before partial-existing-sector or overwrite fallback.
After a successful fallback, establish a fresh confirmed snapshot before
resuming buffering. Preserve local map/backlink/range checks and padding.

Acceptance: the SB0 focused case reaches **68 writes** and its publication
trace has the required order. Optimized cases cover 128/256-byte sectors,
cache off/on, fragmented allocation, map and bitmap boundaries, partial tails,
split directory rows, append and a disk-full staged prefix. Verify all reported
bytes and cursor positions independently. Recheck BREAK between groups and
failure after at least one earlier publication checkpoint. These boundary and
cancellation cases are required before committing coalescing.

Suggested commit: `perf: coalesce SpartaDOS metadata within each Write`.

## SB3: close lifetime, failure and interrupted-media coverage

Extend the existing [write](../../tools/test_filesystem_write.py),
[edge](../../tools/test_filesystem_write_edges.py) and
[lifetime](../../tools/test_filesystem_write_lifetime.py) fixtures for the new
publication boundaries. Replace assumptions that every four payload sectors
are confirmed with expectations derived from fixture map/bitmap boundaries
and the observed dependency trace. Keep exact confirmed-prefix assertions;
do not weaken them to accept any short result. Resolve fault ordinals against
named physical stages and fail stale observation hooks.

Use optimized emitted tests for:

- Read/Write/Seek transitions, append after reopen, inherited writable handles,
  alternating files/mounts, enumeration epochs and unchanged namespace behavior.
- BREAK before mutation, between groups, during drain and after final accepted
  payload; ordinary disk full after staged data; failure and lost confirmation
  at first/middle/last payload and every metadata stage, including either half
  of a split row.
- A failed later checkpoint returning only an earlier confirmed prefix,
  unchanged unrelated allocations, mount-offline behavior, causal error
  precedence, terminal Close errors, stop/drain and eventual resource retirement.
- Flush between settled Writes, last Close clearing the incomplete flag, and
  no batch state or borrowed pointers surviving reply or workspace reuse.

Add test-only RESET cuts after payload, bitmap, header, map and directory
publication. Inspect the resulting disposable media on the host; distinguish
unreferenced payload, allocation leaks/count mismatch and maps beyond published
length. Require the incomplete flag where Close has not completed. Do not add
repair code or imply that a mount detects these conditions. Sector tearing
remains outside any atomicity claim.

Run selected [native DOS round trips](../../tools/test_filesystem_roundtrip.py)
on both SDFS sector sizes for map growth, fragmented allocation and split rows,
using pinned DOS fixtures. Keep guard, context/OS-restoration and bounded
completion assertions in emitted runs. Reuse builds only when their source,
observer and toolchain freshness checks pass. This is targeted development
coverage, not a new full qualification matrix.

Acceptance: all selected assertions pass, including clean retirement after
faults. Record the case list, geometries, input hashes and actual outcomes.
Shared production storage and reserved bank-zero deltas remain zero relative
to SB2; report any necessary implementation correction explicitly.

Suggested commit: `test: cover buffered SpartaDOS write lifetimes and faults`.

## SB4: measure COPY throughput, cancellation and memory

Compare SB0's frozen writer with the current writer using the same 16 KiB COPY
artifact, source bytes, target layout and fresh disposable media. Use the
existing performance harness with `--buffer 16384`; retain accurately timed
Generic 57600 media and the pinned machine configuration. Measure source Open
through destination Close, excluding command loading, keyboard injection and
printing. Include cold and deliberately warm source cases on 128/256-byte
SDFS targets; keep fast-media functional results separate.

Report payload/bitmap/header/map/directory reads and verified writes, guest
cycles or time, effective throughput and the additional cost of map/bitmap
boundaries and split rows. A 128-byte map has 62 pointers, so the 68-write model
does not apply to a 16 KiB request on that geometry.

Measure physical BREAK to Write reply while stopped between groups and during
ordered drain. Report both the four-sector payload checkpoint and the dependent
metadata cost; do not infer the new latency from the old four-sector result.
If a matched sequential COPY regresses, resolve the extra reads/scans before
accepting the performance change. Make only measured emulator timing claims;
real-drive performance needs separate hardware evidence.

Measure optimized resident code size and peak worker stack use, with guards
enabled. Record the rounded shared allocation, fixed/root/kernel/public-Task/
idle/boot bank-zero totals including alignment and reserved capacity, and zero
new per-Task allocations. Stay within the upper-RAM ceiling and existing stack
reservations. The existing accurate 256-byte MyDOS timeout is not a reason to
change SIO deadlines or transport policy in this work.

Acceptance: matched sequential extension reduces metadata traffic and measured
COPY time; the focused count target and memory limits hold. Publish the actual
timings and BREAK bound, without claiming hosted-system qualification.

Suggested commit: `docs: record SpartaDOS write buffering measurements`.

## SB5: document the current behavior and refresh demos

After executable acceptance, update the
[write contract](../reference/filesystem-writes.md) and
[mutation protocol](filesystem-write-protocol.md) to describe request-scoped
SDFS publication, the potentially larger failed checkpoint, confirmed-prefix
results and cancellation/drain behavior. Distinguish MyDOS's existing groups.
Keep Flush/Close and lightweight-mount recovery limits explicit.

Add a completed implementation/measurement record and machine-readable
development evidence following the [documentation organization](../contributing/README.md#maintaining-the-documentation).
Move completed discussion to history where appropriate, update indexes and
roadmap, and check links. Record the development tier and actual execution
scope under the [testing policy](../contributing/testing.md).

Rebuild matching resident images and commands. Refresh standard and VBXE
shell-only preview packages through [build_demo.py](../../tools/build_demo.py),
including OF816, the five-second autoboot, pinned ROM, matching system/work
disks, cartridge images, licences and checksums. Keep PRIMES available as a
command. On the exact packaged images, check boot to shell, real COPY to WORK,
reopen/read-back, DIR/LIST and a usable prompt after completion/cancellation.
Keep diagnostic sources, manifests and test output outside the ZIPs.

Acceptance: development checks, documentation links and package checks pass;
artifact hashes and scope are recorded. Building these previews does not
publish a release or establish platform qualification. Run applicable frozen
release matrices only for a release qualification step or an explicit request.

Suggested commit: `docs: complete SpartaDOS write buffering delivery`.

## Completion gates

Each code slice runs the host suite and its selected optimized emitted cases;
SB1 also has the small raw/optimized layout probe. Do not duplicate the full
integration sequence in raw mode. Report actual execution scope and memory
deltas per slice, including zero reserved bank-zero change, before committing.

Complete when the current implementation settles every Write before reply,
all selected normal/boundary/failure cases preserve confirmed-prefix semantics,
the conditional 68-write target and memory limits hold, matched COPY measurements
show improvement, and documentation plus preview packages describe that exact
implementation. Cross-Write buffering remains a separate design decision.
