# Batched directory enumeration

Status: implemented through EB1–EB3. Measurements retain eight-entry scanner
refills; see the [execution record](../history/directory-batching.md).

[Plans](README.md) · [Files enumeration analysis](../history/files-enumeration-analysis.md) ·
[Implementation plan](directory-batching-implementation-plan.md) ·
[Current DOS contract](../reference/dos.md) ·
[Cancellation contract](../reference/foreground-break.md)

Add one public synchronous DOS operation, `ExNextBatch`, which returns several
directory entries through one request and reply. Start Files and the file
selector with eight entries per request; support capacities up to sixteen and
measure both sizes. Reuse the existing filesystem Task, lock, enumeration
cookie, backend steps and cancellation mechanism. Ordinary `ExNext` remains
available for callers needing one complete FileInfoBlock at a time.

This is directory-result batching, not a general request-batching framework.
It adds no kernel service, Task, port, directory cache or scheduling policy.

## Why batch at the DOS boundary

The [analysis](../history/files-enumeration-analysis.md) measured warm scans at
193 ms for nine `SYS:` entries and 533 ms for 29 `SYS:C` entries. Both had zero
physical disk commands and zero presenter CPU during enumeration. The latter
uses 33 DOS transactions: Lock, Examine, 30 ExNext calls and UnLock.

Each entry repeats caller admission, publication, worker queue selection,
dispatch, reply and collection. A caller-side loop around ordinary ExNext
would retain these costs. The batch must be a single filesystem packet, with
the worker continuing to the next entry before replying.

For 29 entries, capacities eight and sixteen reduce that transaction count to
seven and five respectively, including the unchanged setup and cleanup. These
are counts, not predicted speedups. Backend work, interrupts and cold disk
latency remain, and drawing occurs after the measured scan.

## Public operation and storage

Public C surface, with equivalent generated native Action! declarations:

```c
struct DirEntry {
    UBYTE name[108];
    LONG kind;
    LONG size;
    UWORD infoFlags;
};

struct DirBatch {
    UWORD capacity;
    struct DirEntry entries[1]; /* Allocate capacity records after the header. */
};

LONG ExNextBatch(BPTR lock, struct FileInfoBlock *cursor,
                 struct DirBatch *batch);
```

The caller initializes `capacity` to 1–16 and supplies `2 + capacity * 118`
bytes. The fixed wire layout is a two-byte header followed by 118-byte records:
name at offset 0, kind at 108, size at 112 and flags at 116. Record offsets are
relative to each record, not the batch header. Generate sizes and offsets from
`abi/dos.json`; do not infer allocation size from `sizeof(struct DirBatch)`,
which includes its first record. The header contains no pointers or callbacks.
Three arguments fit the existing C-to-DOS bridge without widening its argument
envelope.

`kind` has the existing ST_FILE/ST_USERDIR semantics. `name` is terminated;
bytes after the terminator are unspecified. `size` and the FIB_SIZE_EXACT and
FIB_SIZE_BOUND bits follow ordinary ExNext metadata rules. Unavailable size is
-1 with both bits clear; directory size is zero and exact. Other flag bits are
zero. This preserves MyDOS size bounds without treating them as exact lengths.
No dates, comments, protection or allocated-sector counts are returned. Callers
needing those fields retain ExNext/Examine; exact queries remain separate.

The caller owns the live lock, cursor and complete buffer and keeps them stable
until the synchronous call returns after collecting its terminal reply. No
other task may inspect partially written results or modify these objects during
the call. A pending cancellation does not release their lifetime early.

## Cursor and continuation

Start with `Lock` and successful `Examine` on a directory. Use that exact FIB
and lock for subsequent calls. The batch operation updates only `fib_DiskKey`
and the private enumeration cookie; the other FIB fields do not describe the
last batch entry. Read metadata from the returned records.

Keep the current cookie binding to the lock, FIB address, object ticket and
mount mutation epoch. No new enumeration handle is needed. ExNext and
ExNextBatch may alternate at completed call boundaries, advancing the same
cursor. Moving/copying the cursor or modifying its private fields is misuse.

Return entries in the same backend order as ExNext. Each complete published
record advances the cookie past that entry, including preceding skipped slots.
An incomplete record never advances the public cursor. End-of-directory records
the existing exhausted position. Between batches, a namespace change retains
the current ERROR_OBJECT_IN_USE behavior; restart with Examine. Enumeration is
not a snapshot, and returned names are not locks on their objects.

## Results and errors

Return the number of complete records, from zero through capacity. `IoErr()`
is set on every call and explains why it stopped:

| Result | IoErr | Meaning |
| --- | --- | --- |
| capacity | 0 | Full batch; more entries may exist. |
| 0 through capacity − 1 | ERROR_NO_MORE_ENTRIES | Normal end, including an empty directory. |
| 0 through capacity − 1 | Another error, including ERROR_BREAK | A valid prefix followed by failure or cancellation. |

All records below the returned count are usable, even on error; remaining
records are unspecified. Read IoErr immediately, before cleanup or another DOS
call. Zero is not a Boolean failure test, and a short count alone is not proof
of normal end. A full batch does not look ahead solely to discover EOF: an
exact multiple of the capacity needs a subsequent zero-entry terminal call.

Failure before the first record leaves the cursor unchanged. On partial
failure the cursor retains the last committed position; it never skips the
unreturned entry. A caller can resume after clearing a break or resolving a
transient error while the lock/epoch remain valid. Epoch invalidation requires
a restart. Invalid capacity returns zero with ERROR_BAD_ARGUMENTS before
submission and changes neither cursor nor records.

This prefix contract belongs to the new operation. ExNext retains its existing
error/cancellation behavior: preserve the old FIB before result publication,
with the existing cookie update on normal end-of-directory.

## Worker execution and cancellation

Resolve and retain the lock/mount once through the ordinary DOS admission path.
Send one new DOS action carrying the lock, cursor and batch addresses in the
existing packet argument fields. The worker trusts that admitted object rather
than repeating the caller's ownership lookup. Check the enumeration cookie and
epoch once at batch admission. Keep operational errors and media validation;
do not introduce buffer walks or per-entry pointer/type validation.

Extend the existing [directory state machine](../../lib/fs/fsdirectory.act):

1. Restore the directory context and start from the cookie's next ordinal.
2. Use the existing bounded entry/decode/metadata steps, including I/O suspension
   and skipped/deleted entries. Request ordinary metadata, not exact file extents.
3. Check cancellation, then write one complete compact record and commit its
   count and cookie in one worker step.
4. If the capacity is reached, publish the terminal result and reply. Otherwise
   restore the parent directory context and continue to the next entry.
5. On end, error or cancellation, reply once with the committed count and cause.

Restoring context between entries matters: the current single-entry path may
descend into a returned directory while checking ancestry. The next batch entry
must use the original enumerated directory, not that child's workspace state.
Reuse that restoration logic and the current backend cursor/cache; do not
repeat client admission or start a nested DOS request per entry.

Record publication is a short completion-wins step, not a batch-wide critical
section. Ordinary task preemption and interrupts remain enabled. Restore normal
cancellation eligibility before the next entry; never leave `service.stage=70`
set across the batch. If the last record completes the batch, its terminal reply
wins over a later break. Earlier filesystem/transport errors retain precedence.

Add the action to the existing cancellation classification. Queued cancellation
returns zero and ERROR_BREAK without touching output. Active cancellation
retires in-flight backend/transport work and preserves the committed prefix.
In particular, adapt the generic [abort checkpoint](../../lib/fs/fsabort.act),
which resets packet results before action-specific handling. All error
exits must retain the batch count and collect exactly one reply. No new public
asynchronous request API or cancellation channel is introduced.

## Batch size and service fairness

Use eight records initially; sixteen is the supported maximum and a measured
alternative. The count limits returned records, not disk latency or the number
of deleted slots traversed. Preserve bounded backend steps and cancellation
checkpoints even while skipping entries or waiting on media.

Other Tasks can run during a batch. Other filesystem packets wait until the
current batch retires, because the worker still owns one active operation.
Preserve normal FIFO/volume/management selection between packets. Do not suspend
and multiplex multiple filesystem operations merely to interleave batches.
Compare eight and sixteen for throughput, another client's request latency and
file-selector cancellation response before choosing the shipped default.

## Shared scanner adoption

Use [FileScan](../../c/calypsi/file-list.c) for both the browser and file selector.
Keep its one-entry-at-a-time consumer interface: refill a private batch only
when exhausted, then return locally buffered entries on subsequent calls.
Capture count and IoErr once per refill, retaining a terminal status while its
valid prefix is consumed. Preserve the file selector's event checks between
consumed entries; an in-progress DOS batch still follows existing DOS wait/input
and foreground-cancellation behavior.

Keep the existing 256-entry display limit and name/type snapshot. The browser
must accumulate sizes from the compact records, not stale cursor FIB fields.
Expose those values through the scanner's current-entry state without expanding
every retained FileEntry into a full FIB. Preserve size validity flags.

At the limit, examine one further returned entry to distinguish exactly 256
from a truncated listing. Never copy beyond the snapshot allocation. On a real
scan error or cancellation, preserve the current UI policy of rejecting the
incomplete listing, despite the public operation offering a usable prefix.
Do not render a successful partial directory silently.

Allocate one upper-memory buffer per active scan, release it on all finish and
failure paths, and keep FileScanEnd idempotent. Save the causal error before
UnLock/free cleanup. No allocation per entry and no automatic fallback to the
old packet-per-entry scan on allocation failure. Report ERROR_NO_FREE_STORE.
Native DIR/other clients can adopt the public API separately.

## Memory and ABI scope

Eight records require **946 bytes**, sixteen **1,890 bytes**, excluding allocator
overhead. The existing 260-byte FIB and retained directory list remain. Small
batch pointer/count/status fields live in caller and filesystem upper-memory
state; no result array belongs on a Task stack. Publish their actual sizes in
the implementation record.

Target reserved bank-zero growth is **0 fixed, 0 per public Task and 0 idle
bytes**, including guards, alignment and unused capacity. Code and upper-memory
heap growth must still be reported; zero bank-zero growth is not zero total cost.

Generate the action, constants, records and native binding from
[DOS ABI metadata](../../abi/dos.json). Extend the native DOS provider, COMMAND
imports, C entry table/binding and relevant ABI revisions together, rebuilding
callers. Keep one implementation behind all bindings. The numeric action and
entry identifiers belong in the implementation plan; no new COP selector is
required. ExNext is a supported single-entry operation, not an obsolete profile.

## Development evidence required

Use focused emitted-code checks for ordering and metadata parity with ExNext,
empty/short/exact-multiple batches, alternating single and batch calls, the
256-entry limit, independent cursors, epoch changes and early cleanup. Include
SDFS, MyDOS size-bound behavior and RAM, plus a bank-crossing output buffer.
Exercise cancellation before submission, while queued, between entries and
during I/O; inject an error after a committed prefix. Check counts, cookie
progress, untouched bounds, reply ownership and guards. Small raw/optimized
ABI probes are appropriate for the new record layout and bridge; ordinary
functional scenarios use optimized builds.

Repeat the matched warm SYS:, SYS:C and RAM: scans at capacities eight and sixteen.
Record DOS transactions, caller/worker/interrupt CPU, elapsed enumeration,
physical I/O and one competing filesystem client's delay. Also measure complete
Files refresh/initial opening and selector cancellation separately from the
scan interval. Do not claim that transaction reduction predicts drawing or
disk speed. Refresh the OF816 demo when the implementation is ready.

Empty-queue checks, caller-local GetMsg, backend arithmetic/date cleanup and
directory caching are separate changes. Keep them out of this comparison so
the measured batching gain remains attributable.
