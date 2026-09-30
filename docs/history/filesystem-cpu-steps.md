# Filesystem CPU-step consolidation

> Historical record: applies to the revisions and profiles described below.
> See the [current documentation](../architecture/filesystems.md) and [history index](README.md).

Ordinary request preparation used to return to the filesystem worker after
identity checks, media checks, action selection, handle lookup and argument
copying. Each return repeated the cancellation pump, checkpoint and indirect
dispatch even though there was no I/O or substantial scan between them.

The common handler now performs that bounded setup in ordinary calls. Dispatch
uses `CASE` and action constants generated from `abi/dos.json` into the private
packet definitions. Packet identity is checked once when the worker claims it.
The packet layout, action values and public DOS ABI are unchanged.

| Work | New flow |
| --- | --- |
| Read / Seek | Dispatch, validate handle and arguments, then begin the backend operation. |
| Close / UnLock | Dispatch, validate the object and release it directly. |
| Open / Lock | Dispatch and prepare resolution; initialize the private object before the publication checkpoint. |
| Examine / ExNext | Validate the lock, result buffer and enumeration state together; start the bounded backend work. |
| Directory result | Clear, name, fill and publish the result in one completion step. |

`FSHANDLER` has 7 step routines instead of 17; `FSDIRECTORY` has 4 instead of 14.
They retain ordinary helpers for readability. This reduces worker-loop trips;
it does not require a new scheduler operation or callback framework.

For Read/Seek setup, the path from a claimed packet to the backend's Begin call
uses one worker callback instead of six. This is a control-flow count, excluding
packet claim and subsequent backend chunks, not an elapsed-time measurement.

## Cancellation and bounds

The worker still pumps cancellation after claiming a packet, between backend
chunks and before issuing a sector request. The backend continues to return
after each bounded scan, copy or seek chunk, including work on cached sectors.
There is no loop that drains all CPU states until physical I/O becomes necessary.

Open and Lock still return to the worker with an unpublished object. Cancellation
there frees the object; successful publication then owns the completion.
Directory measurement likewise returns before modifying the caller's result.
Once publication starts, clearing the old enumeration cookie, constructing the
result and saving its replacement form one bounded completion-wins region.
Cancellation cannot leave a partially replaced cookie.

Cancellation remains cooperative at these boundaries. A short CPU operation can
finish before a newly pending break is observed. Task preemption remains enabled;
no scheduler exclusion region is enlarged by combining these calls.

## Memory and validation

Reserved bank-zero delta: **0 fixed bytes / 0 bytes per task**, including guards,
alignment and unused capacity. Service records, heap allocation sizes, task DP
and stack reservations are unchanged. The deeper direct-call paths are checked
with the existing native guards and stack watermark observations.

The matching standard system uses pinned compiler
`bcabe0a4cbb8bb57b389a8596aa8fd72cb9ee0c7`, optimization, stack checks, eight task
slots and `config/shell-sdfs.json`:

| Compiler code | Before | After | Saved |
| --- | ---: | ---: | ---: |
| FSHANDLER | 9,664 B | 8,940 B | 724 B |
| FSDIRECTORY | 7,257 B | 6,611 B | 646 B |
| FSPACKET | 3,485 B | 3,469 B | 16 B |
| Whole system | 481,245 B | 479,859 B | **1,386 B** |

All other routine sizes are unchanged. Code still occupies banks `$01–$08`.
Fixed upper and bank-zero reservations match the baseline exactly. The largest
local frame in each changed module is unchanged; nested calls are assessed
separately through execution, not inferred from individual frame sizes.

Development checks pass: 234 host tests, generated DOS definitions, raw and
optimized mixed MyDOS/SpartaDOS integration (118 assertions each), and nine
optimized MyDOS cancellation cases. These cover allocation rollback, handle and
directory publication, directory scanning, lookup, partial-copy cancellation and
seek-position preservation. Guards, heap ownership and OS restoration pass.
The largest observed non-root public stack use is 328 bytes with 1,024 reserved;
the 256-byte interrupt reserve remains untouched. Watermarks cover these runs,
not a static bound for every possible call path.

The first cancellation selection also included SpartaDOS-only directory
accounting against MyDOS, whose directory size is immediate. The runner now
rejects that unsupported combination before compilation. The applicable cases
reuse the unchanged instrumented binary after checking sources and configuration.

[Machine-readable evidence](../development/filesystem-cpu-steps.json) records image
hashes, source hashes, stack observations and reproduction commands. Detailed
outputs are under `build/development/fs-cpu-steps`. These are development checks;
the full release matrix and timing measurements were not repeated.
