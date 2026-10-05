# Filesystem mutation ordering

This records the W0 decisions for the
[write implementation plan](filesystem-write-implementation-plan.md).
The protocol is implemented; see the [current write contract](../reference/filesystem-writes.md)
and [development record](../history/filesystem-write-implementation.md).
No mount-time allocation audit or resident checker is introduced.

## Format inputs

The [native mutation fixtures](../../tests/fixtures/filesystem-write/README.md)
exercise original MyDOS 4.50 and SpartaDOS X 4.50 on 128/256-byte media. Their
manifest records exact bytes and native read-back; the host-only
[allocation oracle](../../tools/filesystem_audit.py) separately verifies ownership
and free counts. Mutation ordering below is Exec816's write-through policy;
the native DOSes buffer writes and do not promise this ordering.

MyDOS fields follow the pinned authors' 4.51 sources in the
[format reference](../reference/mydos.md): MDOS2 DKOPEN/DKCLOS and MDOS3
RBITMP/WBITMP/MAPIOC. New Exec files use sixteen-bit links, status $47 while
open and $46 when closed. Preserve existing ten-bit links and file ordinals.
Canonical new empty files have one zeroed sector, count one and zero payload.
Both accepted existing empty forms remain valid inputs. Directory records are
16 bytes; directory allocation is eight contiguous sectors. VTOC allocation
bits use one for free, with the header count in bytes 3–4. Pin legitimate fixed
and final-sector reservations from the supplied volume profile; never infer
free sectors from the geometry alone.

SDFS uses the guide and pinned Altirra sources linked from the
[format reference](../reference/spartados.md). New empty files have one zeroed
map sector and length zero, matching native output. Active files use $88 while
open and $08 when closed; preserve other supported flags on update. A directory
header uses $28, its actual parent map, and initial length 23. Data and map
allocation bits use one for free; sector 1 bytes 13–14 retain the free count.
Native images may reserve the final sector. New timestamps use six zero bytes
when no wall-clock source exists; preserve existing timestamps on update.

## Common boundaries

Use verified WRITE $57, with READ $52 for read-modify-write. The SIO adapter
owns framing, checksums, timeouts and exact reply collection. No retries follow
an uncertain write. A successful operation means the peripheral confirmed its
required writes; it is not a power-loss durability or sector-atomicity claim.

Validate names, protection, sharing, representable lengths and required memory
before mutation. Preflight allocation for one data commit unit, including new
maps and directory growth; reserve metadata sectors before exposing references.
Clear newly allocated sectors, preserve unrelated bytes on partial updates,
and invalidate cache entries before writing. Retain staged bytes until terminal
collection. A failed write invalidates the mount and preserves its causal error.

Read validation stays local to the affected object. Walk a chain/map before
destructive reclamation to reject detected loops/range/count corruption, without
building a volume-wide ownership map. Consistent input allocation remains an
explicit assumption. No detached chain is reusable until its reference has been
removed on disk. Failed reclamation can leak allocation and requires external
checking; do not attempt speculative rollback after lost completion.

## Mutation tables

Each arrow below requires confirmed completion before the next dependent write.
Native incomplete flags stay set throughout a writable backing's lifetime.
Directory records that straddle sectors require separate writes and cannot be
treated as atomic records.

| Operation | Write order and logical completion |
| --- | --- |
| Create MyDOS file | Preflight directory slot and one sector; reserve VTOC bit/count; zero data plus EOF trailer; publish $47 entry with count one and first sector. Publish the preallocated handle only after entry completion. |
| Create SDFS file | Preflight slot/growth and one map; reserve bitmap/count; zero map; prepare any directory growth; publish $88 record pointing to that map with length zero. Publish the handle after the record and directory extent complete. |
| Open existing for update | Validate the target, preallocate handle/backing and acquire its lease; set its native incomplete flag before publishing the writable handle. Reject sparse SDFS files before mutation. |
| Overwrite existing payload | Read the affected sector; replace only requested payload bytes; verified write; update any required entry metadata; advance cursor/completed count. The remaining suffix is preserved. |
| Extend MyDOS within the last sector | Update payload and used-byte trailer; write the sector; preserve the chain count; advance the confirmed cursor and length. |
| Extend MyDOS with another sector | Reserve new allocation; write initialized payload/EOF trailer; connect the previous trailer (or first-sector entry for a zero-start input); update directory sector count; advance cursor/length. Preserve ten-bit ordinal encoding and its address limit. |
| Extend SDFS within a data sector | Write changed payload; update directory byte length if EOF grows; advance the confirmed cursor/length. |
| Extend SDFS with new data/map | Reserve data and any map; initialize data and new map with its back-link; connect map chain/data pointer; update directory length; advance cursor/length. A zero pointer within existing logical data is unsupported for writers. |
| Truncate MyDOS | Validate old chain; retain its detached head in operation state; mark incomplete and publish the canonical empty extent (reusing the first sector when present); free detached tail allocation and counts; publish writable handle. |
| Truncate SDFS | Validate old maps; retain old allocation for reclamation; mark incomplete and detach data/additional maps while retaining a zeroed first map; set length zero; release detached allocation/counts; publish writable handle. |
| Flush | Ensure each accepted data unit's required writes have completed. Keep the native incomplete flag and writer lease; preserve position. There is no dirty write-back queue. |
| Last Close | Finish required data/allocation/extent updates; clear the native incomplete flag; consume the wrapper/backing and release the lease. Failure still consumes the wrapper after all I/O retires and leaves the mount unvalidated. |
| Create directory | Preflight parent capacity and full child allocation; reserve and zero sectors; initialize child header where applicable; publish parent entry/extent; return the preallocated lock. MyDOS requires a contiguous eight-sector child. |
| Delete file/empty directory | Validate target and reclaimable extent; reject live objects and nonempty directory; tombstone the parent entry to remove live reachability; release sectors and update counts. Finish reclamation before reporting success. |
| Same-parent rename | Validate destination/collision/protection/busy state; replace the name in the same entry slot, retaining identity/allocation/flags/timestamp; update a renamed SDFS directory's own header name; finish all record sectors before success. |

SDFS directory growth reserves and initializes additional data/map sectors
before connecting them. Initialize the new record area before extending record
zero's authoritative length. A parent's cached subdirectory length must not
become an alternative authority. Preserve the format's end marker whenever
there is a following record slot.

## Cancellation and storage

Before the first mutation, ordinary cancellation leaves disk unchanged. A data
write's protected unit is one payload sector plus dependent metadata writes;
honor BREAK between units and report only the confirmed prefix. Namespace
operations and truncation defer cancellation through required reclamation and
finalization once mutation begins, bounded by volume geometry. Once an Open
commits, retain the protected state through handle publication so a final
checkpoint cannot free an unpublished backing while leaving a live disk writer.

During a protected unit, BLOCKWIRE.TransferCommitted still collects exact
replies and pumps control messages, but does not ask SIO to abandon the active
transaction. Reads needed to finish that unit use the same policy. A terminal
transport error always wins over pending BREAK. Normal reads retain their
existing cancellation path. No Forbid/IRQ/NMI exclusion spans I/O.

The shared worker uses three additional 256-byte staged sectors,
one 23-byte record and bounded scalar/entry state, totaling 878 requested bytes
(880 after heap rounding). The existing block buffer
is separate. File backing owns rights, lease and cursor state, not sector buffers.
The development record measures the remaining object growth. Fixed and
per-Task bank-zero reservation deltas remain zero, including guards and padding.
