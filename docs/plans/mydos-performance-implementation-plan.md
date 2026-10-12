# MyDOS performance implementation plan

[Implementation plans](README.md) · [Roadmap](../roadmap.md) ·
[MyDOS contract](../reference/mydos.md) ·
[Write contract](../reference/filesystem-writes.md) ·
[Testing policy](../contributing/testing.md)

Status: MP0–MP6 complete at the development tier. Each executable slice was
committed after its focused checks. See the
[implementation record](../history/mydos-performance.md) and
[final evidence](../development/mydos-performance-final.json).
This follows the completed
[filesystem and DOS performance work](filesystem-dos-performance-implementation-plan.md).

Reduce repeated MyDOS work without adding a cache, changing the disk format or
enlarging shared storage. Start with duplicate VTOC writes and private-buffer
copies, then retain bitmap and cursor state within established lifetimes.
Keep the existing four-sector extension limit, selected-file preflight before
destructive operations, and current completion, cancellation and error rules.
The changes also affect shared helpers, so each affected helper needs a focused
SpartaDOS regression.

## Scope and invariants

- Keep mounting to the existing header check. Do not add an ownership scan,
  fsck, whole-volume bitmap allocation or repair logic.
- Preserve 128/256-byte MyDOS sectors, per-file ten/sixteen-bit link decoding,
  file ordinals, the ten-bit address limit, directory ancestry and exact EOF
  count validation. Do not infer byte length from sector count.
- Keep each file's bounded traversal and cycle state across small reads and
  forward seeks. Restart it when seeking before the retained sector or after
  an invalidated traversal.
- Preserve the writer lease and exclusive external ownership of mounted media.
  Establish private resources and immutable geometry once; retain checks of
  newly read trailers, mutable allocation state and terminal I/O completion.
- Preserve reserve-before-link and unlink-before-free ordering. Settle every
  required write before reply; introduce no dirty metadata between requests.
  Failed/uncertain mutations retain the causal error and invalidate the mount.
- Retain initialized directory storage, canonical empty-file trailers and
  existing unused-tail handling. Add no preliminary zero-fill writes for newly
  extended payloads.
- Keep DOS/device ABI, cache capacity, 2,048-byte transfer staging, mutation
  buffers, Task/stack/DP reservations and file-cursor storage capacity unchanged.
  Use existing native memory primitives; compiler/runtime defects belong in
  actionc, with focused regressions there.

## MP0 Baseline and observers

Freeze the pinned compiler, ROM, emulator configuration, source media and
current optimized emission before modifying production code. Reuse retained
builds only when their relevant sources and observer transforms match. Keep
large artifacts under `build/mydos-performance`; retain compact results and
hashes under `docs/development` as implementation progresses.

Extend existing runners rather than creating another benchmark framework:

- Use [COPY measurement](../../tools/measure_write_performance.py) with a 16 KiB
  buffer, fresh destinations, cold and warm source cases, and a separate
  existing-file replacement case. Measure accurate Generic 57600 SIO on one
  primary 128-byte workload. Select a bounded 256-byte comparison where sector
  arithmetic changes; distinguish fast-media functional checks from timings.
- Record writable Open, Delete, Truncate and CreateDir separately from COPY.
  Count logical bitmap/payload/directory fetches, physical sector writes and
  chain visits, including same-page and later-page VTOC cases.
- Measure warm file reads, same-sector/forward/backward seeks, unmeasured
  seek-to-EOF and one repeated directory listing. The listing establishes the
  cost deferred to a future size cache; this plan does not promise to remove it.
- Record native MyDOS metadata/file/write code and affected shared helper code
  separately, plus actual requested/rounded heap bytes and observed stack use.

Keep intrusive counters out of timing comparisons, or use identical observers
on both sides and label their overhead. Passive counts and independently
audited persisted bytes/allocation accompany the measurements.

Acceptance: reproducible baseline cases, explicit observer scope and enough
attribution to distinguish physical I/O savings from cache-only CPU savings.

## MP1 Native copies and one directory read per update

Replace the byte loop in [FSCORE.CopyEntry](../../lib/fs/fscore.act) with
`A816MEMORY.Move` using the complete emitted record size. Use Move for the
length-plus-NUL copy in [FSRELATIVE.Seed](../../lib/fs/fsrelative.act). Convert
plain name/ancestor copies in changed MyDOS routines when their extents are
already known; retain byte inspection/folding loops. Use Clear for the changed
fixed-size record initialization, without broad formatting edits.

Separate loading a MyDOS directory record from storing its modified sector in
[MYDOSWRITE](../../lib/mydos/mydoswrite.act). Mark, Rename and Delete load the
sector once, update its record, then store the retained `state.map` bytes.
Creation can use the same store helper after its own slot lookup/loading.
Audit every call site before removing the old combined helper.

The retained directory sector belongs only to the current synchronous helper:
no nested call may overwrite `state.map` before publication. Preserve the full
physical sector, including neighbouring entries and the unused second half on
256-byte media. Keep metadata invalidation and terminal collection unchanged.

Checks: optimized MyDOS create/open/close/rename/delete with independent saved
byte checks; a maximum-length relative path and deep ancestry; one shared
SpartaDOS record-copy/relative-path case. Cover a far record or path crossing a
bank boundary with the existing memory primitive. Inspect emitted code to
confirm the ordinary byte loops are gone.

Acceptance: one directory fetch/copy per record update instead of two; unchanged
physical writes, neighbouring bytes, flags, errors, guards and ownership.

## MP2 Combine VTOC bit and count publication

Change [FSALLOC.Change](../../lib/fs/fsalloc.act) so a bitmap page that is also
the free-count header is updated entirely in `state.scratch` and written once.
Validate the bit transition and count arithmetic before submitting that write.
When the bitmap and header are different sectors, keep the existing ordered
two-sector publication and failure policy. Do not change TakeGroup's established
four-sector extension ordering.

For CreateDir, keep the existing eight-sector reservation and per-sector
initialization; this slice removes duplicate same-sector writes without
introducing grouped allocation/free publication.

Checks: optimized real-adapter single allocation/free, canonical file creation,
eight-sector directory creation/removal, replacement/truncation and deletion;
128/256-byte MyDOS bitmap geometry, header-page and later-page sectors; cache
disabled; failed write and BREAK at the new physical boundaries. Update fault
injection by semantic stage rather than retaining obsolete write ordinals.
Use the independent [media audit](../../tools/filesystem_audit.py) for successful
operations. Check the shared allocator's separate-header SpartaDOS path once.

Acceptance: each same-header allocation/free submits one VTOC write instead of
two. Later-page operations preserve their two distinct writes. No references
become reachable before reservation or reusable before detachment.

## MP3 Retain bitmap pages and simplify bitmap arithmetic

Give MyDOS selected-file validation the same call-local scratch lifetime used
by SpartaDOS: the first allocation lookup loads a page, later lookups use
`AllocatedCached`, and a page change reloads it. Payload reads target
`state.data`, so they must not retire the scratch bitmap. Do not persist an
unqualified page tag across operations or mounted volumes.

Keep ordinary mutation paths conservative until their scratch writers have
been traced. Reclamation changes the bitmap; it cannot borrow the validation
page as if it were unchanged. A retained-page flag must reset on every operation
entry and scratch overwrite, including errors and cancellation.

Replace division/modulo by the admitted 128/256/512-byte sector size in bitmap
addressing with shifts/masks derived in the current call. For MyDOS include
the ten-byte header before page selection. Retain sufficiently wide arithmetic
for sector `$FFFF`; narrow only after the bound is established.

In the allocator scan, retain page/byte position while examining successive
bits instead of recomputing it through a full helper chain per candidate.
Keep the allocation hint, wraparound, contiguous eight-sector search,
single-page extension bound, partial free-space result and protected extents.
Check cancellation at bounded scan chunks and page changes; do not remove
responsiveness while skipping full bitmap bytes.

Checks: selected-file writable Open with many sectors on one bitmap page,
fragmented references crossing pages and returning to a prior page, allocation
bit errors, cache-disabled operation and alternating volumes. Add bounded
scanner cases for full bytes, contiguous runs, wraparound, metadata exclusion,
partial groups and near-`$FFFF` arithmetic. Exercise the shared 512-byte SDFS
allocator path. Inspect emitted code for removed division/modulo helpers.

Acceptance: within writable-open validation, bitmap loads follow page changes
rather than payload count. Disk results and selected free sectors retain their
documented bounds; no new bitmap buffer or permanent page cache is allocated.

## MP4 Reuse file cursors for seeking and writing

Refactor [MYDOSFILE.Target](../../lib/mydos/mydosfile.act) to use a valid retained
sector when the target is within it, and continue forward from it for later
targets. Restart only when the target precedes its base or traversal is invalid.
Same-sector Seek needs cursor metadata, not a new sector fetch; a following
Read must still fetch the matching payload because another operation may have
replaced the shared adapter buffer.

For unknown-length `OFFSET_END`, continue an existing valid traversal where
possible. When measurement reaches EOF, retain that terminal cursor: offset
zero from EOF must finish immediately; a negative target inside the retained
terminal sector also needs no second walk. Earlier targets restart normally.
Reject positive offsets past EOF. Preserve previous-position return values,
seek rollback and partial-read cancellation.

In [MYDOSWRITE.Write](../../lib/mydos/mydoswrite.act), derive the within-sector
position from `file.position - chain.base` and traverse by accumulated validated
payload extents. Remove repeated whole-file division/modulo and reconstruction
of a base already carried by the cursor. Preserve partial overwrite, existing
suffix bytes, EOF extension and the current writer's nonterminal-payload rules;
do not restrict the reader's supported short-sector layouts.

Checks: same-sector backward/forward seeks, repeated small forward seeks,
exact sector boundaries, known/unknown EOF, zero-byte terminal sectors,
negative END offsets, failed/canceled seeks, subsequent reads, fragmented files,
ten-bit links and files over 64 KiB. Exercise alternating handles/volumes to
prove no cursor borrows shared bytes. Reuse MyDOS file and public DOS write/
append cases; retain constant-space cycle detection across calls.

Acceptance: same-sector Seek performs no sector fetch, forward seeks do not
rescan the prefix, and an unmeasured Seek(END, 0) traverses each remaining sector
once. Sequential Write no longer performs position division/modulo per step.

## MP5 Validate established state once

Write down the provenance of each removable check before deleting it. Limit
the change to MyDOS traversal and existing directory-lock state; do not expand
into another DOS ownership or transport-admission refactor.

- Preserve the check of a newly decoded next link before accepting its payload.
  Avoid repeating its geometry/ancestor check when Advance consumes that exact
  admitted link. First sectors, restart, mutation-created links and error
  recovery still need a clear admission path. Do not confuse an admitted sector
  number with validated trailer bytes or retained adapter data.
- Establish directory ancestry when resolving/descending and publishing a lock.
  Relative operations can trust that private established ancestry while retaining
  mount identity, directory type, live-object/lease and operation error checks.
  Remove pairwise ancestry revalidation only after auditing every construction
  and restoration path; keep detection of corrupt on-disk descent.
- Keep the complete selected-file preflight before Delete/Truncate. During the
  subsequent reclaim walk, continue reading links and checking relevant mutable
  allocation state, but avoid repeating immutable geometry/ancestry established
  by the protected preflight. Do not allocate a chain index to avoid the second
  walk: it is still needed to recover successors with constant storage.

Prefer explicit internal helpers/arguments over new persistent validation flags.
Keep checks whose removal cannot be justified by an established lifetime, and
record the reason. Preserve detected-corruption errors and bounded completion.

Checks: malformed initial/next links, ordinal mismatch, cycles, count mismatch,
ancestor overlap, deep relative paths, reused locks, failed reads and partial
BREAK. Reuse selected MyDOS file, relative-path, write-edge and mutation-lifetime
cases. Direct parser fixtures must establish the same valid initial state as
production; do not convert corruption regressions into successful operations.

Acceptance: each removed check has a documented owner and lifetime, and emitted
path counts show the reduction without losing operational checks or corruption
detection at newly read media boundaries.

## MP6 Matched measurements and documentation

Repeat the MP0 workloads with unchanged media, SIO timing, cache budget and
observer scope. Reuse final optimized emission across cold/warm replay where
supported. Run the host suite and only affected native regressions not already
covered by passing slices. Add one shared SDFS SIO write case and one IDE COPY
comparison to catch regressions from shared copies/allocation arithmetic.

Report physical writes, logical fetches, bitmap loads, chain visits, gateway
calls and wall time separately. Record MyDOS and shared emitted code bytes,
upper allocations, observed filesystem stack use and unchanged reservations.
Compare cache-only Open/Seek costs separately from accurate-disk throughput;
do not claim a particular speedup before measuring it.

Update current MyDOS/write/architecture contracts where behavior is clarified.
Add `docs/history/mydos-performance.md` and compact development evidence,
linking both from the relevant indexes and this plan. The mutation protocol's
physical-boundary examples and failure fixtures must match the new write count.

Acceptance: planned write/fetch/visit reductions are observed, independently
audited bytes and allocation remain correct, and no unexplained timing, code,
memory, guard or cleanup regression remains. Remaining full release qualification
is explicit. Demo refreshes and publishing are separate tasks.

## Validation and memory budget

Use development checks for each coherent slice: the host suite plus focused
optimized emitted-code cases. Extend existing runners with narrow selectors if
needed. Reuse an emission only while its inputs are unchanged. Use raw and
optimized probes only for changed compiler-facing layouts/interfaces or a
suspected compiler defect; do not repeat whole-system scenarios in raw mode.

Starting points are [MyDOS files](../../tools/test_mydos_files.py),
[metadata](../../tools/test_mydos.py),
[relative paths](../../tools/test_dos_relative.py),
[writes](../../tools/test_filesystem_write.py),
[write edges](../../tools/test_filesystem_write_edges.py),
[mutation lifetime](../../tools/test_filesystem_write_lifetime.py) and
[round trips](../../tools/test_filesystem_roundtrip.py). Keep stack/domain guards,
register restoration, OS coexistence, terminal reply ownership and deadlines.

MP0–MP6 target **0 additional fixed / 0 per-Task / 0 idle reserved bank-zero
bytes**, counting guards, alignment and unused capacity. Shared upper-RAM
allocations and record capacities also stay unchanged. Report actual old/new
emitted sizes, rounded allocations and stack use for each slice; a need for
growth requires revising this budget before implementation, not hiding it in
unused reservations. Do not shrink Task pools as part of these changes.

## Deferred work

The audit identified further opportunities, kept separate from MP0–MP6:

- A bounded cache of completed MyDOS byte lengths for repeated directory
  listings. Define identity, mutation/lease invalidation and storage ownership
  before choosing whether to reuse or extend the existing SDFS extent cache.
- Grouped allocation/free publication for CreateDir, Delete and Truncate.
  Define bitmap-page transitions, count settlement, failure ordering and bounded
  cancellation before extending the current mutation protocol.
- Lazy SDFS backend allocation in MyDOS-only configurations, smaller SIO-only
  staging, and mutation-buffer consolidation. Audit mixed mounts, remounts,
  allocation rollback and every scratch lifetime first. Measure the saving
  against extra dispatch/nullable-state code; do not reduce IDE capacity.

MP6 measurements prioritize these follow-ups. They are not acceptance conditions
for the current implementation plan.
