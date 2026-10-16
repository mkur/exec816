# Batched directory enumeration implementation plan

Status: EB1 implemented and checked; EB2–EB3 pending.

[Execution record](../history/directory-batching.md).

[Design](directory-batching-design.md) ·
[Enumeration analysis](../history/files-enumeration-analysis.md) ·
[DOS contract](../reference/dos.md) ·
[Testing policy](../contributing/testing.md)

Implement the public ExNextBatch operation, adopt it in the shared Files/file
selector scanner, then measure eight versus sixteen entries per request. Work
in three executable slices, with a separate commit after each completed slice.
The existing analysis supplies the baseline; there is no separate baseline
slice.

## Scope and invariants

- One packet and terminal reply per batch, through the existing filesystem Task.
  Native DOS, COMMAND and C bindings reach the same implementation.
- Keep ordinary ExNext, the 260-byte FIB and its existing enumeration cookie.
  No new handle, cache, Task, port, kernel operation or scheduler policy.
- Keep caller-owned storage and minimal admission checks. Resolve/retain the
  lock once; preserve cookie/epoch, media, cancellation and ownership rules.
- Retain normal preemption, bounded backend steps and transport retirement.
  No batch-wide Forbid or IRQ masking, and no forced yield between entries.
- Keep empty-queue/GetMsg changes, backend arithmetic/date optimization,
  renderer work and native command migration outside these slices.
- Target reserved bank-zero deltas of **0 fixed, 0 per public Task and 0 idle
  bytes**, including guards, alignment and unused capacity, in every slice.

## Slice sequence

| Slice | Executable result | Focused evidence |
| --- | --- | --- |
| EB1 | Complete public batch operation and all bindings, with partial results and cancellation | ABI/layout probes and native backend/ownership cases |
| EB2 | Files, desktop folder windows and the file selector use eight-entry refills | Scanner boundaries, cleanup and real application navigation |
| EB3 | Measured batch-size choice and refreshed OF816 demo | Matched scans, competing-client delay and packaged UI smoke |

## EB1 Public operation and worker continuation

Primary files: `abi/dos.json`, `abi/program.json`, `abi/c-program.json`, their
generators, `lib/dos/doscalls.act`, `dos-implementation.inc`, `programapi.act`,
`c/calypsi/dos.c`, `dos-bridge.inc`, and `lib/fs/fshandler.act`, `fsdirectory.act`,
`fsinfo.act`, `fstypes.act`, `fsoperation.act`, `fsabort.act`, `fspacket.act`.

### ABI and admission

1. Allocate `ACTION_EXAMINE_BATCH=28`, currently unused in the DOS action table.
   Update DOS revision 10→11, COMMAND program version 18→19 and C program
   version 19→20 together. Recheck these allocations if the tree changes before
   implementation; do not renumber existing entries or retain an old profile.
2. Define DirEntry and the DirBatch header/first-record declaration from the
   design. Generate `DIR_ENTRY_SIZE=118`, `DIR_BATCH_HEADER_SIZE=2` and
   `DIR_BATCH_MAX=16`, record offsets and native/C/COMMAND declarations. Extend
   the existing generators only as needed for this layout. Do not build a
   general variable-record serialization layer.
3. Add `ExNextBatch(lock, cursor, batch)` with a LONG count result. The native
   signature is three three-byte pointers; the existing C bridge passes its
   three full-width argument cells to a native wrapper. Append local C DOS
   table entry 24, growing ExecDosEntries from 24 to 25 entries, and append
   the loaded C import. Update startup binding, loaded providers and capacity
   checks through their owning sources/generators. Verify COMMAND provider fit.
4. Add one DOS admission routine using the current Task's DOS slot and existing
   owned-lock/mount retention. Read/check capacity once, rejecting values outside
   1–16 with zero/ERROR_BAD_ARGUMENTS before submission. Trust caller-owned live
   storage. Set Arg1=admitted lock, Arg2=cursor, Arg3=batch; retain Arg7's current
   owner identity. Mirror the existing C address-representation check once at
   narrowing, without adding worker-side address/type revalidation.
5. Send one cancellable DOS packet and release the retained mount only after
   terminal reply collection. Preserve the operation's IoErr through cleanup.
   Keep all three bindings executable in this slice, before GUI adoption.

### Directory state machine

6. Route the new action to the existing directory worker. Split out the small
   common ancestry/cookie setup if needed; the batch branch uses the already
   admitted lock instead of another FindObject search. Check the existing
   cookie identity, ticket, epoch and ordinal bound once at admission.
7. Keep only a current output pointer and remaining capacity in upper-memory
   service state; use the packet's `dp_Res1` as the committed count and the
   existing enumIndex as the working ordinal. Reset this state at admission
   and terminal retirement. No per-batch worker allocation or result array.
8. Share BeginEntry, BufferedEntry, skipped-entry handling and ordinary Metadata
   with ExNext. After each result, restore the enumerated parent's ancestry
   before starting the next entry. A returned subdirectory must not become the
   next iteration's parent. Preserve existing backend caches and initial media
   admission; do not call ExNext recursively or measure selected file extents.
9. Write name/type/size/size flags directly to the compact result. Reuse small
   metadata/name translation helpers where necessary to keep ExNext and batch
   meanings identical. Do not clear/build/copy a full FIB per batch entry or
   zero unused name bytes. Advance the output pointer by 118 rather than
   multiplying the record index on every publication.
10. Publish each complete record, its cookie and committed count in one bounded
    worker step after the cancellation checkpoint. Intermediate records retain
    normal cancellation eligibility on the next step. Use completion-wins
    handling only around final retirement; stage 70 must not cover the batch.
11. Reply at capacity with count/0; do not look ahead for EOF. On observed EOF,
    save the exhausted cookie and reply with count/ERROR_NO_MORE_ENTRIES. Other
    failures retain the committed count, causal error and last published cookie.
    Unreturned record bytes are unspecified; the caller's buffer bounds are not.

### Cancellation and error integration

12. Classify the new action as cancellable. Pre-submission and queued cancellation
    return zero/ERROR_BREAK without advancing the cookie or touching records.
    Active cancellation preserves `dp_Res1`, invalidates/retires backend work
    through the existing path and collects one terminal reply before releasing
    borrowed storage. Update FSABORT's generic result reset for this action.
13. Audit every directory, metadata and I/O error exit for prefix preservation.
    An error after three published records returns three and that error; it
    must not reset the count, advance beyond the fourth record or fabricate EOF.
    An earlier media error wins over a later break. A completed final record and
    terminal reply win over a late cancellation.

### Checks and completion

Add one focused runner, `tools/test_directory_batch.py`, with selectable ABI,
enumeration and cancellation groups. Reuse existing build, media and cancellation
helpers from `test_directory_metadata_abi.py`, `test_directory_metadata_fault.py`
and `test_filesystem_active_cancel.py`; keep diagnostic hooks out of production.
Use a small raw/optimized ABI probe for offsets/stride, all three pointers,
count/IoErr return, a bank-crossing buffer, context restoration and an actual C
and loaded COMMAND call. Functional cases otherwise use optimized emission.

Cover the following in a few reusable fixtures, not a Cartesian platform matrix:

- Capacities 1, 8 and 16; empty, short and exact-multiple directories; invalid
  capacities 0 and 17 with no packet submission or output changes.
- SDFS names/order/sizes, RAM enumeration and a MyDOS sample with bounded and
  exact-empty sizes. Compare independently expected records and ordinary ExNext.
  Include deleted slots and successive directory entries to catch ancestry reuse.
- Alternating ExNext/ExNextBatch, independent FIBs, ordinary ExNext behavior and
  mutation-epoch rejection. Non-cookie FIB bytes remain unchanged by batch calls.
- Cancellation before submission, while queued, before the first publication,
  after a prefix, during real I/O and after final publication. Inject one causal
  error after a prefix; check resume without skipped/duplicated entries while
  the epoch remains valid. Verify exact reply collection and unchanged guards.
- Release all locks/retentions after success, failure and cancellation; reuse
  the client for another operation to expose stale batch/packet state.

Update the DOS reference with the new operation/result table and the foreground
break reference with its prefix behavior. Regenerate/check ABI outputs, rebuild
affected callers and report native code, provider fit, stack observations and
upper-memory service/C-table growth. Keep previous measurement records intact.

Acceptance: one usable API with complete termination/lifetime semantics, no
per-entry request/reply exchanges and no changed ExNext contract.

Suggested commit: `Add bounded DOS directory batch enumeration`.

## EB2 Shared scanner and application adoption

Primary files: `c/calypsi/file-list.h`, `file-list.c`, `aes-fsel.c`,
`examples/gem-browser/browser.c` and their focused fixtures.

1. Extend FileScan with its batch pointer, buffered count/index, terminal status
   and current-entry size/flags. Keep FileEntry's retained name/type layout and
   the 256-entry limit. Place all new persistent state in the existing upper-RAM
   scanner owner; no stack array or enlarged bank-zero reservation.
2. Allocate one 946-byte upper-memory batch buffer at scan start, with capacity
   eight. Allocate before retaining a new directory lock, or unwind the lock on
   allocation failure. Return ERROR_NO_FREE_STORE without silently reverting to
   packet-per-entry enumeration. Retain Lock/Examine and their ordinary errors.
3. On refill, call ExNextBatch and immediately save count/IoErr. Subsequent
   FileScanNext calls consume records locally. Never interpret a zero count as
   success or a short count as EOF without the saved status. Preserve terminal
   status until all permitted buffered entries are consumed.
4. Copy only name/type to the retained list; expose current size/flags through
   FileScan. Change Browser's total accumulation to use those fields, not the
   cursor FIB. Keep exact totals unchanged for SDFS/RAM; preserve bound/unknown
   meaning for other backends rather than adding -1 or claiming an exact total.
   Do not obtain extra metadata through per-file requests.
5. Bound refills by the remaining display capacity. At 256 stored entries, use
   a one-record request to distinguish a truncated listing from exact exhaustion.
   Never write entry 257. A known error from the returned batch takes precedence
   over successful/truncated UI completion; clear the incomplete displayed list
   using the current error policy. Public API prefix usability remains intact.
6. Preserve file-selector event checks between consumed entries. An event may
   stop the scanner and discard buffered results, but never free an in-flight
   request's storage. Keep the existing DOS/foreground wait behavior inside a
   refill; do not add another GUI cancellation mechanism.
7. Make FileScanEnd release the lock and buffer once, clear borrowed/current
   state and remain harmless when called again. Save causal error before cleanup.
   Apply this to failed begin, normal EOF, error, cancellation, truncation and
   selector/dialog teardown. Do not change painting, sorting or selection policy.

Checks: extend the focused runner with an emitted C scanner group covering
0/8/9 entries, 255/256/257 entries, final-prefix error, allocation failure,
early stop and repeated cleanup. Use the emitted scanner fixture with controlled DOS replies for large-count
boundaries: RAM has only 256 nodes including its root and cannot hold 257 entries. Check
names/types, current size flags, count/truncation/error and heap/lock cleanup.
Run one optimized desktop/standalone Files and file-selector walkthrough for
navigation, Refresh, path change and cancellation; target existing helpers rather
than rerunning the entire GUI suite. Rebuild all affected application artifacts.

Acceptance: identical successful listings and ordinary interaction, eight-entry
DOS refills with no per-entry ExNext traffic, correct summary/error handling and
no ownership leaks. Report actual FileScan/owner growth and allocator overhead;
the 946 bytes are payload, not the complete allocation cost.

Suggested commit: `Batch Files and file-selector directory scans`.

## EB3 Measurements and demo delivery

1. Extend `tools/trace_files_enumeration.py` for ExNextBatch calls, counts and
   terminal status. Replace its current N+1 ExNext/N+4 packet assumptions with
   explicit single-entry and batch expectations selected from the observed
   build. Read changed scanner offsets from current emitted layout metadata,
   not the old hard-coded error offset. Validate old captures as old captures;
   do not rewrite their results as if they used the new implementation.
2. Reuse the retained baseline and exact compiler/ROM/machine/media pins from
   the analysis where inputs match. Rebuilt applications can change directory
   contents/layout; if that prevents a matched comparison, run one parent
   control on the same comparison media. Keep compiler, clocks, cache policy,
   serial timing and directory contents fixed. No toolchain update in this plan.
   Capture any missing complete-UI/competing-client baseline once from the
   retained parent; the existing scan measurements do not supply those endpoints.
3. Compare eight and sixteen with one narrow scanner build-time capacity setting,
   defaulting to eight. Public maximum stays sixteen. Run three warm repetitions
   each of SYS:, SYS:C and RAM: with the established scan boundaries, including
   final UnLock. Retain physical I/O and presenter activity counters so unrelated
   work cannot silently enter a scan comparison.
4. Record elapsed scan and caller/filesystem/interrupt CPU separately, packet
   counts, batch counts, successful records and physical commands. For unchanged
   nine/29/two-entry listings, expect total DOS transactions of **5/7/4** at eight
   and **4/5/4** at sixteen, versus **13/33/6**. Exact multiples still require the
   terminal empty batch. Counts must agree with the returned names and statuses.
5. Measure one repeatable competing DOS client's short operation while a batch
   runs, and file-selector cancellation/input response, for both capacities.
   Include one cold/transport-wait case for lifetime and latency reporting;
   distinguish it from warm throughput. Normal preemption does not mean another
   filesystem request can execute during the active batch.
6. Separately measure complete Files Refresh and initial New Window feedback,
   through visible completion, plus selector usable-list completion. Preserve
   paint counts and keep scan-only timings distinct from complete UI timings.
   Use narrow passive markers/counters; avoid retaining another broad trace of
   every function when the selected intervals answer the question.
7. Keep eight unless sixteen gives a repeatable additional throughput benefit
   worth the measured competing-client/cancellation delay. Report the tradeoff
   explicitly. Require reduced warm enumeration time/CPU beyond observed run
   spread, correct packet counts and no new redraw work; do not invent an
   unmeasured millisecond or speedup target. If an objective is missed, record
   it before considering another optimization.
8. Save compact inputs/results to `docs/development/directory-batching.json` and
   an execution record under `docs/history/directory-batching.md`; keep bulky
   artifacts under `build/directory-batching`. Update the design/plan status and
   relevant indexes with actual outcomes and validation limits.
9. Build the final demo using `tools/build_demo.py`, with OF816, five-second
   autoboot, matching rebuilt apps/system disk and pinned ROM/license notices.
   Smoke-test the extracted `exec816-demo.zip`: folder navigation/refresh,
   file-selector open/cancel, normal EXIT and intact guards. Publish its path,
   checksum and launch command; distribute only the normal demo contents.

Suggested commit: `Measure directory batching and refresh the demo`.

## Validation and resource limits

Use development-tier checks throughout. Run the affected focused cases per slice
and reuse passing evidence when inputs remain unchanged. Raw/optimized pairing
is confined to the small ABI probe; no broad filesystem/GUI or release matrix.
Cancellation and ownership changes require the targeted emitted failure cases,
even though no kernel or IRQ implementation changes. Documentation-only work
needs content/link checks, not an emulator run.

Buffers cost 946/1,890 bytes for eight/sixteen entries plus allocator overhead,
only while scanning. Report service fields, application owner growth, binding
table/provider/code growth and stack observations separately. Every slice reports
fixed/per-public-Task/idle reserved bank-zero deltas, including zero. Do not grow
Task pools or introduce bank-zero scratch to accommodate a heap result buffer.

Completion means the public contract, shared scanner, focused correctness checks,
matched measurements and packaged demo are delivered. Timing results and any
remaining latency issues must be explicit; development checks do not qualify
the hosted platform or real hardware.
