# MyDOS and SpartaDOS write support implementation plan

Status: proposed; implementation has not started. Both filesystems remain
read-only under their current [DOS](../reference/dos.md),
[MyDOS](../reference/mydos.md) and [SpartaDOS](../reference/spartados.md)
contracts. This plan adds a shared write path, delivers SpartaDOS first because
it is the standard demo filesystem, then brings MyDOS to the same API subset.

Use small executable slices and the [development testing tier](../contributing/testing.md).
Release qualification and physical-device support remain separate gates.

## Outcome and scope

Applications can create, overwrite, extend and truncate regular files, flush
and close them, create directories, delete files or empty directories, and
rename entries within their current directory. Existing shell output
redirection then works on explicitly writable mounts. No additional argument
parser or new command suite is required for this milestone.

Deliver both 128- and 256-byte media within the existing supported format
subsets. Preserve 8.3 names, the 255-byte path limit, 16-level directory bound,
unchanged binary/ATASCII data, and explicit mount geometry and transport
profiles. A successful close must produce a file readable by Exec816 and the
pinned independent/native DOS readers after the disk is reopened.

Defer formatting, an on-target filesystem checker/repair utility, write-back
caching, journaling, atomic replacement, cross-directory moves, cross-volume
rename, recursive deletion,
sparse-file creation, seek past EOF, SetFileSize, SetProtection, SetFileDate,
volume-label changes and new COPY/DELETE/MAKEDIR commands. Existing sparse SDFS
files remain readable but cannot be opened for writing in this first version.
Do not broaden the supported DOS derivatives or peripheral profiles implicitly.

## Starting points and required changes

The [filesystem architecture](../architecture/filesystems.md) already has the
right ownership: one filesystem worker, one active filesystem operation, a
separate SIO worker, shared upper-RAM workspace and reference-counted file
backing. Extend that implementation rather than adding workers per file or
private kernel services.

| Area | Current boundary and planned change |
| --- | --- |
| [DOSCALLS](../../lib/dos/doscalls.act) | Disk Open accepts only MODE_OLDFILE; nonempty disk Write returns write-protected. Route writable modes and Write through filesystem packets. |
| [FSHANDLER](../../lib/fs/fshandler.act), [FSBACKEND](../../lib/fs/fsbackend.act) | Existing operations resolve/read/seek/examine. Add parent-plus-leaf resolution, allocation and resumable mutation operations to the common backend contract. |
| [FSPACKET](../../lib/fs/fspacket.act), [FSFILES](../../lib/fs/fsfiles.act) | Close currently performs no I/O and frees the last backing immediately. Finalize a writer before consuming its last reference; keep memory release free of hidden I/O. |
| [BLOCKIO](../../lib/io/blockio.act), [BLOCKCACHE](../../lib/io/blockcache.act) | The cache is read-only. BLOCKCACHE.Write currently populates that cache; it does not write a sector to disk. Add an explicit write-through operation and unambiguous cache-store naming. |
| [SIODRIVER](../../lib/io/siodriver.act), [SIO ABI](../../abi/sio.json) | Exact 256-byte transfers are currently admitted only for READ on the supported fast profiles. Validate and implement 256-byte sector writes before enabling those writable mounts. |
| [FSABORT](../../lib/fs/fsabort.act), [FSOPERATION](../../lib/fs/fsoperation.act), [BLOCKWIRE](../../lib/io/blockwire.act) | Read-oriented cancellation can stop at any worker checkpoint and request active SIO cancellation. Mutations need explicit safe checkpoints and completion collection. |
| [Mount generator](../../tools/generate_dos_mounts.py), [FSTYPES](../../lib/fs/fstypes.act) | Descriptors have no access policy. Add an encoded read-only/read-write policy and a separately tracked effective writable state. |
| [DOSPROCESS](../../lib/dos/dosprocess.act), [PROCESS](../../lib/dos/process.act) | A failed Close currently makes cleanup fail and Finish abort. An ordinary disk-finalization error must become a command failure while remaining resources still retire. |

## Proposed public behavior

### Access modes and ownership

Add an `access` mount setting with `readonly` as the default and `readwrite`
as an explicit request. Reject unknown values and unsupported writable
profile/geometry combinations. A read-write request must pass the lightweight
mount checks below before publication; do not silently downgrade it.
Preserve startup's all-or-nothing publication of the initial mount set.
Mount reporting must distinguish configured access, writable admission and
subsequent unvalidated/offline state. SYS: shares the underlying mount's policy.

| Operation | Selected behavior on an admitted writable disk |
| --- | --- |
| Open MODE_OLDFILE | Existing regular file, read-only handle, initial position zero. |
| Open MODE_READWRITE | Open existing or create missing regular file; preserve existing bytes; initial position zero; read/write handle. |
| Open MODE_NEWFILE | Create missing or truncate existing regular file to zero; read/write handle. Never replace a directory. |
| Write | Overwrite at the current position and extend at EOF; preserve the unwritten suffix. No implicit newline or text conversion. |
| Seek | Preserve the current contract, including old-position return and destinations restricted to zero through EOF. Append is Seek to EOF followed by Write. |
| Flush(handle) | Complete this backing's data/allocation/length updates and report any failure; preserve its position and ownership. No pending write-back data is retained. |
| Close(handle) | Consume that owned wrapper once. The last writer reference finalizes the on-disk entry before releasing backing and its writer lease. |
| CreateDir(path) | Create one missing directory and return an owned shared lock. Allocate the result before mutating disk. Parents must already exist. |
| DeleteFile(path) | Delete a regular file or empty directory, then release its allocation. Reject root, protected, busy and nonempty targets. |
| Rename(old, new) | Rename within the same parent directory and volume without replacing another object. Resolve aliases to mount identity before comparing paths. |

These mode restrictions are deliberate Exec816 choices. Amiga
[Open](https://developer.amigaos3.net/autodocs/dos.library/Open.html) permits
both reads and writes with all three modes and shared MODE_READWRITE opens.
This first implementation keeps existing input handles read-only and gives
each writable backing an exclusive writer lease, avoiding lock upgrades and
independent cursors modifying the same file. Independently opened readers or
locks on that file conflict with a writer in either admission order and return
ERROR_OBJECT_IN_USE. Different files may have live writers; the worker still
serializes their operations. Public exclusive Lock support remains deferred.

Process inheritance shares the backing, cursor, access rights and writer
lease. It creates no second independent writer. Closing an inherited wrapper
does not finalize while another reference remains. Directory locks, including
CurrentDir, may coexist with changes to children; they prevent deleting or
renaming that directory itself. Reject deleting/renaming a directory with live
descendant objects so retained ancestry cannot become stale.

Check access, protection, name, target type, sharing and representable size
before the first mutation. New names use uppercase ASCII 8.3 spelling while
retaining the existing legal punctuation; preserve existing names unless
explicitly renamed. Creation must reject folded-name collisions, and all
operations must retain the existing ambiguous-match error. A rename resolving
to the same entry and same stored name is a successful no-op. Cross-volume
rename gets a distinct error; a cross-directory move is explicitly unsupported.

Add missing packet actions, error constants and Fault descriptions in
[dos.json](../../abi/dos.json), then generate language bindings and checked
command providers. Include disk full, object exists, directory not empty,
rename across devices and object write/delete protection errors, using the
Amiga numeric definitions where applicable. Keep mount protection distinct
from file protection and disk corruption. Add Flush, CreateDir, DeleteFile and
Rename to the public library and command imports; rebuild callers when ABI
versions change. Do not retain a parallel read-only ABI.

Flush is a filesystem synchronization operation here, unlike Amiga's
[buffered-stream Flush](https://developer.amigaos3.net/autodocs/dos.library/Flush.html).
For a valid read-only disk handle it succeeds without media mutation. Define
non-disk behavior in the same ABI change: unbuffered NIL/console/pipe handles
have nothing pending and succeed after ordinary ownership validation.
No generic device CMD_FLUSH or CMD_UPDATE is assumed to provide a disk barrier.

### Results and finalization failures

Write validates ownership, the upper-RAM buffer and length before starting.
A valid zero-length request returns zero without allocation or I/O; a nonempty
request additionally requires write access.
Return the confirmed byte count, or -1 if no bytes completed before failure.
A short positive result retains its causal IoErr, and advances the shared
position only by that completed prefix. Success clears stale operation errors.
Validate arithmetic before narrowing to on-disk fields; report an unrepresentable
requested final size before changing any bytes.

The completed prefix consists of data whose required allocation/link/length
updates have also completed. A later uncertain write may already have changed
additional physical bytes; a short count is not a rollback guarantee. Mark
that mount unvalidated and stop ordinary access rather than continuing with
cached assumptions. Read-only handles reject nonempty Write without I/O.

Close follows Amiga's
[consume-on-failure rule](https://developer.amigaos3.net/autodocs/dos.library/Close.html):
after a terminal reply, the wrapper is invalid even when finalization failed.
Collect every submitted I/O before unlinking/freeing it. Success preserves
entry IoErr; failure returns false with the causal disk error. If finalization
cannot complete, leave the native incomplete indication where possible,
invalidate the mount and release in-memory ownership without pretending the
disk entry was successfully closed. Never retry through the freed handle.
Close and UnLock must still retire owned objects on unvalidated/offline mounts;
ordinary access rejection must not trap their references and prevent unmount.

Process cleanup must distinguish a terminal close error from unresolved
ownership. Continue closing remaining owned resources after a terminal error;
retain the first cleanup error, return FAIL when the command otherwise
succeeded, and preserve an earlier command failure and its cause. Still treat
an outstanding request or non-retired object as an ownership invariant failure.
Apply the same error precedence to shell redirection cleanup and pipelines.

MODE_NEWFILE is destructive when Open commits, including before a redirected
command runs. This milestone does not promise temporary-file replacement or
preservation after a later command/load failure. Document and test that behavior.

## Integrity and mutation protocol

### Lightweight mounting and local validation

Mounting does not perform fsck. Retain format recognition and bounded checks of
geometry, header fields, metadata extents and declared count ranges. Do not walk
directories, file chains or sector maps, compare all allocation bits with file
ownership, or recompute free-space totals during mounting. Pin each format's
fixed/reserved extents in W0 so the allocator excludes them without a scan.
Mounting must not depend on the number or length of existing files.

Writable media is assumed to have consistent allocation metadata when mounted.
Use the on-disk VTOC/bitmap for allocation, scanning it only as allocation needs
require. Preserve count fields with checked arithmetic; a plausible recorded
count is not proof that it matches every allocation bit. Validate directories,
maps, chains, ranges, flags and counts as an operation encounters them. Keep
bounded walks and cycle detection; preflight the target chain/map when needed
for destructive operations. A MyDOS truncate/delete can require walking that
file, but opening a volume must not read every file's payload sectors.

Local checks reject detected corruption and native incomplete entries involved
in a mutation. Do not reclaim an unclosed entry or unexplained allocated sector
as free space. These checks cannot establish ownership across unrelated files:
cross-links, a live sector incorrectly marked free, and lost allocations may
remain undetected. Document that limit rather than adding a resident global
ownership map. Read-only mounting keeps its existing behavior.

Require unchanged media and exclusive external ownership while mounted. An
uncertain mutation makes the current mount unvalidated and disables further
ordinary access; do not automatically remount or resume writing. Before an
explicit writable remount, the medium must be checked/repaired externally or
restored from a known-good image. A lightweight remount itself does not prove
recovery, and Exec816 provides no checker or repair code in this milestone.

Keep full allocation audits in host-side development tools. Independently scan
test images before/after mutations and injected failures, including both file
chains and maps, without shipping the checker or its sector-ownership bitset
in the resident system. A future on-target checker can be a separately loaded
utility with its own memory budget and scope.

### Write-through sectors and cache coherence

Prefer the disk's verified sector WRITE command, subject to the pinned
transport contract established in W0/W1. Prove command framing, data checksum,
ACK/completion, length and timeout behavior for each enabled profile. Sending
all bytes or receiving an initial ACK does not mean the sector write completed.
Do not enable arbitrary 256-byte commands or introduce automatic write retries
or baud-rate fallback after an uncertain completion.

The block layer accepts an immutable staged sector until its exact I/O reply
is collected. Invalidate the affected cache entry before submission and install
replacement bytes only after confirmed completion. A 256-byte sector's two
cache units must change together. Invalidate backend map/metadata caches too;
cache identity remains mount plus generation, including access through SYS:.
Allocation, freeing and sector reuse cannot expose stale data. Exercise the
uncached fallback as well as a warm cache.

Use read-modify-write for partial sectors and directory records, retaining
unrelated bytes. Zero newly allocated sectors before linking them into a live
file/directory, including unused data tails and directory padding. Short boot
sector handling remains explicit. Reuse neither buffers nor requests while
SIO owns them, including on error or BREAK.

### Commit ordering and cancellation

Specify a sector-by-sector mutation table for each operation before coding its
backend. Each table identifies preflight checks, native incomplete flags,
allocation changes, data/link/record writes, the logical commit point,
cancellation checkpoints and failure disposition. In particular:

1. Reserve allocation before publishing a new reference; initialize data and
   maps before publishing the new length or directory entry.
2. Remove live reachability before releasing old sectors. Do not free an old
   file chain merely because truncation or deletion has started.
3. Keep bitmap free counts, chain/map counts, EOF and directory metadata in the
   specified order. A directory record spanning two sectors is two writes.
4. Preallocate in-memory results and work buffers before mutation. Disk-full
   preflight for the next data unit includes its maps and metadata allocations.
5. Use the format's native open/incomplete state during a writer's lifetime;
   clear it on the final successful close. Flush settles data and metadata but
   does not advertise a still-open writer as a natively closed file.

Data Writes have bounded commit units, initially one payload sector plus its
required metadata updates. BREAK before mutation cancels without changes;
after mutation starts, defer it until that unit is consistent and return the
committed prefix. Continue pumping cancellation/control messages and allowing
other Tasks to run while collecting transport completion. Update both worker
checkpoints and BLOCKWIRE; changing only FSABORT is insufficient.

Creation, truncation, deletion and rename have operation-specific commit
points. Once their mutation has begun, finish required reclamation/finalization
before honoring BREAK; if already committed, return the operation's success.
Do not claim constant cancellation latency: freeing a large file can require
a volume-bounded walk. Set and test step/transfer bounds for those walks, measure
worst-case cancellation delay on the supported geometry, and document it.
Shutdown and service stop must drain the same protocol before freeing state.
No Forbid, IRQ mask or NMI exclusion may span disk I/O.

On a failed or uncertain write after mutation begins, preserve the causal error,
invalidate caches, and make the affected mount unvalidated. If SIO requires
bus recovery, retire all affected mounts under the existing offline rules.
Do not attempt speculative compensating writes after a lost completion.
Safe no-change failures discovered during preflight do not poison the mount.

Neither disk format provides a journal here. Power loss, torn sectors or
multi-sector metadata failure can leave an incomplete file, leaked allocation,
or a volume requiring repair; in-place overwrite is not atomic. Tests must
characterize these outcomes with independent host allocation checks and byte
comparisons. Prove that runtime access stops on detected corruption or uncertain
mutation, without claiming that mounting discovers every damaged structure.
A device ACK does not guarantee host/physical power-loss durability.

## Format-specific work

### SpartaDOS filesystem

Implement bitmap allocation/freeing and counts, map-page initialization and
growth, map next/previous links, and data-pointer updates. Enforce 24-bit byte
lengths and the geometry's actual capacity. Count map sectors as allocation;
test growth past 62/126 pointers and reclamation of complete map chains.

Update 23-byte directory records even across sector/map boundaries. Grow
directories as mapped files, maintain record zero's authoritative length and
parent map, preserve unrelated flags, and use the native incomplete bit.
Initialize new directories with a valid header and end marker. Deleting an
empty directory releases both map and data allocation. Same-parent rename
preserves its map identity and does not rewrite ancestry.

Preserve existing timestamps on updates initially; initialize a missing/new
timestamp using the native unspecified representation verified in W0. Exec816
must not invent wall-clock time from uptime. Setting modification dates waits
for an explicit clock/date policy. Preserve supported status/protection fields;
reject unsupported live structures before any write.

### MyDOS

Implement the VTOC's descending logical-page mapping, allocation bits and free
counts for marker 2 and supported extended MyDOS layouts on both sector sizes.
Reserve boot, root, the entire VTOC extent and directory extents. Use wide
arithmetic through the final representable sector. An empty directory needs
eight contiguous sectors, even when aggregate free space is larger.

Write 125/253-byte payloads and their three-byte chain trailers; update the
directory's sector count separately from byte length. Preserve an existing
file's ten-bit or sixteen-bit link mode. Ten-bit links retain the parent entry
ordinal in their high bits and cannot allocate sectors beyond 1023; report
allocation exhaustion without silently converting the file. New files use the
native sixteen-bit MyDOS form confirmed by the W0 producer fixtures.

Pin the canonical empty-file encoding against native output in W0, while
continuing to read both currently accepted forms. Update the final trailer for
partial-sector extension and clear stale bytes beyond EOF. Truncation releases
the old chain only after detachment; directory slot reuse resets all fields and
preserves the end-of-directory convention. Never treat the second half of a
256-byte directory sector as extra entries. Rename stays in the same slot,
avoiding a rewrite of every ten-bit trailer's file number.

### Metadata visible through DOS

Examine must fetch or refresh metadata after completed mutations rather than
returning cached length/block counts from a lock. Introduce a directory mutation
epoch in the existing FIB cookie budget; changes invalidate active enumeration
and return a documented restart-required error, initially ERROR_OBJECT_IN_USE.
Restart by calling Examine again. Verify the layout against the 32 reserved FIB
bytes without growing the public 260-byte structure. Bind writer leases and
object identities to mount generation and entry lifetime so slot reuse cannot
revive a stale reference. Bound epoch counters and handle exhaustion explicitly.

Directory lookup/enumeration must recognize incomplete entries owned by a live
writer in this mount generation: list their last committed metadata and apply
the sharing error to conflicting opens/locks. Do not hide them as abandoned
MyDOS files or reject the whole directory as malformed SDFS. An incomplete
entry without that live ownership still follows the local corruption rules;
the native flag alone never grants permission to resume someone else's write.

## Executable slices

Commit each slice after its affected development checks. W0 fixes the mutation
tables and fixtures; W1–W3 establish the common path. W4–W5 deliver SDFS before
W6–W7 deliver MyDOS. W8 depends on both backends and completes namespace parity;
W9 integrates the result. Keep unsupported actions rejected until their slice
is complete. Failure/cancellation tests accompany each slice, not just W9.

| Slice | Implementation and acceptance gate |
| --- | --- |
| W0 Contracts and independent fixtures | Record native MyDOS/SDFS create, append, overwrite, truncate, close, directory and delete output; pin producer versions/hashes. Specify exact empty/incomplete/timestamp encodings, reserved sectors, sector-write command and per-operation commit tables. Add independent host allocation validators and expected failure classifications. No runtime writes yet. |
| W1 Physical sector writes | Add checked block/SIO write support, including 256-byte admission and adapter phases where required; generate changed ABI definitions. Emitted tests write/read back disposable media on each supported profile/size, including short boot-sector addressing, protection, checksum, NAK, timeout and lost-completion cases. Prove reply collection, register restoration and bounded transport completion. |
| W2 Write-through and mutation lifecycle | Add shared staged writes, cache invalidation, operation commit state, deferred BREAK and stop/drain behavior. Exercise warm/cold/disabled cache, 256-byte paired entries, alias access, failed writes and sector reuse through emitted code. Preserve existing read cancellation and bus-offline behavior. |
| W3 Mount access and DOS ownership | Encode access policy with lightweight mount checks, writer leases and metadata/enumeration invalidation. Add packets, errors, providers and Close/Process cleanup lifecycle. Prove that mounting empty and populated media of the same geometry does not walk file data, directories or maps. Cover zero-mutation rejection, locally detected corruption, allocation failure, inheritance, conflicts, last close and cleanup error precedence using controlled backend operations. |
| W4 SDFS create and sequential write | Implement create/empty file, bitmap allocation, first map/data sectors, extending writes, Flush and final Close. Raw/optimized programs write varied binary lengths through the public API; independent/native readers reopen the resulting disk. Include disk full, incomplete close, live-writer lookup/enumeration and directory-record straddles. |
| W5 SDFS update and truncate | Add existing-file read/write, partial overwrites, append, map-page growth, MODE_NEWFILE truncation and allocation reuse. Cover 62/126-pointer transitions, maximum size/capacity arithmetic, protected files, rejected sparse writers and injected failures at each metadata phase. |
| W6 MyDOS create and sequential write | Implement VTOC updates, canonical new/empty files, chain extension, Flush and final Close on 128/256-byte media. Cover payload/trailer boundaries, bitmap-page transitions, live-writer lookup/enumeration and sectors above 1023 with native MyDOS read-back. |
| W7 MyDOS update and truncate | Preserve ten-bit/sixteen-bit modes on overwrites and extension; implement truncation/reclamation and entry reuse. Test ten-bit allocation exhaustion, directory ordinals, partial final sectors, every accepted empty encoding and injected trailer/VTOC/count failures. |
| W8 Namespace parity | Implement CreateDir, DeleteFile and same-parent Rename in both backends, extending metadata refresh and enumeration invalidation to these operations. Test full MyDOS directories, missing contiguous extents, SDFS directory growth, empty/nonempty deletion, protection, busy descendants, alias-equivalent paths, name collisions and committed-operation cancellation. |
| W9 Shell integration and evidence | Exercise real redirected commands and inherited output, cleanup failure reporting, remount/read-back and simultaneous work on both formats. Update current contracts, architecture, guides and development evidence, then refresh the OF816 distribution. Record actual coverage and remaining limits without claiming release qualification. |

## Validation and interoperability

Use the pinned compiler from [actionc.json](../../toolchain/actionc.json), the
dedicated AltirraOS 65816 ROM and recorded emulator/device settings. Follow the
[handwritten code style](../contributing/style.md) and fix compiler defects in
actionc with focused regressions instead of filesystem-specific workarounds.

Reuse [the MyDOS producer](../../tools/mydos_producer.py),
[the pinned Altirra SDFS reader/producer](../../tools/sdfs_reference.py) and
[native SDFS fixtures](../../tests/fixtures/sdfs/README.md). W0 must inspect the
authors' MyDOS sources referenced in the [format contract](../reference/mydos.md)
and the SpartaDOS X guide/source references in the
[SDFS contract](../reference/spartados.md); read-only qualification does not prove
the selected write ordering. Keep expected allocation checks independent of
the guest writer rather than validating it solely by rereading through itself.

All mutation tests work on disposable copies of pinned images. Capture the
actual guest-modified ATR through the emulator's persistence path, close/reopen
it, run independent structural checks and byte comparison, then perform native
DOS read-back for each implemented format/geometry. Also append/modify selected
Exec-created files under the original DOS and read them back in Exec816. A
cache hit or host-created expected ATR is not evidence of guest disk writes.

Focused development coverage includes:

- Raw and optimized emitted code for each public operation, zero/exact/short
  buffers, multi-bank upper-RAM data, invalid ownership and arithmetic limits.
- Lengths zero, one, payload minus/at/plus one, multi-sector/multi-map data,
  alternating Read/Write/Seek and unchanged overwrite suffixes.
- Full disk, full directory, protected media/file, fragmented allocation,
  cache fallback, sector reuse, two mounts, SYS aliases and inherited cursors.
- Native incomplete entries, map/chain loops, locally detected allocation/count
  errors, directory boundary records, mount cancellation and teardown. Verify
  that mounting remains lightweight with many/large files in both formats.
- Host-only whole-volume checks for cross-links, bitmap/ownership mismatches,
  lost allocation and free-count errors; do not require runtime mount to detect
  corruption outside the metadata it reads.
- BREAK before submission, during each mutation phase, between commit units,
  on last Close and during stop; verify exact result/error, consumed handles,
  resource release and a usable prompt or the documented offline result.
- Controlled failures before a write, after media mutation but before completion,
  and at every multi-sector metadata boundary. Cold-reopen each resulting image;
  classify intact, committed-prefix, incomplete or externally detected
  inconsistent outcomes. Keep host findings separate from runtime detection.
- Stack/domain guards, native register restoration, OS coexistence and bounded
  completion for the changed transport, worker and Process lifetime paths.

Normalize host text before parsing fixtures; retain exact ATR and ATASCII bytes.
Reuse existing focused read/seek, cancellation, mount, inheritance and SIO
regressions; do not rerun every unrelated qualification matrix after each slice.
Expand to release matrices only for a release or explicit qualification claim.

For W9, use a read-only SYS: plus disposable writable WORK: media and exercise:

```text
ECHO saved >WORK:OUT.TXT
CAT WORK:OUT.TXT
CAT SYS:STORY.TXT >WORK:COPY.TXT
CMP SYS:STORY.TXT WORK:COPY.TXT
```

Repeat on each filesystem, close all references, unmount/remount and compare
again through independent readers. Use native API fixtures for append,
directories, deletion and rename; adding commands is outside this milestone.
Test late Close failure even after a command returns OK and inherited output
held by a pipeline. Ensure errors reach the retained console once.

Refresh only through [tools/build_demo.py](../../tools/build_demo.py), retaining
OF816, the matching disk, pinned ROM/notices and five-second autoboot into the
standard shell/prime demo. Provide a clearly disposable writable data disk for
the walkthrough. Distribute only exec816-demo.zip with boot/media files, short
guide, notices and checksums; keep manifests, fixtures and test output outside
the ZIP.

## Memory budget and completion record

Target for every slice: **0 additional fixed bank-zero bytes and 0 additional
bank-zero bytes per Task**, including guards, alignment and unused reserved
capacity. Keep the existing filesystem/SIO Tasks, DPs and stack reservations.
Measure stack high-water marks with current checked builds; do not infer spare
stack from unchanged reservations. Follow the
[platform budget](../reference/platform.md#bank-zero-memory-budget).

Allocate bounded mutation state in upper RAM, shared by the serialized worker.
Budget iterative ancestry state and a fixed number of 256-byte staged sectors;
W0's tables must establish the exact simultaneous buffer count before allocation
is implemented. No resident checker code or whole-volume ownership bitset is
required.
Avoid per-file sector buffers and whole-file rollback copies. Add only rights,
writer identity and retained finalization state to file backing; measure the
per-open and per-mount growth explicitly.

For each slice report requested/rounded upper-RAM allocations, resident data
and provider-manifest use, reserved spare capacity, code growth, fixed and
per-Task bank-zero deltas, and observed stack headroom. Check generated providers
against the current 1,664-byte reservation instead of silently enlarging it.
The optional sector cache must remain optional; failure to allocate mandatory
write workspace rejects writable admission before disk mutation.

Completion requires both formats passing the selected development coverage,
native interoperability, defined failure outcomes, cleanup and the packaged
walkthrough. Record implemented slices, source/toolchain/media hashes, measured
bounds and report paths in a linked history page and development JSON. Update
reference pages only as behavior lands. This plan-only change needs content
and link checks and has zero runtime or memory effect.
